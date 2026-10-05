"use client";
import { useEffect, useState } from "react";
import { api, type Schemas } from "../../../lib/api";
import { getWorkspaceId } from "../../../lib/auth/session";
import { CompareView } from "./CompareView";

export default function Page() {
  const [data, setData] = useState<Schemas["Comparison"] | null>(null);
  const [rec, setRec] = useState<Schemas["Recommendation"][]>([]);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    (async () => {
      const ws = getWorkspaceId() ?? (await api().get("/v1/workspaces"))[0].id;
      setData(await api().get("/v1/workspaces/{ws}/usage/compare", { params: { ws }, query: { dims: "structure,model,context_mode" } }));
      setRec(await api().get("/v1/workspaces/{ws}/profile/recommendations", { params: { ws } }).catch(() => []));
    })().catch((e) => setErr(String(e.message ?? e)));
  }, []);
  if (err) return <p role="alert">{err}</p>;
  return data ? <CompareView data={data} recommendations={rec} /> : <p>불러오는 중…</p>;
}
