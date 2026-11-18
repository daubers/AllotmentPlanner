import { deleteAccount, downloadUrl, parseReauthResult, reauthMessage, requestExport, SharedAllotmentsError, startReauth } from "./client";

const session = { serverUrl: "https://plot.example.com", authHeader: async () => "Bearer t" };
const json = (status: number, body?: unknown) =>
  new Response(body === undefined ? null : JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

test("the reauth redirect is read for its code or error", () => {
  expect(parseReauthResult("allotment://auth?reauth=abc")).toEqual({ code: "abc" });
  expect(parseReauthResult("allotment://auth?error=wrong_account")).toEqual({ error: "wrong_account" });
  expect(parseReauthResult("allotment://auth")).toEqual({ error: "failed" });
  expect(reauthMessage("wrong_account")).toMatch(/not the account/);
  expect(reauthMessage("nope")).toMatch(/failed/);
});

test("starting a confirmation asks the server for the phone flow and returns a full address", async () => {
  const fetchImpl = jest.fn(async () => json(200, { url: "/api/v1/auth/oidc/idp/login?client=mobile&reauth=r1" }));
  const url = await startReauth(session, "idp", fetchImpl as unknown as typeof fetch);
  expect(url).toBe("https://plot.example.com/api/v1/auth/oidc/idp/login?client=mobile&reauth=r1");
  const [called, init] = fetchImpl.mock.calls[0] as unknown as [string, RequestInit];
  expect(called).toBe("https://plot.example.com/api/v1/auth/oidc/idp/reauth?client=mobile&redirect=allotment%3A%2F%2Fauth");
  expect(init.method).toBe("POST");
  expect((init.headers as Record<string, string>).Authorization).toBe("Bearer t");
});

test("deleting sends the proof and passes success", async () => {
  const fetchImpl = jest.fn(async () => json(204));
  await deleteAccount(session, { password: "pw" }, fetchImpl as unknown as typeof fetch);
  const [, init] = fetchImpl.mock.calls[0] as unknown as [string, RequestInit];
  expect(init.method).toBe("DELETE");
  expect(JSON.parse(init.body as string)).toEqual({ password: "pw" });
});

test("a refused deletion says which shared allotments are in the way", async () => {
  const fetchImpl = async () => json(409, { message: "Only owner", errors: { allotments: [{ id: 3, name: "Shared" }] } });
  const err = await deleteAccount(session, { password: "pw" }, fetchImpl as unknown as typeof fetch).catch((e) => e);
  expect(err).toBeInstanceOf(SharedAllotmentsError);
  expect(err.allotments).toEqual([{ id: 3, name: "Shared" }]);
});

test("a wrong password shows the server's message", async () => {
  const fetchImpl = async () => json(403, { message: "That password is not right" });
  await expect(deleteAccount(session, { password: "x" }, fetchImpl as unknown as typeof fetch)).rejects.toThrow("That password is not right");
});

test("the export and its download address", async () => {
  const fetchImpl = async () => json(202, { id: 5, status: "pending" });
  expect(await requestExport(session, fetchImpl as unknown as typeof fetch)).toEqual({ id: 5, status: "pending" });
  expect(downloadUrl(session, "/api/v1/auth/me/export/5/file?t=x")).toBe("https://plot.example.com/api/v1/auth/me/export/5/file?t=x");
});
