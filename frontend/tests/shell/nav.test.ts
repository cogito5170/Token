import { describe, expect, it } from "vitest";
import { mkdtempSync, mkdirSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { buildNav } from "../../src/lib/nav/registry";
import { scanRoutes } from "../../src/lib/nav/scan";

function screen(root: string, rel: string, meta: object) {
  const d = join(root, "(app)", rel);
  mkdirSync(d, { recursive: true });
  writeFileSync(join(d, "nav.json"), JSON.stringify(meta));
}

describe("route registry", () => {
  it("discovers screens from the file system, grouped and ordered, with no shared nav edit", () => {
    const root = mkdtempSync(join(tmpdir(), "nav-"));
    screen(root, "overview", { group: "usage", label: "개요", order: 10 });
    screen(root, "token-mix", { group: "usage", label: "토큰 구성", order: 20 });
    screen(root, "compare", { group: "consulting", label: "구성 비교" });
    screen(root, "audit", { group: "footer", label: "감사 로그", adminOnly: true });
    const nav = buildNav(scanRoutes(root), { isAdmin: false });
    expect(nav.map((g) => g.label)).toEqual(["사용 현황", "컨설팅"]);
    expect(nav[0].items.map((i) => i.href)).toEqual(["/overview", "/token-mix"]);
    expect(buildNav(scanRoutes(root), { isAdmin: true }).at(-1)!.items[0].href).toBe("/audit");
  });

  it("orders groups 사용 현황 / 실행 / 컨설팅", () => {
    const e = (group: any, label: string) => ({ group, label, href: "/" + label });
    expect(buildNav([e("consulting", "c"), e("run", "r"), e("usage", "u")]).map((g) => g.id)).toEqual(["usage", "run", "consulting"]);
  });

  it("rejects an unknown group", () => {
    const root = mkdtempSync(join(tmpdir(), "nav-"));
    screen(root, "x", { group: "nope", label: "x" });
    expect(() => scanRoutes(root)).toThrow();
  });
});
