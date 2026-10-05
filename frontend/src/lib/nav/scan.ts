import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import type { GroupId, NavEntry, NavMeta } from "./registry";
import { GROUPS } from "./registry";

/** Server-only: walk `<appDir>/(app)` for nav.json files; route group parentheses are not part of the URL. */
export function scanRoutes(appDir: string): NavEntry[] {
  const out: NavEntry[] = [];
  const walk = (dir: string, segs: string[]) => {
    if (!existsSync(dir)) return;
    for (const name of readdirSync(dir)) {
      const p = join(dir, name);
      if (!statSync(p).isDirectory()) continue;
      const isGroup = /^\(.*\)$/.test(name);
      walk(p, isGroup ? segs : [...segs, name]);
    }
    const meta = join(dir, "nav.json");
    if (existsSync(meta)) {
      const m = JSON.parse(readFileSync(meta, "utf8")) as NavMeta;
      if (!GROUPS.some((g) => g.id === m.group)) throw new Error(`${meta}: unknown group ${m.group as GroupId}`);
      out.push({ ...m, href: "/" + segs.join("/") });
    }
  };
  walk(join(appDir, "(app)"), []);
  return out;
}
