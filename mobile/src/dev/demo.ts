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

// --- seeds, trays and plantings (the screens added in AM-44) ----------------------------------------
let packets: any[] = [
  { id: 1, status: "active", name: "Tomato", variety: "Moneymaker", supplier: "Suttons", stock: "part", sow_depth_mm: 5, germinate_days_min: 7, germinate_days_max: 14, best_before_year: 2027, seeds_in_packet: 50, maturity_days_min: 70, maturity_days_max: 90, notes: "", calendar: { sow_indoors: [2, 3, 4], plant_out: [5, 6], harvest: [8, 9, 10] }, photos: [], updated_at: "2026-10-01T10:00:00Z" },
  { id: 2, status: "active", name: "Carrot", variety: "Flyaway F1", supplier: "Mr Fothergill's", stock: "full", sow_depth_mm: 15, germinate_days_min: 14, germinate_days_max: 21, best_before_year: 2028, seeds_in_packet: 500, notes: "", calendar: { sow_outdoors: [3, 4, 5, 6, 7], harvest: [6, 7, 8, 9, 10, 11] }, photos: [], updated_at: "2026-10-01T10:00:00Z" },
  { id: 3, status: "active", name: "Kale", variety: "", supplier: "Johnsons", stock: "low", notes: "", calendar: { sow_outdoors: [4, 5], plant_out: [6, 7], harvest: [10, 11, 12, 1, 2] }, photos: [], updated_at: "2026-10-01T10:00:00Z" },
  { id: 4, status: "draft", name: "Parsley", variety: "Moss Curled 2", supplier: "Mr Fothergill's", stock: "full", sow_depth_mm: 15, germinate_days_min: 14, germinate_days_max: 21, best_before_year: null, seeds_in_packet: 500, notes: "", calendar: { sow_indoors: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12], sow_outdoors: [3, 4, 5, 6, 7], harvest: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12] }, photos: [], updated_at: "2026-10-29T10:00:00Z" },
];
const scans = [{ id: 1, status: "ready", packet_id: 4, media_id: 1, calendar_source: "graphic", rotation: 0, missing: ["best_before_year"], crop: null, finished_at: "2026-10-29T10:00:00Z" }];
let tray: any = {
  id: 1, name: "Greenhouse 1", rows: 3, cols: 4, tray_type: "12-cell", location: "left shelf", status: "active", sown_on: "2026-03-01", updated_at: "2026-03-02T10:00:00Z",
  kinds: [{ packet_id: 1, name: "Tomato", variety: "Moneymaker", cells: 3, seeds: 3 }, { packet_id: 3, name: "Kale", variety: "", cells: 2, seeds: 2 }],
  cells: [
    { row: 0, col: 0, packet_id: 1, count: 1, status: "germinated" },
    { row: 0, col: 1, packet_id: 1, count: 1, status: "germinated" },
    { row: 0, col: 2, packet_id: 1, count: 1, status: "sown" },
    { row: 1, col: 0, packet_id: 3, count: 1, status: "sown" },
    { row: 1, col: 1, packet_id: 3, count: 1, status: "failed" },
  ],
  photos: [],
};
const counts = () => {
  const c: any = { empty: tray.rows * tray.cols, sown: 0, germinated: 0, failed: 0, planted_out: 0 };
  for (const cell of tray.cells) { c[cell.status] += 1; c.empty -= 1; }
  return c;
};
let plantings: any[] = [
  { id: 1, feature_id: 1, bed_name: "Raised bed 1", packet_id: 2, packet_name: "Carrot", packet_variety: "Flyaway F1", region: polygon([0.5, 0.5], [5, 0.5], [5, 4], [0.5, 4]), area_m2: 15.7, count: 60, method: "direct_sow", status: "growing", sown_on: "2026-04-10", notes: "", warnings: [] },
  { id: 2, feature_id: 1, bed_name: "Raised bed 1", packet_id: 1, packet_name: "Tomato", packet_variety: "Moneymaker", region: polygon([5.5, 0.5], [9.5, 0.5], [9.5, 4.5], [5.5, 4.5]), area_m2: 16, count: 6, method: "transplant", status: "harvesting", sown_on: "2026-03-01", planted_on: "2026-05-20", notes: "", warnings: [] },
];

