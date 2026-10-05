import io
import re
import sys
import types
import unittest
from pathlib import Path

from app.domains.ingestion import registry, scrub
from app.domains.ingestion.adapters import ClaudeCodeAdapter, GaL0Adapter, anthropic_export, openai_export, common
from app.domains.usage.api import CallIn

ROOT = Path(__file__).resolve().parents[6]
FIX = ROOT / "fixtures" / "ingest"
ADAPTERS = Path(common.__file__).parent

try:
    import telemetry.usage  # noqa: F401
    HAVE_L0 = True
except ImportError:
    HAVE_L0 = False


def calls(items):
    return [i.call for i in items if isinstance(i, registry.ParsedCall)]


def fake_modules(**mods):
    """Stand in for pinned parsers (used only to test mapping when the packages are not installed)."""
    saved = {k: sys.modules.get(k) for k in ("telemetry", *mods)}
    pkg = types.ModuleType("telemetry")
    sys.modules["telemetry"] = pkg
    for name, fn in mods.items():
        m = types.ModuleType(name)
        for k, v in fn.items():
            setattr(m, k, v)
        sys.modules[name] = m
    return saved


def restore(saved):
    for k, v in saved.items():
        if v is None:
            sys.modules.pop(k, None)
        else:
            sys.modules[k] = v


class ScrubTests(unittest.TestCase):
    # Fake secrets assembled at runtime so the repo secret scan stays clean.
    CASES = {
        "anthropic_key": "sk-" + "ant-" + "A1b2C3d4E5f6",
        "openai_key": "sk-" + "B" * 20,
        "google_key": "AI" + "za" + "C" * 25,
        "github_token": "gh" + "p_" + "D" * 24,
        "aws_key": "AK" + "IA" + "E" * 16,
        "slack_token": "xo" + "xb-" + "1234567890-abc",
        "jwt": "ey" + "Jhbg.ey" + "JzdWI.sig_-x",
        "assignment": "pass" + "word=hunter2hunter2",
        "high_entropy": "a1" * 20,
        "private_key": "-----BEGIN " + "RSA PRIVATE KEY-----\nMIIFAKE\n-----END RSA PRIVATE KEY-----",
    }

    def test_every_pattern_has_a_case(self):
        self.assertEqual({k for k, _ in scrub.PATTERNS}, set(self.CASES))

    def test_every_pattern_is_removed(self):
        for kind, secret in self.CASES.items():
            with self.subTest(kind=kind):
                out = scrub.scrub_text(f"before {secret} after")
                self.assertIn(f"[REDACTED:{kind}]", out)
                self.assertNotIn(secret.split("=")[-1] if kind == "assignment" else secret, out)
                self.assertTrue(out.startswith("before ") and out.endswith(" after"))

    def test_nested_values(self):
        out = scrub.scrub_value({"a": ["x " + self.CASES["aws_key"]], "n": 3})
        self.assertNotIn(self.CASES["aws_key"], str(out))
        self.assertEqual(out["n"], 3)


class BodyTests(unittest.TestCase):
    DATA = {"model": "m", "input_tokens": 5, "content": "my prompt", "nested": {"text": "t", "k": 1}}

    def test_bodies_dropped_by_default(self):
        out = common.drop_bodies(self.DATA)
        self.assertEqual(out, {"model": "m", "input_tokens": 5, "nested": {"k": 1}})

    def test_kept_bodies_are_scrubbed(self):
        secret = "gh" + "p_" + "F" * 24
        out = common.drop_bodies({"content": "x " + secret}, store_bodies=True)
        self.assertNotIn(secret, out["content"])


class NoOwnParserTests(unittest.TestCase):
    def test_no_adapter_parses_jsonl_or_transcripts(self):
        for name in ("claude_code.py", "ga_l0.py"):
            src = (ADAPTERS / name).read_text()
            self.assertNotIn("json", src.replace("jsonl", "").lower().replace("l0.json", ""), name)
            self.assertIsNone(re.search(r"splitlines|for line in|readline", src), name)
        self.assertIn("from_cc_jsonl", (ADAPTERS / "claude_code.py").read_text())
        self.assertIn("read_lenient", (ADAPTERS / "ga_l0.py").read_text())
        self.assertIn("l0_usage", (ADAPTERS / "exports.py").read_text())


