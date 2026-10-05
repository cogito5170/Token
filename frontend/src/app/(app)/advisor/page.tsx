"use client";
import { useCallback, useEffect, useState } from "react";
import { api, type Schemas } from "../../../lib/api";
import { getWorkspaceId } from "../../../lib/auth/session";
import { AdvisorView, decideProposal } from "./AdvisorView";

export default function Page() {
  const [ws, setWs] = useState<string | null>(null);
  const [findings, setFindings] = useState<Schemas["Finding"][]>([]);
  const [proposals, setProposals] = useState<Schemas["Proposal"][]>([]);
  const [confirmId, setConfirmId] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const load = useCallback(async (w: string) => {
    setFindings(await api().get("/v1/workspaces/{ws}/advisor/findings", { params: { ws: w } }));
    setProposals(await api().get("/v1/workspaces/{ws}/proposals", { params: { ws: w } }));
  }, []);
  useEffect(() => {
    (async () => {
      const w = getWorkspaceId() ?? (await api().get("/v1/workspaces"))[0].id;
      setWs(w);
      await load(w);
    })().catch((e) => setErr(String(e.message ?? e)));
  }, [load]);
  const decide = async (p: Schemas["Proposal"], d: "accept" | "reject" | "apply", confirmed = false) => {
    if (!ws) return;
    try {
      await decideProposal((body) => api().post("/v1/workspaces/{ws}/proposals/{proposal}/decision", { params: { ws, proposal: p.id }, body }), d, confirmed);
      setConfirmId(null);
      await load(ws);
    } catch (e) { setErr(String((e as Error).message)); }
  };
  return (
    <>
      {err ? <p role="alert">{err}</p> : null}
      <AdvisorView findings={findings} proposals={proposals} confirmId={confirmId}
        onDecide={(p, d) => decide(p, d)} onAskApply={(p) => setConfirmId(p.id)}
        onConfirm={(p) => decide(p, "apply", true)} onCancel={() => setConfirmId(null)} />
    </>
  );
}
