import { readFileSync } from "node:fs";
import { join } from "node:path";
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

const root = process.cwd();
const css = ["src/styles/tokens.css", "src/components/components.css"].map((f) => readFileSync(join(root, f), "utf8")).join("\n");
const gallery = readFileSync(join(root, "tests/components/.build/gallery.html"), "utf8");
const SECTIONS = ["chips", "kpi", "range", "cost", "bars", "figures", "kanban", "drawer"];

async function open(page: Page, theme: "light" | "dark") {
  const html = `<!doctype html><html lang="ko" data-theme="${theme}"><head><meta charset="utf-8"><title>gallery</title><style>${css}
body{margin:0;background:var(--gc-color-bg);color:var(--gc-color-text);font-family:var(--gc-font-sans);font-size:var(--gc-text-md)}</style></head><body>${gallery}</body></html>`;
  await page.setContent(html);
}

for (const theme of ["light", "dark"] as const) {
  test.describe(theme, () => {
    test.beforeEach(async ({ page }) => open(page, theme));

    for (const id of SECTIONS) {
      test(`snapshot ${id}`, async ({ page }) => {
        await expect(page.locator(`#${id}`)).toHaveScreenshot(`${id}-${theme}.png`);
      });
    }

    test("axe finds no violations", async ({ page }) => {
      const r = await new AxeBuilder({ page: page as never }).disableRules(["page-has-heading-one"]).analyze() // gallery is not a page;
      expect(r.violations.map((v) => `${v.id}: ${v.nodes.length}`)).toEqual([]);
    });

    test("chips differ by line style, not color", async ({ page }) => {
      const s = await page.$$eval("#chips .gc-chip", (els) =>
        els.map((e) => {
          const c = getComputedStyle(e);
          return { bs: c.borderTopStyle, bw: c.borderTopWidth, bc: c.borderTopColor };
        }),
      );
      expect(s.map((x) => x.bs)).toEqual(["solid", "solid", "dashed", "dotted"]);
      expect(new Set(s.map((x) => x.bc)).size).toBe(1);
      // measured (filled) vs calculated (outlined) differ by fill, not hue
      const bg = await page.$$eval("#chips .gc-chip", (els) => els.map((e) => getComputedStyle(e).backgroundColor));
      expect(bg[0]).not.toBe(bg[1]);
    });

    test("numbers use tabular-nums", async ({ page }) => {
      const v = await page.$$eval(".num", (els) => els.map((e) => getComputedStyle(e).fontVariantNumeric));
      expect(v.length).toBeGreaterThan(10);
      for (const x of v) expect(x).toContain("tabular-nums");
    });

    test("unknown renders an em dash", async ({ page }) => {
      await expect(page.locator("#kpi .gc-kpi-value").nth(1)).toHaveText("—");
      await expect(page.locator("#cost .gc-cost-value").nth(3)).toHaveText("—");
    });
  });
}
