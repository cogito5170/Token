"use client";
import "../../../components/components.css";
import { useEffect, useState } from "react";
import { api } from "../../../lib/api";
import { OverviewView } from "./View";
import { loadOverview, type OverviewData } from "./load";
import { useWorkspaceId } from "./useWorkspace";

export default function Page() {
  const ws = useWorkspaceId();
  const [data, setData] = useState<OverviewData | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    if (!ws) return;
    loadOverview(api(), ws).then(setData).catch((e: Error) => setErr(e.message));
  }, [ws]);
  if (err) return <p role="alert">불러오지 못했습니다: {err}</p>;
  if (!data) return <p>불러오는 중…</p>;
  return <OverviewView data={data} />;
}
