import { useState } from "react";
import { dayOf, type Media } from "./group";

/** Before/after view: drag the handle to reveal the later photo over the earlier one. */
export default function CompareSlider({ before, after }: { before: Media; after: Media }) {
  const [pos, setPos] = useState(50);
  return (
    <figure className="compare" aria-label="Before and after comparison">
      <div className="compare-stage">
        <img src={before.thumb_url ?? before.url} alt={`Before: ${dayOf(before)}`} />
        <div className="compare-top" style={{ clipPath: `inset(0 0 0 ${pos}%)` }}>
          <img src={after.thumb_url ?? after.url} alt={`After: ${dayOf(after)}`} />
        </div>
        <div className="compare-handle" style={{ left: `${pos}%` }} aria-hidden="true" />
      </div>
      <input type="range" min={0} max={100} value={pos} onChange={(e) => setPos(Number(e.target.value))} aria-label="Slide between before and after" />
      <figcaption>
        <span>{dayOf(before)}</span>
        <span>{dayOf(after)}</span>
      </figcaption>
    </figure>
  );
}
