"use client";
import "../../../components/components.css";
import { useEffect, useState } from "react";
import { api, type Schemas } from "../../../lib/api";
import { useWorkspaceId } from "../overview/useWorkspace";
import { CallSizeView } from "./View";
import { loadCallSize, loadOutlierCalls } from "./load";

export default function Page() {
  const ws = useWorkspaceId();
  const [hist, setHist] = useState<Schemas["Histogram"] | null>(null);
  const [calls, setCalls] = useState<Schemas["CallPage"] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    if (!ws) return;
    loadCallSize(api(), ws).then(setHist).catch((e: Error) => setErr(e.message));
  }, [ws]);
  if (err) return <p role="alert">불러오지 못했습니다: {err}</p>;
  if (!hist || !ws) return <p>불러오는 중…</p>;
  const open = () => { if (!calls) loadOutlierCalls(api(), ws, hist.threshold).then(setCalls).catch((e: Error) => setErr(e.message)); };
  return <CallSizeView hist={hist} calls={calls} onOpenOutliers={open} />;
}
