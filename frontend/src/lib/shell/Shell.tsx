"use client";
import { useEffect, useState, type ReactNode } from "react";
import { usePathname, useRouter } from "next/navigation";
import Link from "next/link";
import type { NavGroup } from "../nav/registry";
import { api } from "../api";
import type { Schemas } from "../api";
import { getAccessToken, getWorkspaceId, isAuthPath, setAccessToken, setWorkspaceId } from "../auth/session";
import { desktopBridge, isLivePath, shellMode } from "./desktop";

export function WorkspaceSwitcher() {
  const [list, setList] = useState<Schemas["Workspace"][]>([]);
  const [current, setCurrent] = useState<string>("");
  useEffect(() => {
    api().get("/v1/workspaces").then((ws) => {
      setList(ws);
      const saved = getWorkspaceId();
      const id = ws.find((w) => w.id === saved)?.id ?? ws[0]?.id ?? "";
      if (id) setWorkspaceId(id);
      setCurrent(id);
    }).catch(() => setList([]));
  }, []);
  return (
    <div className="gc-ws">
      <label>
        <span className="gc-sr">워크스페이스</span>
        <select value={current} onChange={(e) => { setWorkspaceId(e.target.value); setCurrent(e.target.value); }}>
          {list.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
        </select>
      </label>
    </div>
  );
}

export function Shell({ nav, children }: { nav: NavGroup[]; children: ReactNode }) {
  const path = usePathname() ?? "/";
  const router = useRouter();
  const auth = isAuthPath(path);
  const [ready, setReady] = useState(false);
  // inside the desktop shell /live is bare; the bridge is set by the preload before any page script runs
  const bare = isLivePath(path) && desktopBridge() !== null;
  useEffect(() => {
    const mode = shellMode({ path, auth, desktop: desktopBridge() !== null, hasToken: !!getAccessToken() });
    if (mode === "redirect") router.replace("/login");
    else setReady(true);
  }, [auth, router, path]);

  if (auth || bare) return <main className="gc-main">{children}</main>;
  if (!ready) return null;
  return (
    <div className="gc-shell">
      <nav className="gc-nav" aria-label="주 메뉴">
        <strong>ga Console</strong>
        <WorkspaceSwitcher />
        {nav.map((g) => (
          <section key={g.id}>
            {g.label && <h2>{g.label}</h2>}
            <ul>
              {g.items.map((i) => (
                <li key={i.href}>
                  <Link href={i.href} aria-current={path === i.href ? "page" : undefined}>{i.label}</Link>
                </li>
              ))}
            </ul>
          </section>
        ))}
        <div className="gc-spacer" />
        <button type="button" onClick={() => { setAccessToken(null); router.replace("/login"); }}>로그아웃</button>
      </nav>
      <main className="gc-main">{children}</main>
    </div>
  );
}
