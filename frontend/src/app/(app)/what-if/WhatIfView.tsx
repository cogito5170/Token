import { RangeBand, StatusChip } from "../../../components";
import { formatMetric } from "../../../lib/format";
import type { Schemas } from "../../../lib/api";

export const TITLE = "구성을 이렇게 바꾸면 같은 작업의 토큰과 비용이 얼마나 달라질까?";
type Assumption = Schemas["Assumption"];
export const KINDS: Assumption["kind"][] = ["model_swap", "context_cap", "node_count", "cache_prefix_fixed", "structure"];
const show = (v: unknown) => (typeof v === "string" ? v : JSON.stringify(v));

export function AssumptionList({ items }: { items: Assumption[] }) {
  return (
    <ol className="gc-assumptions" aria-label="가정 목록">
      {items.map((a, i) => (
        <li key={i} data-kind={a.kind}><code>{a.kind}</code>{a.from !== undefined ? <span> {show(a.from)} → </span> : <span> → </span>}<span className="num">{show(a.value)}</span></li>
      ))}
    </ol>
  );
}

export function SimulationResult({ s }: { s: Schemas["Simulation"] }) {
  const keys = Object.keys(s.result.simulated);
  return (
    <section aria-label="시뮬레이션 결과" data-provenance="SIMULATED">
      <p><StatusChip provenance="SIMULATED" /> 아래 값은 측정이 아니라 다음 가정에서 계산한 시뮬레이션이다.</p>
      <h2>가정</h2>
      <AssumptionList items={s.assumptions} />
      <p className="num">근거: 호출 {s.basis.calls} · 작업 {s.basis.tasks} · 가격표 v{s.basis.price_version}</p>
      {keys.map((k) => {
        const sim = s.result.simulated[k];
        const base = s.result.baseline[k];
        const fmt = (n: number) => formatMetric({ value: n, unit: sim.unit });
        return (
          <div key={k} data-metric={k}>
            <h3>{k}</h3>
            {base ? <p className="num">현재 {formatMetric(base)} <StatusChip provenance={base.provenance} /></p> : null}
            <RangeBand band={sim} min={0} max={Math.max(sim.p90, base?.value ?? 0, 1)} kind="SIMULATED" label={`${k} 시뮬레이션 P10–P90`} format={fmt} />
          </div>
        );
      })}
    </section>
  );
}

export function WhatIfForm({ onSubmit, busy }: { onSubmit: (a: Assumption[]) => void; busy?: boolean }) {
  return (
    <form className="gc-form" onSubmit={(ev) => {
      ev.preventDefault();
      const d = new FormData(ev.currentTarget);
      const kind = String(d.get("kind")) as Assumption["kind"];
      const raw = String(d.get("value") ?? "");
      const num = Number(raw);
      onSubmit([{ kind, value: raw !== "" && Number.isFinite(num) ? num : raw }]);
    }}>
      <label>가정 <select name="kind">{KINDS.map((k) => <option key={k}>{k}</option>)}</select></label>
      <label>값 <input name="value" required /></label>
      <button type="submit" disabled={busy}>시뮬레이션</button>
    </form>
  );
}

export function WhatIfView({ result, onSubmit, busy }: { result?: Schemas["Simulation"] | null; onSubmit: (a: Assumption[]) => void; busy?: boolean }) {
  return (
    <main className="gc-screen" data-screen="what_if">
      <h1>{TITLE}</h1>
      <WhatIfForm onSubmit={onSubmit} busy={busy} />
      {result ? <SimulationResult s={result} /> : null}
    </main>
  );
}
