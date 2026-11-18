import { checkCompat, compareVersions, REQUIRED_API_LEVEL } from "./compat";

test("versions compare as numbers, not text", () => {
  expect(compareVersions("1.10.0", "1.9.2")).toBe(1);
  expect(compareVersions("1.4", "1.4.0")).toBe(0);
  expect(compareVersions("1.4.1", "1.5.0")).toBe(-1);
  expect(compareVersions("1.5.0-beta.1", "1.5.0")).toBe(0);
});

test("an app older than the server's minimum is told to update the app", () => {
  const c = checkCompat({ apiLevel: REQUIRED_API_LEVEL, minAppVersion: "1.5.0" }, "1.4.1");
  expect(c?.kind).toBe("update-app");
  expect(c?.message).toMatch(/1\.5\.0/);
});

test("a server behind the app's API level, or one that predates the check, is told to update the server", () => {
  expect(checkCompat({ apiLevel: REQUIRED_API_LEVEL - 1 }, "1.4.1")?.kind).toBe("update-server");
  expect(checkCompat({ serverVersion: "0.15.2" }, "1.4.1")?.kind).toBe("update-server");
});

test("a compatible or unreachable server gives no warning", () => {
  expect(checkCompat({ apiLevel: REQUIRED_API_LEVEL, minAppVersion: "1.0.0" }, "1.4.1")).toBeNull();
  expect(checkCompat(null, "1.4.1")).toBeNull();
});
