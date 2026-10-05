# Motion rules (live monitor)

Owner: design. Encoding per signal: `design/encoding.json`. Timings and easing: `design/tokens.json` `motion`.

1. **Time is event time.** Every animation is a pure function of (monitor events up to t, t). The renderer never reads
   the wall clock directly; live mode feeds t = now, replay feeds t from the scrubber. Same events + same t = same scene
   (the replay determinism test compares the scene graph, not pixels).
2. **One stage, no pages.** Bands top to bottom: waiting shelf (tiles), the stage (figures, lines, pulses), done shelf.
   Side shelf on the right for failed tiles. The rest rim is the stage border. Nothing scrolls; the scene rescales.
3. **Shape carries meaning, color only supports it.** Figure = role shape (circle, rounded square, hexagon, triangle,
   diamond, pill in role order). Ring around a figure = its current item's fate (closed / jagged / open / flat cap).
   Line weight = pi (1-6 px). Size = work done on the current item (area ~ sqrt(tokens)). Lightness = activity
   (live 100 %, waiting 60 %, idle 40 %). Hue: at most one accent (blue) + one warm (orange, tension only).
4. **Rhythm is the mood.** Breathing tempo rises with elapsed time in a turn (calm -> tense); collaboration syncs
   pulses; stall slows everything to 0.3x and dims; all-done settles and sweeps once.
5. **Words.** Only `build`, `wait`, `talk`, `test`, `done`, lowercase, 12 px mono, near the figure, shown <= 2 s
   (stall and done words stay while true). `test` is reserved until ga emits check events (reports/CMD-GC0.md).
   Never "node", "queue", "token" or any CS term on the stage.
6. **Numbers only on hover/tap**, small (12 px mono, tabular), in a tooltip anchored to the figure, tile or line.
7. **Reduced motion** (`prefers-reduced-motion: reduce` or the in-app switch): no travel, no breathing, no particles,
   no sweeps; state changes swap shapes instantly with an opacity fade <= 120 ms. Every encoding entry lists its
   reduced-motion form.
8. **Limits.** <= 60 fps, <= 400 moving particles, pulses merge when > 20 are in flight; the stage stays legible with
   12 figures.
9. **In ga 0.6 a turn is opaque.** There is no turn.started and no intra-turn event: a working figure shows
   "running (elapsed)" as inner particles driven by ga-budget.jsonl growth, elapsed measured from the last
   observed node.started / run.end.
