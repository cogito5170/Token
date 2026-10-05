"use client";
import { useEffect, useState } from "react";
import { api, type Schemas } from "../../../lib/api";
import { getWorkspaceId } from "../../../lib/auth/session";
import { canViewAudit } from "./access";

export default function Page() {
  const [role, setRole] = useState<Schemas["Workspace"]["role"] | null>(null);
  const [items, setItems] = useState<Schemas["AuditEntry"][]>([]);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    const ws = getWorkspaceId();
    if (!ws) return;
    api().get("/v1/workspaces/{ws}", { params: { ws } }).then((w) => setRole(w.role)).catch(() => setRole(null));
  }, []);
  useEffect(() => {
    const ws = getWorkspaceId();
    if (!ws || !canViewAudit(role)) return;
    api().get("/v1/workspaces/{ws}/audit-log", { params: { ws } }).then((p) => setItems(p.items)).catch(() => setError("감사 로그를 불러오지 못했습니다."));
  }, [role]);
  if (!canViewAudit(role)) return null;
  return (
    <section>
      <h1>감사 로그</h1>
      {error && <p className="gc-error" role="alert">{error}</p>}
      <table>
        <thead><tr><th>시각</th><th>행위자</th><th>동작</th><th>대상</th></tr></thead>
        <tbody>
          {items.map((e) => (
            <tr key={e.id}><td>{e.at}</td><td>{e.actor_kind}</td><td>{e.action}</td><td>{e.target_kind}:{e.target_id}</td></tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
