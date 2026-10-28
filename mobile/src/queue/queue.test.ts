import { JobQueue, MemoryJobStore, PermanentError, RetryableError, backoffMs } from "./queue";

function setup(handler: jest.Mock) {
  let t = 1_000_000;
  const store = new MemoryJobStore();
  const queue = new JobQueue(store, { send: handler }, () => t);
  return { queue, store, advance: (ms: number) => (t += ms) };
}

test("a job that succeeds is removed", async () => {
  const { queue } = setup(jest.fn().mockResolvedValue(undefined));
  await queue.enqueue("send", { a: 1 });
  expect(queue.state().pending).toBe(1);
  await queue.run();
  expect(queue.state()).toEqual({ pending: 0, failed: 0, active: null });
});

test("queuing the same id twice sends it once", async () => {
  const handler = jest.fn().mockResolvedValue(undefined);
  const { queue } = setup(handler);
  await queue.enqueue("send", {}, "same");
  await queue.enqueue("send", {}, "same");
  await queue.run();
  expect(handler).toHaveBeenCalledTimes(1);
});

test("a failed attempt waits longer each time, then goes through", async () => {
  const handler = jest
    .fn()
    .mockRejectedValueOnce(new RetryableError("no signal"))
    .mockRejectedValueOnce(new TypeError("Network request failed"))
    .mockResolvedValue(undefined);
  const { queue, advance } = setup(handler);
  await queue.enqueue("send", {});
  await queue.run();
  expect(handler).toHaveBeenCalledTimes(1);
  await queue.run(); // too soon
  expect(handler).toHaveBeenCalledTimes(1);
  advance(backoffMs(1));
  await queue.run();
  expect(handler).toHaveBeenCalledTimes(2);
  advance(backoffMs(1)); // second delay is longer than the first
  await queue.run();
  expect(handler).toHaveBeenCalledTimes(2);
  advance(backoffMs(2));
  await queue.run();
  expect(handler).toHaveBeenCalledTimes(3);
  expect(queue.state().pending).toBe(0);
});

test("a rejected job is parked with its reason until retried", async () => {
  const handler = jest.fn().mockRejectedValueOnce(new PermanentError("422: too large")).mockResolvedValue(undefined);
  const { queue } = setup(handler);
  const id = await queue.enqueue("send", {});
  await queue.run();
  await queue.run();
  expect(handler).toHaveBeenCalledTimes(1);
  expect(queue.state()).toMatchObject({ pending: 0, failed: 1 });
  expect((await queue.jobs())[0].error).toBe("422: too large");
  await queue.retry(id);
  await queue.run();
  expect(queue.state()).toMatchObject({ pending: 0, failed: 0 });
});

test("an unknown job type fails instead of retrying forever", async () => {
  const { queue } = setup(jest.fn());
  await queue.enqueue("mystery", {});
  await queue.run();
  expect(queue.state().failed).toBe(1);
});

test("jobs go in the order they were saved, and progress is reported", async () => {
  const order: number[] = [];
  const seen: number[] = [];
  let queueRef: JobQueue;
  const handler = jest.fn(async (p: { n: number }, ctx) => {
    order.push(p.n);
    ctx.onProgress(0.5);
    seen.push(queueRef.state().active?.progress ?? -1);
  });
  const { queue, advance } = setup(handler);
  queueRef = queue;
  await queue.enqueue("send", { n: 1 });
  advance(10);
  await queue.enqueue("send", { n: 2 });
  await queue.run();
  expect(order).toEqual([1, 2]);
  expect(seen).toEqual([0.5, 0.5]);
});

test("backoff grows and levels off", () => {
  expect(backoffMs(1)).toBeLessThan(backoffMs(2));
  expect(backoffMs(50)).toBe(backoffMs(6));
});
