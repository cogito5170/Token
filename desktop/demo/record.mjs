// Launches the packaged app (AppImage if built, else the repo shell) against demo/replay.py and records a video
// (webm, 1280x800) plus 4 screenshots into demo/out/. Usage: node demo/record.mjs   (needs DISPLAY or Xvfb)
import { _electron as electron } from "@playwright/test";
import { spawn } from "node:child_process";
import { copyFileSync, existsSync, mkdirSync, readdirSync, renameSync, rmSync, statSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import * as readline from "node:readline";

const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, "..");
const out = join(here, "out");
const installers = join(root, "dist", "installers");
const image = existsSync(installers) ? readdirSync(installers).find((n) => n.endsWith(".AppImage")) : undefined;
const noSandbox = process.getuid?.() === 0 ? ["--no-sandbox"] : [];
const SHOTS = [["01-design-kickoff", 8], ["02-collaboration", 20], ["03-red-judge", 26.5], ["04-integration-done", 37]]; // seconds into the run

rmSync(out, { recursive: true, force: true });
mkdirSync(out, { recursive: true });
const rp = spawn("python3", [join(here, "replay.py"), "--duration", "40"], { stdio: ["ignore", "pipe", "inherit"] });
try {
  const ga = await new Promise((res) => readline.createInterface({ input: rp.stdout }).once("line", res));
  const t0 = Date.now();
  const app = await electron.launch({
    ...(image ? { executablePath: join(installers, image), args: [...noSandbox, "--ga-dir", ga] } : { args: [root, ...noSandbox, "--ga-dir", ga] }),
    env: { ...process.env, APPIMAGE_EXTRACT_AND_RUN: "1" },
    recordVideo: { dir: join(out, "video-tmp"), size: { width: 1280, height: 800 } },
  });
  const page = await app.firstWindow();
  await page.waitForSelector('[data-testid="stage"]');
  const video = page.video();
  for (const [name, at] of SHOTS) {
    const wait = t0 + at * 1000 - Date.now();
    if (wait > 0) await page.waitForTimeout(wait);
    await page.screenshot({ path: join(out, `${name}.png`) });
  }
  await page.waitForTimeout(Math.max(0, t0 + 40_000 - Date.now()));
  await app.close();
  const src = await video.path();
  renameSync(src, join(out, "demo.webm"));
  rmSync(join(out, "video-tmp"), { recursive: true, force: true });
  console.log("recorded:", readdirSync(out).map((n) => `${n} (${(statSync(join(out, n)).size / 1e6).toFixed(2)} MB)`).join(", "));
  if (process.argv.includes("--preview")) {
    const prev = join(here, "preview");
    mkdirSync(prev, { recursive: true });
    for (const n of readdirSync(out)) copyFileSync(join(out, n), join(prev, n));
  }
} finally { rp.kill(); }
