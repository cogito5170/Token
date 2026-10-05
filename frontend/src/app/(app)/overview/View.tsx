import { CostPair, KpiTile, StatusChip } from "../../../components";
import { formatMetric } from "../../../lib/format";
import { budgetUsePermille, type OverviewData } from "./load";
import { EChart } from "./EChart";
import { trendOption } from "./trend";

export function OverviewView({ data }: { data: OverviewData }) {
  const t = data.summary.tiles;
  const budget = budgetUsePermille(data);
  return (
    <div className="gc-screen">
      <h1>개요</h1>
      <p className="gc-period num">{data.summary.period.from} ~ {data.summary.period.to}</p>
      <div className="gc-tiles">
        <KpiTile label="총 토큰" value={formatMetric(t.total_tokens)} unit="토큰" provenance={t.total_tokens.provenance} />
        <section className="gc-kpi" aria-label="비용">
          <div className="gc-kpi-label">비용 <StatusChip provenance={t.cost_list.provenance} /> <StatusChip provenance={t.cost_cli.provenance} /></div>
          <CostPair apiListMicroUsd={t.cost_list.value} cliMicroUsd={t.cost_cli.value} cliCoveragePermille={t.cost_cli.coverage_permille} />
        </section>
        <KpiTile label="맞힌 작업 수" value={formatMetric(t.correct_tasks)} unit="건" provenance={t.correct_tasks.provenance} />
        <section className="gc-kpi" aria-label="맞힌 작업당 비용">
          <div className="gc-kpi-label">맞힌 작업당 비용 <StatusChip provenance={t.cost_list_per_correct.provenance} /></div>
          <CostPair apiListMicroUsd={t.cost_list_per_correct.value} cliMicroUsd={t.cost_cli_per_correct.value} cliCoveragePermille={t.cost_cli_per_correct.coverage_permille ?? t.cost_cli.coverage_permille} />
        </section>
        <KpiTile label="예산 사용률" value={formatMetric({ value: budget.value, unit: "permille" })} provenance={budget.provenance} />
      </div>
      <section aria-label="일별 추세">
        <h2>{data.summary.trend.bucket === "day" ? "일별 추세" : "추세"}</h2>
        <EChart label="토큰과 비용(정가, CLI) 추세선" option={trendOption(data.summary.trend.series)} />
      </section>
    </div>
  );
}
