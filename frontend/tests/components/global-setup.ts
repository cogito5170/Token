import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { build } from "esbuild";

/**
 * Playwright's own transform forces its JSX runtime on .tsx files, so the gallery is bundled with
 * esbuild (automatic React runtime) and rendered to static HTML once; the spec loads that markup.
 */
export default async function globalSetup() {
  const root = join(dirname(fileURLToPath(import.meta.url)), "../..");
  const out = join(root, "tests/components/.build");
  mkdirSync(out, { recursive: true });
  const bundle = join(out, "gallery.mjs");
  await build({
    entryPoints: [join(root, "src/components/Gallery.tsx")],
    outfile: bundle,
    bundle: true,
    format: "esm",
    platform: "node",
    jsx: "automatic",
    external: ["react", "react-dom", "react/jsx-runtime"],
    logLevel: "silent",
  });
  const mod = await import(pathToFileURL(bundle).href + `?t=${Date.now()}`);
  const React = await import("react");
  const { renderToStaticMarkup } = await import("react-dom/server");
  writeFileSync(join(out, "gallery.html"), renderToStaticMarkup(React.createElement(mod.Gallery)));
}
