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
