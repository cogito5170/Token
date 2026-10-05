import { expect, test } from "@playwright/test";
import { createRequire } from "node:module";
const sec = createRequire(__filename)("../src/security.js");

test("webPreferences are hardened", () => {
  expect(sec.WEB_PREFERENCES).toMatchObject({ contextIsolation: true, nodeIntegration: false, sandbox: true, webviewTag: false });
});
test("proxy allows only GET/HEAD on monitor paths", () => {
  const p = "/v1/workspaces/w/monitor/sources";
  expect(sec.allowedProxy("GET", p)).toBe(true);
  for (const m of ["POST", "PUT", "PATCH", "DELETE", "OPTIONS"]) expect(sec.allowedProxy(m, p)).toBe(false);
  expect(sec.allowedProxy("GET", "/v1/workspaces/w/runs")).toBe(false);
});
test("only app:// may be navigated to", () => {
  expect(sec.allowedNavigation("app://app/live/")).toBe(true);
  expect(sec.allowedNavigation("https://example.com/")).toBe(false);
  expect(sec.allowedNavigation("file:///etc/passwd")).toBe(false);
});
test("csp lists inline script hashes and no remote origin", () => {
  const html = '<script src="/a.js"></script><script>self.x=1</script>';
  const h = sec.inlineScriptHashes(html);
  expect(h).toHaveLength(1);
  expect(sec.csp(h)).toContain(h[0]);
  expect(sec.csp(h)).not.toMatch(/https?:|\*|unsafe-eval/);
});

test("IF2: static export comes from the env flag, not from rewriting the copied config; no tracked screenshot is overwritten", async () => {
  const { readFileSync, existsSync } = await import("node:fs");
  const { join } = await import("node:path");
  const { execFileSync } = await import("node:child_process");
  const root = join(__dirname, "..");
  const build = readFileSync(join(root, "scripts", "build-renderer.mjs"), "utf8");
  expect(build).toContain('GC_STATIC_EXPORT: "1"');
  expect(build).not.toMatch(/next\.config\.mjs/);
  expect(readFileSync(join(root, "src", "preload.js"), "utf8")).not.toMatch(/sessionStorage|gc\.access/);
  const spec = readFileSync(join(__dirname, "shell.spec.ts"), "utf8");
  expect(spec).toContain('"test-results", "electron-window.png"');
  expect(existsSync(join(__dirname, "electron-window.png"))).toBe(false);
  const tracked = execFileSync("git", ["ls-files", "desktop/tests"], { cwd: join(root, ".."), encoding: "utf8" });
  expect(tracked).not.toMatch(/\.png/);
});

test("IF2: installers are configured (AppImage, dmg, nsis), unsigned, with the product name and no credentials", async () => {
  const { readFileSync } = await import("node:fs");
  const { join } = await import("node:path");
  const pkg = JSON.parse(readFileSync(join(__dirname, "..", "package.json"), "utf8"));
  expect(pkg.build.productName).toBe("GA Console Monitor");
  expect(pkg.build.appId).toMatch(/^[a-z0-9.]+$/);
  expect(pkg.build.linux.target).toContain("AppImage");
  expect(pkg.build.mac.target).toContain("dmg");
  expect(pkg.build.mac.identity).toBeNull();
  expect(pkg.build.win.target).toContain("nsis");
  expect(JSON.stringify(pkg.build)).not.toMatch(/certificate|password|CSC_|notariz|appleId|apiKey/i);
  expect(pkg.devDependencies["electron-builder"]).toMatch(/^\d+\.\d+\.\d+$/); // pinned
});
