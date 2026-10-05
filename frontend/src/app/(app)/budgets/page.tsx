"use client";
import { useEffect, useState } from "react";
import { api, type Schemas } from "../../../lib/api";
import { getWorkspaceId } from "../../../lib/auth/session";
import { BurnView } from "./BurnView";

export default function Page() {
  const [burn, setBurn] = useState<Schemas["BurnSeries"] | null>(null);
  const [thr, setThr] = useState<number[] | undefined>();
  const [empty, setEmpty] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    (async () => {
      const ws = getWorkspaceId() ?? (await api().get("/v1/workspaces"))[0].id;
      const budgets = await api().get("/v1/workspaces/{ws}/budgets", { params: { ws } });
      if (!budgets.length) return setEmpty(true);
      setThr(budgets[0].thresholds);
      setBurn(await api().get("/v1/workspaces/{ws}/budgets/{budget}/burn", { params: { ws, budget: budgets[0].id } }));
    })().catch((e) => setErr(String(e.message ?? e)));
  }, []);
  if (err) return <p role="alert">{err}</p>;
  if (empty) return <p>설정된 예산이 없다.</p>;
  return burn ? <BurnView burn={burn} thresholds={thr} /> : <p>불러오는 중…</p>;
}
