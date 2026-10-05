"use client";
import { useEffect, useRef } from "react";
import { registerThemes } from "../../../lib/charts/theme";

/** Thin ECharts host: loads echarts lazily (browser only), applies the token theme, resizes with its box. */
export function EChart({ option, label, height = 280, onClick }: {
  option: object;
  label: string;
  height?: number;
  onClick?: (p: { data?: unknown; seriesName?: string }) => void;
}) {
  const box = useRef<HTMLDivElement>(null);
  const click = useRef(onClick);
  click.current = onClick;
  useEffect(() => {
    type Chart = { setOption: (o: object, n?: boolean) => void; resize: () => void; dispose: () => void; on: (e: string, f: (p: never) => void) => void };
    let chart: Chart | null = null;
    let ro: ResizeObserver | null = null;
    let dead = false;
    import("echarts").then((echarts) => {
      if (dead || !box.current) return;
      registerThemes(echarts);
      const dark = typeof window !== "undefined" && window.matchMedia?.("(prefers-color-scheme: dark)").matches;
      const c = echarts.init(box.current, dark ? "gc-dark" : "gc-light") as unknown as Chart;
      chart = c;
      c.setOption(option, true);
      c.on("click", ((p: { data?: unknown; seriesName?: string }) => click.current?.(p)) as never);
      ro = new ResizeObserver(() => chart?.resize());
      ro.observe(box.current);
    });
    return () => { dead = true; ro?.disconnect(); chart?.dispose(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [JSON.stringify(option)]);
  return <div ref={box} role="img" aria-label={label} style={{ width: "100%", height }} />;
}