class L0TokensTests(unittest.TestCase):
    """l0_usage returns (fields, null_names); these run without the package."""

    def test_maps_l0_names_and_keeps_none(self):
        t = common.l0_tokens({"input_tokens": 1000, "cache_read_input_tokens": 500,
                              "cache_creation_input_tokens": 200, "output_tokens": 300})
        self.assertEqual((t["input_tokens"], t["cache_read_tokens"], t["cache_write_5m_tokens"],
                          t["cache_write_1h_tokens"], t["output_tokens"], t["thinking_tokens"]),
                         (1000, 500, 200, None, 300, None))

    def test_split_wins_over_total(self):
        t = common.l0_tokens({"cache_creation_input_tokens": 9, "cache_creation_5m_input_tokens": 4,
                              "cache_creation_1h_input_tokens": 5})
        self.assertEqual((t["cache_write_5m_tokens"], t["cache_write_1h_tokens"]), (4, 5))

    def test_export_adapter_unpacks_tuple_from_l0_usage(self):
        stub = lambda provider, u: ({"input_tokens": 600, "cache_read_input_tokens": 400, "output_tokens": None},
                                    ["output_tokens"])
        saved = fake_modules(**{"telemetry.usage": {"l0_usage": stub}})
        try:
            out = calls(openai_export().parse(io.BytesIO(
                b"date,model,input_tokens,input_cached_tokens,output_tokens\n2026-03-02,m,1000,400,\n")))
        finally:
            restore(saved)
        self.assertEqual((out[0].input_tokens, out[0].cache_read_tokens, out[0].output_tokens), (600, 400, None))


class MappingWithStubbedParsers(unittest.TestCase):
    def test_claude_code_maps_llm_response_only(self):
        ev = [{"type": "run.start", "data": {}},
              {"type": "llm.response", "at": "2026-03-01T10:00:00Z",
               "data": {"model": "m1", "response_id": "r1", "call_index": 0, "input_tokens": 10,
                        "output_tokens": 4, "cache_read_tokens": None, "content": "SECRET PROMPT"}}]
        saved = fake_modules(**{"telemetry.collect": {"from_cc_jsonl": lambda p, r, h: iter(ev)}})
        try:
            out = calls(ClaudeCodeAdapter().parse(io.BytesIO(b"x")))
        finally:
            restore(saved)
        self.assertEqual(len(out), 1)
        c = out[0]
        self.assertEqual((c.model_id, c.input_tokens, c.output_tokens, c.cache_read_tokens, c.time_basis),
                         ("m1", 10, 4, None, "reported"))
        self.assertNotIn("SECRET", repr(c))

    def test_ga_run_end_used_only_without_llm_response(self):
        end = {"type": "run.end", "run_id": "r", "seq": 3, "at": None,
               "data": {"reported_input_tokens": 7, "reported_output_tokens": 2, "cost_usd": 0.25, "api_calls": 3,
                        "model": "m"}}
        saved = fake_modules(**{"telemetry.ledger": {"read_lenient": lambda p: ([end], [{"line_no": 9}])}})
        try:
            items = list(GaL0Adapter().parse(io.BytesIO(b"x")))
        finally:
            restore(saved)
        self.assertEqual([i.line_no for i in items if isinstance(i, registry.ParsedReject)], [9])
        c = calls(items)[0]
        self.assertEqual((c.input_tokens, c.output_tokens, c.cost_cli_microusd, c.tool_calls, c.time_basis),
                         (7, 2, 250_000, 3, "ingested"))
        resp = {"type": "llm.response", "run_id": "r", "seq": 2, "data": {"model": "m", "input_tokens": 1}}
        saved = fake_modules(**{"telemetry.ledger": {"read_lenient": lambda p: ([resp, end], [])}})
        try:
            out = calls(GaL0Adapter().parse(io.BytesIO(b"x")))
        finally:
            restore(saved)
        self.assertEqual([c.input_tokens for c in out], [1])


@unittest.skipUnless(HAVE_L0, "l0-telemetry (pinned f6c7ae2) not installed")
class ExportFixtureTests(unittest.TestCase):
    def test_anthropic_csv(self):
        out = calls(anthropic_export().parse(io.BytesIO((FIX / "anthropic_usage.csv").read_bytes())))
        self.assertEqual(len(out), 2)
        self.assertEqual((out[0].role, out[0].call_index, out[0].cost_provider_microusd, out[0].output_tokens),
                         ("aggregate", None, 12_000, 300))
        self.assertEqual(out[0].cache_read_tokens, 500)
        self.assertNotEqual(out[0].dedupe_key, out[1].dedupe_key)

    def test_openai_csv_input_minus_cached(self):
        out = calls(openai_export().parse(io.BytesIO((FIX / "openai_usage.csv").read_bytes())))
        self.assertEqual((out[0].input_tokens, out[0].cache_read_tokens, out[0].output_tokens), (600, 400, 50))

    def test_bad_rows_rejected_without_content(self):
        items = list(openai_export().parse(io.BytesIO(b"date,model,input_tokens\n2026-03-02,,5\n")))
        self.assertEqual([(i.line_no, i.code) for i in items], [(1, "bad_row")])

    def test_calls_are_callin(self):
        out = calls(anthropic_export().parse(io.BytesIO((FIX / "anthropic_usage.csv").read_bytes())))
        self.assertTrue(all(isinstance(c, CallIn) for c in out))


if __name__ == "__main__":
    unittest.main()
