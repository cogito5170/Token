import type { Schemas } from "../../../lib/api";
import { StatusChip } from "../../../components";
import { formatPermille } from "../../../lib/format";
import { EChart } from "../overview/EChart";
import { MIX, MIX_LABEL, byModel, mixShares } from "./load";
import { mixOption } from "./options";

export function TokenMixView({ set, mode, onMode }: { set: Schemas["SeriesSet"]; mode: "none" | "model"; onMode: (m: "none" | "model") => void }) {
  const shares = mixShares(set);
  const prov = set.series[0]?.provenance ?? "MEASURED";
  return (
    <div className="gc-screen">
      <h1>토큰 구성</h1>
      <div className="gc-mixshares">
        {MIX.map((k) => <span key={k} className="num">{MIX_LABEL[k]} {formatPermille(shares[k])}</span>)}
        <StatusChip provenance={prov} />
      </div>
      <div role="group" aria-label="보기 전환">
        <button type="button" aria-pressed={mode === "none"} onClick={() => onMode("none")}>전체</button>
        <button type="button" aria-pressed={mode === "model"} onClick={() => onMode("model")}>모델별</button>
      </div>
      {mode === "model" ? (
        <div className="gc-multiples">
          {[...byModel(set)].map(([model, s]) => (
            <EChart key={model} label={`${model || "전체"} 토큰 구성`} height={200} option={mixOption(s, model || "전체")} />
          ))}
        </div>
      ) : (
        <EChart label="토큰 구성 누적 영역 차트" option={mixOption(set.series)} />
      )}
    </div>
  );
}
