/** What the camera screen tells the person while they walk round taking photos, and the summary at
 *  the end. It is all plain functions so it can be tested without a phone.
 *
 *  The rules come from how real sets failed in the mapping pipeline: photos taken from one spot
 *  (no parallax), a GPS fix that never updated, a camera tilted at the sky or the grass, and
 *  nothing but one direction covered. */

export type Fix = { lat: number; lng: number; accuracy: number | null; timestamp: number };

export type Shot = {
  lat: number;
  lng: number;
  accuracy: number | null;
  heading: number | null;
  takenAt: number;
};

export type Advice = {
  id: string;
  /** "block" stops the shutter; "warn" is shown but the photo can still be taken. */
  level: "block" | "warn";
  text: string;
};

export const MIN_STEP_M = 1.0; // photos closer together than this add no depth information
export const MAX_FIX_AGE_MS = 10_000;
export const ROUGH_ACCURACY_M = 15;
export const MAX_TILT_DEG = 25;
export const SECTOR_DEG = 30;
export const SECTORS = 360 / SECTOR_DEG;
export const MIN_PHOTOS_FOR_MAP = 5;

const EARTH_M = 6_371_000;

/** Distance in metres between two points (haversine). */
export function distanceM(a: { lat: number; lng: number }, b: { lat: number; lng: number }): number {
  const rad = Math.PI / 180;
  const dLat = (b.lat - a.lat) * rad;
  const dLng = (b.lng - a.lng) * rad;
  const h =
    Math.sin(dLat / 2) ** 2 + Math.cos(a.lat * rad) * Math.cos(b.lat * rad) * Math.sin(dLng / 2) ** 2;
  return 2 * EARTH_M * Math.asin(Math.min(1, Math.sqrt(h)));
}

/** How far the camera is pointing above (+) or below (-) the horizon, from the phone's pitch
 *  (DeviceMotion ``beta``, radians; 90 degrees when the phone is held upright). */
export function cameraPitchDeg(betaRad: number): number {
  return (betaRad * 180) / Math.PI - 90;
}

/** A compass heading, preferring true north; null when the sensor has none (a negative reading). */
export function pickHeading(trueHeading: number, magHeading: number): number | null {
  if (trueHeading >= 0) return trueHeading % 360;
  if (magHeading >= 0) return magHeading % 360;
  return null;
}

export type Conditions = {
  fix: Fix | null;
  heading: number | null;
  /** Camera pitch from the horizon in degrees, if the motion sensor works. */
  pitchDeg: number | null;
  last: Shot | null;
  now: number;
};

export function adviceFor(c: Conditions): Advice[] {
  const out: Advice[] = [];
  if (!c.fix) {
    out.push({ id: "no-fix", level: "block", text: "Waiting for a GPS fix…" });
  } else if (c.now - c.fix.timestamp > MAX_FIX_AGE_MS) {
    out.push({ id: "old-fix", level: "block", text: "The GPS fix is out of date. Check location is on and you are outdoors." });
  } else {
    if (c.fix.accuracy !== null && c.fix.accuracy > ROUGH_ACCURACY_M) {
      out.push({ id: "rough", level: "warn", text: `GPS is rough (±${Math.round(c.fix.accuracy)} m). Wait a moment if you can.` });
    }
    if (c.last && distanceM(c.last, c.fix) < MIN_STEP_M) {
      out.push({ id: "step", level: "warn", text: "Take a step or two before the next photo: shots from one spot can't be joined up." });
    }
  }
  if (c.heading === null) {
    out.push({ id: "no-compass", level: "warn", text: "No compass reading. Move the phone in a figure of eight." });
  }
  if (c.pitchDeg !== null && Math.abs(c.pitchDeg) > MAX_TILT_DEG) {
    out.push({
      id: "tilt",
      level: "warn",
      text: c.pitchDeg > 0 ? "Pointing too high: bring the camera down level." : "Pointing too low: lift the camera to look along the ground.",
    });
  }
  return out;
}

export function blocked(advice: Advice[]): boolean {
  return advice.some((a) => a.level === "block");
}

export type Summary = {
  photos: number;
  /** Total length of the path between shots, in metres. */
  walkedM: number;
  /** Furthest any shot was from the middle of all of them, in metres. */
  spreadM: number;
  /** How many of the 12 compass sectors have a photo facing into them. */
  sectors: number;
  /** Photos taken within a metre of the one before. */
  tooClose: number;
  roughFixes: number;
};

export function summarise(shots: Shot[]): Summary {
  let walked = 0;
  let tooClose = 0;
  for (let i = 1; i < shots.length; i++) {
    const d = distanceM(shots[i - 1], shots[i]);
    walked += d;
    if (d < MIN_STEP_M) tooClose++;
  }
  let spread = 0;
  if (shots.length) {
    const lat = shots.reduce((s, p) => s + p.lat, 0) / shots.length;
    const lng = shots.reduce((s, p) => s + p.lng, 0) / shots.length;
    spread = Math.max(...shots.map((p) => distanceM(p, { lat, lng })));
  }
  const seen = new Set(
    shots.filter((s) => s.heading !== null).map((s) => Math.floor(((s.heading as number) % 360) / SECTOR_DEG)),
  );
  return {
    photos: shots.length,
    walkedM: walked,
    spreadM: spread,
    sectors: seen.size,
    tooClose,
    roughFixes: shots.filter((s) => s.accuracy !== null && s.accuracy > ROUGH_ACCURACY_M).length,
  };
}

/** Plain-language feedback on a finished walk: what is good and what to redo. */
export function verdict(s: Summary): string[] {
  const notes: string[] = [];
  if (s.photos < MIN_PHOTOS_FOR_MAP) {
    notes.push(`Only ${s.photos} photos: at least ${MIN_PHOTOS_FOR_MAP} overlapping ones are needed to build a map, and 20 or more work much better.`);
    return notes;
  }
  if (s.spreadM < 3) notes.push("You hardly moved: walk along the edge so the photos are taken from different places.");
  if (s.tooClose > s.photos / 3) notes.push(`${s.tooClose} photos were taken almost on top of the one before. Step further between shots.`);
  if (s.sectors < 4) notes.push(`The photos face only ${s.sectors} of ${SECTORS} compass directions. Also turn to look at the other sides, with the fence in view.`);
  if (s.roughFixes > s.photos / 3) notes.push("The GPS was rough for many shots. Next time wait for a steadier fix in the open.");
  if (!notes.length) {
    notes.push(`${s.photos} photos over ${Math.round(s.walkedM)} m facing ${s.sectors} of ${SECTORS} directions: a good set.`);
  }
  return notes;
}
