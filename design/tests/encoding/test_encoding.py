"""CMD-DS2: the live monitor encoding table is complete, wordless enough and motion-safe."""
import importlib.util
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ENC = json.loads((ROOT / "design/encoding.json").read_text(encoding="utf-8"))
TOK = json.loads((ROOT / "design/tokens.json").read_text(encoding="utf-8"))
MOTION_MD = (ROOT / "design/motion.md").read_text(encoding="utf-8")

_spec = importlib.util.spec_from_file_location("check_docs", ROOT / "scripts/check_docs.py")
CD = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(CD)

SIGNALS = {e["signal"]: e for e in ENC["signals"]}
SCREEN = CD.screen_signals((ROOT / "docs/visualization.md").read_text(encoding="utf-8"))
REQUIRED = [f"l0:{k}" for k in CD.L0_KINDS] + SCREEN
GA_EMITTED = {f"l0:{k}" for k in CD.L0_KINDS_GA} | set(SCREEN)
WORDS = ("build", "wait", "talk", "test", "done")
BANNED = {w.lower() for w in ENC["glossary_banned_on_stage"]}
SHOWN = [e for e in ENC["signals"] if e["visual"] != "none"]
EMPTY = {"", "none", "n/a"}


def blank(v):
    return v is None or str(v).strip().lower() in EMPTY or str(v).strip().lower().startswith("n/a")


class Coverage(unittest.TestCase):
    def test_every_required_signal_has_an_entry(self):
        self.assertTrue(SCREEN, "visualization.md live_monitor lists no signals")
        missing = [s for s in REQUIRED if s not in SIGNALS]
        self.assertEqual(missing, [])

    def test_no_unknown_or_duplicate_signals(self):
        names = [e["signal"] for e in ENC["signals"]]
        self.assertEqual(len(names), len(set(names)))
        self.assertEqual(sorted(set(names) - set(REQUIRED)), [])

    def test_signal_names_are_monitor_event_kinds(self):
        for s in SIGNALS:
            self.assertRegex(s, r"^(l0:[a-z_]+(\.[a-z_]+)+|file:[a-z_.]+|derived:[a-z_]+)$")

    def test_emitted_flag_matches_ga_pin(self):
        for s, e in SIGNALS.items():
            self.assertIs(e["emitted_by_ga_0_6"], s in GA_EMITTED, s)


class GaEmitted(unittest.TestCase):
    def test_visual_reduced_motion_and_non_color_cue(self):
        for s in sorted(GA_EMITTED):
            e = SIGNALS[s]
            for key in ("visual", "motion", "reduced_motion", "not_color_only"):
                self.assertFalse(blank(e.get(key)), f"{s} has no real {key}")

    def test_catalog_only_none_has_reason(self):
        for e in ENC["signals"]:
            if e["visual"] == "none":
                self.assertNotIn(e["signal"], GA_EMITTED)
                self.assertTrue(str(e.get("reason", "")).strip(), e["signal"])
                self.assertEqual(e["target"], "none")

    def test_every_shown_signal_is_complete(self):
        for e in SHOWN:
            for key in ("visual", "motion", "reduced_motion", "not_color_only"):
                self.assertFalse(blank(e.get(key)), f"{e['signal']} {key}")

    def test_non_color_cue_names_a_shape_or_size(self):
        cues = ("shape", "outline", "ring", "dot", "line", "size", "arc", "position", "shelf", "tether", "mark",
                "halo", "tile", "distance", "weight", "thick", "density", "stillness", "spark", "tick", "presence")
        for e in SHOWN:
            cue = e["not_color_only"].lower()
            self.assertTrue(any(c in cue for c in cues), f"{e['signal']}: {cue}")


