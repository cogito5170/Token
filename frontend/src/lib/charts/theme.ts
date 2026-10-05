import { tokens } from "../tokens/tokens.generated";

export type ThemeName = "light" | "dark";

/** ECharts theme object built only from design/tokens.json (via tokens.generated.ts). */
export function echartsTheme(name: ThemeName) {
  const t = tokens.themes[name];
  const s = t.series;
  return {
    color: [s.input, s.cache_read, s.cache_write, s.output],
    backgroundColor: "transparent",
    textStyle: { color: t.text, fontFamily: tokens.font.sans },
    title: { textStyle: { color: t.text }, subtextStyle: { color: t.muted } },
    legend: { textStyle: { color: t.muted } },
    categoryAxis: { axisLine: { lineStyle: { color: t.border } }, axisLabel: { color: t.muted }, splitLine: { show: false } },
    valueAxis: { axisLine: { show: false }, axisLabel: { color: t.muted }, splitLine: { lineStyle: { color: t.border } } },
    tooltip: { backgroundColor: t.surface, borderColor: t.border, textStyle: { color: t.text } },
    line: { lineStyle: { width: 2 } },
    animationDuration: tokens.motion.duration_ms.slow,
  };
}

export const registerThemes = (echarts: { registerTheme: (n: string, t: object) => void }) => {
  echarts.registerTheme("gc-light", echartsTheme("light"));
  echarts.registerTheme("gc-dark", echartsTheme("dark"));
};

/** Line dash for a provenance (chips and lines differ by shape, not color). */
export const provenanceLine = (p: keyof typeof tokens.provenance) => tokens.provenance[p].line;
