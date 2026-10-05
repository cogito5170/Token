import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "tests",
  outputDir: "tests/components/.build/results",
  globalSetup: "./tests/components/global-setup.ts",
  testMatch: "**/*.spec.ts",
  snapshotPathTemplate: "{testDir}/{testFileDir}/__snapshots__/{arg}{ext}",
  expect: { toHaveScreenshot: { maxDiffPixelRatio: 0, animations: "disabled" } },
  use: {
    viewport: { width: 1280, height: 900 },
    launchOptions: process.env.PLAYWRIGHT_CHROMIUM_PATH ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_PATH } : {},
  },
  reporter: "list",
});
