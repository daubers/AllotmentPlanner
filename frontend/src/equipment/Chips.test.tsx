import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderHook, act } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const get = vi.fn();
vi.mock("../api/client", () => ({
  api: { GET: (...a: unknown[]) => get(...a), POST: vi.fn(), PATCH: vi.fn(), DELETE: vi.fn() },
  authHeader: async () => null,
  sessionRejected: vi.fn(),
}));

import EquipmentChips from "./EquipmentChips";
import ToolTicks from "./ToolTicks";
import { useDebounced } from "./useDebounced";

const eq = (id: number, name: string, status: "in_service" | "out_of_action" = "in_service") => ({ id, name, kind: "spade", kind_label: "Spade", quantity: 1, notes: "", used_for: "", keywords: [], status });
const owned = [eq(1, "Border spade"), eq(2, "Hand fork"), eq(3, "Old fork", "out_of_action")];

function chips(props: Partial<React.ComponentProps<typeof EquipmentChips>> = {}) {
  const onChange = vi.fn();
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <EquipmentChips allotmentId={1} value={[]} onChange={onChange} {...props} />
    </QueryClientProvider>,
  );
  return onChange;
}

beforeEach(() => {
  get.mockReset();
  get.mockImplementation(async () => ({ data: owned }));
});

describe("EquipmentChips", () => {
  it("says when nothing is needed", async () => {
    chips();
    expect(await screen.findByText("None needed")).toBeInTheDocument();
  });

  it("shows what is on the job, by name, and removes one", async () => {
    const onChange = chips({ value: [1, 2] });
    expect(await screen.findByText(/Border spade/)).toBeInTheDocument();
    expect(screen.getByText(/Hand fork/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Remove Border spade" }));
    expect(onChange).toHaveBeenCalledWith([2]);
  });

  it("uses the names it is given until the list has loaded", () => {
    get.mockImplementation(() => new Promise(() => {})); // never answers
    chips({ value: [9], known: [{ id: 9, name: "Borrowed barrow", kind: null, kind_label: "Other", quantity: 1, status: "in_service" }] });
    expect(screen.getByText(/Borrowed barrow/)).toBeInTheDocument();
  });

  it("offers suggestions as chips that add on a click, and not ones already on the job", async () => {
    const onChange = chips({
      value: [2],
      suggestions: [
        { ...eq(1, "Border spade"), reason: "digging" },
        { ...eq(2, "Hand fork"), reason: "weeding" },
      ],
    });
    const add = await screen.findByRole("button", { name: "Add Border spade" });
    expect(add).toHaveAttribute("title", "Suggested for digging");
    expect(screen.queryByRole("button", { name: "Add Hand fork" })).not.toBeInTheDocument();
    await userEvent.click(add);
    expect(onChange).toHaveBeenCalledWith([2, 1]);
  });

  it("can add anything else you own from a list", async () => {
    const onChange = chips({ value: [1] });
    const select = await screen.findByLabelText("Add equipment");
    expect(screen.queryByRole("option", { name: "Border spade" })).not.toBeInTheDocument(); // already on it
    expect(screen.getByRole("option", { name: "Old fork (out of action)" })).toBeInTheDocument();
    await userEvent.selectOptions(select, "Hand fork");
    expect(onChange).toHaveBeenCalledWith([1, 2]);
  });

  it("marks equipment that is out of action", async () => {
    chips({ value: [3] });
    expect(await screen.findByText(/Old fork \(out of action\)/)).toBeInTheDocument();
  });

  it("only looks when disabled", async () => {
    chips({ value: [1], disabled: true, suggestions: [{ ...eq(2, "Hand fork"), reason: "weeding" }] });
    expect(await screen.findByText(/Border spade/)).toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Add equipment")).not.toBeInTheDocument();
  });
});

describe("ToolTicks", () => {
  const items = [{ ...eq(1, "Dibber"), reason: "sowing" }, { ...eq(2, "Seed tray"), reason: "sowing" }];

  it("shows nothing without suggestions", () => {
    const { container } = render(<ToolTicks items={[]} unticked={new Set()} onToggle={vi.fn()} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("ticks what will be added and reports a change", async () => {
    const onToggle = vi.fn();
    render(<ToolTicks items={items} unticked={new Set([2])} onToggle={onToggle} />);
    expect(screen.getByRole("checkbox", { name: "Dibber" })).toBeChecked();
    expect(screen.getByRole("checkbox", { name: "Seed tray" })).not.toBeChecked();
    await userEvent.click(screen.getByRole("checkbox", { name: "Dibber" }));
    expect(onToggle).toHaveBeenCalledWith(1);
  });

  it("can be switched off", () => {
    render(<ToolTicks items={items} unticked={new Set()} onToggle={vi.fn()} disabled />);
    for (const box of screen.getAllByRole("checkbox")) expect(box).toBeDisabled();
  });
});

describe("useDebounced", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("waits until the value stops changing", () => {
    const { result, rerender } = renderHook(({ v }) => useDebounced(v, 400), { initialProps: { v: "a" } });
    expect(result.current).toBe("a");
    rerender({ v: "ab" });
    act(() => vi.advanceTimersByTime(300));
    rerender({ v: "abc" });
    act(() => vi.advanceTimersByTime(300));
    expect(result.current).toBe("a"); // still typing
    act(() => vi.advanceTimersByTime(150));
    expect(result.current).toBe("abc");
  });
});
