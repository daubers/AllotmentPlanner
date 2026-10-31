import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const get = vi.fn();
const post = vi.fn();
vi.mock("../api/client", () => ({
  api: { GET: (...a: unknown[]) => get(...a), POST: (...a: unknown[]) => post(...a) },
  authHeader: async () => null,
  sessionRejected: vi.fn(),
}));

import SuggestTasks from "./SuggestTasks";

const s = (key: string, title: string, extra = {}) => ({ key, title, description: "Tomato in Spring, sown 1 Mar", due_date: "2026-11-08", added: false, ...extra });

function setup(kind: "tray" | "planting" = "tray") {
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <SuggestTasks allotmentId={1} target={{ kind, id: 7 }} />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  get.mockReset();
  post.mockReset();
  get.mockResolvedValue({ data: [s("a", "Check germination: Tomato"), s("b", "Plant out Tomato", { due_date: "2026-12-01" })] });
  post.mockResolvedValue({ data: [{ id: 1 }, { id: 2 }] });
});

describe("SuggestTasks", () => {
  it("asks nothing until opened, then lists the suggestions", async () => {
    setup();
    expect(get).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: "Suggest tasks" }));
    expect(await screen.findByText("Check germination: Tomato")).toBeInTheDocument();
    expect(get.mock.calls[0][0]).toContain("/trays/{tray_id}/suggested-tasks");
    expect(get.mock.calls[0][1].params.path).toEqual({ allotment_id: 1, tray_id: 7 });
  });

  it("adds them all in one go and says how many", async () => {
    setup();
    await userEvent.click(screen.getByRole("button", { name: "Suggest tasks" }));
    await userEvent.click(await screen.findByRole("button", { name: "Add all 2 tasks" }));
    await waitFor(() => expect(post).toHaveBeenCalledTimes(1));
    expect(await screen.findByRole("status")).toHaveTextContent("Added 2 tasks");
    expect(screen.queryByRole("button", { name: /^Add / })).not.toBeInTheDocument();
  });

  it("marks what is already added and offers only the rest", async () => {
    get.mockResolvedValue({ data: [s("a", "Check germination: Tomato", { added: true }), s("b", "Plant out Tomato")] });
    setup("planting");
    await userEvent.click(screen.getByRole("button", { name: "Suggest tasks" }));
    expect(await screen.findByText(/already added/)).toBeInTheDocument();
    expect(get.mock.calls[0][0]).toContain("/plantings/{planting_id}/suggested-tasks");
    expect(screen.getByRole("button", { name: "Add the other 1 task" })).toBeInTheDocument();
  });

  it("explains when there is nothing to suggest", async () => {
    get.mockResolvedValue({ data: [] });
    setup();
    await userEvent.click(screen.getByRole("button", { name: "Suggest tasks" }));
    expect(await screen.findByText(/Nothing to suggest/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^Add / })).not.toBeInTheDocument();
  });

  it("shows the server's message when adding fails", async () => {
    post.mockResolvedValue({ error: { message: "Tray not found" } });
    setup();
    await userEvent.click(screen.getByRole("button", { name: "Suggest tasks" }));
    await userEvent.click(await screen.findByRole("button", { name: "Add all 2 tasks" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Tray not found");
  });
});
