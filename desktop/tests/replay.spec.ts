import { expect, test } from "@playwright/test";
import { spawnSync } from "node:child_process";
import { join } from "node:path";

test("demo replay unit tests (python)", () => {
  const r = spawnSync("python3", ["-m", "unittest", "-v", "test_replay"], { cwd: __dirname, encoding: "utf8" });
  expect(r.stderr + r.stdout).toContain("OK");
  expect(r.status).toBe(0);
});
