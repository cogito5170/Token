"use client";
import "../../../components/components.css";
import { useEffect, useState } from "react";
import { api, type Schemas } from "../../../lib/api";
import { useWorkspaceId } from "../overview/useWorkspace";
import { TokenMixView } from "./View";
import { loadTokenMix } from "./load";

export default function Page() {
  const ws = useWorkspaceId();
  const [mode, setMode] = useState<"none" | "model">("none");
  const [set, setSet] = useState<Schemas["SeriesSet"] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    if (!ws) return;
    loadTokenMix(api(), ws, mode).then(setSet).catch((e: Error) => setErr(e.message));
  }, [ws, mode]);
  if (err) return <p role="alert">불러오지 못했습니다: {err}</p>;
  if (!set) return <p>불러오는 중…</p>;
  return <TokenMixView set={set} mode={mode} onMode={setMode} />;
}
