"""CMD-DS3: golden scenes are reproducible from the fixture recording and use only allowed words."""
import json
import unittest
from pathlib import Path

from design.golden import reference as ref

ROOT = Path(__file__).resolve().parents[3]
GOLDEN = ROOT / "design/golden"
ENC = ref.load_encoding(ROOT)
EVENTS = ref.load_events(ROOT / ref.RECORDING)


def golden(name):
    return json.loads((GOLDEN / name).read_text(encoding="utf-8"))


class Reproducible(unittest.TestCase):
    def test_every_golden_regenerates_byte_identically(self):
        want = ref.golden_files(ROOT)
        have = sorted(p.name for p in GOLDEN.glob("t*.json"))
        self.assertEqual(have, sorted(want))
        for name, text in want.items():
            self.assertEqual((GOLDEN / name).read_text(encoding="utf-8"), text, name)

    def test_scene_is_pure(self):
        for t in ref.T_MS:
            a = ref.scene(EVENTS, t, ENC)
            b = ref.scene(list(reversed(EVENTS)), t, ENC)
            self.assertEqual(ref.render(a), ref.render(b), t)

    def test_recording_hash_matches(self):
        import hashlib
        digest = hashlib.sha256((ROOT / ref.RECORDING).read_bytes()).hexdigest()
        for p in GOLDEN.glob("t*.json"):
            self.assertEqual(golden(p.name)["recording"]["sha256"], digest, p.name)


class Words(unittest.TestCase):
    def test_only_allowed_words(self):
        allowed = set(ENC["words"]) - set(ENC["words_reserved"])
        for p in GOLDEN.glob("t*.json"):
            g = golden(p.name)
            listed = set(g["words"])
            self.assertLessEqual(listed, allowed, p.name)
            shown = {f["word"] for f in g["figures"] if f["word"]} | ({g["stage_word"]} if g["stage_word"] else set())
            self.assertEqual(shown, listed, p.name)

    def test_one_word_per_figure_and_no_banned_terms(self):
        banned = {w.lower() for w in ENC["glossary_banned_on_stage"]}
        for p in GOLDEN.glob("t*.json"):
            for f in golden(p.name)["figures"]:
                self.assertTrue(f["word"] is None or isinstance(f["word"], str))
                self.assertNotIn((f["word"] or "").lower(), banned)


class Semantics(unittest.TestCase):
    """Spot checks that the golden tells the fixture story (fixtures/monitor/script.json)."""

    def test_values_come_from_the_encoding(self):
        for p in GOLDEN.glob("t*.json"):
            g = golden(p.name)
            for f in g["figures"]:
                self.assertIn(f["state"], ENC["figures"]["states"])
                self.assertIn(f["ring"], ENC["figures"]["rings"])
                self.assertIn(f["shape"], ENC["figures"]["shapes"])
            for t in g["tiles"]:
                self.assertIn(t["shelf"], ENC["tiles"]["shelves"])
            for e in g["edges"]:
                self.assertTrue(ENC["figures"]["edge_weight_px"]["min"] <= e["weight_px"] <= ENC["figures"]["edge_weight_px"]["max"])
            self.assertIn(g["mood"]["active"], ENC["moods"]["priority"])

    def test_story(self):
        g0 = golden("t00000.json")
        self.assertEqual(g0["figures"], [])
        self.assertEqual({t["id"]: t["shelf"] for t in g0["tiles"]}, {"w1": "waiting", "w2": "waiting"})

        g3 = golden("t03000.json")
        n2 = {f["node"]: f for f in g3["figures"]}["n2"]
        self.assertEqual((n2["state"], n2["tether_to"], n2["word"]), ("waiting_peer", "n1", "wait"))

        g4 = golden("t04000.json")
        self.assertEqual(g4["edges"], [{"a": "n1", "b": "n2", "messages": 3, "pi_permille": 750, "weight_px": 5}])
        self.assertEqual(g4["mood"]["active"], "collaboration")
        self.assertIn("talk", g4["words"])

        g5 = golden("t05000.json")
        self.assertEqual({t["id"]: t["parent"] for t in g5["tiles"]}["w3"], "w1")

        g7 = golden("t07000.json")
        self.assertEqual({f["node"]: f["ring"] for f in g7["figures"]}["n1"], "verified")

        g8 = golden("t08000.json")
        self.assertEqual(g8["dropped_marks"], ["w9"])

        g9 = golden("t09000.json")
        self.assertEqual({f["state"] for f in g9["figures"]}, {"retired"})
        self.assertEqual({t["shelf"] for t in g9["tiles"]}, {"done"})
        self.assertEqual((g9["mood"]["active"], g9["mood"]["tempo_permille"], g9["stage_word"]), ("all_done", 0, "done"))

        g12 = golden("t12000.json")
        self.assertEqual([f["word"] for f in g12["figures"]], [None, None])
        self.assertEqual(g12["words"], ["done"])  # all_done word is sticky


if __name__ == "__main__":
    unittest.main()
