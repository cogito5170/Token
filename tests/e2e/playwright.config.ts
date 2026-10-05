import { defineConfig } from "@playwright/test";

// Started by scripts/e2e_stack.py, which exports E2E_WEB_URL / E2E_API_URL / E2E_SHOTS / E2E_SKIP_REASON.
export default defineConfig({
  testDir: ".",
  testMatch: "**/*.spec.ts",
  timeout: 120_000,
  reporter: "list",
  workers: 1,
  outputDir: "/tmp/gc-e2e-results",
  use: {
    baseURL: process.env.E2E_WEB_URL,
    viewport: { width: 1280, height: 900 },
    launchOptions: process.env.PLAYWRIGHT_CHROMIUM_PATH ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_PATH } : {},
  },
});
