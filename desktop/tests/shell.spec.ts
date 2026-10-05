import { _electron as electron, expect, test, type ElectronApplication, type Page } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdtempSync, readdirSync, readFileSync, statSync, existsSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const root = join(__dirname, "..");

function fixture(): string {
  const dir = join(mkdtempSync(join(tmpdir(), "ga-desktop-")), ".ga");
  execFileSync("python3", [join(__dirname, "make_fixture.py"), dir]);
  return dir;
}

/** path -> mtime + sha256 for every entry (files and dirs), so any create/modify/delete shows up. */
function treeState(dir: string): Record<string, string> {
  const out: Record<string, string> = {};
  const walk = (d: string) => {
    for (const n of readdirSync(d)) {
      const p = join(d, n);
      const st = statSync(p);
      if (st.isDirectory()) { out[p] = `dir:${st.mtimeMs}`; walk(p); }
      else out[p] = `${st.mtimeMs}:${createHash("sha256").update(readFileSync(p)).digest("hex")}`;
    }
  };
  walk(dir);
  return out;
}

const alive = (pid: number) => { try { process.kill(pid, 0); return true; } catch { return false; } };
async function gone(pid: number, ms = 8000) {
  const end = Date.now() + ms;
  while (Date.now() < end) { if (!alive(pid)) return true; await new Promise((r) => setTimeout(r, 100)); }
  return false;
}
const isRoot = process.getuid?.() === 0;

async function launch(ga: string): Promise<{ app: ElectronApplication; page: Page; logs: string[] }> {
  const app = await electron.launch({
    args: [root, ...(isRoot ? ["--no-sandbox"] : []), "--ga-dir", ga],
    env: { ...process.env, GA_PYTHON: process.env.GA_PYTHON || "python3" } as Record<string, string>,
  });
  const logs: string[] = [];
  const proc = app.process();
  proc.stdout?.on("data", (d) => logs.push(String(d)));
  proc.stderr?.on("data", (d) => logs.push(String(d)));
  const page = await app.firstWindow();
  await page.waitForSelector('[data-testid="stage"]');
  return { app, page, logs };
}
const sidecarPid = (app: ElectronApplication) => app.evaluate(() => (global as any).__gaSidecarPid as number);

test("launches against a fixture .ga dir and shows the stage", async () => {
  const { app, page } = await launch(fixture());
  try {
    const canvas = page.getByTestId("stage");
    await expect(canvas).toBeVisible();
    // the stage must actually paint scene content, not stay blank: poll until some pixel is non-background
    await expect.poll(async () => page.evaluate(() => {
      const c = document.querySelector<HTMLCanvasElement>('[data-testid="stage"]')!;
      const d = c.getContext("2d")!.getImageData(0, 0, c.width, c.height).data;
      const seen = new Set<number>();
      for (let i = 0; i < d.length; i += 4 * 97) seen.add((d[i] << 16) | (d[i + 1] << 8) | d[i + 2]);
      return seen.size;
    }), { timeout: 30_000 }).toBeGreaterThan(3);
    await page.screenshot({ path: join(__dirname, "electron-window.png") });
  } finally { await app.close(); }
});

test("renderer has no Node access and the preload exposes no token", async () => {
  const { app, page } = await launch(fixture());
  try {
    const r = await page.evaluate(() => ({
      require: typeof (window as any).require, process: typeof (window as any).process,
      module: typeof (window as any).module, buffer: typeof (window as any).Buffer,
      bridge: Object.keys((window as any).gaDesktop ?? {}),
    }));
    expect(r).toEqual({ require: "undefined", process: "undefined", module: "undefined", buffer: "undefined", bridge: ["sidecarUrl"] });
    const prefs = await app.evaluate(() => (global as any).__gaWindow.webContents.getLastWebPreferences());
    expect(prefs.contextIsolation).toBe(true);
    expect(prefs.nodeIntegration).toBe(false);
    expect(prefs.sandbox).toBe(true);
    expect(prefs.webSecurity).toBe(true);
  } finally { await app.close(); }
});

test("strict CSP, no remote content, GET-only proxy", async () => {
  const { app, page } = await launch(fixture());
  try {
    const csp = await page.evaluate(async () => (await fetch("/live/")).headers.get("content-security-policy") ?? "");
    expect(csp).toContain("default-src 'none'");
    expect(csp).toContain("connect-src 'self'");
    expect(csp).not.toMatch(/unsafe-eval|unsafe-inline.*script-src|script-src[^;]*unsafe-inline|https?:|\*/);
    // remote content is blocked
    expect(await page.evaluate(() => fetch("https://example.com/").then(() => "loaded", () => "blocked"))).toBe("blocked");
    expect(await page.evaluate(() => fetch("http://127.0.0.1:1/").then(() => "loaded", () => "blocked"))).toBe("blocked");
    // no write verbs reach the sidecar
    const post = await page.evaluate(() => fetch("/v1/workspaces/x/monitor/sources", { method: "POST" }).then((r) => r.status));
    expect(post).toBe(405);
    // reads go through and are authorized by main (the renderer never held a token)
    const src = await page.evaluate(() => fetch("/v1/workspaces/00000000-0000-0000-0000-000000000000/monitor/sources").then((r) => r.status));
    expect(src).toBe(200);
    // navigation away from app:// is refused
    await page.evaluate(() => { location.href = "https://example.com/"; });
    await page.waitForTimeout(500);
    expect(page.url()).toMatch(/^app:\/\/app\//);
  } finally { await app.close(); }
});

test("the one-time token is never logged or written to disk", async () => {
  const { app, page, logs } = await launch(fixture());
  let token = "";
  try {
    const pid = await sidecarPid(app);
    token = /GC_SIDECAR_TOKEN=([^\0]+)/.exec(readFileSync(`/proc/${pid}/environ`, "latin1"))?.[1] ?? "";
    expect(token.length).toBeGreaterThan(20);
    expect(await page.content()).not.toContain(token);
    expect(await page.evaluate(() => JSON.stringify([{ ...sessionStorage }, { ...localStorage }]))).not.toContain(token);
    const userData = await app.evaluate(({ app }) => app.getPath("userData"));
    await app.close();
    const hits: string[] = [];
    const walk = (d: string) => {
      for (const n of readdirSync(d)) {
        const p = join(d, n);
        const st = statSync(p);
        if (st.isDirectory()) walk(p);
        else if (st.size < 20e6 && readFileSync(p).includes(token)) hits.push(p);
      }
    };
    if (existsSync(userData)) walk(userData);
    expect(hits).toEqual([]);
    expect(logs.join("")).not.toContain(token);
  } finally { await app.close().catch(() => {}); }
});

test("the sidecar dies with the app (graceful quit and SIGKILL)", async () => {
  {
    const { app } = await launch(fixture());
    const pid = await sidecarPid(app);
    expect(alive(pid)).toBe(true);
    await app.close();
    expect(await gone(pid)).toBe(true);
  }
  {
    const { app } = await launch(fixture());
    const pid = await sidecarPid(app);
    app.process().kill("SIGKILL");
    expect(await gone(pid)).toBe(true);
  }
});

test("nothing is written inside the .ga dir", async () => {
  const ga = fixture();
  const before = treeState(ga);
  const { app, page } = await launch(ga);
  try {
    await page.waitForTimeout(3000); // several sidecar polls
    await page.evaluate(() => fetch("/v1/workspaces/x/monitor/sources", { method: "DELETE" }));
  } finally { await app.close(); }
  expect(treeState(ga)).toEqual(before);
});
