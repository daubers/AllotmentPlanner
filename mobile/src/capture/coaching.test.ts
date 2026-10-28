import {
  adviceFor,
  blocked,
  cameraPitchDeg,
  distanceM,
  pickHeading,
  summarise,
  verdict,
  type Conditions,
  type Shot,
} from "./coaching";

const NOW = 1_000_000;
const here = { lat: 51.6174, lng: -1.1099 };
// 0.00001 degrees of latitude is about 1.11 m
const north = (m: number) => ({ lat: here.lat + m / 111_195, lng: here.lng });

const fix = (over: Partial<Conditions["fix"] & object> = {}) => ({ ...here, accuracy: 4, timestamp: NOW - 1000, ...over });
const shot = (p: { lat: number; lng: number }, heading: number | null = 90, accuracy: number | null = 4): Shot => ({
  ...p,
  heading,
  accuracy,
  takenAt: NOW,
});
const base = (over: Partial<Conditions> = {}): Conditions => ({
  fix: fix(),
  heading: 90,
  pitchDeg: 0,
  last: null,
  now: NOW,
  ...over,
});

test("distance is in metres", () => {
  expect(distanceM(here, north(10))).toBeCloseTo(10, 0);
  expect(distanceM(here, here)).toBe(0);
});

test("pitch is measured from the horizon", () => {
  expect(cameraPitchDeg(Math.PI / 2)).toBeCloseTo(0);
  expect(cameraPitchDeg(Math.PI / 2 + Math.PI / 6)).toBeCloseTo(30);
});

test("a negative true heading falls back to the magnetic one, or nothing", () => {
  expect(pickHeading(370, 10)).toBe(10);
  expect(pickHeading(-1, 200)).toBe(200);
  expect(pickHeading(-1, -1)).toBeNull();
});

test("all is well: no advice", () => {
  expect(adviceFor(base())).toEqual([]);
});

test("no fix, or an old one, stops the shutter", () => {
  expect(blocked(adviceFor(base({ fix: null })))).toBe(true);
  expect(blocked(adviceFor(base({ fix: fix({ timestamp: NOW - 60_000 }) })))).toBe(true);
});

test("a rough fix and standing still are warnings that don't stop you", () => {
  const rough = adviceFor(base({ fix: fix({ accuracy: 40 }) }));
  expect(rough.map((a) => a.id)).toEqual(["rough"]);
  expect(blocked(rough)).toBe(false);
  const still = adviceFor(base({ last: shot(north(0.3)) }));
  expect(still.map((a) => a.id)).toEqual(["step"]);
  expect(adviceFor(base({ last: shot(north(3)) }))).toEqual([]);
});

test("tilt up or down is called out, as is a missing compass", () => {
  expect(adviceFor(base({ pitchDeg: 40 }))[0].text).toMatch(/too high/);
  expect(adviceFor(base({ pitchDeg: -40 }))[0].text).toMatch(/too low/);
  expect(adviceFor(base({ heading: null })).map((a) => a.id)).toEqual(["no-compass"]);
});

test("a good walk is summarised and praised", () => {
  const shots = Array.from({ length: 12 }, (_, i) => shot(north(i * 4), i * 30));
  const s = summarise(shots);
  expect(s.photos).toBe(12);
  expect(s.walkedM).toBeCloseTo(44, 0);
  expect(s.sectors).toBe(12);
  expect(s.tooClose).toBe(0);
  expect(verdict(s)[0]).toMatch(/a good set/);
});

test("standing in one spot turning round is flagged", () => {
  const shots = Array.from({ length: 10 }, (_, i) => shot(north(0.1 * (i % 2)), i * 36));
  const s = summarise(shots);
  expect(s.tooClose).toBeGreaterThan(3);
  const notes = verdict(s).join(" ");
  expect(notes).toMatch(/hardly moved/);
  expect(notes).toMatch(/on top of the one before/);
});

test("one direction only, and too few photos, are flagged", () => {
  const same = Array.from({ length: 8 }, (_, i) => shot(north(i * 3), 100 + i));
  expect(verdict(summarise(same)).join(" ")).toMatch(/only 1 of 12 compass directions/);
  expect(verdict(summarise(same.slice(0, 3)))[0]).toMatch(/Only 3 photos/);
  expect(summarise([])).toMatchObject({ photos: 0, walkedM: 0, spreadM: 0, sectors: 0 });
});
