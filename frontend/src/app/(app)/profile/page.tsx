"use client";
import { useEffect, useState } from "react";
import { api, type Schemas } from "../../../lib/api";
import { getWorkspaceId } from "../../../lib/auth/session";
import { ProfileView } from "./ProfileView";

export default function Page() {
  const [ws, setWs] = useState<string | null>(null);
  const [profile, setProfile] = useState<Schemas["Profile"] | null>(null);
  const [stats, setStats] = useState<Schemas["PersonalStat"][]>([]);
  const [rec, setRec] = useState<Schemas["Recommendation"][]>([]);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    (async () => {
      const w = getWorkspaceId() ?? (await api().get("/v1/workspaces"))[0].id;
      setWs(w);
      setProfile(await api().get("/v1/workspaces/{ws}/profile", { params: { ws: w } }));
      setStats(await api().get("/v1/workspaces/{ws}/profile/stats", { params: { ws: w } }));
      setRec(await api().get("/v1/workspaces/{ws}/profile/recommendations", { params: { ws: w } }));
    })().catch((e) => setErr(String(e.message ?? e)));
  }, []);
  if (err) return <p role="alert">{err}</p>;
  if (!profile) return <p>불러오는 중…</p>;
  return <ProfileView profile={profile} stats={stats} recommendations={rec} onSave={async (body) => {
    if (!ws) return;
    try { setProfile(await api().request("put", "/v1/workspaces/{ws}/profile", { params: { ws }, body })); }
    catch (e) { setErr(String((e as Error).message)); }
  }} />;
}
