import { RangeBand, StatusChip } from "../../../components";
import { formatMetric, formatPermille } from "../../../lib/format";
import type { Schemas } from "../../../lib/api";

export const TITLE = "이 작업은 토큰과 비용이 얼마나 들 것으로 추정되고, 그 견적은 얼마나 맞아 왔는가?";
type Range = Schemas["Range"];
const f = (r: Range) => (n: number) => formatMetric({ value: n, unit: r.unit });

function Row({ label, r }: { label: string; r: Range }) {
  const hi = Math.max(r.p90, 1);
  return (
    <li>
      <span>{label}</span> <StatusChip provenance="ESTIMATED" />
      <RangeBand band={r} min={0} max={hi} kind="ESTIMATED" label={`${label} P10–P90`} format={f(r)} />
    </li>
  );
}

export function EstimateResult({ e }: { e: Schemas["Estimate"] }) {
  return (
    <section aria-label="견적 결과" data-provenance="ESTIMATED">
      <ul className="gc-estimate">
        <Row label="입력 토큰" r={e.input_tokens} />
        <Row label="캐시 토큰" r={e.cache_tokens} />
        <Row label="출력 토큰" r={e.output_tokens} />
        <Row label="비용 (list)" r={e.cost_list} />
        {e.cost_cli ? <Row label="비용 (cli)" r={e.cost_cli} /> : null}
        <Row label="호출 수" r={e.calls} />
      </ul>
      <p className="num">성공 확률 {formatMetric(e.success_prob)} <StatusChip provenance="ESTIMATED" /></p>
      <p className="num">근거 {e.evidence.n} 건{e.evidence.basis ? ` (${e.evidence.basis})` : ""} · 견적기 v{e.estimator.version} · 최근 MAPE {e.estimator.mape_permille === null ? "—" : formatPermille(e.estimator.mape_permille)}</p>
    </section>
  );
}

export function AccuracyPanel({ a }: { a: Schemas["Accuracy"] }) {
  return (
    <section aria-label="자체 측정 MAPE" data-testid="self-mape">
      <h2>이 견적기의 자체 측정 정확도</h2>
      <dl className="num">
        <dt>표본</dt><dd>{a.n} 건</dd>
        <dt>토큰 MAPE</dt><dd>{formatMetric(a.mape_tokens)}</dd>
        <dt>비용 MAPE</dt><dd>{formatMetric(a.mape_cost)}</dd>
        <dt>P10–P90 포함률</dt><dd>{formatMetric(a.coverage_p10_p90)}</dd>
      </dl>
    </section>
  );
}

export function EstimateForm({ onSubmit, busy }: { onSubmit: (r: Schemas["EstimateRequest"]) => void; busy?: boolean }) {
  return (
    <form className="gc-form" onSubmit={(ev) => {
      ev.preventDefault();
      const d = new FormData(ev.currentTarget);
      const loc = String(d.get("repo_size_loc") ?? "");
      onSubmit({
        description: String(d.get("description") ?? ""),
        task_kind: String(d.get("task_kind")) as Schemas["EstimateRequest"]["task_kind"],
        model: String(d.get("model") ?? ""),
        ...(loc ? { repo_size_loc: Number(loc) } : {}),
      });
    }}>
      <label>작업 설명 <textarea name="description" required /></label>
      <label>종류 <select name="task_kind" defaultValue="feature">{["feature", "bug", "refactor", "docs", "other"].map((k) => <option key={k}>{k}</option>)}</select></label>
      <label>모델 <input name="model" required /></label>
      <label>저장소 크기 (LOC) <input name="repo_size_loc" type="number" min={0} step={1} /></label>
      <button type="submit" disabled={busy}>견적 내기</button>
    </form>
  );
}

export function EstimateView({ result, accuracy, onSubmit, busy }: { result?: Schemas["Estimate"] | null; accuracy?: Schemas["Accuracy"] | null; onSubmit: (r: Schemas["EstimateRequest"]) => void; busy?: boolean }) {
  return (
    <main className="gc-screen" data-screen="estimate">
      <h1>{TITLE}</h1>
      <EstimateForm onSubmit={onSubmit} busy={busy} />
      {result ? <EstimateResult e={result} /> : null}
      {accuracy ? <AccuracyPanel a={accuracy} /> : null}
    </main>
  );
}
