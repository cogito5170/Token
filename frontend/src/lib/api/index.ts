import { createClient, type ApiClient } from "./client";
import { createFakeFetch } from "./fake";
import { getAccessToken } from "../auth/session";

export * from "./client";
export { createFakeFetch, fixtures } from "./fake";

let shared: ApiClient | null = null;

/** App-wide client. NEXT_PUBLIC_API_MODE=fake (default until the backend is wired) serves screens from the fake API. */
export function api(): ApiClient {
  if (!shared) {
    const fake = (process.env.NEXT_PUBLIC_API_MODE ?? "fake") === "fake";
    shared = createClient({ getToken: getAccessToken, fetch: fake ? createFakeFetch().fetch : undefined });
  }
  return shared;
}