class Words(unittest.TestCase):
    def test_word_set(self):
        self.assertEqual(tuple(ENC["words"]), WORDS)
        self.assertEqual(tuple(CD.WORDS), WORDS)

    def test_at_most_one_allowed_word(self):
        for e in ENC["signals"]:
            w = e.get("word")
            self.assertTrue(w is None or (isinstance(w, str) and w in WORDS), e["signal"])

    def test_no_banned_word_on_stage(self):
        for core in ("node", "queue", "token", "agent", "llm"):
            self.assertIn(core, BANNED)
        stage = [e.get("word") for e in ENC["signals"]]
        stage += [st.get("word") for st in ENC["figures"]["states"].values()]
        stage += [r.get("word") for r in ENC["figures"]["rings"].values()]
        stage += [m.get("word") for m in ENC["moods"]["rules"].values()]
        for w in filter(None, stage):
            self.assertIn(w, WORDS)
            self.assertNotIn(w.lower(), BANNED)

    def test_test_word_reserved(self):
        self.assertIn("test", ENC["words_reserved"])
        self.assertNotIn("test", [e.get("word") for e in ENC["signals"]])

    def test_word_style(self):
        ws = ENC["word_style"]
        self.assertEqual((ws["case"], ws["size_px"], ws["max_per_figure"], ws["emoji"]), ("lower", 12, 1, False))
        for s in ws["sticky_while_true"]:
            self.assertIn(s, SIGNALS)

    def test_no_emoji_anywhere(self):
        raw = (ROOT / "design/encoding.json").read_text(encoding="utf-8") + MOTION_MD
        self.assertFalse(re.search("[\U0001F000-\U0001FAFF☀-➿]", raw))


class Motion(unittest.TestCase):
    def test_durations_agree_with_tokens(self):
        tok = TOK["motion"]["duration_ms"]
        for k, v in ENC["durations_ms"].items():
            if k in tok:
                self.assertEqual(v, tok[k], k)
            self.assertIsInstance(v, int)

    def test_every_shown_signal_names_a_duration(self):
        for e in SHOWN:
            self.assertIn(e["duration"], ENC["durations_ms"], e["signal"])

    def test_reduced_motion_has_no_movement(self):
        rm = ENC["reduced_motion"]
        self.assertLessEqual(rm["max_fade_ms"], 120)
        for e in SHOWN:
            text = e["reduced_motion"].lower()
            for term in rm["forbidden_terms"]:
                self.assertNotIn(term, text, e["signal"])

    def test_targets(self):
        allowed = {"figure", "tile", "edge", "meter", "stage"}
        for e in SHOWN:
            self.assertIn(e["target"], allowed, e["signal"])

    def test_limits(self):
        lim = ENC["limits"]
        self.assertEqual((lim["fps_max"], lim["particles_max"], lim["pulses_merge_above"]), (60, 400, 20))
        self.assertGreaterEqual(ENC["stage"]["max_figures_legible"], 12)

    def test_motion_md_mentions_rules(self):
        for needle in ("이벤트 시간", "prefers-reduced-motion", "durations_ms", "forbidden_terms", "build", "wait", "talk", "test",
                       "done") + tuple(f"derived:{m}" for m in ENC["moods"]["rules"]) + tuple(ENC["figures"]["shapes"]):
            self.assertIn(needle, MOTION_MD)


class FiguresAndMoods(unittest.TestCase):
    def test_role_shapes_distinct(self):
        shapes = ENC["figures"]["shapes"]
        self.assertEqual(len(shapes), 6)
        self.assertEqual(len(set(shapes)), 6)

    def test_states_match_snapshot(self):
        # docs/data-model.md 7.3 figure state values
        self.assertEqual(set(ENC["figures"]["states"]),
                         {"idle", "running", "waiting_peer", "continuing", "retiring", "retired"})
        light = [s["lightness_pct"] for s in ENC["figures"]["states"].values()]
        self.assertTrue(all(0 < x <= 100 for x in light))

    def test_rings_differ_by_shape(self):
        shapes = [r["shape"] for r in ENC["figures"]["rings"].values()]
        self.assertEqual(len(shapes), len(set(shapes)))
        self.assertTrue({"verified", "failed", "needs_judgement", "budget"} <= set(ENC["figures"]["rings"]))

    def test_edge_weight(self):
        w = ENC["figures"]["edge_weight_px"]
        self.assertEqual((w["min"], w["max"]), (1, 6))

    def test_moods_cover_derived_signals(self):
        derived = {s.split(":", 1)[1] for s in SIGNALS if s.startswith("derived:")}
        self.assertEqual(set(ENC["moods"]["rules"]), derived)
        self.assertEqual(set(ENC["moods"]["priority"]), derived)
        for name, rule in ENC["moods"]["rules"].items():
            self.assertEqual(rule["word"], SIGNALS[f"derived:{name}"]["word"], name)

    def test_tiles_shelves_match_snapshot(self):
        self.assertEqual(set(ENC["tiles"]["shelves"]), {"waiting", "held", "done", "failed"})
        bands = {b["name"] for b in ENC["stage"]["bands"]}
        for shelf in ("waiting_shelf", "done_shelf", "failed_shelf", "rest_rim"):
            self.assertIn(shelf, bands)


if __name__ == "__main__":
    unittest.main()
