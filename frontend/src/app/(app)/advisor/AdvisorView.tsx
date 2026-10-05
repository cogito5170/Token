import { StatusChip } from "../../../components";
import { formatMetric } from "../../../lib/format";
import type { Schemas } from "../../../lib/api";

export const TITLE = "어떤 호출 패턴에서 토큰을 얼마나 아낄 수 있고, 그 제안을 적용해도 되는가?";
type Proposal = Schemas["Proposal"];

/** Apply needs an explicit confirm step; anything else cannot send `apply`. */
export async function decideProposal(
  post: (body: Schemas["ProposalDecision"]) => Promise<Proposal>,
  decision: Schemas["ProposalDecision"]["decision"],
  confirmed: boolean,
  note?: string,
): Promise<Proposal> {
  if (decision === "apply" && !confirmed) throw new Error("apply requires confirm");
  return post({ decision, ...(decision === "apply" ? { confirm: true } : {}), ...(note ? { note } : {}) });
}

export function FindingsList({ findings }: { findings: Schemas["Finding"][] }) {
  if (!findings.length) return <p className="gc-empty">진단 결과가 없다.</p>;
  return (
    <ul className="gc-findings">
      {findings.map((f) => (
        <li key={f.id} data-rule={f.rule_id}>
          <strong>{f.rule_id}</strong> <StatusChip provenance="ESTIMATED" />{" "}
          <span className="num">절감 {formatMetric({ value: f.savings.p50, unit: f.savings.unit })} (P10–P90 {formatMetric({ value: f.savings.p10, unit: f.savings.unit })} – {formatMetric({ value: f.savings.p90, unit: f.savings.unit })}) · 토큰 {formatMetric(f.savings_tokens)} · 근거 호출 {f.evidence_call_ids.length} 건</span>
        </li>
      ))}
    </ul>
  );
}

export function ConfirmDialog({ proposal, onConfirm, onCancel }: { proposal: Proposal; onConfirm: () => void; onCancel: () => void }) {
  return (
    <div role="dialog" aria-modal="true" aria-labelledby="gc-confirm-title" className="gc-dialog" data-proposal={proposal.id}>
      <h2 id="gc-confirm-title">적용 확인</h2>
      <p>이 제안({proposal.kind})을 실제로 적용한다. 되돌리려면 별도 변경이 필요하다.</p>
      {proposal.expected_savings ? <p className="num">예상 절감 {formatMetric(proposal.expected_savings)} <StatusChip provenance="ESTIMATED" /></p> : null}
      <button type="button" data-action="confirm-apply" onClick={onConfirm}>확인하고 적용</button>
      <button type="button" data-action="cancel" onClick={onCancel}>취소</button>
    </div>
  );
}

export function ProposalsList({ proposals, confirmId, onDecide, onAskApply, onConfirm, onCancel }: {
  proposals: Proposal[]; confirmId?: string | null;
  onDecide?: (p: Proposal, d: "accept" | "reject") => void;
  onAskApply?: (p: Proposal) => void; onConfirm?: (p: Proposal) => void; onCancel?: () => void;
}) {
  const confirming = proposals.find((p) => p.id === confirmId);
  return (
    <section aria-label="제안">
      {proposals.length === 0 ? <p className="gc-empty">제안이 없다.</p> : (
        <ul className="gc-proposals">
          {proposals.map((p) => (
            <li key={p.id} data-state={p.state}>
              <strong>{p.kind}</strong> · <span>{p.state}</span>
              {p.blocked_reason ? <span> ({p.blocked_reason})</span> : null}
              {p.expected_savings ? <span className="num"> · 예상 절감 {formatMetric(p.expected_savings)}</span> : null}
              {p.state === "proposed" ? (
                <>
                  <button type="button" data-action="accept" onClick={() => onDecide?.(p, "accept")}>수락</button>
                  <button type="button" data-action="reject" onClick={() => onDecide?.(p, "reject")}>거절</button>
                </>
              ) : null}
              {p.state === "accepted" ? <button type="button" data-action="apply" onClick={() => onAskApply?.(p)}>적용…</button> : null}
            </li>
          ))}
        </ul>
      )}
      {confirming ? <ConfirmDialog proposal={confirming} onConfirm={() => onConfirm?.(confirming)} onCancel={() => onCancel?.()} /> : null}
    </section>
  );
}

export function AdvisorView(props: { findings: Schemas["Finding"][] } & Parameters<typeof ProposalsList>[0]) {
  return (
    <main className="gc-screen" data-screen="advisor">
      <h1>{TITLE}</h1>
      <FindingsList findings={props.findings} />
      <ProposalsList {...props} />
    </main>
  );
}
