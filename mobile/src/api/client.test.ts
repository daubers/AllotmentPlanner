import { createApi } from "./client";
import { Session, type KeyValueStore } from "../auth/session";

function memory(): KeyValueStore {
  const data = new Map<string, string>();
  return {
    get: async (k) => data.get(k) ?? null,
    set: async (k, v) => void data.set(k, v),
    remove: async (k) => void data.delete(k),
  };
}
const token = () => `x.${Buffer.from(JSON.stringify({ exp: Date.now() / 1000 + 900 })).toString("base64")}.y`;

async function signedIn() {
  const login = jest
    .fn()
    .mockResolvedValue(new Response(JSON.stringify({ access_token: token(), refresh_token: "r" }), { status: 200 }));
  const session = new Session(memory(), login);
  await session.login("h:1", "a@b.c", "pw");
  return session;
}

afterEach(() => jest.restoreAllMocks());

test("a request carries the login, and a normal answer comes back", async () => {
  const session = await signedIn();
  const seen = jest.fn();
  jest.spyOn(globalThis, "fetch").mockImplementation(async (req) => {
    seen((req as Request).headers.get("Authorization"));
    return new Response(JSON.stringify([{ id: 1, name: "Plot", role: "owner" }]), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  });
  const { data, error } = await createApi(session).GET("/api/v1/allotments");
  expect(error).toBeUndefined();
  expect(data).toHaveLength(1);
  expect(seen.mock.calls[0][0]).toMatch(/^Bearer /);
});

test("a refused login signs out without the middleware throwing", async () => {
  const session = await signedIn();
  jest.spyOn(globalThis, "fetch").mockImplementation(async () => new Response("{}", { status: 401 }));
  const result = await createApi(session).GET("/api/v1/allotments");
  expect(result.response.status).toBe(401);
  expect(session.signedIn).toBe(false);
});

test("a response object from another realm (as on React Native) is accepted", async () => {
  // Stand-in for RN's fetch: an object that quacks like a Response but is not `instanceof Response`.
  const real = new Response("[]", { status: 200, headers: { "Content-Type": "application/json" } });
  const foreign = Object.create(null, {
    status: { value: 200 },
    ok: { value: true },
    headers: { value: real.headers },
    clone: { value: () => foreign },
    text: { value: () => real.clone().text() },
    json: { value: () => real.clone().json() },
    body: { value: null },
  });
  const session = await signedIn();
  jest.spyOn(globalThis, "fetch").mockImplementation(async () => foreign);
  await expect(createApi(session).GET("/api/v1/allotments")).resolves.toBeDefined();
});
