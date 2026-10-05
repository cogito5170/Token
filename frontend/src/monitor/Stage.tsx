"use client";
// CMD-FE2: the live monitor stage. One full-screen canvas; each animation frame draws
// draw(frame(events, t)). t comes from one clock: live = now - first event, replay = the scrubber.
// Numbers only in the hover tooltip; the scrubber and the motion switch show only on hover.
import { useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import { tokens } from "../lib/tokens/tokens.generated";
import { draw, type Theme } from "./draw";
import { encoding as enc } from "./encoding";
import { frame, hitTest, type Frame } from "./frame";
import { bySeq, ms } from "./scene";
import type { MonitorEvent } from "./types";

export interface StageProps {
  events: readonly MonitorEvent[];
  mode: "live" | "replay";
  /** Fixed t (ms) — stops the clock (tests, stills). */
  at?: number;
  reduced?: boolean;
  theme?: Theme;
}

function useMedia(q: string): boolean {
  const [v, setV] = useState(false);
  useEffect(() => {
    if (typeof window === "undefined" || !window.matchMedia) return;
    const m = window.matchMedia(q);
    setV(m.matches);
    const on = () => setV(m.matches);
    m.addEventListener("change", on);
    return () => m.removeEventListener("change", on);
  }, [q]);
  return v;
}

export function Stage({ events, mode, at, reduced, theme }: StageProps) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const last = useRef<Frame | null>(null);
  const sysReduced = useMedia("(prefers-reduced-motion: reduce)");
  const sysLight = useMedia("(prefers-color-scheme: light)");
  const [still, setStill] = useState(false);
  const isReduced = reduced ?? (sysReduced || still);
  const th: Theme = theme ?? (sysLight ? "light" : "dark");
  const evs = useMemo(() => bySeq(events), [events]);
  const t0 = evs.length ? ms(evs[0].observed_at) : 0;
  const end = evs.length ? ms(evs[evs.length - 1].observed_at) - t0 + enc.word_style.max_on_stage_ms : 0;
  const [scrub, setScrub] = useState<number | null>(null);
  const playStart = useRef<number | null>(null);
  const [tip, setTip] = useState<{ x: number; y: number; lines: string[] } | null>(null);
  const tRef = useRef(0);

  useEffect(() => {
    const cv = canvas.current;
    if (!cv) return;
    const ctx = cv.getContext("2d");
    if (!ctx) return;
    let raf = 0;
    const tick = (wall: number) => {
      let t: number;
      if (at !== undefined) t = at;
      else if (mode === "live") t = Date.now() - t0;
      else if (scrub !== null) t = scrub;
      else {
        if (playStart.current === null) playStart.current = wall;
        t = Math.min(end, wall - playStart.current);
      }
      tRef.current = t;
      const dpr = window.devicePixelRatio || 1;
      const w = cv.clientWidth, h = cv.clientHeight;
      if (cv.width !== Math.round(w * dpr) || cv.height !== Math.round(h * dpr)) {
        cv.width = Math.round(w * dpr);
        cv.height = Math.round(h * dpr);
      }
      const f = frame(evs, t, { width: w, height: h, reduced: isReduced });
      last.current = f;
      draw(ctx, f, th, dpr);
      if (at === undefined) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [evs, mode, at, scrub, isReduced, th, t0, end]);

  const t = tokens.themes[th];
  const root: CSSProperties = { position: "fixed", inset: 0, background: t.bg, overflow: "hidden" };
  return (
    <div style={root} data-theme={th} data-reduced={isReduced ? "1" : "0"}>
      <canvas
        ref={canvas}
        data-testid="stage"
        role="img"
        aria-label="live"
        style={{ width: "100%", height: "100%", display: "block" }}
        onMouseMove={(e) => {
          const r = e.currentTarget.getBoundingClientRect();
          const hit = last.current ? hitTest(last.current, e.clientX - r.left, e.clientY - r.top) : null;
          setTip(hit?.hover?.length ? { x: e.clientX - r.left, y: e.clientY - r.top, lines: hit.hover } : null);
        }}
        onMouseLeave={() => setTip(null)}
      />
      {tip && (
        <div
          data-testid="tip"
          style={{
            position: "absolute", left: tip.x + 12, top: tip.y + 12, pointerEvents: "none",
            font: `${tokens.type_scale_px.xs}px ${tokens.font.mono}`, fontVariantNumeric: tokens.font.numeric,
            color: t.muted, background: t.surface, border: `1px solid ${t.border}`, borderRadius: tokens.radius_px.sm,
            padding: `${tokens.space_px[1]}px ${tokens.space_px[2]}px`,
          }}
        >
          {tip.lines.map((l, i) => <div key={i}>{l}</div>)}
        </div>
      )}
      <div className="gc-monitor-bar" data-testid="bar">
        {mode === "replay" && (
          <input
            type="range"
            aria-label="time"
            data-testid="scrubber"
            min={0}
            max={end}
            step={50}
            defaultValue={0}
            onInput={(e) => setScrub(Number((e.target as HTMLInputElement).value))}
            style={{ flex: 1, accentColor: t.accent }}
          />
        )}
        <button
          type="button"
          aria-label="still"
          aria-pressed={still}
          data-testid="still"
          onClick={() => setStill((s) => !s)}
          style={{ width: 20, height: 20, borderRadius: tokens.radius_px.full, border: `1px solid ${t.border}`, background: still ? t.accent : "transparent", cursor: "pointer" }}
        />
      </div>
      <style>{`
        .gc-monitor-bar { position: absolute; left: 0; right: 0; bottom: 0; height: 40px; display: flex; gap: ${tokens.space_px[3]}px;
          align-items: center; padding: 0 ${tokens.space_px[4]}px; opacity: 0; transition: opacity ${enc.durations_ms.base}ms; }
        .gc-monitor-bar:hover, .gc-monitor-bar:focus-within { opacity: 1; }
        @media (prefers-reduced-motion: reduce) { .gc-monitor-bar { transition: opacity ${enc.reduced_motion.max_fade_ms}ms; } }
      `}</style>
    </div>
  );
}
