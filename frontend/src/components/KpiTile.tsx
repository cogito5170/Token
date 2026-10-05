import { EM_DASH } from "../lib/format";
import { StatusChip } from "./StatusChip";
import type { Provenance } from "./types";

export type KpiTileProps = {
  label: string;
  value: string | null;
  unit?: string;
  provenance: Provenance;
  /** Pre-formatted change versus the previous period, e.g. "+12.5%". */
  delta?: string | null;
};

export function KpiTile({ label, value, unit, provenance, delta }: KpiTileProps) {
  return (
    <section className="gc-kpi" aria-label={label}>
      <div className="gc-kpi-label">{label}</div>
      <div className="gc-kpi-row">
        <span className="gc-kpi-value num">{value ?? EM_DASH}</span>
        {unit ? <span className="gc-kpi-unit">{unit}</span> : null}
        <StatusChip provenance={provenance} />
      </div>
      {delta !== undefined ? <div className="gc-kpi-delta num">직전 기간 대비 {delta ?? EM_DASH}</div> : null}
    </section>
  );
}
