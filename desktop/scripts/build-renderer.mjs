// Builds the static Next.js export of the frontend into desktop/renderer/ without touching frontend/.
// It copies frontend/ to desktop/.build/ and runs `next build` with GC_STATIC_EXPORT=1 (static export; frontend config is untouched).
import { cpSync, rmSync, existsSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(dirname(fileURLToPath(import.meta.url)));
const src = join(here, "..", "frontend");
const root = join(here, ".build");
const tmp = join(root, "frontend"); // keeps the repo-relative imports (../../../design) resolvable
const out = join(here, "renderer");

rmSync(root, { recursive: true, force: true });
cpSync(join(here, "..", "design"), join(root, "design"), { recursive: true });
cpSync(src, tmp, { recursive: true, filter: (p) => !/[\\/](node_modules|\.next|out)([\\/]|$)/.test(p) });
const run = (cmd, args) => {
  const r = spawnSync(cmd, args, { cwd: tmp, stdio: "inherit", env: { ...process.env, GC_STATIC_EXPORT: "1" } });
  if (r.status !== 0) process.exit(r.status ?? 1);
};
run("npm", ["ci", "--no-audit", "--no-fund"]);
run("npx", ["next", "build"]);
rmSync(out, { recursive: true, force: true });
cpSync(join(tmp, "out"), out, { recursive: true });
rmSync(root, { recursive: true, force: true });
console.log("renderer ready:", out, existsSync(join(out, "live", "index.html")) ? "(live ok)" : "(live MISSING)");
