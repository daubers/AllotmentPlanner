import { useEffect, useMemo, useRef, useState } from "react";
import { useIsMutating, useMutationState } from "@tanstack/react-query";
import type L from "leaflet";
import { Circle, Polygon, Tooltip } from "react-leaflet";
import { colourFor, KINDS } from "./kinds";
import { patchKey, useSuggestionActions } from "../suggestions/hooks";
import { layerToGeometry } from "./convert";
import { confidenceWord, mergeTicks, photosOf, seenIn, shapeOf, type Sighting, type Suggestion } from "../suggestions/model";
import { SightingDialog, SightingPhoto } from "../suggestions/SightingPhoto";

/** Put a layer's label back on the layer after it was moved or reshaped. */
function replaceLabel(layer: L.Layer) {
  const l = layer as L.Layer & { closeTooltip(): void; openTooltip(): void };
  l.closeTooltip();
  l.openTooltip();
}

/** One suggestion on the map. Its shape is given to Leaflet only when the saved shape changes, so
 *  re-rendering (hovering the list, say) never puts a moved footprint back; moving or reshaping it
 *  with the editing tools saves the new shape. */
function SuggestionShape({ suggestion: s, on, focused, onMove }: { suggestion: Suggestion; on: boolean; focused: boolean; onMove(id: number, change: { geometry: Record<string, unknown>; radius_m?: number }): void }) {
  const shape = useMemo(() => shapeOf(s), [s.geometry, s.radius_m]); // eslint-disable-line react-hooks/exhaustive-deps
  if (!shape) return null;
  const options = {
    color: colourFor(s.kind),
    weight: focused ? 4 : 2,
    dashArray: "6 6",
    fillOpacity: on ? 0.25 : 0.05,
    opacity: on ? 1 : 0.5,
  };
  const save = (e: { target: L.Layer }) => {
    const { geometry, radius_m } = layerToGeometry(e.target);
    onMove(s.id!, { geometry: geometry as unknown as Record<string, unknown>, ...(radius_m ? { radius_m } : {}) });
    replaceLabel(e.target);
  };
  // Geoman's events are not in Leaflet's types. The label follows while the shape is dragged or its
  // corners are, not just once it is let go.
  const eventHandlers = {
    "pm:edit": save,
    "pm:dragend": save,
    "pm:drag": (e: { target: L.Layer }) => replaceLabel(e.target),
    "pm:markerdrag": (e: { target: L.Layer }) => replaceLabel(e.target),
  } as unknown as L.LeafletEventHandlerFnMap;
  const label = <Tooltip permanent direction="top" className="suggestion-label">{s.name}</Tooltip>;
  return shape.type === "circle" ? (
    <Circle center={shape.centre} radius={shape.radius} pathOptions={options} eventHandlers={eventHandlers}>{label}</Circle>
  ) : (
    <Polygon positions={shape.ring} pathOptions={options} eventHandlers={eventHandlers}>{label}</Polygon>
  );
}

/** The pending suggestions drawn on the map as dashed outlines, so they can be told from real shapes. */
export function SuggestionShapes({ allotmentId, suggestions, ticked, focused }: { allotmentId: number; suggestions: Suggestion[]; ticked: Set<number>; focused: number | null }) {
  const { patch } = useSuggestionActions(allotmentId);
  const move = (id: number, change: { geometry: Record<string, unknown>; radius_m?: number }) => patch.mutate({ id, ...change });
  return (
    <>
      {suggestions.map((s) => (
        <SuggestionShape key={s.id} suggestion={s} on={ticked.has(s.id!)} focused={focused === s.id} onMove={move} />
      ))}
    </>
  );
}

/** Says whether changes to the found items are saved: saving, saved, or what went wrong. */
export function SaveStatus({ allotmentId }: { allotmentId: number }) {
  const saving = useIsMutating({ mutationKey: patchKey(allotmentId) }) > 0;
  const last = useMutationState({
    filters: { mutationKey: patchKey(allotmentId) },
    select: (m) => ({ status: m.state.status, error: m.state.error as Error | null }),
  }).at(-1);
  if (saving) return <p role="status" className="save-status muted">Saving…</p>;
  if (last?.status === "error") return <p role="alert" className="save-status error">Not saved: {last.error?.message ?? "something went wrong"}. The change was undone.</p>;
  if (last?.status === "success") return <p role="status" className="save-status saved">✓ All changes saved</p>;
  return null;
}

