import { BarList } from "./BarList";
import { CostPair } from "./CostPair";
import { EvidenceDrawer } from "./EvidenceDrawer";
import { FigureCard } from "./FigureCard";
import { KanbanColumn } from "./KanbanColumn";
import { KpiTile } from "./KpiTile";
import { RangeBand } from "./RangeBand";
import { StatusChip } from "./StatusChip";

/** Static fixtures of every shared component; used by visual tests (and a route may mount it). */
export function Gallery() {
  return (
    <main className="gc-gallery">
      <section id="chips" className="gc-gal-block">
        {(["MEASURED", "CALCULATED", "ESTIMATED", "SIMULATED"] as const).map((p) => <StatusChip key={p} provenance={p} />)}
      </section>
      <section id="kpi" className="gc-gal-block">
        <KpiTile label="이번 달 토큰" value="1,234,567" unit="토큰" provenance="MEASURED" delta="+12.5%" />
        <KpiTile label="예상 비용" value={null} provenance="ESTIMATED" delta={null} />
      </section>
      <section id="range" className="gc-gal-block">
        <RangeBand kind="ESTIMATED" label="추정 범위" band={{ p10: 20, p50: 45, p90: 80 }} min={0} max={100} />
        <RangeBand kind="SIMULATED" label="가정 범위" band={{ p10: 10, p50: 30, p90: 60 }} min={0} max={100} />
      </section>
      <section id="cost" className="gc-gal-block">
        <CostPair apiListMicroUsd={1234} cliMicroUsd={900} cliCoveragePermille={875} />
        <CostPair apiListMicroUsd={12_345_678} cliMicroUsd={null} />
      </section>
      <section id="bars" className="gc-gal-block">
        <BarList label="모델별 토큰" items={[{ key: "a", label: "model-a", value: 900_000 }, { key: "b", label: "model-b", value: 450_000 }, { key: "c", label: "model-c", value: 12_000 }]} />
      </section>
      <section id="figures" className="gc-gal-block">
        <FigureCard name="노드 1" role="build" state="working" stats={[["토큰", "1,234"]]} />
        <FigureCard name="노드 2" role="test" state="waiting" />
        <FigureCard name="노드 3" role="done" state="done" />
        <FigureCard name="노드 4" role="build" state="failed" />
      </section>
      <section id="kanban" className="gc-gal-block">
        <KanbanColumn kind="queued" count={2}><FigureCard name="작업 A" role="대기" state="waiting" /></KanbanColumn>
        <KanbanColumn kind="running" count={1}><FigureCard name="작업 B" role="실행" state="working" /></KanbanColumn>
        <KanbanColumn kind="judged" count={0} />
        <KanbanColumn kind="closed" count={3} />
      </section>
      <section id="drawer" className="gc-gal-block">
        <EvidenceDrawer defaultOpen summary="근거 보기" sections={[{ title: "근거 호출", items: ["call-1 1,200 토큰", "call-2 800 토큰"] }, { title: "가정", items: ["캐시 적중률 60%"] }]} />
      </section>
    </main>
  );
}
