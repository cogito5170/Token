// CLI: node src/lib/gen/run.mjs [--check]
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { parse } from "yaml";
import openapiTS, { astToString } from "openapi-typescript";
import { buildCss, buildTokensModule } from "./build.mjs";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "../../../..");
const fe = resolve(root, "frontend");

export async function outputs() {
  const tokens = JSON.parse(readFileSync(resolve(root, "design/tokens.json"), "utf8"));
  const spec = parse(readFileSync(resolve(root, "docs/api/openapi.yaml"), "utf8"));
  const ast = await openapiTS(spec);
  return {
    "src/styles/tokens.css": buildCss(tokens),
    "src/lib/tokens/tokens.generated.ts": buildTokensModule(tokens),
    "src/lib/api/schema.d.ts": "// GENERATED from docs/api/openapi.yaml by `npm run gen`. Do not edit.\n" + astToString(ast),
  };
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const out = await outputs();
  for (const [p, c] of Object.entries(out)) {
    const f = resolve(fe, p);
    if (process.argv.includes("--check")) {
      if (readFileSync(f, "utf8") !== c) { console.error(`stale: ${p}`); process.exitCode = 1; }
    } else { mkdirSync(dirname(f), { recursive: true }); writeFileSync(f, c); }
  }
}
