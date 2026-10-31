import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import Modal from "./Modal";

describe("Modal", () => {
  it("shows its title and content as a dialog", () => {
    render(<Modal title="Edit task" onClose={vi.fn()}><p>Hello</p></Modal>);
    expect(screen.getByRole("dialog", { name: "Edit task" })).toBeInTheDocument();
    expect(screen.getByText("Hello")).toBeInTheDocument();
  });

  it("closes from the close button and on Esc", async () => {
    const onClose = vi.fn();
    render(<Modal title="Edit task" onClose={onClose}>x</Modal>);
    await userEvent.click(screen.getByRole("button", { name: "Close" }));
    expect(onClose).toHaveBeenCalledTimes(1);
    screen.getByRole("dialog").dispatchEvent(new Event("cancel", { cancelable: true }));
    expect(onClose).toHaveBeenCalledTimes(2);
  });
});
