import "./leaflet-global";
import "@geoman-io/leaflet-geoman-free";
import "@geoman-io/leaflet-geoman-free/dist/leaflet-geoman.css";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { useCallback, useEffect, useReducer, useRef, useState } from "react";
import { LayersControl, MapContainer, TileLayer, useMap } from "react-leaflet";
import { api } from "../api/client";
import type { Task } from "../tasks/group";
import { useLayers } from "../maps/hooks";
import { initialView, layersToShow, type Box } from "../maps/status";
import { useTaskActions, useTasks } from "../tasks/hooks";
import { useSuggestions } from "../suggestions/hooks";
import { suggestionBox, type Suggestion } from "../suggestions/model";
import PlantingShapes from "./PlantingShapes";
import { SuggestionShapes, SuggestionsPanel } from "./Suggestions";
import TaskDialog from "../tasks/TaskDialog";
import { History } from "./history";
import { pinGroups, pinPopup } from "./pins";
import { byStack, edgeZ, inRing, nextBeneath } from "./stack";
import {
  featureToLayer,
  KINDS,
  layerToGeometry,
  restyle,
  styleFor,
  type FeatureProps,
  type GeoJSONFeature,
  type Kind,
} from "./convert";

type Props = { allotmentId: number; canEdit: boolean };
type Item = { id: number; name: string; kind: Kind; locked: boolean; z: number };
type LayerWithId = L.Layer & { featureId?: number };

const DEFAULT_CENTRE: L.LatLngTuple = [51.5, -0.12];

/** The user's own photo maps, drawn over the base map and under the shapes. */
function PhotoLayers({ allotmentId }: { allotmentId: number }) {
  const layers = useLayers(allotmentId);
  return (
    <>
      {layersToShow(layers.data).map((l, i) => (
        <TileLayer
          key={`${l.id}-${l.tile_url}`}
          url={l.tile_url!}
          opacity={l.opacity}
          minNativeZoom={l.min_zoom}
          maxNativeZoom={l.max_zoom}
          maxZoom={22}
          bounds={[[l.bounds![1], l.bounds![0]], [l.bounds![3], l.bounds![2]]]}
          zIndex={10 + i}
        />
      ))}
    </>
  );
}

/** Opens the map on the plot: the drawn shapes, visible photo layers and suggestions waiting for review together. Only when
 *  the allotment has neither does it fall back to where the person is. Runs once per visit, so it
 *  never fights the person panning around. */
function InitialView({ drawn, allotmentId, suggestions }: { drawn: Box | null | undefined; allotmentId: number; suggestions: { pending: boolean; data: Suggestion[] | undefined } }) {
  const map = useMap();
  const layers = useLayers(allotmentId);
  const done = useRef(false);
  useEffect(() => {
    if (done.current || drawn === undefined || layers.isPending || suggestions.pending) return; // wait for all to load
    done.current = true;
    const waiting = (suggestions.data ?? []).map(suggestionBox).filter((b): b is Box => b !== null);
    const view = initialView(drawn, layers.data, waiting);
    // No animation: the opening view should just appear, and a zoom animation still running when the
    // person leaves the page makes Leaflet throw once its timer fires on the removed map.
    if (view) map.fitBounds(view, { padding: [24, 24], maxZoom: 21, animate: false });
    else navigator.geolocation?.getCurrentPosition((p) => map.setView([p.coords.latitude, p.coords.longitude], 19, { animate: false }));
  }, [map, drawn, layers.isPending, layers.data, suggestions.pending, suggestions.data]);
  return null;
}

