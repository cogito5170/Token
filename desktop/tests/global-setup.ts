// Builds the static renderer if it is missing, and starts a headless X server when there is no DISPLAY.
import { spawn, spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { join } from "node:path";

const root = join(__dirname, "..");

export default async function globalSetup() {
  if (!existsSync(join(root, "renderer", "live", "index.html"))) {
    const r = spawnSync("node", ["scripts/build-renderer.mjs"], { cwd: root, stdio: "inherit" });
    if (r.status !== 0) throw new Error("renderer build failed");
  }
  if (!process.env.DISPLAY) {
    const x = spawn("Xvfb", [":97", "-screen", "0", "1280x800x24", "-nolisten", "tcp"], { stdio: "ignore" });
    process.env.DISPLAY = ":97";
    await new Promise((r) => setTimeout(r, 1000));
    return async () => { x.kill(); };
  }
}
