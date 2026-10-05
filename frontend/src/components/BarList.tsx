import { formatTokens } from "../lib/format";

export type BarItem = { key: string; label: string; value: number };

/** Ranked bars with numbers. Order is the caller's (fixed); bars scale to the largest value. */
export function BarList({ items, format = formatTokens, label }: { items: BarItem[]; format?: (n: number) => string; label: string }) {
  const max = Math.max(1, ...items.map((i) => i.value));
  return (
    <ol className="gc-barlist" aria-label={label}>
      {items.map((i) => (
        <li key={i.key} className="gc-bar">
          <span className="gc-bar-label">{i.label}</span>
          <span className="gc-bar-track" aria-hidden="true">
            <span className="gc-bar-fill" style={{ width: `${(i.value / max) * 100}%` }} />
          </span>
          <span className="gc-bar-value num">{format(i.value)}</span>
        </li>
      ))}
    </ol>
  );
}