function TaskPins({ group, tasks, version, onMove }: { group: React.RefObject<L.FeatureGroup>; tasks: Task[]; version: unknown; onMove?: (tasks: Task[], to: L.LatLng) => Promise<boolean> }) {
  const map = useMap();
  useEffect(() => {
    const pins = L.layerGroup().addTo(map);
    const find = (id: number) => group.current.getLayers().find((l) => (l as LayerWithId).featureId === id);
    for (const { latlng, tasks: here } of pinGroups(tasks, find)) {
      const icon = L.divIcon({ className: "", html: '<span class="task-pin">📌</span>', iconSize: [22, 22], iconAnchor: [4, 22] });
      const marker = L.marker(latlng, { icon, keyboard: false, draggable: !!onMove, title: `${here.length} open task${here.length > 1 ? "s" : ""}` })
        .bindPopup(pinPopup(here))
        .addTo(pins);
      // A dropped pin is saved (and can be undone); if the save fails it goes back where it was.
      marker.on("dragend", async () => {
        if (!(await onMove!(here, marker.getLatLng()))) marker.setLatLng(latlng);
      });
    }
    return () => {
      pins.remove();
    };
  }, [map, group, tasks, version, onMove]);
  return null;
}

type Shape = { geometry: GeoJSONFeature["geometry"]; radius_m: number | null };
type Snapshot = { geometry: Shape["geometry"]; properties: Partial<FeatureProps> };
type Actions = {
  update(id: number, props: Partial<FeatureProps>): void;
  remove(id: number): void;
  focus(id: number): void;
  add(features: (GeoJSONFeature & { id: number })[]): void;
  arrange(id: number, edge: "top" | "bottom"): void;
};

const sameShape = (a: Shape, b: Shape) => a.radius_m === b.radius_m && JSON.stringify(a.geometry) === JSON.stringify(b.geometry);
const asFeature = (data: unknown) => data as GeoJSONFeature & { id: number };

/** Is this point on the layer? Areas by containment, lines and pins by a few pixels' tolerance. */
function covers(map: L.Map, layer: L.Layer | undefined, at: L.LatLng): boolean {
  if (layer instanceof L.Circle) return map.distance(at, layer.getLatLng()) <= layer.getRadius();
  if (layer instanceof L.Polygon) {
    const ring = (layer.getLatLngs() as L.LatLng[][])[0].map((p) => [p.lng, p.lat] as [number, number]);
    return inRing([at.lng, at.lat], ring);
  }
  if (layer instanceof L.Polyline) {
    const pts = (layer.getLatLngs() as L.LatLng[]).map((p) => map.latLngToLayerPoint(p));
    const here = map.latLngToLayerPoint(at);
    return pts.slice(1).some((p, i) => L.LineUtil.pointToSegmentDistance(here, pts[i], p) <= 8);
  }
  if (layer instanceof L.Marker) return map.latLngToLayerPoint(layer.getLatLng()).distanceTo(map.latLngToLayerPoint(at)) <= 14;
  return false;
}

