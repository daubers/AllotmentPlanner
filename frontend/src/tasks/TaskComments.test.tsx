import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const get = vi.fn();
const post = vi.fn();
const patch = vi.fn();
const del = vi.fn();
vi.mock("../api/client", () => ({
  api: {
    GET: (...a: unknown[]) => get(...a),
    POST: (...a: unknown[]) => post(...a),
    PATCH: (...a: unknown[]) => patch(...a),
    DELETE: (...a: unknown[]) => del(...a),
  },
  authHeader: async () => null,
  sessionRejected: vi.fn(),
}));

import TaskComments from "./TaskComments";

const comment = (over = {}) => ({
  id: 1, task_id: 9, body: "Started on the left row", status: null, progress: null, author: "Ann", author_id: 1,
  created_at: "2026-11-02T09:30:00Z", updated_at: "2026-11-02T09:30:00Z", edited: false, ...over,
});

function setup(props: Partial<React.ComponentProps<typeof TaskComments>> = {}) {
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <TaskComments allotmentId={1} taskId={9} canEdit meId={1} {...props} />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  for (const m of [get, post, patch, del]) m.mockReset();
  get.mockResolvedValue({ data: [comment(), comment({ id: 2, body: "", status: "doing", progress: "waiting on seed", author: "Bob", author_id: 2, edited: true })] });
  post.mockResolvedValue({ data: comment({ id: 3 }) });
  patch.mockResolvedValue({ data: comment() });
  del.mockResolvedValue({});
});

describe("TaskComments", () => {
  it("lists comments with their time, author, status and progress", async () => {
    setup();
    expect(await screen.findByText("Started on the left row")).toBeInTheDocument();
    expect(document.querySelector(".badge.status-doing")).toHaveTextContent("In progress");
    expect(screen.getByText("waiting on seed")).toBeInTheDocument();
    expect(screen.getByText("(edited)")).toBeInTheDocument();
    expect(screen.getAllByRole("time")).toHaveLength(2);
  });

  it("posts a comment that sets a status", async () => {
    setup();
    await screen.findByText("Started on the left row");
    await userEvent.type(screen.getByLabelText("New comment"), "All done");
    await userEvent.selectOptions(screen.getByLabelText("Set status"), "done");
    await userEvent.click(screen.getByRole("button", { name: "Add comment" }));
    await waitFor(() => expect(post).toHaveBeenCalled());
    expect(post.mock.calls[0][1].body).toEqual({ body: "All done", status: "done", progress: null });
  });

  it("will not post an empty comment", async () => {
    setup();
    await screen.findByText("Started on the left row");
    await userEvent.click(screen.getByRole("button", { name: "Add comment" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Write something");
    expect(post).not.toHaveBeenCalled();
  });

  it("only offers edit on your own comments, and delete on yours or any if you own the plot", async () => {
    setup();
    await screen.findByText("Started on the left row");
    expect(screen.getAllByRole("button", { name: "Edit" })).toHaveLength(1);
    expect(screen.getAllByRole("button", { name: "Delete" })).toHaveLength(1);
  });

  it("lets an owner delete anyone's comment", async () => {
    setup({ isOwner: true });
    await screen.findByText("Started on the left row");
    expect(screen.getAllByRole("button", { name: "Delete" })).toHaveLength(2);
    await userEvent.click(screen.getAllByRole("button", { name: "Delete" })[1]);
    await waitFor(() => expect(del).toHaveBeenCalled());
  });

  it("is read-only for a viewer", async () => {
    setup({ canEdit: false });
    await screen.findByText("Started on the left row");
    expect(screen.queryByLabelText("New comment")).toBeNull();
    expect(screen.queryByRole("button", { name: "Edit" })).toBeNull();
  });
});
