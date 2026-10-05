# ADR-0009 UI: design role, tokens, fonts, monitor rendering

- Status: adopted (CMD-GC0 additions, spec 3.1.1 and 7.1)
- Decision:
  - **A sixth role, `design`, owns the visual language.** It owns `design/tokens.json`, `design/encoding.json` (every observable signal -> its visual mapping), `design/motion.md`, the golden scenes, `docs/ui-design.md` and `docs/ui/**`. frontend implements and never invents colors, sizes, durations or encodings.
  - **Tokens are one JSON file.** frontend generates CSS variables and the ECharts theme from it at build time. Contrast pairs and series lightness gaps are machine-checked by `scripts/check_docs.py`.
  - **Fonts:** IBM Plex Sans KR + IBM Plex Mono (OFL, self-hosted). They cover Hangul and Latin in one family, have clear tabular numerals, and Mono suits the few monitor words. Alternatives: Pretendard (good Hangul, but no matching mono) and Noto Sans KR (heavier, less distinct numerals).
  - **Analysis charts stay ECharts** (ADR-0001).
  - **The live monitor renders with plain Canvas 2D** driven by a pure `scene(events, t)` function: deterministic, testable as a scene graph, and no WebGL/GPU variance.
  - **Colors:** light theme by default, dark for the monitor and desktop shell. Blue/orange only, never red/green as the sole cue.
- Why: the user asked for an intuitive, easy-on-the-eyes UI and for design to be a job of its own (spec 3.1.1). Tokens plus an encoding table make that a contract that `check_docs.py` and visual tests can hold frontend to.
