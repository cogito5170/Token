import type { ReactNode } from "react";

export type EvidenceSection = { title: string; items: string[] };

/** Evidence one click away: collapsed by default, native <details> keeps keyboard operation. */
export function EvidenceDrawer({ summary, sections, defaultOpen = false, children }: { summary: string; sections: EvidenceSection[]; defaultOpen?: boolean; children?: ReactNode }) {
  return (
    <details className="gc-drawer" open={defaultOpen}>
      <summary className="gc-drawer-summary">{summary}</summary>
      <div className="gc-drawer-body">
        {sections.map((s) => (
          <div key={s.title} className="gc-drawer-section">
            <h4>{s.title}</h4>
            <ul>{s.items.map((i) => <li key={i} className="num">{i}</li>)}</ul>
          </div>
        ))}
        {children}
      </div>
    </details>
  );
}
