// CMD-FE2 done_when (browser part): the real canvas renders the same pixels for the same events + t,
// reduced motion keeps pixels still between frames, no text on stage but the five words, numbers only on hover.
import { mkdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { build } from "esbuild";
import { expect, test, type Page } from "@playwright/test";
import { encoding } from "../../src/monitor/encoding";
import { events, repo } from "./fixture";

const fe = join(repo, "frontend");
const out = join(fe, "tests/monitor/.build");
const SHOTS = join(fe, "tests/monitor");
const W = 1280, H = 800;
let bundle = "";

test.beforeAll(async () => {
  mkdirSync(out, { recursive: true });
  await build({
    entryPoints: [join(fe, "tests/monitor/harness.tsx")],
    outfile: join(out, "harness.js"),
    bundle: true,
    format: "iife",
    platform: "browser",
    jsx: "automatic",
    define: { "process.env.NODE_ENV": '"production"' },
    logLevel: "silent",
  });
  bundle = readFileSync(join(out, "harness.js"), "utf8");
});

async function open(page: Page) {
  await page.setViewportSize({ width: W, height: H });
  await page.setContent(`<!doctype html><html lang="en"><head><meta charset="utf-8"><title>live</title>
<style>html,body{margin:0;height:100%}</style></head><body><div id="app"></div></body></html>`);
  // record every text the canvas is asked to draw
  await page.evaluate(() => {
    const w = window as unknown as { drawn: string[] };
    w.drawn = [];
    const p = CanvasRenderingContext2D.prototype;
    const fill = p.fillText, stroke = p.strokeText;
    p.fillText = function (s: string, ...a: [number, number]) { w.drawn.push(s); return fill.call(this, s, ...a); };
    p.strokeText = function (s: string, ...a: [number, number]) { w.drawn.push(`stroke:${s}`); return stroke.call(this, s, ...a); };
  });
  await page.addScriptTag({ content: bundle });
}

const paint = (page: Page, t: number, reduced: boolean, theme: "dark" | "light" = "dark") =>
  page.evaluate(([ev, t, reduced, theme, W, H]) =>
    (window as any).gc.paint(ev, t, { width: W, height: H, reduced }, theme) as string, [events, t, reduced, theme, W, H] as const);

const mount = (page: Page, props: Record<string, unknown>) =>
  page.evaluate(([ev, p]) => (window as any).gc.mount({ events: ev, ...p }), [events, props] as const);

async function stagePixels(page: Page): Promise<string> {
  await page.waitForTimeout(80);
  return page.locator("[data-testid=stage]").evaluate((c: HTMLCanvasElement) => c.toDataURL("image/png"));
}

test.describe("stage in the browser", () => {
  test.beforeEach(async ({ page }) => open(page));

  test("same events + same t paint the same pixels twice", async ({ page }) => {
    for (const t of [0, 3000, 4200, 5000, 9100]) {
      for (const reduced of [false, true]) expect(await paint(page, t, reduced)).toBe(await paint(page, t, reduced));
    }
    expect(await paint(page, 4100, false)).not.toBe(await paint(page, 4400, false));
  });

  test("the mounted Stage at a fixed t equals a direct paint and repeats", async ({ page }) => {
    await mount(page, { mode: "replay", at: 5000, reduced: false, theme: "dark" });
    const a = await stagePixels(page);
    await mount(page, { mode: "replay", at: 7000, reduced: false, theme: "dark" });
    const b = await stagePixels(page);
    await mount(page, { mode: "replay", at: 5000, reduced: false, theme: "dark" });
    expect(await stagePixels(page)).toBe(a);
    expect(b).not.toBe(a);
  });

  test("reduced motion: pixels stay still between frames with no new event", async ({ page }) => {
    // no event and no word expiry between 5500 and 5900 (events at 5000 and 7000, the 4000 words end at 6000)
    expect(await paint(page, 5516, true)).toBe(await paint(page, 5500, true));
    expect(await paint(page, 5900, true)).toBe(await paint(page, 5500, true));
    expect(await paint(page, 5516, false)).not.toBe(await paint(page, 5500, false));
  });

  test("prefers-reduced-motion turns the stage still", async ({ page }) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    await mount(page, { mode: "live" });
    await expect(page.locator("[data-reduced]")).toHaveAttribute("data-reduced", "1");
    await page.emulateMedia({ reducedMotion: "no-preference" });
    await expect(page.locator("[data-reduced]")).toHaveAttribute("data-reduced", "0");
    await page.locator("[data-testid=bar]").hover();
    await page.locator("[data-testid=still]").click();
    await expect(page.locator("[data-reduced]")).toHaveAttribute("data-reduced", "1");
  });

  test("no text on stage except the five words; numbers only on hover", async ({ page }) => {
    await mount(page, { mode: "replay", theme: "dark" });
    // replay plays the whole recording from t=0
    await page.waitForTimeout(12500);
    const drawn: string[] = await page.evaluate(() => (window as any).drawn);
    expect(drawn.length).toBeGreaterThan(0);
    for (const s of new Set(drawn)) expect(encoding.words, s).toContain(s);
    expect((await page.evaluate(() => document.body.innerText)).trim()).toBe("");
    await expect(page.locator("[data-testid=bar]")).toHaveCSS("opacity", "0");
    await expect(page.locator("[data-testid=tip]")).toHaveCount(0);
  });

  test("hover shows small numbers next to a figure, then hides them", async ({ page }) => {
    await mount(page, { mode: "replay", at: 5000, theme: "dark" });
    const fig = await page.evaluate(([ev, W, H]) =>
      (window as any).gc.frame(ev, 5000, { width: W, height: H, reduced: false }).els.find((e: any) => e.kind === "figure"),
      [events, W, H] as const);
    await stagePixels(page); // the first frame is drawn
    await page.mouse.move(fig.x + 1, fig.y + 1);
    await page.mouse.move(fig.x, fig.y);
    const tip = page.locator("[data-testid=tip]");
    await expect(tip).toBeVisible();
    expect(await tip.innerText()).toMatch(/\d/);
    expect(await tip.evaluate((e) => getComputedStyle(e).fontSize)).toBe("12px");
    await page.mouse.move(5, 5);
    await expect(tip).toHaveCount(0);
  });

  test("the scrubber appears only on hover and moves time", async ({ page }) => {
    await mount(page, { mode: "replay", theme: "dark" });
    const bar = page.locator("[data-testid=bar]");
    await expect(bar).toHaveCSS("opacity", "0");
    await bar.hover();
    await expect(bar).toHaveCSS("opacity", "1");
    await page.locator("[data-testid=scrubber]").fill("5000");
    const a = await stagePixels(page);
    await page.locator("[data-testid=scrubber]").fill("9000");
    expect(await stagePixels(page)).not.toBe(a);
  });

  test("screenshots for review (dark, light, reduced)", async ({ page }) => {
    await mount(page, { mode: "replay", at: 4300, reduced: false, theme: "dark" });
    await page.waitForTimeout(100);
    await page.screenshot({ path: join(SHOTS, "stage-dark.png") });
    await mount(page, { mode: "replay", at: 4300, reduced: false, theme: "light" });
    await page.waitForTimeout(100);
    await page.screenshot({ path: join(SHOTS, "stage-light.png") });
    await mount(page, { mode: "replay", at: 7500, reduced: true, theme: "dark" });
    await page.waitForTimeout(100);
    await page.screenshot({ path: join(SHOTS, "stage-reduced.png") });
  });
});
