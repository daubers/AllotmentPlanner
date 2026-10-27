import "@geoman-io/leaflet-geoman-free";
import "@geoman-io/leaflet-geoman-free/dist/leaflet-geoman.css";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { useEffect, useRef, useState } from "react";
import { LayersControl, MapContainer, TileLayer, useMap } from "react-leaflet";
import { api } from "../api/client";
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

function Editor({ allotmentId, canEdit, onItems, onSelect, registerActions }: Props & {
  onItems(items: Item[]): void;
  onSelect(id: number | null): void;
  registerActions(a: { update(id: number, props: Partial<FeatureProps>): void; remove(id: number): void; focus(id: number): void }): void;
}) {
  const map = useMap();
  const group = useRef(L.featureGroup());
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
      if (bounds.isValid()) map.fitBounds(bounds.pad(0.2), { maxZoom: 20 });
      else navigator.geolocation?.getCurrentPosition((p) => map.setView([p.coords.latitude, p.coords.longitude], 19));
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

  return (
    <div className="editor">
      <MapContainer center={DEFAULT_CENTRE} zoom={18} maxZoom={21} className="map">
        <LayersControl position="topright">
          <LayersControl.BaseLayer checked name="Street">
            <TileLayer attribution="&copy; OpenStreetMap contributors" url="https://tile.openstreetmap.org/{z}/{x}/{y}.png" maxNativeZoom={19} maxZoom={21} />
          </LayersControl.BaseLayer>
          <LayersControl.BaseLayer name="Satellite">
            <TileLayer attribution="Tiles &copy; Esri" url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}" maxNativeZoom={19} maxZoom={21} />
          </LayersControl.BaseLayer>
        </LayersControl>
        <Editor
          allotmentId={allotmentId}
          canEdit={canEdit}
          onItems={setItems}
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
          <form className="details" key={current.id} onSubmit={(e) => e.preventDefault()}>
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
      </aside>
    </div>
  );
}
