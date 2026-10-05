"use client";
import { useEffect, useState } from "react";
import { api, type Schemas } from "../../../lib/api";
import { getWorkspaceId } from "../../../lib/auth/session";
import { WhatIfView } from "./WhatIfView";

export default function Page() {
  const [ws, setWs] = useState<string | null>(null);
  const [result, setResult] = useState<Schemas["Simulation"] | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    (async () => setWs(getWorkspaceId() ?? (await api().get("/v1/workspaces"))[0].id))().catch((e) => setErr(String(e.message ?? e)));
  }, []);
  return (
    <>
      {err ? <p role="alert">{err}</p> : null}
      <WhatIfView result={result} busy={busy} onSubmit={async (assumptions) => {
        if (!ws) return;
        const to = new Date(), from = new Date(to.getTime() - 30 * 86_400_000);
        setBusy(true); setErr(null);
        try { setResult(await api().post("/v1/workspaces/{ws}/simulations", { params: { ws }, body: { assumptions, basis: { from: from.toISOString(), to: to.toISOString() } } })); }
        catch (e) { setErr(String((e as Error).message)); }
        finally { setBusy(false); }
      }} />
    </>
  );
}
