import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, renderHook, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const patch = vi.fn();
vi.mock("../api/client", () => ({
  api: { GET: vi.fn(), POST: vi.fn(), PATCH: (...a: unknown[]) => patch(...a), DELETE: vi.fn() },
  authHeader: async () => null,
  sessionRejected: vi.fn(),
}));

import { SaveStatus } from "../map/Suggestions";
import { useSuggestionActions } from "./hooks";
import type { Suggestion } from "./model";

const square = (x: number) => ({ type: "Polygon", coordinates: [[[x, 0], [x, 1], [x + 1, 1], [x, 0]]] });
const list = [{ id: 1, name: "Shed", geometry: square(0) }, { id: 2, name: "Tree", geometry: square(5) }] as unknown as Suggestion[];

let qc: QueryClient;
const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={qc}>{children}</QueryClientProvider>;

beforeEach(() => {
  patch.mockReset();
  qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  qc.setQueryData(["suggestions", 7], list);
});

describe("moving a found item", () => {
  it("shows the new place at once and keeps it once saved", async () => {
    let finish: (v: unknown) => void = () => {};
    patch.mockReturnValue(new Promise((r) => (finish = r)));
    const { result } = renderHook(() => useSuggestionActions(7), { wrapper });
    act(() => result.current.patch.mutate({ id: 1, geometry: square(9) }));
    await waitFor(() => expect((qc.getQueryData(["suggestions", 7]) as Suggestion[])[0].geometry).toEqual(square(9)));
    expect((qc.getQueryData(["suggestions", 7]) as Suggestion[])[1].geometry).toEqual(square(5)); // others untouched
    finish({ data: { id: 1, name: "Shed", geometry: square(9) } });
    await waitFor(() => expect(result.current.patch.isSuccess).toBe(true));
  });

  it("puts it back if the server refuses", async () => {
    patch.mockResolvedValue({ data: undefined, error: { message: "A Polygon can't become a Point" } });
    const { result } = renderHook(() => useSuggestionActions(7), { wrapper });
    await act(async () => {
      await result.current.patch.mutateAsync({ id: 1, geometry: square(9) }).catch(() => {});
    });
    expect((qc.getQueryData(["suggestions", 7]) as Suggestion[])[0].geometry).toEqual(square(0));
    await waitFor(() => expect(result.current.patch.error?.message).toBe("A Polygon can't become a Point"));
  });
});

describe("SaveStatus", () => {
  it("says nothing before any change, then saving, then saved", async () => {
    let finish: (v: unknown) => void = () => {};
    patch.mockReturnValue(new Promise((r) => (finish = r)));
    const { container } = render(<SaveStatus allotmentId={7} />, { wrapper });
    expect(container).toBeEmptyDOMElement();
    const { result } = renderHook(() => useSuggestionActions(7), { wrapper });
    act(() => result.current.patch.mutate({ id: 1, name: "Barn" }));
    expect(await screen.findByText("Saving…")).toBeInTheDocument();
    finish({ data: { id: 1, name: "Barn" } });
    expect(await screen.findByText(/All changes saved/)).toBeInTheDocument();
  });

  it("says when a change was not saved and was undone", async () => {
    patch.mockResolvedValue({ data: undefined, error: { message: "Nope" } });
    render(<SaveStatus allotmentId={7} />, { wrapper });
    const { result } = renderHook(() => useSuggestionActions(7), { wrapper });
    await act(async () => {
      await result.current.patch.mutateAsync({ id: 1, name: "Barn" }).catch(() => {});
    });
    expect(await screen.findByRole("alert")).toHaveTextContent("Not saved: Nope");
  });
});
