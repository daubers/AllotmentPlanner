import { Session, type KeyValueStore } from "../auth/session";
import { makeHandlers } from "./handlers";
import { PermanentError, RetryableError } from "./queue";

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
const ctx = { onProgress: jest.fn() };

test("a request is sent to the server with the login", async () => {
  const session = await signedIn();
  const fetchImpl = jest.fn().mockResolvedValue(new Response("{}", { status: 200 }));
  const { request } = makeHandlers({ session, fetchImpl, uploadFile: jest.fn() });
  await request({ method: "PATCH", path: "/api/v1/tasks/3", body: { status: "done" } }, ctx);
  const [url, init] = fetchImpl.mock.calls[0];
  expect(url).toBe("http://h:1/api/v1/tasks/3");
  expect(init.headers.Authorization).toMatch(/^Bearer /);
  expect(init.body).toBe('{"status":"done"}');
});

test("outcomes are sorted into retry, permanent and signed out", async () => {
  const session = await signedIn();
  const answer = (status: number, body = "{}") =>
    makeHandlers({
      session,
      fetchImpl: jest.fn().mockResolvedValue(new Response(body, { status })),
      uploadFile: jest.fn(),
    }).request({ method: "POST", path: "/x" }, ctx);

  await expect(answer(503)).rejects.toBeInstanceOf(RetryableError);
  await expect(answer(429)).rejects.toBeInstanceOf(RetryableError);
  await expect(answer(422, '{"message":"Name is required"}')).rejects.toThrow("Name is required");
  await expect(answer(404)).rejects.toBeInstanceOf(PermanentError);
  await expect(answer(401)).rejects.toBeInstanceOf(RetryableError);
  expect(session.signedIn).toBe(false);
});

test("no connection is retried", async () => {
  const session = await signedIn();
  const { request } = makeHandlers({
    session,
    fetchImpl: jest.fn().mockRejectedValue(new TypeError("Network request failed")),
    uploadFile: jest.fn(),
  });
  await expect(request({ method: "POST", path: "/x" }, ctx)).rejects.toBeInstanceOf(RetryableError);
});

test("an upload goes to the allotment's media endpoint with its fields and reports progress", async () => {
  const session = await signedIn();
  const uploadFile = jest.fn().mockImplementation(async (a) => {
    a.onProgress(0.5);
    return { status: 201, body: "{}" };
  });
  const onProgress = jest.fn();
  const { upload } = makeHandlers({ session, uploadFile });
  await upload(
    { allotmentId: 7, uri: "file:///a.jpg", name: "a.jpg", mimeType: "image/jpeg", fields: { task_id: "4" } },
    { onProgress },
  );
  const args = uploadFile.mock.calls[0][0];
  expect(args.url).toBe("http://h:1/api/v1/allotments/7/media");
  expect(args.fields).toEqual({ task_id: "4" });
  expect(onProgress).toHaveBeenCalledWith(0.5);
  expect(onProgress).toHaveBeenLastCalledWith(1);
});

test("an upload that drops or is too big is handled", async () => {
  const session = await signedIn();
  const dropped = makeHandlers({ session, uploadFile: jest.fn().mockRejectedValue(new Error("x")) });
  await expect(
    dropped.upload({ allotmentId: 1, uri: "f", name: "n", mimeType: "image/jpeg" }, ctx),
  ).rejects.toBeInstanceOf(RetryableError);
  const big = makeHandlers({ session, uploadFile: jest.fn().mockResolvedValue({ status: 413, body: "" }) });
  await expect(big.upload({ allotmentId: 1, uri: "f", name: "n", mimeType: "image/jpeg" }, ctx)).rejects.toThrow(
    "Too large",
  );
});
