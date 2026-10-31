import { useEffect, useRef, type ReactNode } from "react";

/** A dialog over the page (native <dialog>: focus stays inside it and Esc closes it). */
export default function Modal({ title, onClose, children }: { title: string; onClose(): void; children: ReactNode }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current;
    if (dialog && !dialog.open) dialog.showModal();
  }, []);
  return (
    <dialog
      ref={ref}
      className="modal"
      aria-label={title}
      onCancel={(e) => {
        e.preventDefault();
        onClose();
      }}
      onClick={(e) => e.target === ref.current && onClose()}
    >
      <div className="modal-head">
        <h2>{title}</h2>
        <button type="button" className="link" aria-label="Close" onClick={onClose}>✕</button>
      </div>
      <div className="modal-body">{children}</div>
    </dialog>
  );
}
