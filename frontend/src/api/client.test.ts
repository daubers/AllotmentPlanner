import { describe, expect, it } from "vitest";
import { isPublicAuthCall } from "./client";

describe("isPublicAuthCall", () => {
  it.each([
    "/api/v1/auth/login",
    "/api/v1/auth/register",
    "/api/v1/auth/refresh",
    "/api/v1/auth/config",
    "/api/v1/auth/oidc/exchange",
    "/api/v1/auth/oidc/google/login?client=web",
  ])("sends %s without a token", (url) => expect(isPublicAuthCall(`https://x.test${url}`)).toBe(true));

  it.each([
    "/api/v1/auth/me",
    "/api/v1/auth/oidc/identities",
    "/api/v1/auth/oidc/identities/3",
    "/api/v1/auth/oidc/google/link",
  ])("sends %s with the token", (url) => expect(isPublicAuthCall(`https://x.test${url}`)).toBe(false));
});
