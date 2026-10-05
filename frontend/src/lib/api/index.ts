import { createClient, type ApiClient } from "./client";
import { createFakeFetch } from "./fake";
import { getAccessToken } from "../auth/session";

export * from "./client";
export { createFakeFetch, fixtures } from "./fake";

let shared: ApiClient | null = null;

/** NEXT_PUBLIC_API_MODE=real talks to the API at NEXT_PUBLIC_API_URL; anything else (default) serves the fake API. */
export const isFakeMode = (mode: string | undefined) => mode !== "real";

/** App-wide client. */
export function api(): ApiClient {
  if (!shared) {
    const fake = isFakeMode(process.env.NEXT_PUBLIC_API_MODE);
    shared = createClient({ getToken: getAccessToken, fetch: fake ? createFakeFetch().fetch : undefined });
  }
  return shared;
}
