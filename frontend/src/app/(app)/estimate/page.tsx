"use client";
import { useEffect, useState } from "react";
import { api, type Schemas } from "../../../lib/api";
import { getWorkspaceId } from "../../../lib/auth/session";
import { EstimateView } from "./EstimateView";

export default function Page() {
  const [ws, setWs] = useState<string | null>(null);
  const [result, setResult] = useState<Schemas["Estimate"] | null>(null);
  const [acc, setAcc] = useState<Schemas["Accuracy"] | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    (async () => {
      const w = getWorkspaceId() ?? (await api().get("/v1/workspaces"))[0].id;
      setWs(w);
      setAcc(await api().get("/v1/workspaces/{ws}/estimation/accuracy", { params: { ws: w } }));
    })().catch((e) => setErr(String(e.message ?? e)));
  }, []);
  return (
    <>
      {err ? <p role="alert">{err}</p> : null}
      <EstimateView result={result} accuracy={acc} busy={busy} onSubmit={async (body) => {
        if (!ws) return;
        setBusy(true); setErr(null);
        try { setResult(await api().post("/v1/workspaces/{ws}/estimates", { params: { ws }, body })); }
        catch (e) { setErr(String((e as Error).message)); }
        finally { setBusy(false); }
      }} />
    </>
  );
}
