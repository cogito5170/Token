// CMD-FE2: draws a Frame on a Canvas 2D context. It only draws: no clock, no state, no decisions.
// Colors come from design/tokens.json (one accent, warm only for tension); text only from frame words.
import { tokens } from "../lib/tokens/tokens.generated";
import { encoding as enc } from "./encoding";
import type { El, Frame } from "./frame";

export type Theme = "dark" | "light";

/** The subset of CanvasRenderingContext2D the stage uses (lets tests record calls). */
export type Ctx = Pick<CanvasRenderingContext2D,
  "save" | "restore" | "setTransform" | "fillRect" | "clearRect" | "beginPath" | "closePath" | "moveTo" | "lineTo" | "arc" |
  "quadraticCurveTo" | "fill" | "stroke" | "fillText" | "setLineDash" | "rect"> & {
  fillStyle: string | CanvasGradient | CanvasPattern;
  strokeStyle: string | CanvasGradient | CanvasPattern;
  lineWidth: number;
  lineCap: CanvasLineCap;
  globalAlpha: number;
  font: string;
  textBaseline: CanvasTextBaseline;
  textAlign: CanvasTextAlign;
};

function polygon(c: Ctx, x: number, y: number, r: number, n: number, rot: number) {
  for (let i = 0; i < n; i++) {
    const a = rot + (2 * Math.PI * i) / n;
    if (i === 0) c.moveTo(x + r * Math.cos(a), y + r * Math.sin(a));
    else c.lineTo(x + r * Math.cos(a), y + r * Math.sin(a));
  }
  c.closePath();
}

function roundRect(c: Ctx, x: number, y: number, w: number, h: number, rr: number) {
  c.moveTo(x + rr, y);
  c.lineTo(x + w - rr, y);
  c.quadraticCurveTo(x + w, y, x + w, y + rr);
  c.lineTo(x + w, y + h - rr);
  c.quadraticCurveTo(x + w, y + h, x + w - rr, y + h);
  c.lineTo(x + rr, y + h);
  c.quadraticCurveTo(x, y + h, x, y + h - rr);
  c.lineTo(x, y + rr);
  c.quadraticCurveTo(x, y, x + rr, y);
  c.closePath();
}

/** Figure outline by role shape (encoding figures.shapes). */
export function shapePath(c: Ctx, shape: string, x: number, y: number, r: number) {
  c.beginPath();
  switch (shape) {
    case "rounded_square": roundRect(c, x - r * 0.88, y - r * 0.88, r * 1.76, r * 1.76, r * 0.35); break;
    case "hexagon": polygon(c, x, y, r, 6, 0); break;
    case "triangle": polygon(c, x, y + r * 0.15, r * 1.1, 3, -Math.PI / 2); break;
    case "diamond": polygon(c, x, y, r * 1.05, 4, -Math.PI / 2); break;
    case "pill": roundRect(c, x - r * 1.2, y - r * 0.7, r * 2.4, r * 1.4, r * 0.7); break;
    default: c.arc(x, y, r, 0, 2 * Math.PI);
  }
}

