import { Session, normaliseServerUrl, secondsLeft, type KeyValueStore } from "./session";

function memory(): KeyValueStore & { data: Map<string, string> } {
  const data = new Map<string, string>();
  return {
    data,
    get: async (k) => data.get(k) ?? null,
    set: async (k, v) => void data.set(k, v),
    remove: async (k) => void data.delete(k),
  };
}

function jwt(expiresInS: number): string {
  const payload = Buffer.from(JSON.stringify({ exp: Date.now() / 1000 + expiresInS })).toString("base64");
  return `x.${payload}.y`;
}

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

test("server addresses are tidied", () => {
  expect(normaliseServerUrl(" 192.168.1.5:8000/ ")).toBe("http://192.168.1.5:8000");
  expect(normaliseServerUrl("https://plot.example.com//")).toBe("https://plot.example.com");
  expect(normaliseServerUrl("  ")).toBe("");
});

test("secondsLeft reads a token's expiry and treats rubbish as expired", () => {
  expect(Math.round(secondsLeft(jwt(300)))).toBe(300);
  expect(secondsLeft("not a token")).toBe(0);
});

test("login saves the server and tokens, and a new session loads them", async () => {
  const store = memory();
  const fetchImpl = jest.fn().mockResolvedValue(json(200, { access_token: jwt(900), refresh_token: "r" }));
  const session = new Session(store, fetchImpl);
  await session.login("10.0.0.2:8000", "a@b.c", "pw");
  expect(fetchImpl.mock.calls[0][0]).toBe("http://10.0.0.2:8000/api/v1/auth/login");
  const again = new Session(store);
  await again.load();
  expect(again.signedIn).toBe(true);
  expect(again.serverUrl).toBe("http://10.0.0.2:8000");
});

test("login explains a wrong password and an unreachable server", async () => {
  const wrong = new Session(memory(), jest.fn().mockResolvedValue(json(401, {})));
  await expect(wrong.login("h", "a@b.c", "x")).rejects.toThrow("Wrong email or password");
  const down = new Session(memory(), jest.fn().mockRejectedValue(new TypeError("Network request failed")));
  await expect(down.login("h", "a@b.c", "x")).rejects.toThrow("Can't reach");
});

test("an expiring token is refreshed once for concurrent callers", async () => {
  const store = memory();
  const fresh = jwt(900);
  const fetchImpl = jest
    .fn()
    .mockResolvedValueOnce(json(200, { access_token: jwt(10), refresh_token: "r" }))
    .mockResolvedValue(json(200, { access_token: fresh }));
  const session = new Session(store, fetchImpl);
  await session.login("h", "a@b.c", "pw");
  const [a, b] = await Promise.all([session.authHeader(), session.authHeader()]);
  expect(a).toBe(`Bearer ${fresh}`);
  expect(b).toBe(`Bearer ${fresh}`);
  expect(fetchImpl).toHaveBeenCalledTimes(2); // login + one refresh
});

test("going offline during a refresh keeps the login; a refused refresh signs out", async () => {
  const expired = jest.fn();
  const offline = new Session(
    memory(),
    jest
      .fn()
      .mockResolvedValueOnce(json(200, { access_token: jwt(5), refresh_token: "r" }))
      .mockRejectedValue(new TypeError("offline")),
  );
  await offline.login("h", "a@b.c", "pw");
  await offline.authHeader();
  expect(offline.signedIn).toBe(true);

  const refused = new Session(
    memory(),
    jest
      .fn()
      .mockResolvedValueOnce(json(200, { access_token: jwt(5), refresh_token: "r" }))
      .mockResolvedValue(json(401, {})),
  );
  refused.onExpired(expired);
  await refused.login("h", "a@b.c", "pw");
  await refused.authHeader();
  expect(refused.signedIn).toBe(false);
  expect(expired).toHaveBeenCalledTimes(1);
});
