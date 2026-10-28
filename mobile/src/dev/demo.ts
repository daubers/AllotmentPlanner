/** Fake server answers for previewing the screens in a browser (`EXPO_PUBLIC_DEMO=1 npx expo start --web`).
 *  Does nothing unless that variable is set, so a normal build never uses it. */

const M_LAT = 111_195;
const M_LNG = 69_000;
const at = (x: number, y: number): [number, number] => [-1.1 + x / M_LNG, 51.6 + y / M_LAT];
const polygon = (...pts: [number, number][]) => {
  const ring = pts.map(([x, y]) => at(x, y));
  return { type: "Polygon", coordinates: [[...ring, ring[0]]] };
};

const BED = polygon([0, 0], [10.6, 0.4], [10.1, 5.7], [-0.3, 4.6]);
const BED_FIXED = polygon([0, 0], [10, 0], [10, 5], [0, 5]);
const SHED = polygon([14, 1], [17.2, 1.3], [17, 4.2], [14.1, 4]);
const POND = { type: "Point", coordinates: at(22, 6) };

const item = (id: number, fid: number, name: string, kind: string, a: number, b: number, drawn: number | null, value: number | null, extra = {}) => ({
  id,
  feature_id: fid,
  feature_name: name,
  feature_kind: "bed",
  kind,
  a,
  b,
  label: kind === "radius" ? "Radius" : `${a + 1} to ${b + 1}`,
  drawn_m: drawn,
  value_m: value,
  note: "",
  skipped: false,
  stale: false,
  ...extra,
});

let items = [
  item(1, 1, "Raised bed 1", "edge", 0, 1, 10.61, 10),
  item(2, 1, "Raised bed 1", "edge", 1, 2, 5.31, 5),
  item(3, 1, "Raised bed 1", "edge", 2, 3, 10.4, null),
  item(4, 1, "Raised bed 1", "edge", 3, 0, 4.61, null),
  item(5, 1, "Raised bed 1", "diagonal", 0, 2, 12.1, null),
  item(6, 2, "Shed", "edge", 0, 1, 3.2, 3.2),
  item(7, 2, "Shed", "edge", 1, 2, 2.9, 2.9),
  item(8, 2, "Shed", "edge", 2, 3, 2.9, 2.85),
  item(9, 2, "Shed", "edge", 3, 0, 3.0, 3.0),
  item(10, 2, "Shed", "diagonal", 0, 2, 4.3, 4.25),
  item(11, 3, "Pond", "radius", 0, 0, 2.0, null),
];

function checklist() {
  const progress = (id: number, name: string, corners: number) => {
    const mine = items.filter((i) => i.feature_id === id && !i.skipped && !i.stale);
    return { id, name, kind: "bed", corners, total: mine.length, measured: mine.filter((i) => i.value_m !== null).length };
  };
  const features = [progress(1, "Raised bed 1", 4), progress(2, "Shed", 4), progress(3, "Pond", 1)];
  return {
    length_unit: "m",
    items,
    features,
    total: features.reduce((s, f) => s + f.total, 0),
    measured: features.reduce((s, f) => s + f.measured, 0),
  };
}

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

const payload = btoa(JSON.stringify({ exp: 4_102_444_800 }));
const TOKEN = `x.${payload}.y`;

async function handle(url: string, method: string, body: any): Promise<Response> {
  const path = new URL(url).pathname;
  if (path.endsWith("/auth/login")) return json({ access_token: TOKEN, refresh_token: "r" });
  if (path === "/api/v1/allotments") {
    return json([
      { id: 1, name: "Plot 12, Hill Lane", description: "", length_unit: "m", role: "owner" },
      { id: 2, name: "Community orchard", description: "", length_unit: "m", role: "viewer" },
    ]);
  }
  if (path.endsWith("/features")) {
    const f = (id: number, g: unknown) => ({ type: "Feature", id, geometry: g, properties: { name: "", kind: "bed" } });
    return json({ type: "FeatureCollection", features: [f(1, BED), f(2, SHED), f(3, POND)] });
  }
  if (path.endsWith("/measurements/fit")) {
    return json({
      applied: false,
      features: [
        { feature_id: 1, name: "Raised bed 1", changed: true, rms_before_m: 0.31, rms_after_m: 0.002, max_move_m: 0.62, missing: 1, recheck: [], geometry: BED_FIXED, drawn_geometry: BED, radius_m: null, error: null },
        { feature_id: 2, name: "Shed", changed: true, rms_before_m: 0.09, rms_after_m: 0.04, max_move_m: 0.12, missing: 0, recheck: [8], geometry: polygon([14, 1], [17.2, 1.1], [17.1, 4], [14, 4]), drawn_geometry: SHED, radius_m: null, error: null },
      ],
    });
  }
  const one = path.match(/\/measurements\/(\d+)$/);
  if (one && method === "PATCH") {
    items = items.map((i) => (i.id === Number(one[1]) ? { ...i, ...body } : i));
    return json(items.find((i) => i.id === Number(one[1])));
  }
  if (path.endsWith("/measurements/sync") || path.endsWith("/measurements")) return json(checklist());
  if (path.endsWith("/map-jobs")) return json({ id: 1 }, 202);
  return json({ message: "not in the demo" }, 404);
}

if (process.env.EXPO_PUBLIC_DEMO === "1") {
  // Start signed in (add ?signout to the address to see the sign-in screen).
  try {
    const ls = globalThis.localStorage;
    if (ls && !String(globalThis.location?.search).includes("signout")) {
      ls.setItem("allotment.server", "http://demo");
      ls.setItem("allotment.tokens", JSON.stringify({ access_token: TOKEN, refresh_token: "r" }));
      ls.setItem("allotment.current", "1");
    } else ls?.clear();
  } catch {
    /* no storage */
  }
  globalThis.fetch = (async (input: any, init?: RequestInit) => {
    const url = typeof input === "string" ? input : input.url;
    const method = (init?.method ?? input.method ?? "GET").toUpperCase();
    let body: any = undefined;
    try {
      body = init?.body ? JSON.parse(init.body as string) : undefined;
    } catch {
      /* not JSON */
    }
    return handle(url.startsWith("http") ? url : `http://demo${url}`, method, body);
  }) as typeof fetch;
}
