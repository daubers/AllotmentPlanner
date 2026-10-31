import "@testing-library/jest-dom/vitest";

// jsdom has no modal dialogs: open the element so its contents are on the page.
HTMLDialogElement.prototype.showModal = function showModal(this: HTMLDialogElement) {
  this.setAttribute("open", "");
};
HTMLDialogElement.prototype.close = function close(this: HTMLDialogElement) {
  this.removeAttribute("open");
};
