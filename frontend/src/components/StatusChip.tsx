import type { Provenance } from "./types";

/** Label text from design/tokens.json provenance.label_ko; shape (border style), never color, tells them apart. */
const LABEL: Record<Provenance, string> = {
  MEASURED: "측정",
  CALCULATED: "계산",
  ESTIMATED: "추정",
  SIMULATED: "가정",
};
const SHAPE: Record<Provenance, string> = {
  MEASURED: "solid",
  CALCULATED: "outlined",
  ESTIMATED: "dashed",
  SIMULATED: "dotted",
};

export function StatusChip({ provenance }: { provenance: Provenance }) {
  return (
    <span className="gc-chip num" data-provenance={provenance} data-shape={SHAPE[provenance]}>
      {LABEL[provenance]}
    </span>
  );
}
