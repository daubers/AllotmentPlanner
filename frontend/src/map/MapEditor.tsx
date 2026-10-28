import "./leaflet-global";
import "@geoman-io/leaflet-geoman-free";
import "@geoman-io/leaflet-geoman-free/dist/leaflet-geoman.css";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { useEffect, useRef, useState } from "react";
import { LayersControl, MapContainer, TileLayer, useMap } from "react-leaflet";
import { api } from "../api/client";
import type { Task } from "../tasks/group";
import { useLayers } from "../maps/hooks";
import { initialView, layersToShow, type Box } from "../maps/status";
import { useTaskActions, useTasks } from "../tasks/hooks";
import { pinGroups, pinPopup } from "./pins";
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
type Item = { id: number; name: string; kind: Kind };
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

/** Opens the map on the plot: the drawn shapes and any visible photo layers together. Only when
 *  the allotment has neither does it fall back to where the person is. Runs once per visit, so it
 *  never fights the person panning around. */
function InitialView({ drawn, allotmentId }: { drawn: Box | null | undefined; allotmentId: number }) {
  const map = useMap();
  const layers = useLayers(allotmentId);
  const done = useRef(false);
  useEffect(() => {
    if (done.current || drawn === undefined || layers.isPending) return; // wait for both to load
    done.current = true;
    const view = initialView(drawn, layers.data);
    if (view) map.fitBounds(view, { padding: [24, 24], maxZoom: 21 });
    else navigator.geolocation?.getCurrentPosition((p) => map.setView([p.coords.latitude, p.coords.longitude], 19));
  }, [map, drawn, layers.isPending, layers.data]);
  return null;
}

function TaskPins({ group, tasks, version }: { group: React.RefObject<L.FeatureGroup>; tasks: Task[]; version: unknown }) {
  const map = useMap();
  useEffect(() => {
    const pins = L.layerGroup().addTo(map);
    const find = (id: number) => group.current.getLayers().find((l) => (l as LayerWithId).featureId === id);
    for (const { latlng, tasks: here } of pinGroups(tasks, find)) {
      const icon = L.divIcon({ className: "", html: '<span class="task-pin">📌</span>', iconSize: [22, 22], iconAnchor: [4, 22] });
      L.marker(latlng, { icon, keyboard: false, title: `${here.length} open task${here.length > 1 ? "s" : ""}` })
        .bindPopup(pinPopup(here))
        .addTo(pins);
    }
    return () => {
      pins.remove();
    };
  }, [map, group, tasks, version]);
  return null;
}

