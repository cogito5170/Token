"use client";
import { useEffect, useState } from "react";
import { api, type Schemas } from "../../../lib/api";

export default function Page() {
  const [items, setItems] = useState<Schemas["Notification"][]>([]);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    api().get("/v1/notifications").then((r) => setItems(r as Schemas["Notification"][])).catch(() => setError("알림을 불러오지 못했습니다."));
  }, []);
  async function read(id: string) {
    await api().request("post", "/v1/notifications/{notification}/read", { params: { notification: id } });
    setItems((xs) => xs.map((n) => (n.id === id ? { ...n, read_at: new Date().toISOString() } : n)));
  }
  return (
    <section>
      <h1>알림</h1>
      {error && <p className="gc-error" role="alert">{error}</p>}
      {items.length === 0 && !error && <p>새 알림이 없습니다.</p>}
      <ul>
        {items.map((n) => (
          <li key={n.id} data-read={n.read_at ? "true" : "false"}>
            {n.text} <time dateTime={n.created_at}>{n.created_at.slice(0, 16).replace("T", " ")}</time>
            {!n.read_at && <button onClick={() => read(n.id)}>읽음</button>}
          </li>
        ))}
      </ul>
    </section>
  );
}
