"""CMD-GC24 S2: hashes from Claude Code / ga L0 bodies, NULL from CSV, no body text kept."""
import hashlib
import io
import unittest

from app.domains.ingestion.adapters import ClaudeCodeAdapter, GaL0Adapter, anthropic_export, common

from .test_adapters import FIX, HAVE_L0, calls, fake_modules, restore

FILE_A = "BODY-OF-FILE-A " * 40          # ~600 bytes
FILE_B = "body of file b " * 20
SECRET_TEXT = "TOP-SECRET-PROMPT-TEXT"


def ev(i, blocks, system="You are a coding agent. " * 5):
    return {"type": "llm.response", "at": f"2026-03-01T10:0{i}:00Z",
            "data": {"model": "claude-haiku-4-5-20251001", "response_id": f"r{i}", "call_index": i,
                     "input_tokens": 5000, "output_tokens": 200, "cache_read_tokens": 0, "system": system,
                     "messages": [{"role": "user", "content": b} for b in blocks]}}


EVENTS = [ev(0, [FILE_A, FILE_B]), ev(1, [FILE_A, SECRET_TEXT]), ev(2, [FILE_A])]


def parse_cc(events=EVENTS, raw=b"x"):
    saved = fake_modules(**{"telemetry.collect": {"from_cc_jsonl": lambda p, r, h: iter(events)}})
    try:
        return calls(ClaudeCodeAdapter().parse(io.BytesIO(raw)))
    finally:
        restore(saved)


def h12(text, tokens):
    return f"{hashlib.sha256(text.encode()).hexdigest()[:12]}:{tokens}"


class AdapterHashTests(unittest.TestCase):
    def test_claude_code_prefix_and_block_hashes_are_exact_and_stable(self):
        a, b = parse_cc(), parse_cc()
        self.assertEqual([c.content_hashes for c in a], [c.content_hashes for c in b])
        sys_text = "You are a coding agent. " * 5
        self.assertEqual(a[0].prompt_prefix_hash, hashlib.sha256(sys_text.encode()).hexdigest())
        self.assertEqual(a[0].prompt_prefix_hash, a[1].prompt_prefix_hash)
        self.assertEqual(a[0].content_hashes, [h12(FILE_A, -(-len(FILE_A) // 4)), h12(FILE_B, -(-len(FILE_B) // 4))])
        # the same block hashes the same across calls: that is what R2 keys on
        self.assertEqual(a[0].content_hashes[0], a[2].content_hashes[0])

    def test_changed_prefix_changes_hash(self):
        out = parse_cc([ev(0, [FILE_A]), ev(1, [FILE_A], system="another prefix")])
        self.assertNotEqual(out[0].prompt_prefix_hash, out[1].prompt_prefix_hash)

    def test_block_tokens_from_parser_win_over_estimate(self):
        e = ev(0, [])
        e["data"]["messages"] = [{"content": "abc", "tokens": 77}]
        self.assertEqual(parse_cc([e])[0].content_hashes, [h12("abc", 77)])

    def test_no_body_text_survives(self):
        for c in parse_cc():
            self.assertNotIn("BODY-OF-FILE", repr(c))
            self.assertNotIn(SECRET_TEXT, repr(c))
            self.assertIsNone(c.body_ref)

    def test_event_without_body_gives_null_not_empty(self):
        e = {"type": "llm.response", "at": "2026-03-01T10:00:00Z",
             "data": {"model": "m", "response_id": "r", "input_tokens": 1, "output_tokens": 1}}
        c = parse_cc([e])[0]
        self.assertIsNone(c.prompt_prefix_hash)
        self.assertIsNone(c.content_hashes)
        self.assertEqual(common.content_digest({"system": "", "messages": []}), (None, None))

    def test_ga_l0_llm_response_hashed_run_end_null(self):
        resp = {"type": "llm.response", "run_id": "r", "seq": 1, "at": "2026-03-01T10:00:00Z",
                "data": {"model": "m", "input_tokens": 1, "prompt": "ga prompt text"}}
        end = {"type": "run.end", "run_id": "r2", "seq": 2, "data": {"reported_input_tokens": 3, "model": "m",
                                                                    "prompt": "ignored"}}
        saved = fake_modules(**{"telemetry.ledger": {"read_lenient": lambda p: ([resp, end], [])}})
        try:
            out = calls(GaL0Adapter().parse(io.BytesIO(b"x")))
        finally:
            restore(saved)
        self.assertEqual(out[0].prompt_prefix_hash, hashlib.sha256(b"ga prompt text").hexdigest())
        self.assertEqual(out[0].content_hashes, [h12("ga prompt text", 4)])
        self.assertNotIn("ga prompt text", repr(out[0]))
        saved = fake_modules(**{"telemetry.ledger": {"read_lenient": lambda p: ([end], [])}})
        try:
            out = calls(GaL0Adapter().parse(io.BytesIO(b"x")))
        finally:
            restore(saved)
        self.assertEqual((out[0].prompt_prefix_hash, out[0].content_hashes), (None, None))

    @unittest.skipUnless(HAVE_L0, "l0-telemetry (pinned f6c7ae2) not installed")
    def test_csv_rows_leave_hashes_null(self):
        for c in calls(anthropic_export().parse(io.BytesIO((FIX / "anthropic_usage.csv").read_bytes()))):
            self.assertIsNone(c.prompt_prefix_hash)
            self.assertIsNone(c.content_hashes)


if __name__ == "__main__":
    unittest.main()