function Editor({ allotmentId, canEdit, group, onItems, onBounds, onSelect, registerActions }: Props & {
  group: React.RefObject<L.FeatureGroup>;
  onItems(items: Item[]): void;
  onBounds(bounds: Box | null): void;
  onSelect(id: number | null): void;
  registerActions(a: { update(id: number, props: Partial<FeatureProps>): void; remove(id: number): void; focus(id: number): void }): void;
}) {
  const map = useMap();
  const meta = useRef(new Map<number, Item>());

  useEffect(() => {
    const g = group.current.addTo(map);
    const publish = () => onItems([...meta.current.values()]);
    const path = { params: { path: { allotment_id: allotmentId } } };

    const attach = (layer: LayerWithId, id: number) => {
      layer.featureId = id;
      g.addLayer(layer);
      layer.on("click", () => onSelect(id));
      if (!canEdit) return;
      const save = async () => {
        const { geometry, radius_m } = layerToGeometry(layer);
        await api.PATCH("/api/v1/allotments/{allotment_id}/features/{feature_id}", {
          params: { path: { allotment_id: allotmentId, feature_id: id } },
          body: { geometry, properties: radius_m ? { radius_m } : undefined },
        });
      };
      layer.on("pm:edit", save);
      layer.on("pm:dragend", save);
    };

    const track = (f: GeoJSONFeature & { id: number }) => {
      meta.current.set(f.id, { id: f.id, name: f.properties.name ?? "", kind: (f.properties.kind as Kind) ?? "other" });
    };

    api.GET("/api/v1/allotments/{allotment_id}/features", path).then(({ data }) => {
      const features = (data?.features ?? []) as (GeoJSONFeature & { id: number })[];
      for (const f of features) {
        track(f);
        attach(featureToLayer(f) as LayerWithId, f.id);
      }
      publish();
      const bounds = g.getBounds();
      // The view is chosen by <InitialView>, which also knows about photo layers.
      onBounds(bounds.isValid() ? [[bounds.getSouth(), bounds.getWest()], [bounds.getNorth(), bounds.getEast()]] : null);
    });

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
        const created = data as unknown as GeoJSONFeature & { id: number };
        track(created);
        attach(layer, created.id);
        restyle(layer, created.properties.kind ?? "other");
        publish();
        onSelect(created.id);
      });
      map.on("pm:remove", async (e) => {
        const id = (e.layer as LayerWithId).featureId;
        if (id === undefined) return;
        await api.DELETE("/api/v1/allotments/{allotment_id}/features/{feature_id}", {
          params: { path: { allotment_id: allotmentId, feature_id: id } },
        });
        meta.current.delete(id);
        publish();
        onSelect(null);
      });
    }

    const find = (id: number) => g.getLayers().find((l) => (l as LayerWithId).featureId === id);
    registerActions({
      async update(id, props) {
        const { data } = await api.PATCH("/api/v1/allotments/{allotment_id}/features/{feature_id}", {
          params: { path: { allotment_id: allotmentId, feature_id: id } },
          body: { properties: props },
        });
        if (!data) return;
        const f = data as unknown as GeoJSONFeature & { id: number };
        track(f);
        const layer = find(id);
        if (layer) restyle(layer, f.properties.kind ?? "other");
        publish();
      },
      async remove(id) {
        await api.DELETE("/api/v1/allotments/{allotment_id}/features/{feature_id}", {
          params: { path: { allotment_id: allotmentId, feature_id: id } },
        });
        const layer = find(id);
        if (layer) g.removeLayer(layer);
        meta.current.delete(id);
        publish();
        onSelect(null);
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
    };
    // The editor is rebuilt only when the allotment or permission changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [allotmentId, canEdit, map]);

  return null;
}

export default function MapEditor({ allotmentId, canEdit }: Props) {
  const [items, setItems] = useState<Item[]>([]);
  const [selected, setSelected] = useState<number | null>(null);
  const actions = useRef<Parameters<Parameters<typeof Editor>[0]["registerActions"]>[0] | null>(null);
  const current = items.find((i) => i.id === selected);
  const group = useRef(L.featureGroup());
  const tasks = useTasks(allotmentId);
  const [drawnBounds, setDrawnBounds] = useState<Box | null | undefined>(undefined); // undefined: not loaded yet
  const taskActions = useTaskActions(allotmentId);
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
        </LayersControl>
        <PhotoLayers allotmentId={allotmentId} />
        <InitialView drawn={drawnBounds} allotmentId={allotmentId} />
        <TaskPins group={group} tasks={tasks.data ?? []} version={items} />
        <Editor
          group={group}
          allotmentId={allotmentId}
          canEdit={canEdit}
          onItems={setItems}
          onBounds={setDrawnBounds}
          onSelect={setSelected}
          registerActions={(a) => (actions.current = a)}
        />
      </MapContainer>

      <aside className="panel">
        <h2>Map features</h2>
        {!canEdit && <p className="muted">View only: ask an owner for editor access to draw.</p>}
        {items.length === 0 && <p className="muted">{canEdit ? "Use the toolbar on the map to draw a bed, path, tree…" : "Nothing drawn yet."}</p>}
        <ul className="feature-list">
          {items.map((i) => (
            <li key={i.id}>
              <button className={i.id === selected ? "active" : ""} onClick={() => { setSelected(i.id); actions.current?.focus(i.id); }}>
                <span className="swatch" style={{ background: styleFor(i.kind).color }} />
                {i.name || `Unnamed ${i.kind}`}
              </button>
            </li>
          ))}
        </ul>
        {current && (
          <form className="details" key={current.id} onSubmit={(e) => { e.preventDefault(); (document.activeElement as HTMLElement | null)?.blur(); }}>
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
            {canEdit && <button type="button" className="danger" onClick={() => actions.current?.remove(current.id)}>Delete</button>}
          </form>
        )}
        {current && (
          <section className="panel-tasks">
            <h3>Tasks here</h3>
            {featureTasks.length === 0 && <p className="muted">No open tasks.</p>}
            <ul className="tasks">
              {featureTasks.map((t) => (
                <li key={t.id} className="task">
                  <input type="checkbox" aria-label={`Complete ${t.title}`} disabled={!canEdit} checked={false} onChange={() => taskActions.complete.mutate(t.id!)} />
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
                  if (input.value.trim()) taskActions.create.mutate({ title: input.value.trim(), feature_id: current.id });
                  input.value = "";
                }}
              >
                <input name="title" placeholder="Add a task here" aria-label="New task for this feature" maxLength={200} />
                <button type="submit">Add</button>
              </form>
            )}
          </section>
        )}
      </aside>
    </div>
  );
}
