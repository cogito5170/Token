import type { ReactNode } from "react";

export type KanbanKind = "queued" | "running" | "judged" | "closed";
export const KANBAN_TITLE: Record<KanbanKind, string> = { queued: "대기", running: "실행", judged: "판정", closed: "완료/실패" };

export function KanbanColumn({ kind, count, children }: { kind: KanbanKind; count: number; children?: ReactNode }) {
  return (
    <section className="gc-kanban" data-kind={kind} aria-label={KANBAN_TITLE[kind]}>
      <h3 className="gc-kanban-title">
        {KANBAN_TITLE[kind]} <span className="gc-kanban-count num">{count}</span>
      </h3>
      <div className="gc-kanban-body">{children}</div>
    </section>
  );
}
