// Access token lives in memory + sessionStorage; the refresh token is an httpOnly cookie the browser holds.
const KEY = "gc.access";
const WS_KEY = "gc.workspace";
let memory: string | null = null;

const store = () => (typeof window === "undefined" ? null : window.sessionStorage);

export function getAccessToken(): string | null {
  return memory ?? store()?.getItem(KEY) ?? null;
}
export function setAccessToken(t: string | null) {
  memory = t;
  if (t) store()?.setItem(KEY, t); else store()?.removeItem(KEY);
}
export function getWorkspaceId(): string | null {
  return store()?.getItem(WS_KEY) ?? null;
}
export function setWorkspaceId(id: string) {
  store()?.setItem(WS_KEY, id);
}
export const AUTH_PATHS = ["/login", "/signup"];
export const isAuthPath = (p: string) => AUTH_PATHS.includes(p);
