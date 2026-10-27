import L from "leaflet";
import type { Task } from "../tasks/group";

type Locatable = L.Layer & { getBounds?(): L.LatLngBounds; getLatLng?(): L.LatLng };

/** Where a task's pin goes: its own point, else the centre of the feature it is pinned to. */
export function taskLatLng(task: Task, findLayer: (featureId: number) => L.Layer | undefined): L.LatLng | null {
  const loc = task.location as { coordinates?: [number, number] } | null | undefined;
  if (loc?.coordinates) return L.latLng(loc.coordinates[1], loc.coordinates[0]);
  if (task.feature_id == null) return null;
  const layer = findLayer(task.feature_id) as Locatable | undefined;
  // Markers and circles first: Circle.getBounds() needs the layer to be on a map.
  if (layer?.getLatLng) return layer.getLatLng();
  if (layer?.getBounds) return layer.getBounds().getCenter();
  return null;
}

/** Open tasks that have a position, grouped by position so overlapping pins become one. */
export function pinGroups(tasks: Task[], findLayer: (featureId: number) => L.Layer | undefined) {
  const groups = new Map<string, { latlng: L.LatLng; tasks: Task[] }>();
  for (const t of tasks) {
    if (t.status === "done") continue;
    const latlng = taskLatLng(t, findLayer);
    if (!latlng) continue;
    const key = `${latlng.lat.toFixed(7)},${latlng.lng.toFixed(7)}`;
    const group = groups.get(key) ?? { latlng, tasks: [] };
    group.tasks.push(t);
    groups.set(key, group);
  }
  return [...groups.values()];
}

/** Popup built from DOM nodes (task titles are user text, so never injected as HTML). */
export function pinPopup(tasks: Task[]): HTMLElement {
  const root = document.createElement("div");
  const list = document.createElement("ul");
  list.style.cssText = "margin:0;padding-left:1.1rem";
  for (const t of tasks) {
    const li = document.createElement("li");
    li.textContent = t.due_date ? `${t.title} (${t.due_date})` : (t.title ?? "");
    list.append(li);
  }
  root.append(list);
  return root;
}
