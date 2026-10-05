import { afterEach, describe, expect, it, vi } from "vitest";
import * as React from "react";
import { createElement } from "react";
import { renderToString } from "react-dom/server";
import { spawnSync } from "node:child_process";
import { join } from "node:path";

vi.mock("next/navigation", () => ({ usePathname: () => (globalThis as any).__path, useRouter: () => ({ replace: () => {} }) }));
vi.mock("next/link", () => ({ default: (p: any) => createElement("a", { href: p.href }, p.children) }));

import { Shell } from "../../src/lib/shell/Shell";
import { liveBase, shellMode } from "../../src/lib/shell/desktop";

const g = globalThis as any;
g.React = React; // vitest transforms JSX with the classic runtime
const nav = [{ id: "usage", label: "사용", items: [{ href: "/overview", label: "개요" }] }] as any;
const render = (path: string) => { g.__path = path; return renderToString(createElement(Shell as any, { nav }, createElement("i", { id: "child" }))); };

afterEach(() => { delete g.window; delete g.__path; });

describe("Shell under the desktop bridge", () => {
  it("renders /live bare (child, no nav chrome) when window.gaDesktop exists", () => {
    g.window = { gaDesktop: { sidecarUrl: "app://app" } };
    for (const p of ["/live", "/live/"]) {
      const html = render(p);
      expect(html).toContain('id="child"');
      expect(html).not.toContain("<nav");
    }
  });
  it("keeps the normal gate for other paths and for the web (no bridge)", () => {
    g.window = { gaDesktop: { sidecarUrl: "app://app" } };
    expect(render("/overview")).toBe(""); // not ready until a token is found
    delete g.window;
    expect(render("/live")).toBe("");
  });
  it("shellMode: desktop+/live never redirects; web /live without token does", () => {
    const base = { auth: false, hasToken: false };
    expect(shellMode({ ...base, path: "/live/", desktop: true })).toBe("bare");
    expect(shellMode({ ...base, path: "/live", desktop: false })).toBe("redirect");
    expect(shellMode({ ...base, path: "/overview", desktop: true })).toBe("redirect");
    expect(shellMode({ ...base, path: "/overview", desktop: true, hasToken: true })).toBe("chrome");
    expect(shellMode({ ...base, path: "/login", auth: true, desktop: false })).toBe("auth");
  });
});

describe("/live API base", () => {
  const q = (s: string) => new URLSearchParams(s);
  it("uses window.gaDesktop.sidecarUrl when present, ignoring ?api", () => {
    g.window = { gaDesktop: { sidecarUrl: "app://app" } };
    expect(liveBase(q("api=http://evil:1"), "http://d")).toBe("app://app");
  });
  it("else the ?api query, else the default", () => {
    expect(liveBase(q("api=http://x:2"), "http://d")).toBe("http://x:2");
    expect(liveBase(q(""), "http://d")).toBe("http://d");
  });
});

describe("static export flag", () => {
  const load = (flag?: string) => {
    const code = `import("./next.config.mjs").then(m=>console.log(JSON.stringify(m.default)))`;
    const env = { ...process.env, GC_STATIC_EXPORT: flag } as any;
    if (flag === undefined) delete env.GC_STATIC_EXPORT;
    const r = spawnSync("node", ["-e", code], { cwd: join(__dirname, "..", ".."), env, encoding: "utf8" });
    return JSON.parse(r.stdout);
  };
  it("is off by default and on with GC_STATIC_EXPORT=1", () => {
    expect(load()).toEqual({ reactStrictMode: true });
    expect(load("1")).toEqual({ reactStrictMode: true, output: "export", trailingSlash: true, images: { unoptimized: true } });
  });
});
