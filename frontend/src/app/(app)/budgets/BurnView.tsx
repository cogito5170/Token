import { StatusChip } from "../../../components";
import { formatMicroUsd } from "../../../lib/format";
import type { Schemas } from "../../../lib/api";

export const TITLE = "예산 대비 누적 사용이 어디까지 왔고, 언제 상한에 닿을 것인가?";
const W = 640, H = 240, PAD = 8;

export function BurnView({ burn, thresholds = [50, 80, 100] }: { burn: Schemas["BurnSeries"]; thresholds?: number[] }) {
  const { limit_microusd: limit, cumulative, projection } = burn;
  const all = [cumulative.list, cumulative.cli, projection.p10, projection.p50, projection.p90];
  const days = [...new Set(all.flatMap((s) => s.points.map((p) => p[0])))].sort();
  const x = (d: string) => PAD + (days.length < 2 ? 0 : (days.indexOf(d) / (days.length - 1)) * (W - 2 * PAD));
  const maxV = Math.max(limit, ...all.flatMap((s) => s.points.map((p) => p[1] ?? 0)));
  const y = (v: number) => H - PAD - (v / Math.max(1, maxV)) * (H - 2 * PAD);
  const line = (s: Schemas["Series"]) => s.points.filter((p) => p[1] !== null).map((p) => `${x(p[0])},${y(p[1] as number)}`).join(" ");
  const bandPts = [...projection.p90.points.filter((p) => p[1] !== null).map((p) => `${x(p[0])},${y(p[1] as number)}`),
    ...[...projection.p10.points].reverse().filter((p) => p[1] !== null).map((p) => `${x(p[0])},${y(p[1] as number)}`)].join(" ");
  const exhaust = (v?: string | null) => (v ? v.slice(0, 10) : "—");
  return (
    <main className="gc-screen" data-screen="budget_burn">
      <h1>{TITLE}</h1>
      <p className="num">상한 {formatMicroUsd(limit)}</p>
      <svg role="img" aria-label="누적 사용과 예측" viewBox={`0 0 ${W} ${H}`} width="100%">
        <polygon data-series="projection-band" data-provenance="ESTIMATED" points={bandPts} fill="currentColor" opacity="0.25" />
        <line data-series="limit" x1={PAD} x2={W - PAD} y1={y(limit)} y2={y(limit)} stroke="currentColor" strokeWidth="2" />
        {thresholds.map((t) => (
          <g key={t} data-threshold={t}>
            <line x1={PAD} x2={W - PAD} y1={y((limit * t) / 100)} y2={y((limit * t) / 100)} stroke="currentColor" strokeWidth="1" strokeDasharray="1 4" />
            <text x={W - PAD} y={y((limit * t) / 100) - 2} textAnchor="end" fontSize="10">{t}%</text>
          </g>
        ))}
        <polyline data-series="cumulative-list" data-provenance="CALCULATED" points={line(cumulative.list)} fill="none" stroke="currentColor" strokeWidth="2" />
        <polyline data-series="cumulative-cli" data-provenance="MEASURED" points={line(cumulative.cli)} fill="none" stroke="currentColor" strokeWidth="2" strokeDasharray="8 2 2 2" />
        <polyline data-series="projection-p50" data-provenance="ESTIMATED" points={line(projection.p50)} fill="none" stroke="currentColor" strokeWidth="2" strokeDasharray="6 4" />
      </svg>
      <ul className="gc-legend">
        <li>누적 list <StatusChip provenance="CALCULATED" /></li>
        <li>누적 cli <StatusChip provenance="MEASURED" /></li>
        <li>예측 P50 · P10–P90 띠 <StatusChip provenance="ESTIMATED" /></li>
      </ul>
      <dl className="num">
        <dt>상한 도달 예상 (P50)</dt><dd>{exhaust(projection.exhaust_at_p50)}</dd>
        <dt>빠른 경우 (P10)</dt><dd>{exhaust(projection.exhaust_at_p10)}</dd>
        <dt>늦은 경우 (P90)</dt><dd>{exhaust(projection.exhaust_at_p90)}</dd>
      </dl>
    </main>
  );
}
