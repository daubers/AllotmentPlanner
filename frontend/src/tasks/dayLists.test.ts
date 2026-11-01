import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useSelectedList } from "./dayLists";

afterEach(() => {
  vi.restoreAllMocks();
  localStorage.clear();
});

describe("useSelectedList", () => {
  it("remembers the list per allotment and shares it between users of the hook", () => {
    const a = renderHook(() => useSelectedList(1));
    const b = renderHook(() => useSelectedList(1));
    const other = renderHook(() => useSelectedList(2));
    expect(a.result.current[0]).toBeNull();
    act(() => a.result.current[1](5));
    expect(b.result.current[0]).toBe(5);
    expect(other.result.current[0]).toBeNull();
    expect(localStorage.getItem("allotment:1:day-list")).toBe("5");
    act(() => a.result.current[1](null));
    expect(b.result.current[0]).toBeNull();
  });

  it("still works when storage is blocked", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    const { result } = renderHook(() => useSelectedList(9));
    act(() => result.current[1](7));
    expect(result.current[0]).toBe(7);
  });
});
