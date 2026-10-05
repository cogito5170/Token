// Browser bundle for stage.spec.ts: the real Stage component plus the pure frame/draw pair.
import { createRoot, type Root } from "react-dom/client";
import { draw, type Theme } from "../../src/monitor/draw";
import { frame, type FrameOptions } from "../../src/monitor/frame";
import { Stage, type StageProps } from "../../src/monitor/Stage";
import type { MonitorEvent } from "../../src/monitor/types";

let root: Root | null = null;
const w = window as unknown as Record<string, unknown>;
w.gc = {
  mount(props: StageProps) {
    const el = document.getElementById("app")!;
    root ??= createRoot(el);
    root.render(<Stage {...props} />);
  },
  /** Paints frame(events, t) on a fresh canvas and returns its pixels as a base64 string. */
  paint(events: MonitorEvent[], t: number, opts: FrameOptions, theme: Theme): string {
    const cv = document.createElement("canvas");
    cv.width = opts.width;
    cv.height = opts.height;
    const ctx = cv.getContext("2d")!;
    draw(ctx, frame(events, t, opts), theme, 1);
    return cv.toDataURL("image/png");
  },
  frame,
};
