import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { SightingDialog, SightingPhoto } from "./SightingPhoto";

const sighting = { media_id: 1, outline: [[0.2, 0.3], [0.5, 0.3], [0.5, 0.6]], score: 0.8, url: "/full.jpg", thumb_url: "/thumb.jpg", width: 4000, height: 3000 };

describe("SightingPhoto", () => {
  it("draws the thumbnail with the outline over it, in the photo's own shape", () => {
    const { container } = render(<SightingPhoto sighting={sighting} alt="Shed" />);
    expect(screen.getByAltText("Shed")).toHaveAttribute("src", "/thumb.jpg");
    expect(container.querySelector("polygon")).toHaveAttribute("points", "0.2,0.3 0.5,0.3 0.5,0.6");
    expect(container.querySelector(".sighting-photo")).toHaveStyle({ aspectRatio: "4000 / 3000" });
  });

  it("uses the full photo when asked, and falls back to it with no thumbnail", () => {
    const { rerender } = render(<SightingPhoto sighting={sighting} full alt="a" />);
    expect(screen.getByAltText("a")).toHaveAttribute("src", "/full.jpg");
    rerender(<SightingPhoto sighting={{ ...sighting, thumb_url: null }} alt="a" />);
    expect(screen.getByAltText("a")).toHaveAttribute("src", "/full.jpg");
  });
});

describe("SightingDialog", () => {
  it("opens as a modal and closes from its button", () => {
    HTMLDialogElement.prototype.showModal = vi.fn();
    const onClose = vi.fn();
    render(<SightingDialog sighting={sighting} name="Shed" onClose={onClose} />);
    expect(HTMLDialogElement.prototype.showModal).toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Close", hidden: true }));
    expect(onClose).toHaveBeenCalled();
  });
});
