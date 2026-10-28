import createClient, { type Middleware } from "openapi-fetch";
import type { Session } from "../auth/session";
import type { components, paths } from "./schema";

export type Allotment = components["schemas"]["Allotment"];

/** A typed client for the server the person signed in to; adds their login to each request. */
export function createApi(session: Session) {
  const auth: Middleware = {
    // Change the request in place and return nothing. Returning the same object looks harmless but
    // openapi-fetch checks `instanceof Request` / `instanceof Response`, and on React Native the
    // objects fetch hands back are not instances of those globals, so returning them throws.
    async onRequest({ request }) {
      if (request.url.includes("/api/v1/auth/")) return;
      const header = await session.authHeader();
      if (header) request.headers.set("Authorization", header);
    },
    async onResponse({ response }) {
      if (response.status === 401) await session.rejected();
    },
  };
  const api = createClient<paths>({ baseUrl: session.serverUrl });
  api.use(auth);
  return api;
}

export type Api = ReturnType<typeof createApi>;
