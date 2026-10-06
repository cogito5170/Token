// Acceptance test for CMD-AGA6 (written by baseline; the executor may not edit it).
import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const css = readFileSync(resolve(__dirname, "../../src/styles/screens.css"), "utf8");
const tokens = readFileSync(resolve(__dirname, "../../src/styles/tokens.css"), "utf8");
const body = css.replace(/\/\*[\s\S]*?\*\//g, "");
const rules = [...body.matchAll(/([^{}]+)\{([^{}]*)\}/g)].map((m) => ({ sel: m[1].split(",").map((s) => s.trim()), decl: m[2].trim() }));
const has = (sel: string) => rules.some((r) => r.sel.includes(sel) && /[a-z-]+\s*:\s*[^;]+/.test(r.decl));

describe("screens.css styles the gc-* classes the screens use", () => {
  for (const sel of [".gc-screen", ".gc-screen h1", ".gc-form", ".gc-form label", ".gc-form input", ".gc-form button",
    ".gc-table", ".gc-table th", ".gc-table td", ".gc-table button", ".gc-empty", ".gc-error", ".gc-kpi", ".gc-kpi-label", ".gc-legend"]) {
    it(`has a rule for ${sel}`, () => expect(has(sel)).toBe(true));
  }
  it("uses tokens only: no hex, rgb() or hsl() colours", () => {
    expect(body).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
    expect(body).not.toMatch(/\b(rgb|rgba|hsl|hsla)\(/);
  });
  it("every var(--…) it uses is defined in tokens.css (an undefined var draws nothing)", () => {
    const defined = new Set([...tokens.matchAll(/(--[a-z0-9-]+)\s*:/g)].map((m) => m[1]));
    const used = [...new Set([...body.matchAll(/var\((--[a-z0-9-]+)/g)].map((m) => m[1]))];
    expect(used.length).toBeGreaterThan(5);
    expect(used.filter((v) => !defined.has(v))).toEqual([]);
  });
});
