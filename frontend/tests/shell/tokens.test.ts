import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { buildCss, baseVarMap, themeVarMap } from "../../src/lib/gen/build.mjs";
import { echartsTheme } from "../../src/lib/charts/theme";

const root = resolve(__dirname, "../../..");
const tokens = JSON.parse(readFileSync(resolve(root, "design/tokens.json"), "utf8"));
const css = readFileSync(resolve(root, "frontend/src/styles/tokens.css"), "utf8");

function declared(block: string): Record<string, string> {
  return Object.fromEntries([...block.matchAll(/^\s*(--[\w-]+|color-scheme):\s*(.+);$/gm)].map((m) => [m[1], m[2]]));
}

describe("CSS variables equal design/tokens.json", () => {
  it("committed tokens.css is the generator output", () => expect(css).toBe(buildCss(tokens)));

  it("every light/dark/base token appears with its exact value", () => {
    const rootBlock = declared(css.slice(css.indexOf(":root {"), css.indexOf("@media")));
    for (const [k, v] of Object.entries(baseVarMap(tokens))) expect(rootBlock[k]).toBe(String(v));
    for (const [k, v] of Object.entries(themeVarMap(tokens, "light"))) expect(rootBlock[k]).toBe(String(v));
    const darkBlock = declared(css.slice(css.indexOf(':root[data-theme="dark"]')));
    for (const [k, v] of Object.entries(themeVarMap(tokens, "dark"))) expect(darkBlock[k]).toBe(String(v));
  });

  it("known spot values", () => {
    expect(css).toContain("--gc-color-accent: #1F5FAD;");
    expect(css).toContain("--gc-layout-nav: 232px;");
    expect(css).toContain("--gc-duration-base: 200ms;");
  });

  it("ECharts theme uses only token colors", () => {
    const t = echartsTheme("dark");
    expect(t.color).toEqual([
      tokens.themes.dark.series.input, tokens.themes.dark.series.cache_read,
      tokens.themes.dark.series.cache_write, tokens.themes.dark.series.output,
    ]);
    expect(t.textStyle.color).toBe(tokens.themes.dark.text);
  });
});
