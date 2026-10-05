import colorsys
import json
import unittest
from pathlib import Path

TOK = json.loads((Path(__file__).resolve().parents[2] / "tokens.json").read_text())
THEMES = TOK["themes"]
TEXT_KEYS = ("text", "muted", "accent", "warm")
UI_KEYS = ("accent", "focus", "warm")
BGS = ("bg", "surface")


def lum(hexcolor):
    h = hexcolor.lstrip("#")
    ch = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    ch = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in ch]
    return 0.2126 * ch[0] + 0.7152 * ch[1] + 0.0722 * ch[2]


def contrast(a, b):
    hi, lo = sorted((lum(a), lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def hue_deg(hexcolor):
    h = hexcolor.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    hh, s, v = colorsys.rgb_to_hsv(r, g, b)
    return hh * 360, s


class TokenTests(unittest.TestCase):
    def test_text_pairs_all_themes(self):
        for name, th in THEMES.items():
            for fg in TEXT_KEYS:
                for bg in BGS:
                    self.assertGreaterEqual(contrast(th[fg], th[bg]), 4.5, f"{name} {fg} on {bg}")

    def test_ui_pairs_all_themes(self):
        for name, th in THEMES.items():
            for fg in UI_KEYS:
                for bg in BGS:
                    self.assertGreaterEqual(contrast(th[fg], th[bg]), 3.0, f"{name} {fg} on {bg}")
            for key, val in th["series"].items():
                for bg in BGS:
                    self.assertGreaterEqual(contrast(val, th[bg]), 3.0, f"{name} series {key} on {bg}")

    def test_declared_pairs_meet_min(self):
        for p in TOK["contrast_pairs"]:
            th = THEMES[p["theme"]]
            self.assertGreaterEqual(contrast(th[p["fg"]], th[p["bg"]]), p["min"], str(p))

    def test_declared_pairs_cover_text_and_ui(self):
        have = {(p["theme"], p["fg"], p["bg"]): p["min"] for p in TOK["contrast_pairs"]}
        for name in THEMES:
            for fg in TEXT_KEYS:
                for bg in BGS:
                    self.assertGreaterEqual(have.get((name, fg, bg), 0), 4.5, f"{name} {fg}/{bg}")
            for fg in ("focus",):
                for bg in BGS:
                    self.assertGreaterEqual(have.get((name, fg, bg), 0), 3.0, f"{name} {fg}/{bg}")

    def test_series_luminance_gap(self):
        gap = TOK["series_min_lightness_gap"]
        self.assertGreaterEqual(gap, 0.08)
        for name, th in THEMES.items():
            lums = sorted(lum(v) for v in th["series"].values())
            for x, y in zip(lums, lums[1:]):
                self.assertGreaterEqual(y - x, 0.08, f"{name} series gap")

    def test_no_red_green(self):
        for name, th in THEMES.items():
            vals = [th[k] for k in ("accent", "warm", "focus")] + list(th["series"].values())
            hues = []
            for v in vals:
                h, s = hue_deg(v)
                if s > 0.25:
                    hues.append(h)
            for h in hues:
                self.assertFalse(h < 20 or h > 340 or 75 <= h <= 170, f"{name} red/green hue {h:.0f}")

    def test_scales_and_provenance(self):
        self.assertEqual(sorted(TOK["type_scale_px"].values()), [12, 14, 16, 20, 24, 28, 32])
        self.assertTrue(all(v % 4 == 0 for v in TOK["space_px"].values()))
        self.assertEqual(set(TOK["provenance"]), {"MEASURED", "CALCULATED", "ESTIMATED", "SIMULATED"})
        chips = [v["chip"] for v in TOK["provenance"].values()]
        self.assertEqual(len(set(chips)), 4)
        self.assertIn("Plex Sans KR", TOK["font"]["sans"])
        self.assertIn("Plex Mono", TOK["font"]["mono"])
        self.assertEqual(set(TOK["motion"]["duration_ms"]), {"instant", "fast", "base", "slow", "breath"})
        self.assertEqual(set(TOK["elevation"]), {"0", "1", "2"})
        self.assertEqual(set(THEMES["light"]), set(THEMES["dark"]))


if __name__ == "__main__":
    unittest.main()
