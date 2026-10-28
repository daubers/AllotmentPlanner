import { afterEach, describe, expect, it, vi } from "vitest";
import { checkFileSize, networkFailureMessage, sendUpload } from "./upload";

vi.mock("../api/client", () => ({ authHeader: vi.fn(async () => "Bearer tok"), sessionRejected: vi.fn() }));
import { sessionRejected } from "../api/client";

const MB = 1024 * 1024;
const GB = 1024 * MB;
const file = (name: string, size: number) => ({ name, size });

/** Just enough of XMLHttpRequest to drive sendUpload. */
class FakeXhr {
  static last: FakeXhr;
  headers: Record<string, string> = {};
  upload: { onprogress?: (e: { lengthComputable: boolean; loaded: number; total: number }) => void } = {};
  onload?: () => void;
  onerror?: () => void;
  onabort?: () => void;
  status = 0;
  responseText = "";
  method = "";
  url = "";
  sent: unknown;
  constructor() {
    FakeXhr.last = this;
  }
  open(method: string, url: string) {
    this.method = method;
    this.url = url;
  }
  setRequestHeader(k: string, v: string) {
    this.headers[k] = v;
  }
  send(body: unknown) {
    this.sent = body;
  }
  respond(status: number, text: string) {
    this.status = status;
    this.responseText = text;
    this.onload?.();
  }
}
const newRequest = () => new FakeXhr() as unknown as XMLHttpRequest;
const start = async (f = file("a.mp4", 10 * MB), extra = {}) => {
  const form = new FormData();
  const promise = sendUpload("/api/v1/allotments/1/media", form, { file: f, newRequest, ...extra });
  await vi.waitFor(() => expect(FakeXhr.last?.sent).toBeDefined());
  return { promise, xhr: FakeXhr.last };
};

afterEach(() => vi.clearAllMocks());

describe("checkFileSize", () => {
  it("accepts files within the limit and when the limit is unknown", () => {
    expect(checkFileSize(file("a.mp4", 3 * GB), 4 * GB)).toBeNull();
    expect(checkFileSize(file("a.mp4", 50 * GB), undefined)).toBeNull();
  });
  it("names the file, its size and the limit", () => {
    expect(checkFileSize(file("GH030116.MP4", 3.9 * GB), 200 * MB)).toBe("GH030116.MP4 is 3.9 GB, but the largest upload allowed is 200.0 MB");
  });
});

describe("networkFailureMessage", () => {
  it("blames the size when the file is over the limit", () => {
    expect(networkFailureMessage(file("big.mp4", 3 * GB), 200 * MB)).toMatch(/3.0 GB.*200.0 MB.*shorter clip/);
  });
  it("otherwise says the connection dropped, not the browser's NetworkError", () => {
    const message = networkFailureMessage(file("ok.mp4", 1.5 * GB), 4 * GB);
    expect(message).toMatch(/connection dropped while uploading 1.5 GB/);
    expect(message).not.toMatch(/NetworkError/);
  });
});

describe("sendUpload", () => {
  it("posts with the bearer token, reports progress and resolves with the item", async () => {
    const onProgress = vi.fn();
    const { promise, xhr } = await start(file("a.mp4", 10 * MB), { onProgress });
    expect([xhr.method, xhr.url]).toEqual(["POST", "/api/v1/allotments/1/media"]);
    expect(xhr.headers.Authorization).toBe("Bearer tok");
    xhr.upload.onprogress?.({ lengthComputable: true, loaded: 5 * MB, total: 10 * MB });
    xhr.upload.onprogress?.({ lengthComputable: false, loaded: 0, total: 0 });
    xhr.respond(201, JSON.stringify({ id: 7, kind: "video" }));
    await expect(promise).resolves.toMatchObject({ id: 7 });
    expect(onProgress.mock.calls.map((c) => c[0])).toEqual([0.5, 1]);
  });

  it("refuses an oversized file without sending anything", async () => {
    await expect(sendUpload("/x", new FormData(), { file: file("big.mp4", 5 * GB), maxBytes: 4 * GB, newRequest })).rejects.toThrow(/5.0 GB.*4.0 GB/);
  });

  it("explains a 413 even when the proxy sends an HTML page", async () => {
    const { promise, xhr } = await start(file("big.mp4", 300 * MB), { maxBytes: 4 * GB });
    xhr.respond(413, "<html>413 Request Entity Too Large</html>");
    await expect(promise).rejects.toThrow(/big.mp4 is too large for the server \(limit 4.0 GB\)/);
  });

  it("passes on the server's own message", async () => {
    const { promise, xhr } = await start();
    xhr.respond(415, JSON.stringify({ message: "Unsupported file type" }));
    await expect(promise).rejects.toThrow("Unsupported file type");
  });

  it("falls back to the status code for an unreadable error", async () => {
    const { promise, xhr } = await start();
    xhr.respond(502, "<html>Bad gateway</html>");
    await expect(promise).rejects.toThrow("Upload failed (HTTP 502)");
  });

  it("turns a dropped connection into a useful message", async () => {
    const { promise, xhr } = await start(file("a.mp4", 1.5 * GB), { maxBytes: 4 * GB });
    xhr.onerror?.();
    await expect(promise).rejects.toThrow(/connection dropped while uploading 1.5 GB/);
  });

  it("signs the person out when the session is rejected", async () => {
    const { promise, xhr } = await start();
    xhr.respond(401, JSON.stringify({ message: "Token has expired" }));
    await expect(promise).rejects.toThrow("Token has expired");
    expect(sessionRejected).toHaveBeenCalledOnce();
  });
});
