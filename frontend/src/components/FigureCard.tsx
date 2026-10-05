export type FigureState = "idle" | "working" | "waiting" | "done" | "failed";

const STATE_KO: Record<FigureState, string> = { idle: "쉼", working: "작업 중", waiting: "대기", done: "완료", failed: "실패" };
/** State is carried by the glyph shape and the word, not by color. */
const GLYPH: Record<FigureState, string> = { idle: "○", working: "◐", waiting: "▫", done: "●", failed: "✕" };

export type FigureCardProps = {
  name: string;
  role: string;
  state: FigureState;
  /** Small pre-formatted numbers, e.g. [["토큰","1,234"]]. */
  stats?: [string, string][];
};

/** Static node summary: the monitor's figure shape and state, drawn without motion. */
export function FigureCard({ name, role, state, stats = [] }: FigureCardProps) {
  return (
    <article className="gc-figure" data-state={state}>
      <div className="gc-figure-head">
        <span className="gc-figure-glyph" aria-hidden="true">{GLYPH[state]}</span>
        <span className="gc-figure-name">{name}</span>
        <span className="gc-figure-state">{STATE_KO[state]}</span>
      </div>
      <div className="gc-figure-role">{role}</div>
      {stats.length ? (
        <dl className="gc-figure-stats">
          {stats.map(([k, v]) => (
            <div key={k}><dt>{k}</dt><dd className="num">{v}</dd></div>
          ))}
        </dl>
      ) : null}
    </article>
  );
}
