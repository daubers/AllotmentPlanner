/** A flat sketch of a bed and what is growing in it: lon/lat in, screen points out, north up. */
export type LonLat = [number, number];
export type Frame = { width: number; height: number; project(p: LonLat): [number, number] };

const M_PER_DEG = 111_320;

export function frameFor(ring: LonLat[], width: number, height: number, padding = 12): Frame {
  const lons = ring.map((p) => p[0]);
  const lats = ring.map((p) => p[1]);
  const [minLon, maxLon, minLat, maxLat] = [Math.min(...lons), Math.max(...lons), Math.min(...lats), Math.max(...lats)];
  const kx = Math.cos((((minLat + maxLat) / 2) * Math.PI) / 180);
  const spanX = Math.max((maxLon - minLon) * kx, 1 / M_PER_DEG);
  const spanY = Math.max(maxLat - minLat, 1 / M_PER_DEG);
  const scale = Math.min((width - 2 * padding) / spanX, (height - 2 * padding) / spanY);
  const offX = (width - spanX * scale) / 2;
  const offY = (height - spanY * scale) / 2;
  return { width, height, project: ([lon, lat]) => [offX + (lon - minLon) * kx * scale, height - (offY + (lat - minLat) * scale)] };
}

/** The ring of a GeoJSON Polygon without its closing point. */
export function ringOf(polygon: { coordinates?: unknown } | null | undefined): LonLat[] {
  const ring = ((polygon?.coordinates as LonLat[][] | undefined) ?? [])[0] ?? [];
  return ring.length > 1 && ring[0][0] === ring[ring.length - 1][0] && ring[0][1] === ring[ring.length - 1][1] ? ring.slice(0, -1) : ring;
}

export const centreOf = (ring: LonLat[]): LonLat => {
  const lons = ring.map((p) => p[0]);
  const lats = ring.map((p) => p[1]);
  return [(Math.min(...lons) + Math.max(...lons)) / 2, (Math.min(...lats) + Math.max(...lats)) / 2];
};

export const PALETTE = ["#4c9a4f", "#e0a526", "#3f87c6", "#d1625b", "#8c6bb1", "#3fa5a0", "#a89a3e", "#7a7a7a"];
export const colourOf = (packetId: number | null | undefined): string => (packetId == null ? PALETTE[7] : PALETTE[packetId % PALETTE.length]);

export const areaLabel = (m2: number): string => (m2 >= 10 ? `${Math.round(m2)} m²` : `${m2.toFixed(1)} m²`);

export const STATUSES: { value: string; label: string }[] = [
  { value: "sown", label: "Sown" },
  { value: "growing", label: "Growing" },
  { value: "harvesting", label: "Harvesting" },
  { value: "finished", label: "Finished" },
  { value: "failed", label: "Failed" },
];
export const STATUS_LABEL = Object.fromEntries(STATUSES.map((s) => [s.value, s.label])) as Record<string, string>;
export const GROWING = ["sown", "growing", "harvesting"];

/** The queued request that changes a planting's state (sent when there is signal). */
export function statusRequest(allotmentId: number, plantingId: number, status: string) {
  return { method: "PATCH" as const, path: `/api/v1/allotments/${allotmentId}/plantings/${plantingId}`, body: { status } };
}
