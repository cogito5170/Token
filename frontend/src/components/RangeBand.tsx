import type { Band } from "./types";

export type RangeBandProps = {
  band: Band;
  /** Axis domain the band is drawn on. */
  min: number;
  max: number;
  kind: "ESTIMATED" | "SIMULATED";
  label: string;
  format?: (n: number) => string;
};

/** P10–P90 band with a P50 mark. Edge style is dashed (ESTIMATED) or dotted (SIMULATED). */
export function RangeBand({ band, min, max, kind, label, format = String }: RangeBandProps) {
  const span = Math.max(1, max - min);
  const pct = (n: number) => Math.min(100, Math.max(0, ((n - min) / span) * 100));
  const l = pct(band.p10);
  const r = pct(band.p90);
  return (
    <figure className="gc-band" data-kind={kind} aria-label={label}>
      <div className="gc-band-track">
        <div className="gc-band-fill" style={{ left: `${l}%`, width: `${r - l}%` }} />
        <div className="gc-band-p50" style={{ left: `${pct(band.p50)}%` }} />
      </div>
      <figcaption className="gc-band-cap num">
        P10 {format(band.p10)} · P50 {format(band.p50)} · P90 {format(band.p90)}
      </figcaption>
    </figure>
  );
}
