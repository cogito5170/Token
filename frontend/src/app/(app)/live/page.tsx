"use client";
// CMD-FE2: /live — the live monitor. ?source=<id> follows the SSE stream; add &recording=<id> to replay it.
// Optional ?api=<base>&ws=<id>; window.gaDesktop.sidecarUrl (desktop shell) wins over ?api. Desktop uses the nil workspace. Read-only.
import { useEffect, useState } from "react";
import { getAccessToken, getWorkspaceId } from "../../../lib/auth/session";
import { fetchRecording, follow, merge, type Endpoint } from "../../../monitor/feed";
import { liveBase } from "../../../lib/shell/desktop";
import { Stage } from "../../../monitor/Stage";
import type { MonitorEvent } from "../../../monitor/types";

const NIL_WS = "00000000-0000-0000-0000-000000000000";

export default function Page() {
  const [events, setEvents] = useState<MonitorEvent[]>([]);
  const [mode, setMode] = useState<"live" | "replay">("live");

  useEffect(() => {
    const q = new URLSearchParams(window.location.search);
    const source = q.get("source");
    if (!source) return;
    const ep: Endpoint = {
      base: liveBase(q, process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"),
      ws: q.get("ws") ?? getWorkspaceId() ?? NIL_WS,
      source,
      token: getAccessToken(),
    };
    const recording = q.get("recording");
    const abort = new AbortController();
    if (recording) {
      setMode("replay");
      fetchRecording(ep, recording).then(setEvents).catch(() => setEvents([]));
    } else {
      void follow(ep, (add) => setEvents((cur) => merge(cur, add)), abort.signal);
    }
    return () => abort.abort();
  }, []);

  return <Stage events={events} mode={mode} />;
}
