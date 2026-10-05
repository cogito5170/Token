// File-system route registry: a screen declares itself by placing `nav.json` next to its page.tsx
//   src/app/(app)/<route>/nav.json  ->  {"group":"usage","label":"개요","order":10}
// so adding a screen never edits a shared nav file.
export const GROUPS = [
  { id: "usage", label: "사용 현황" },
  { id: "run", label: "실행" },
  { id: "consulting", label: "컨설팅" },
  { id: "footer", label: "" },
] as const;
export type GroupId = (typeof GROUPS)[number]["id"];

export interface NavMeta { group: GroupId; label: string; order?: number; adminOnly?: boolean; later?: boolean }
export interface NavEntry extends NavMeta { href: string }
export interface NavGroup { id: GroupId; label: string; items: NavEntry[] }

export function buildNav(entries: NavEntry[], opts: { isAdmin?: boolean } = {}): NavGroup[] {
  return GROUPS.map((g) => ({
    id: g.id,
    label: g.label,
    items: entries
      .filter((e) => e.group === g.id && (!e.adminOnly || opts.isAdmin))
      .sort((a, b) => (a.order ?? 100) - (b.order ?? 100) || a.label.localeCompare(b.label, "ko")),
  })).filter((g) => g.items.length > 0);
}