function drawEl(c: Ctx, e: El, pal: { accent: string; warm: string; text: string; muted: string; border: string; bg: string }) {
  c.globalAlpha = Math.max(0, Math.min(1, e.opacity));
  c.setLineDash([]);
  switch (e.kind) {
    case "dust":
      c.fillStyle = pal.muted;
      c.beginPath(); c.arc(e.x, e.y, e.r, 0, 2 * Math.PI); c.fill();
      break;
    case "band":
      c.strokeStyle = pal.border; c.lineWidth = 1;
      c.beginPath(); roundRect(c, e.x, e.y, e.w!, e.h!, 8); c.stroke();
      break;
    case "horizon":
      c.strokeStyle = e.warm ? pal.warm : pal.accent; c.lineWidth = e.width ?? 1;
      c.beginPath(); c.moveTo(e.x, e.y); c.lineTo(e.x2!, e.y); c.stroke();
      break;
    case "edge": case "link": case "tether":
      c.strokeStyle = e.kind === "link" ? pal.muted : pal.accent; c.lineWidth = e.width ?? 1;
      if (e.kind === "link") c.setLineDash([2, 3]);
      c.beginPath(); c.moveTo(e.x, e.y); c.lineTo(e.x2!, e.y2!); c.stroke();
      break;
    case "pulse": case "inner":
      c.fillStyle = e.kind === "pulse" ? pal.text : pal.bg;
      c.beginPath(); c.arc(e.x, e.y, e.r, 0, 2 * Math.PI); c.fill();
      break;
    case "halo":
      c.fillStyle = pal.accent;
      c.beginPath(); c.arc(e.x, e.y, e.r, 0, 2 * Math.PI); c.fill();
      break;
    case "figure": {
      c.fillStyle = pal.accent;
      shapePath(c, e.shape ?? "circle", e.x, e.y, e.r); c.fill();
      c.strokeStyle = pal.text; c.lineWidth = e.width ?? 2;
      c.stroke();
      for (let i = 0; i < (e.notches ?? 0); i++) { // one inner notch per further cycle of six shapes
        c.fillStyle = pal.bg;
        c.beginPath(); c.arc(e.x, e.y - e.r * 0.45 + i * 6, 2, 0, 2 * Math.PI); c.fill();
      }
      break;
    }
    case "ring": {
      c.strokeStyle = pal.text; c.lineWidth = e.width ?? 2;
      const gap = e.shape === "closed" ? 0 : 0.6;
      c.lineCap = e.shape === "flat_cap" ? "butt" : "round";
      c.beginPath(); c.arc(e.x, e.y, e.r, -Math.PI / 2 + gap / 2, -Math.PI / 2 + 2 * Math.PI - gap / 2); c.stroke();
      if (e.shape === "jagged_gap") { // teeth across the gap
        const a = -Math.PI / 2;
        c.beginPath();
        for (let i = 0; i <= 4; i++) {
          const k = a - gap / 2 + (gap * i) / 4;
          const rr = e.r + (i % 2 ? 4 : -4);
          if (i === 0) c.moveTo(e.x + rr * Math.cos(k), e.y + rr * Math.sin(k)); else c.lineTo(e.x + rr * Math.cos(k), e.y + rr * Math.sin(k));
        }
        c.stroke();
      }
      c.lineCap = "round";
      break;
    }
    case "fuel": {
      c.strokeStyle = pal.muted; c.lineWidth = e.width ?? 2;
      const end = -Math.PI / 2 + 2 * Math.PI * Math.max(0.02, e.frac ?? 0);
      c.beginPath(); c.arc(e.x, e.y, e.r, -Math.PI / 2, end); c.stroke();
      for (let i = 0; i < (e.ticks ?? 0); i++) { // tick marks under tension
        const k = -Math.PI / 2 + (2 * Math.PI * i) / (e.ticks ?? 1);
        c.beginPath(); c.moveTo(e.x + (e.r - 3) * Math.cos(k), e.y + (e.r - 3) * Math.sin(k));
        c.lineTo(e.x + (e.r + 3) * Math.cos(k), e.y + (e.r + 3) * Math.sin(k)); c.stroke();
      }
      break;
    }
    case "tile": {
      const w = e.w ?? 14, h = e.h ?? 10;
      c.strokeStyle = pal.text; c.fillStyle = pal.accent; c.lineWidth = 1.2;
      if (e.dotted) c.setLineDash([1.5, 2.5]);
      if (e.split) { // split in two
        c.beginPath(); roundRect(c, e.x - w / 2 - 2, e.y - h / 2, w / 2 - 1, h, 2); c.stroke();
        c.beginPath(); roundRect(c, e.x + 3, e.y - h / 2 + 2, w / 2 - 1, h, 2); c.stroke();
      } else {
        c.beginPath(); roundRect(c, e.x - w / 2, e.y - h / 2, w, h, 2);
        if (e.filled) c.fill();
        c.stroke();
      }
      break;
    }
    case "rim":
      c.strokeStyle = pal.text; c.fillStyle = pal.text; c.lineWidth = 1.2;
      if (e.shape === "solid_dot") { c.beginPath(); c.arc(e.x, e.y, Math.max(3, e.r), 0, 2 * Math.PI); c.fill(); }
      else if (e.shape === "broken_outline_dot") { c.setLineDash([2, 2]); c.beginPath(); c.arc(e.x, e.y, Math.max(3, e.r), 0, 2 * Math.PI); c.stroke(); }
      break;
    case "word":
      if (!e.text || !enc.words.includes(e.text)) break; // only the five words ever reach the stage
      c.fillStyle = pal.text;
      c.font = `${enc.word_style.size_px}px ${tokens.font.mono}`;
      c.textBaseline = "middle";
      c.textAlign = e.id === "w:stage" ? "center" : "left";
      c.fillText(e.text.toLowerCase(), e.x, e.y);
      break;
  }
}

export function draw(c: Ctx, f: Frame, theme: Theme, dpr = 1) {
  const t = tokens.themes[theme];
  const pal = { accent: t.accent, warm: t.warm, text: t.text, muted: t.muted, border: t.border, bg: t.bg };
  c.save();
  c.setTransform(dpr, 0, 0, dpr, 0, 0);
  c.globalAlpha = 1;
  c.fillStyle = t.bg;
  c.fillRect(0, 0, f.width, f.height);
  c.lineCap = "round";
  for (const e of f.els) drawEl(c, e, pal);
  c.restore();
}
