import { useEffect, useRef } from "react";
import { outlinePoints, type Sighting } from "./model";

/** A photo with the found object outlined. The outline is in 0..1 of the picture, so it lines up at
 *  any size; the box takes the photo's own shape so the two stay together. */
export function SightingPhoto({ sighting, full = false, alt }: { sighting: Sighting; full?: boolean; alt: string }) {
  const src = full ? sighting.url : (sighting.thumb_url ?? sighting.url);
  const ratio = sighting.width && sighting.height ? `${sighting.width} / ${sighting.height}` : undefined;
  return (
    <span className="sighting-photo" style={{ aspectRatio: ratio }}>
      <img src={src} alt={alt} loading="lazy" />
      <svg viewBox="0 0 1 1" preserveAspectRatio="none" aria-hidden="true">
        <polygon points={outlinePoints(sighting.outline)} vectorEffect="non-scaling-stroke" />
      </svg>
    </span>
  );
}

/** The photo large, for checking the outline is on the right thing. */
export function SightingDialog({ sighting, name, onClose }: { sighting: Sighting; name: string; onClose(): void }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    ref.current?.showModal();
  }, []);
  return (
    <dialog
      ref={ref}
      className="lightbox sighting-dialog"
      aria-label={`${name} in a photo`}
      onCancel={(e) => {
        e.preventDefault();
        onClose();
      }}
      onClose={onClose}
      onClick={(e) => e.target === ref.current && onClose()}
    >
      <SightingPhoto sighting={sighting} full alt={`${name}, outlined in the photo`} />
      <div className="inline">
        <button type="button" className="secondary" onClick={onClose}>Close</button>
      </div>
    </dialog>
  );
}