/** Review what was recognised: tick, rename or retype, then add to the map or dismiss. */
export function SuggestionsPanel({ allotmentId, suggestions, ticked, setTicked, focused, setFocused, onAccepted }: {
  allotmentId: number;
  suggestions: Suggestion[];
  ticked: Set<number>;
  setTicked(next: Set<number>): void;
  focused: number | null;
  setFocused(id: number | null): void;
  onAccepted(features: unknown[]): void;
}) {
  const actions = useSuggestionActions(allotmentId);
  const [error, setError] = useState<string | null>(null);
  const known = useRef(new Set<number>());
  const [enlarged, setEnlarged] = useState<{ sighting: Sighting; name: string } | null>(null);

  // New suggestions arrive ticked if likely; the person's own choices on existing ones are kept.
  useEffect(() => {
    setTicked(mergeTicks(ticked, known.current, suggestions));
    known.current = new Set(suggestions.map((s) => s.id!));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [suggestions]);

  if (!suggestions.length) return null;
  const chosen = suggestions.filter((s) => ticked.has(s.id!)).map((s) => s.id!);

  async function run(action: () => Promise<unknown>) {
    try {
      await action();
      setError(null);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  const toggle = (id: number) => {
    const next = new Set(ticked);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setTicked(next);
  };

  return (
    <section className="suggestions" aria-label="Suggestions from photos">
      <h2>Found in your photos <span className="badge">{suggestions.length}</span></h2>
      <p className="muted">Check each one, fix the name or type, drag a footprint if it is in the wrong place, then add the ticked ones to the map.</p>
      <SaveStatus allotmentId={allotmentId} />
      <ul className="suggestion-list">
        {suggestions.map((s) => (
          <li key={s.id} className={focused === s.id ? "focused" : ""} onMouseEnter={() => setFocused(s.id!)} onMouseLeave={() => setFocused(null)}>
            <label className="check">
              <input type="checkbox" checked={ticked.has(s.id!)} onChange={() => toggle(s.id!)} aria-label={`Add ${s.name}`} />
              <span className="swatch" style={{ background: colourFor(s.kind) }} />
              <input
                className="suggestion-name"
                defaultValue={s.name}
                key={`${s.id}-${s.name}`}
                aria-label={`Name of ${s.name}`}
                onBlur={(e) => e.target.value.trim() && e.target.value !== s.name && void run(() => actions.patch.mutateAsync({ id: s.id!, name: e.target.value.trim() }))}
              />
            </label>
            <SuggestionPhotos suggestion={s} onOpen={(sighting) => setEnlarged({ sighting, name: s.name! })} />
            <div className="suggestion-meta">
              <select value={s.kind} aria-label={`Type of ${s.name}`} onChange={(e) => void run(() => actions.patch.mutateAsync({ id: s.id!, kind: e.target.value as (typeof KINDS)[number] }))}>
                {KINDS.map((k) => <option key={k} value={k}>{k}</option>)}
              </select>
              <span className={`conf ${confidenceWord(s.confidence)}`}>{confidenceWord(s.confidence)}</span>
              <span className="muted">{seenIn(s)}</span>
            </div>
          </li>
        ))}
      </ul>
      {error && <p role="alert" className="error">{error}</p>}
      {enlarged && <SightingDialog sighting={enlarged.sighting} name={enlarged.name} onClose={() => setEnlarged(null)} />}
      <div className="inline">
        <button
          type="button"
          disabled={!chosen.length || actions.accept.isPending}
          onClick={() => void run(async () => onAccepted(await actions.accept.mutateAsync(chosen)))}
        >
          Add {chosen.length} to the map
        </button>
        <button type="button" className="secondary" disabled={!chosen.length || actions.dismiss.isPending} onClick={() => void run(() => actions.dismiss.mutateAsync(chosen))}>
          Dismiss ticked
        </button>
      </div>
    </section>
  );
}

/** Thumbnails of the photos that showed this object, with it outlined; click one to see it large. */
function SuggestionPhotos({ suggestion, onOpen }: { suggestion: Suggestion; onOpen(s: Sighting): void }) {
  const { shown, more } = photosOf(suggestion);
  if (!shown.length) return null;
  return (
    <div className="sighting-strip">
      {shown.map((x) => (
        <button key={x.media_id} type="button" className="sighting-thumb" aria-label={`See ${suggestion.name} in a photo`} onClick={() => onOpen(x)}>
          <SightingPhoto sighting={x} alt="" />
        </button>
      ))}
      {more > 0 && <span className="muted">+{more} more</span>}
    </div>
  );
}
