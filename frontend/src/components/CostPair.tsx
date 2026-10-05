import { formatMicroUsd, formatPermille } from "../lib/format";

export type CostPairProps = {
  apiListMicroUsd: number | null;
  cliMicroUsd: number | null;
  /** CLI coverage in permille (0..1000); a "부분 n%" chip shows below 1000. */
  cliCoveragePermille?: number | null;
};

/** The two cost measures always side by side; unknown is an em dash. */
export function CostPair({ apiListMicroUsd, cliMicroUsd, cliCoveragePermille }: CostPairProps) {
  const partial = cliCoveragePermille !== undefined && cliCoveragePermille !== null && cliCoveragePermille < 1000;
  return (
    <div className="gc-costpair">
      <div className="gc-cost">
        <span className="gc-cost-label">API 정가 환산</span>
        <span className="gc-cost-value num">{formatMicroUsd(apiListMicroUsd)}</span>
      </div>
      <div className="gc-cost">
        <span className="gc-cost-label">CLI 비용</span>
        <span className="gc-cost-value num">{formatMicroUsd(cliMicroUsd)}</span>
        {partial ? <span className="gc-chip num" data-shape="outlined">부분 {formatPermille(cliCoveragePermille)}</span> : null}
      </div>
    </div>
  );
}
