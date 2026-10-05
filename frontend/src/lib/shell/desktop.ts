// Desktop shell (ADR-0008): the Electron preload exposes window.gaDesktop = { sidecarUrl }. There is no account in
// that mode, so /live renders bare (no login redirect, no app chrome).
export type DesktopBridge = { sidecarUrl?: string };

export function desktopBridge(): DesktopBridge | null {
  if (typeof window === "undefined") return null;
  const b = (window as unknown as { gaDesktop?: DesktopBridge }).gaDesktop;
  return b && typeof b === "object" ? b : null;
}

export const isLivePath = (p: string) => p.replace(/\/+$/, "") === "/live";

export type ShellMode = "auth" | "bare" | "redirect" | "chrome";

/** auth pages and desktop /live render without chrome; others need a token or go to /login. */
export function shellMode(o: { path: string; auth: boolean; desktop: boolean; hasToken: boolean }): ShellMode {
  if (o.auth) return "auth";
  if (o.desktop && isLivePath(o.path)) return "bare";
  return o.hasToken ? "chrome" : "redirect";
}

/** API base for /live: the desktop bridge wins over ?api=, then the build-time default. */
export function liveBase(q: URLSearchParams, fallback: string): string {
  return desktopBridge()?.sidecarUrl ?? q.get("api") ?? fallback;
}
