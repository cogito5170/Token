import { defineConfig } from "vitest/config";

// Unit tests only: *.spec.ts files belong to Playwright (playwright.config.ts).
export default defineConfig({
  test: {
    include: ["tests/**/*.test.ts"],
    exclude: ["**/*.spec.ts", "node_modules/**"],
  },
});
