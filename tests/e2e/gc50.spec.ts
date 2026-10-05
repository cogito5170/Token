import { expect, test } from "@playwright/test";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const SKIP = process.env.E2E_SKIP_REASON ?? "";
const SHOTS = process.env.E2E_SHOTS ?? "reports/gc50";
const API = process.env.E2E_API_URL ?? "";
const PASSWORD = "e2e-" + Math.random().toString(36).slice(2) + "-Zq8Zq8"; // generated per run, never stored

/** The Claude Code transcript shape backend/tests/test_e2e.py uploads (two calls), plus one call with a 90k-token
 *  context so the advisor's R1 (bulk injection, context > 50000) has something to report. */
function fixture(): string {
  const t0 = Date.now() - 3600_000;
  const lines = [1, 2, 90].map((k, i) => JSON.stringify({
    type: "assistant", sessionId: "cc-session-1", uuid: `u${i + 1}`, timestamp: new Date(t0 + (i + 1) * 60_000).toISOString(),
    message: { id: `msg_${i + 1}`, model: "claude-sonnet-5-5", role: "assistant", content: [],
      usage: { input_tokens: 1000 * k, output_tokens: 50, cache_read_input_tokens: 0, cache_creation_input_tokens: 0 } },
  }));
  const p = join(mkdtempSync(join(tmpdir(), "gc-e2e-")), "session.jsonl");
  writeFileSync(p, lines.join("\n") + "\n");
  return p;
}

test("signup -> upload -> overview -> advisor -> report", async ({ page }) => {
  test.skip(!!SKIP, SKIP);

  // signup (real API), then the shell selects the personal workspace
  await page.goto("/signup");
  await page.getByLabel("이름").fill("E2E");
  await page.getByLabel("이메일").fill(`e2e-${Date.now()}@example.com`);
  await page.getByLabel("비밀번호").fill(PASSWORD);
  await page.getByRole("button", { name: "가입" }).click();
  await expect(page).not.toHaveURL(/\/signup/);
  await expect.poll(() => page.evaluate(() => sessionStorage.getItem("gc.workspace")), { timeout: 30_000 }).toBeTruthy();

  // upload a Claude Code usage file
  await page.goto("/upload");
  const token = await page.evaluate(() => sessionStorage.getItem("gc.access"));
  const ws = await page.evaluate(() => sessionStorage.getItem("gc.workspace"));
  expect(token && ws).toBeTruthy();
  const auth = { authorization: `Bearer ${token}` };
  const src = await page.request.post(`${API}/v1/workspaces/${ws}/sources`, { headers: auth, data: { kind: "upload", name: "e2e" } });
  expect(src.status()).toBe(201); // the upload screen has no source picker yet: it asks for a source id
  const sourceId = (await src.json()).id as string;
  await page.getByLabel("소스 ID").fill(sourceId);
  await page.getByLabel("파일").setInputFiles(fixture());
  await page.getByRole("button", { name: "업로드" }).click();
  await expect(page.getByRole("status")).toContainText("완료", { timeout: 60_000 });
  await page.screenshot({ path: join(SHOTS, "upload.png") });

  // overview with tokens
  await page.goto("/overview");
  const tile = page.getByText("총 토큰").locator("..");
  await expect(tile).toContainText(/[1-9]/, { timeout: 30_000 });
  await expect(page.locator(".gc-screen")).toContainText("토큰");
  await page.waitForTimeout(1000); // chart animation
  await page.screenshot({ path: join(SHOTS, "overview.png") });

  // advisor finding
  await page.goto("/advisor");
  await expect(page.locator(".gc-findings li").first()).toBeVisible({ timeout: 30_000 });
  await page.screenshot({ path: join(SHOTS, "advisor.png") });

  // report export (the web has no report screen yet: the page's own session calls the API, then shows the export)
  const day = (d: number) => new Date(Date.now() + d * 86400_000).toISOString().slice(0, 10);
  const rep = await page.request.post(`${API}/v1/workspaces/${ws}/reports`, { headers: auth, data: { from: day(-30), to: day(1) } });
  expect(rep.status()).toBe(201);
  const rid = (await rep.json()).id as string;
  const csv = await page.request.get(`${API}/v1/workspaces/${ws}/reports/${rid}/export`, { headers: auth, params: { format: "csv" } });
  expect(csv.status()).toBe(200);
  const text = await csv.text();
  expect(text).toContain("savings,");
  await page.setContent(`<html><body style="font:14px monospace;padding:16px"><h1>report export (csv)</h1><pre>${text.replace(/&/g, "&amp;").replace(/</g, "&lt;")}</pre></body></html>`);
  await page.screenshot({ path: join(SHOTS, "report.png") });
});
