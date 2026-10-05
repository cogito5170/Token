// Packaging: stages a self-contained app dir in desktop/dist/app (renderer export + shell sources + the vendored
// read-only Python reader as plain .py files). `npm run dist:linux|mac|win` turns it into an installer with
// electron-builder (config: "build" in package.json); the shell finds the staged files through GA_BACKEND_DIR / GA_RENDERER_DIR or relative paths.
import { cpSync, mkdirSync, rmSync, existsSync, writeFileSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(dirname(fileURLToPath(import.meta.url)));
const out = join(here, "dist", "app");
if (!existsSync(join(here, "renderer", "live", "index.html"))) {
  console.error("renderer/ is missing: run `npm run build:renderer` first");
  process.exit(1);
}
rmSync(out, { recursive: true, force: true });
mkdirSync(out, { recursive: true });
cpSync(join(here, "src"), join(out, "src"), { recursive: true });
cpSync(join(here, "sidecar"), join(out, "sidecar"), { recursive: true });
cpSync(join(here, "renderer"), join(out, "renderer"), { recursive: true });
// only the Run domain reader (stdlib only) is vendored; no other backend code ships
const dom = join("backend", "app", "domains", "run");
mkdirSync(join(out, "backend", "app", "domains"), { recursive: true });
for (const f of ["__init__.py"]) writeFileSync(join(out, "backend", "app", f), "");
writeFileSync(join(out, "backend", "app", "domains", "__init__.py"), "");
cpSync(join(here, "..", dom), join(out, dom), { recursive: true, filter: (p) => !/(__pycache__|[\\/]tests)([\\/]|$)/.test(p) });
const pkg = JSON.parse(readFileSync(join(here, "package.json"), "utf8"));
writeFileSync(join(out, "package.json"), JSON.stringify({ name: pkg.name, version: pkg.version, description: pkg.description, author: pkg.author, main: "src/main.js" }, null, 2));
console.log("staged:", out);
