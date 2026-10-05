import { StatusChip, BarList } from "../../../components";
import { formatMetric } from "../../../lib/format";
import type { Schemas } from "../../../lib/api";

export const TITLE = "구조(A/B/C) · 모델 · 문맥 방식 중 어느 구성이 맞힌 작업당 토큰 · 비용이 가장 낮고 정답률은 어떤가?";

type Range = Schemas["Range"];
const fmt = (r: Range) => formatMetric({ value: r.p50, unit: r.unit });
const span = (r: Range) => `${formatMetric({ value: r.p10, unit: r.unit })} – ${formatMetric({ value: r.p90, unit: r.unit })}`;
const keyLabel = (k: Record<string, string>) => Object.values(k).join(" · ");

export function CompareView({ data, recommendations = [] }: { data: Schemas["Comparison"]; recommendations?: Schemas["Recommendation"][] }) {
  return (
    <main className="gc-screen" data-screen="config_compare">
      <h1>{TITLE}</h1>
      {recommendations.map((r) => (
        <aside key={r.id} className="gc-banner" data-provenance="ESTIMATED" role="note">
          <StatusChip provenance="ESTIMATED" /> <strong>{r.headline}</strong>{" "}
          <span className="num">근거 {r.evidence_n} 건 · 절감 {formatMetric(r.saving)}</span>
        </aside>
      ))}
      <p>범위(P10–P90)는 작업 간 분포이며 추정이 아니다. <StatusChip provenance="CALCULATED" /></p>
      {data.groups.length === 0 ? <p className="gc-empty">비교할 데이터가 없다.</p> : (
        <>
          <BarList label="맞힌 작업당 비용 (list, P50)" items={data.groups.map((g) => ({ key: keyLabel(g.key), label: keyLabel(g.key), value: g.cost_list_per_correct.p50 }))} format={(n) => formatMetric({ value: n, unit: "microusd" })} />
          <table className="gc-table num">
            <thead>
              <tr><th>구성 ({data.dims.join(" · ")})</th><th>작업</th><th>정답</th><th>정답률</th><th>토큰/정답 P50 (P10–P90)</th><th>비용 list/정답</th><th>비용 cli/정답</th></tr>
            </thead>
            <tbody>
              {data.groups.map((g) => (
                <tr key={keyLabel(g.key)}>
                  <td>{keyLabel(g.key)}</td><td>{g.tasks}</td><td>{g.correct}</td>
                  <td>{g.accuracy ? formatMetric(g.accuracy) : "—"}</td>
                  <td>{fmt(g.tokens_per_correct)} ({span(g.tokens_per_correct)})</td>
                  <td>{fmt(g.cost_list_per_correct)} ({span(g.cost_list_per_correct)})</td>
                  <td>{g.cost_cli_per_correct ? `${fmt(g.cost_cli_per_correct)} (${span(g.cost_cli_per_correct)})` : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </main>
  );
}
