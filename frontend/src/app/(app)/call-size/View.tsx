import type { Schemas } from "../../../lib/api";
import { StatusChip } from "../../../components";
import { EM_DASH, formatCount, formatMicroUsd, formatTokens, formatTokensCompact } from "../../../lib/format";
import { EChart } from "../overview/EChart";
import { binPercentile } from "./load";
import { histOption } from "./options";

export function CallSizeView({ hist, calls, onOpenOutliers }: {
  hist: Schemas["Histogram"];
  calls: Schemas["CallPage"] | null;
  onOpenOutliers: () => void;
}) {
  const med = binPercentile(hist.bins, 500), p90 = binPercentile(hist.bins, 900);
  return (
    <div className="gc-screen">
      <h1>호출 크기</h1>
      <div className="gc-mixshares">
        <span className="num">중앙값 {formatTokensCompact(med)}</span>
        <span className="num">P90 {formatTokensCompact(p90)}</span>
        <span className="num">{formatTokensCompact(hist.threshold)} 초과 호출 {formatCount(hist.outliers.length)} 건</span>
        <StatusChip provenance={hist.provenance} />
      </div>
      <EChart label="호출 문맥 크기 히스토그램 (log2 구간)" option={histOption(hist)} onClick={(p) => { if (p.seriesName === "이상치") onOpenOutliers(); }} />
      <details onToggle={(e) => { if ((e.target as HTMLDetailsElement).open) onOpenOutliers(); }}>
        <summary>이상치 호출 목록</summary>
        {calls ? (
          <table>
            <thead><tr><th>호출</th><th>모델</th><th>문맥 토큰</th><th>정가 환산</th><th>CLI 비용</th></tr></thead>
            <tbody>
              {calls.items.map((c) => (
                <tr key={c.id}>
                  <td className="num">{c.id}</td><td>{c.model_id}</td>
                  <td className="num">{formatTokens(c.context_tokens)}</td>
                  <td className="num">{formatMicroUsd(c.cost_list_microusd)}</td>
                  <td className="num">{c.cost_cli_microusd == null ? EM_DASH : formatMicroUsd(c.cost_cli_microusd)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : <p>목록을 열면 불러옵니다.</p>}
      </details>
    </div>
  );
}