function seedDemo(path: string, method: string, body: any, query: URLSearchParams): Response | null {
  const base = path.replace(/^\/api\/v1\/allotments\/\d+/, "");
  if (base === "/packets") {
    const status = query.get("status");
    return json(packets.filter((p) => !status || p.status === status));
  }
  const packet = base.match(/^\/packets\/(\d+)$/);
  if (packet) {
    const i = packets.findIndex((p) => p.id === Number(packet[1]));
    if (method === "PATCH") packets[i] = { ...packets[i], ...body, updated_at: new Date().toISOString() };
    return json(packets[i]);
  }
  if (base === "/packet-scans") return json(scans);
  if (base === "/trays") return json([{ ...tray, counts: counts(), cells: undefined }]);
  if (base === "/trays/1") return json({ ...tray, counts: counts() });
  if (base === "/trays/1/cells" && method === "PATCH") {
    const keys = new Set((body.cells as { row: number; col: number }[]).map((c) => `${c.row},${c.col}`));
    tray.cells = tray.cells.filter((c: any) => !(keys.has(`${c.row},${c.col}`) && body.set.status === "empty"));
    for (const k of keys) {
      const [row, col] = k.split(",").map(Number);
      const cell = tray.cells.find((c: any) => c.row === row && c.col === col);
      if (cell) Object.assign(cell, body.set);
      else if (body.set.packet_id) tray.cells.push({ row, col, count: 1, status: "sown", ...body.set });
    }
    return json({ ...tray, counts: counts() });
  }
  if (base === "/plantings") return json(plantings);
  const planting = base.match(/^\/plantings\/(\d+)$/);
  if (planting && method === "PATCH") {
    plantings = plantings.map((p) => (p.id === Number(planting[1]) ? { ...p, ...body } : p));
    return json(plantings.find((p) => p.id === Number(planting[1])));
  }
  return null;
}

let jobs: any[] | null = null;
/** The demo's jobs, made once so ticking one off sticks. */
function demoTasks() {
  if (jobs) return jobs;
  const day = (n: number) => new Date(Date.now() + n * 86_400_000).toISOString().slice(0, 10);
  const job = (id: number, title: string, due: string | null, extra = {}) => ({ id, title, description: "", status: "todo", priority: "normal", due_date: due, feature_id: null, location: null, ...extra });
  jobs = [
    job(1, "Water the tomatoes", day(0), { feature_id: 1, priority: "high", description: "Deep water at the base, not the leaves." }),
    job(2, "Tie in the beans", day(-2), { feature_id: 1 }),
    job(3, "Fix the shed door", day(0), { feature_id: 2 }),
    job(4, "Net the strawberries", day(-1), { location: { type: "Point", coordinates: at(7, 9) } }),
    job(5, "Order manure", day(5), { feature_id: 1 }),
    job(6, "Check the pond liner", null, { feature_id: 3 }),
  ];
  return jobs;
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
  if (path.endsWith("/tasks") && method === "GET") return json(demoTasks().filter((t) => t.status !== "done"));
  const tick = path.match(/\/tasks\/(\d+)\/(complete|reopen)$/);
  if (tick && method === "POST") {
    const t = demoTasks().find((x) => x.id === Number(tick[1]));
    if (t) t.status = tick[2] === "complete" ? "done" : "todo";
    return json(t ?? {});
  }
  if (path.endsWith("/features")) {
    if (path.includes("/allotments/2/")) return json({ type: "FeatureCollection", features: [] });
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
  const seeds = seedDemo(path, method, body, new URL(url).searchParams);
  if (seeds) return seeds;
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