function Editor({ allotmentId, canEdit, group, history, selected, onItems, onBounds, onSelect, registerActions }: Props & {
  group: React.RefObject<L.FeatureGroup>;
  history: History;
  selected: number | null;
  onItems(items: Item[]): void;
  onBounds(bounds: Box | null): void;
  onSelect(id: number | null): void;
  registerActions(a: Actions): void;
}) {
  const map = useMap();
  const meta = useRef(new Map<number, Item>());
  const selectedRef = useRef(selected);
  selectedRef.current = selected;

  useEffect(() => {
    const g = group.current.addTo(map);
    const publish = () => onItems([...meta.current.values()]);
    const path = { params: { path: { allotment_id: allotmentId } } };
    const saved = new Map<number, Shape>(); // what the server has, for undo
    const alias = new Map<number, number>(); // a deleted feature that undo brought back has a new id

    const resolve = (id: number) => {
      let n = id;
      while (alias.has(n)) n = alias.get(n)!;
      return n;
    };
    const find = (id: number) => g.getLayers().find((l) => (l as LayerWithId).featureId === id);
    const nameOf = (id: number) => meta.current.get(id)?.name || meta.current.get(id)?.kind || "item";
    const patch = (id: number, body: { geometry?: Shape["geometry"]; properties?: Partial<FeatureProps> }) =>
      api.PATCH("/api/v1/allotments/{allotment_id}/features/{feature_id}", {
        params: { path: { allotment_id: allotmentId, feature_id: id } },
        body,
      });

    /** Draws the features bottom to top: the person's own order, then areas under the things on them. */
    const restack = () => {
      for (const item of [...meta.current.values()].sort(byStack)) {
        const layer = find(item.id);
        if (layer instanceof L.Path) layer.bringToFront();
      }
    };
    const under = (at: L.LatLng) =>
      [...meta.current.values()].filter((i) => covers(map, find(i.id), at)).sort(byStack).reverse().map((i) => i.id);

    const track = (f: GeoJSONFeature & { id: number }) => {
      const p = f.properties;
      meta.current.set(f.id, { id: f.id, name: p.name ?? "", kind: (p.kind as Kind) ?? "other", locked: !!p.locked, z: p.z ?? 0 });
    };

    const attach = (layer: LayerWithId, id: number) => {
      layer.featureId = id;
      g.addLayer(layer);
      saved.set(id, layerToGeometry(layer));
      // Alt-click walks down through whatever is stacked under the pointer.
      layer.on("click", (e) => {
        const alt = (e as L.LeafletMouseEvent).originalEvent?.altKey;
        onSelect(alt ? (nextBeneath(under((e as L.LeafletMouseEvent).latlng), selectedRef.current) ?? id) : id);
      });
      if (!canEdit || meta.current.get(id)?.locked) return;
      const save = async () => {
        const now = layerToGeometry(layer);
        const before = saved.get(id);
        if (before && sameShape(before, now)) return;
        const { data } = await patch(id, { geometry: now.geometry, properties: now.radius_m ? { radius_m: now.radius_m } : undefined });
        if (!data) return;
        saved.set(id, now);
        if (before) {
          history.record({ label: `Move ${nameOf(id)}`, target: () => resolve(id), undo: () => writeShape(id, before), redo: () => writeShape(id, now) });
        }
      };
      layer.on("pm:edit", save);
      layer.on("pm:dragend", save);
    };

    /** (Re)draws one feature from what the server says, replacing any layer it already had. */
    const place = (f: GeoJSONFeature & { id: number }) => {
      const old = find(f.id);
      if (old) g.removeLayer(old);
      track(f);
      attach(featureToLayer(f) as LayerWithId, f.id);
    };

    const writeShape = async (id: number, shape: Shape) => {
      const { data } = await patch(resolve(id), { geometry: shape.geometry, properties: shape.radius_m ? { radius_m: shape.radius_m } : undefined });
      if (!data) throw new Error("not saved");
      place(asFeature(data));
      restack();
      publish();
    };

    const setProps = async (id: number, props: Partial<FeatureProps>) => {
      const { data } = await patch(id, { properties: props });
      if (!data) throw new Error("not saved");
      const f = asFeature(data);
      const layer = find(id);
      if (!layer || meta.current.get(id)?.locked !== !!f.properties.locked) place(f);
      else {
        track(f);
        restyle(layer, f.properties.kind ?? "other");
      }
      restack();
      publish();
    };

    const snapshotOf = (id: number, layer: L.Layer | undefined = find(id)): Snapshot | null => {
      const m = meta.current.get(id);
      if (!layer || !m) return null;
      const { geometry, radius_m } = layerToGeometry(layer);
      return { geometry, properties: { name: m.name, kind: m.kind, locked: m.locked, z: m.z, ...(radius_m ? { radius_m } : {}) } };
    };

    const create = async (snap: Snapshot) => {
      const { data } = await api.POST("/api/v1/allotments/{allotment_id}/features", {
        ...path,
        body: { type: "Feature", geometry: snap.geometry, properties: snap.properties },
      });
      if (!data) throw new Error("not saved");
      const f = asFeature(data);
      place(f);
      restack();
      publish();
      return f.id;
    };

    const destroy = async (id: number) => {
      const { error } = await api.DELETE("/api/v1/allotments/{allotment_id}/features/{feature_id}", {
        params: { path: { allotment_id: allotmentId, feature_id: id } },
      });
      if (error) throw new Error("not deleted");
      const layer = find(id);
      if (layer) g.removeLayer(layer);
      meta.current.delete(id);
      saved.delete(id);
      publish();
      onSelect(null);
    };

    /** Brings a deleted feature back; it gets a new id, which older history steps follow. */
    const revive = async (id: number, snap: Snapshot) => {
      const old = resolve(id);
      alias.set(old, await create(snap));
    };

    api.GET("/api/v1/allotments/{allotment_id}/features", path).then(({ data }) => {
      const features = (data?.features ?? []) as (GeoJSONFeature & { id: number })[];
      for (const f of features) place(f);
      restack();
      publish();
      const bounds = g.getBounds();
      // The view is chosen by <InitialView>, which also knows about photo layers.
      onBounds(bounds.isValid() ? [[bounds.getSouth(), bounds.getWest()], [bounds.getNorth(), bounds.getEast()]] : null);
    });

    const removed = (id: number, snap: Snapshot | null, label: string) => {
      if (!snap) return;
      history.record({ label: `Delete ${label}`, target: () => resolve(id), undo: () => revive(id, snap), redo: () => destroy(resolve(id)) });
    };

    if (canEdit) {
      map.pm.addControls({
        position: "topleft",
        drawCircleMarker: false,
        drawText: false,
        cutPolygon: false,
        rotateMode: false,
      });
      map.pm.setGlobalOptions({ pathOptions: styleFor("other") });
      map.on("pm:create", async (e) => {
        const layer = e.layer as LayerWithId;
        map.removeLayer(layer); // re-added by attach() once the server has assigned an id
        const { geometry, radius_m } = layerToGeometry(layer);
        const { data, error } = await api.POST("/api/v1/allotments/{allotment_id}/features", {
          ...path,
          body: { type: "Feature", geometry, properties: radius_m ? { radius_m } : {} },
        });
        if (!data) return alert(`Could not save: ${(error as { message?: string })?.message ?? "unknown error"}`);
        const created = asFeature(data);
        track(created);
        attach(layer, created.id);
        restyle(layer, created.properties.kind ?? "other");
        restack();
        publish();
        onSelect(created.id);
        const snap = snapshotOf(created.id, layer);
        if (snap) {
          history.record({ label: `Add ${nameOf(created.id)}`, target: () => resolve(created.id), undo: () => destroy(resolve(created.id)), redo: () => revive(created.id, snap) });
        }
      });
      map.on("pm:remove", async (e) => {
        const id = (e.layer as LayerWithId).featureId;
        if (id === undefined) return;
        const snap = snapshotOf(id, e.layer);
        const label = nameOf(id);
        const { error } = await api.DELETE("/api/v1/allotments/{allotment_id}/features/{feature_id}", {
          params: { path: { allotment_id: allotmentId, feature_id: id } },
        });
        if (error) return void map.addLayer(e.layer); // the server refused: put it back
        meta.current.delete(id);
        saved.delete(id);
        publish();
        onSelect(null);
        removed(id, snap, label);
      });
    }

    const update = async (id: number, props: Partial<FeatureProps>) => {
      const was = meta.current.get(id);
      if (!was) return;
      const before = Object.fromEntries(Object.keys(props).map((k) => [k, was[k as keyof Item]])) as Partial<FeatureProps>;
      try {
        await setProps(id, props);
      } catch {
        return;
      }
      const label = "locked" in props ? `${props.locked ? "Lock" : "Unlock"} ${was.name || was.kind}` : "z" in props ? `Reorder ${was.name || was.kind}` : `Edit ${was.name || was.kind}`;
      history.record({ label, target: () => resolve(id), undo: () => setProps(resolve(id), before), redo: () => setProps(resolve(id), props) });
    };

    registerActions({
      update,
      async remove(id) {
        const snap = snapshotOf(id);
        const label = nameOf(id);
        try {
          await destroy(id);
        } catch {
          return;
        }
        removed(id, snap, label);
      },
      arrange(id, edge) {
        const z = edgeZ([...meta.current.values()], id, edge);
        if (z !== meta.current.get(id)?.z) void update(id, { z });
      },
      add(features) {
        for (const f of features) place(f);
        restack();
        publish();
      },
      focus(id) {
        const layer = find(id) as (L.Layer & { getBounds?(): L.LatLngBounds; getLatLng?(): L.LatLng }) | undefined;
        if (layer?.getBounds) map.fitBounds(layer.getBounds().pad(0.5));
        else if (layer?.getLatLng) map.setView(layer.getLatLng(), 20);
      },
    });

    return () => {
      map.off("pm:create");
      map.off("pm:remove");
      if (canEdit) map.pm.removeControls();
      g.clearLayers().remove();
      meta.current.clear();
      history.clear();
    };
    // The editor is rebuilt only when the allotment or permission changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [allotmentId, canEdit, map]);

  return null;
}

export default function MapEditor({ allotmentId, canEdit }: Props) {
  const [items, setItems] = useState<Item[]>([]);
  const [selected, setSelected] = useState<number | null>(null);
  const suggestions = useSuggestions(allotmentId, canEdit);
  const [ticked, setTicked] = useState<Set<number>>(new Set());
  const [focusedSuggestion, setFocusedSuggestion] = useState<number | null>(null);
  const actions = useRef<Actions | null>(null);
  const history = useRef(new History()).current;
  const [, redraw] = useReducer((n: number) => n + 1, 0);
  useEffect(() => history.subscribe(redraw), [history]);
  useEffect(() => {
    if (!canEdit) return;
    // Ctrl/Cmd+Z undoes, with Shift (or Ctrl+Y) redoes: unless the person is typing in a field.
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement | null)?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || !(e.metaKey || e.ctrlKey)) return;
      const key = e.key.toLowerCase();
      if (key === "z" && !e.shiftKey) void history.undo();
      else if ((key === "z" && e.shiftKey) || key === "y") void history.redo();
      else return;
      e.preventDefault();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [canEdit, history]);
  const current = items.find((i) => i.id === selected);
  // With something selected, the buttons act on that object alone; otherwise on the latest change anywhere.
  const undoLabel = selected === null ? history.undoLabel : history.undoLabelFor(selected);
  const redoLabel = selected === null ? history.redoLabel : history.redoLabelFor(selected);
  const group = useRef(L.featureGroup());
  const tasks = useTasks(allotmentId);
  const [drawnBounds, setDrawnBounds] = useState<Box | null | undefined>(undefined); // undefined: not loaded yet
  const taskActions = useTaskActions(allotmentId);
  const updateTask = taskActions.update.mutateAsync;
  /** Moves task pins to a new point, as one undoable step. A task with no point of its own goes back to following its feature. */
  const { complete, reopen, create, remove } = taskActions;
  /** Ticks a task off, as an undoable step. */
  const completeTask = async (t: Task) => {
    try {
      await complete.mutateAsync(t.id!);
    } catch {
      return;
    }
    history.record({ label: `Complete ${t.title}`, undo: async () => void (await reopen.mutateAsync(t.id!)), redo: async () => void (await complete.mutateAsync(t.id!)) });
  };
  /** Adds a task, as an undoable step. Redo makes it again, which gives it a new id that undo then follows. */
  const addTask = async (body: { title: string; feature_id: number }) => {
    let id: number;
    try {
      id = (await create.mutateAsync(body)).id!;
    } catch {
      return;
    }
    history.record({
      label: `Add task ${body.title}`,
      undo: async () => void (await remove.mutateAsync(id)),
      redo: async () => void (id = (await create.mutateAsync(body)).id!),
    });
  };
  const moveTasks = useCallback(
    async (moved: Task[], to: L.LatLng) => {
      const point = { type: "Point", coordinates: [to.lng, to.lat] };
      const was = moved.map((t) => ({ id: t.id!, location: (t.location ?? null) as Record<string, unknown> | null }));
      const put = (locations: (Record<string, unknown> | null)[]) => async () => {
        await Promise.all(was.map((t, i) => updateTask({ id: t.id, body: { location: locations[i] } })));
      };
      try {
        await put(was.map(() => point))();
      } catch {
        return false;
      }
      const n = moved.length;
      history.record({ label: `Move ${n > 1 ? `${n} task pins` : "task pin"}`, undo: put(was.map((t) => t.location)), redo: put(was.map(() => point)) });
      return true;
    },
    [updateTask, history],
  );
  const [taskDialog, setTaskDialog] = useState<number | null>(null);
  const featureTasks = (tasks.data ?? []).filter((t) => t.feature_id === selected && t.status !== "done");

  return (
    <div className="editor">
      <MapContainer center={DEFAULT_CENTRE} zoom={18} maxZoom={22} className="map">
        <LayersControl position="topright">
          <LayersControl.BaseLayer checked name="Street">
            <TileLayer attribution="&copy; OpenStreetMap contributors" url="https://tile.openstreetmap.org/{z}/{x}/{y}.png" maxNativeZoom={19} maxZoom={21} />
          </LayersControl.BaseLayer>
          <LayersControl.BaseLayer name="Satellite">
            <TileLayer attribution="Tiles &copy; Esri" url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}" maxNativeZoom={19} maxZoom={21} />
          </LayersControl.BaseLayer>
          <PlantingShapes allotmentId={allotmentId} />
        </LayersControl>
        <PhotoLayers allotmentId={allotmentId} />
        <SuggestionShapes allotmentId={allotmentId} suggestions={suggestions.data ?? []} ticked={ticked} focused={focusedSuggestion} />
        <InitialView drawn={drawnBounds} allotmentId={allotmentId} suggestions={{ pending: canEdit && suggestions.isPending, data: suggestions.data }} />
        <TaskPins group={group} tasks={tasks.data ?? []} version={items} onMove={canEdit ? moveTasks : undefined} />
        <Editor
          group={group}
          allotmentId={allotmentId}
          canEdit={canEdit}
          history={history}
          selected={selected}
          onItems={setItems}
          onBounds={setDrawnBounds}
          onSelect={setSelected}
          registerActions={(a) => (actions.current = a)}
        />
      </MapContainer>

      <aside className="panel">
        {canEdit && (
          <SuggestionsPanel
            allotmentId={allotmentId}
            suggestions={suggestions.data ?? []}
            ticked={ticked}
            setTicked={setTicked}
            focused={focusedSuggestion}
            setFocused={setFocusedSuggestion}
            onAccepted={(features) => actions.current?.add(features as Parameters<NonNullable<typeof actions.current>["add"]>[0])}
          />
        )}
        <h2>Map features</h2>
        {canEdit && (
          <div className="history-buttons">
            <button type="button" disabled={!undoLabel} title={undoLabel ? `Undo: ${undoLabel}${selected === null ? " (Ctrl/⌘+Z)" : ""}` : "Nothing to undo"} onClick={() => void history.undo(selected ?? undefined)}>
              ↶ Undo
            </button>
            <button type="button" disabled={!redoLabel} title={redoLabel ? `Redo: ${redoLabel}${selected === null ? " (Ctrl/⌘+Shift+Z)" : ""}` : "Nothing to redo"} onClick={() => void history.redo(selected ?? undefined)}>
              ↷ Redo
            </button>
            {undoLabel && <span className="muted">{undoLabel}</span>}
          </div>
        )}
        {!canEdit && <p className="muted">View only: ask an owner for editor access to draw.</p>}
        {items.length === 0 && <p className="muted">{canEdit ? "Use the toolbar on the map to draw a bed, path, tree…" : "Nothing drawn yet."}</p>}
        <ul className="feature-list">
          {items.map((i) => (
            <li key={i.id}>
              <button className={i.id === selected ? "active" : ""} onClick={() => { setSelected(i.id); actions.current?.focus(i.id); }}>
                <span className="swatch" style={{ background: styleFor(i.kind).color }} />
                {i.locked && <span aria-label="Locked" title="Locked">🔒</span>}
                {i.name || `Unnamed ${i.kind}`}
              </button>
            </li>
          ))}
        </ul>
        {items.length > 1 && <p className="muted hint">Alt-click on the map to pick what is underneath.</p>}
        {current && (
          <form className="details" key={`${current.id}:${current.name}`} onSubmit={(e) => { e.preventDefault(); (document.activeElement as HTMLElement | null)?.blur(); }}>
            <label>
              Name
              <input defaultValue={current.name} disabled={!canEdit} onBlur={(e) => e.target.value !== current.name && actions.current?.update(current.id, { name: e.target.value })} />
            </label>
            <label>
              Kind
              <select value={current.kind} disabled={!canEdit} onChange={(e) => actions.current?.update(current.id, { kind: e.target.value as Kind })}>
                {KINDS.map((k) => <option key={k}>{k}</option>)}
              </select>
            </label>
            {canEdit && (
              <label className="check">
                <input type="checkbox" checked={current.locked} onChange={(e) => actions.current?.update(current.id, { locked: e.target.checked })} />
                Lock position
              </label>
            )}
            {canEdit && (
              <div className="arrange">
                <button type="button" onClick={() => actions.current?.arrange(current.id, "top")}>Bring to front</button>
                <button type="button" onClick={() => actions.current?.arrange(current.id, "bottom")}>Send to back</button>
              </div>
            )}
            {canEdit && (
              <button type="button" className="danger" disabled={current.locked} title={current.locked ? "Unlock it to delete" : undefined} onClick={() => actions.current?.remove(current.id)}>
                Delete
              </button>
            )}
          </form>
        )}
        {current && (
          <section className="panel-tasks">
            <h3>Tasks here</h3>
            {featureTasks.length === 0 && <p className="muted">No open tasks.</p>}
            <ul className="tasks">
              {featureTasks.map((t) => (
                <li key={t.id} className="task">
                  <input type="checkbox" aria-label={`Complete ${t.title}`} disabled={!canEdit} checked={false} onChange={() => void completeTask(t)} />
                  <div className="task-main"><span className="task-title">{t.title}</span>{t.due_date && <span className="task-meta">📅 {t.due_date}</span>}</div>
                </li>
              ))}
            </ul>
            {canEdit && (
              <form
                className="inline"
                onSubmit={(e) => {
                  e.preventDefault();
                  const input = e.currentTarget.elements.namedItem("title") as HTMLInputElement;
                  if (input.value.trim()) void addTask({ title: input.value.trim(), feature_id: current.id });
                  input.value = "";
                }}
              >
                <input name="title" placeholder="Add a task here" aria-label="New task for this feature" maxLength={200} />
                <button type="submit">Add</button>
                <button type="button" className="secondary" onClick={() => setTaskDialog(current.id)}>More…</button>
              </form>
            )}
          </section>
        )}
        {taskDialog !== null && (
          <TaskDialog allotmentId={allotmentId} canEdit={canEdit} place={{ feature_id: taskDialog }} onClose={() => setTaskDialog(null)} />
        )}
      </aside>
    </div>
  );
}
