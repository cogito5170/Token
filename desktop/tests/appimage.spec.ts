import { _electron as electron, expect, test } from "@playwright/test";
import { spawn } from "node:child_process";
import { existsSync, readdirSync } from "node:fs";
import { join } from "node:path";
import * as readline from "node:readline";

const out = join(__dirname, "..", "dist", "installers");
const image = existsSync(out) ? readdirSync(out).find((n) => n.endsWith(".AppImage")) : undefined;
const isRoot = process.getuid?.() === 0;

// Needs `npm run dist:linux` first (skipped otherwise, like other tests that need a built artifact).
test.skip(!image, "AppImage not built (npm run dist:linux)");

test("the AppImage launches against the replay dir and the stage paints", async () => {
  const rp = spawn("python3", [join(__dirname, "..", "demo", "replay.py"), "--duration", "20"], { stdio: ["ignore", "pipe", "inherit"] });
  try {
    const ga: string = await new Promise((res) => readline.createInterface({ input: rp.stdout! }).once("line", res));
    const app = await electron.launch({
      executablePath: join(out, image!),
      args: [...(isRoot ? ["--no-sandbox"] : []), "--ga-dir", ga],
      env: { ...process.env, APPIMAGE_EXTRACT_AND_RUN: "1" } as Record<string, string>,
    });
    try {
      const page = await app.firstWindow();
      await page.waitForSelector('[data-testid="stage"]', { timeout: 60_000 });
      expect(await app.evaluate(({ app }) => app.getName())).toBe("ga-console-desktop");
      await expect.poll(async () => page.evaluate(() => {
        const c = document.querySelector<HTMLCanvasElement>('[data-testid="stage"]')!;
        const d = c.getContext("2d")!.getImageData(0, 0, c.width, c.height).data;
        const seen = new Set<number>();
        for (let i = 0; i < d.length; i += 4 * 97) seen.add((d[i] << 16) | (d[i + 1] << 8) | d[i + 2]);
        return seen.size;
      }), { timeout: 40_000 }).toBeGreaterThan(3);
    } finally { await app.close(); }
  } finally { rp.kill(); }
});
