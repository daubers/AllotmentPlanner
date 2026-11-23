export type Spacing = { plant: number | null; row: number | null };

/** Square metres one plant takes: plant spacing times row spacing (or itself if there is no row spacing). */
export function cellM2(s: Spacing): number | null {
  if (!s.plant || s.plant <= 0) return null;
  const row = s.row && s.row > 0 ? s.row : s.plant;
  return (s.plant * row) / 10_000;
}

const tenth = (n: number) => Math.round(n * 10) / 10;

/** About how much space `count` plants need, rounded up to a tenth of a square metre. */
export function suggestArea(count: number, s: Spacing): number | null {
  const cell = cellM2(s);
  if (cell === null || !(count > 0)) return null;
  return Math.max(0.1, tenth(Math.ceil(count * cell * 10 - 1e-9) / 10));
}

/** How many plants fit in `area` m2. */
export function suggestCount(area: number, s: Spacing): number | null {
  const cell = cellM2(s);
  if (cell === null || !(area > 0)) return null;
  return Math.floor(area / cell + 1e-9);
}

export const areaFromPercent = (percent: number, bedArea: number): number => tenth((percent / 100) * bedArea);
export const percentOfBed = (area: number, bedArea: number): number => tenth((area / bedArea) * 100);

/** "~2.4 m² for 20 plants at 30 × 30 cm", or null when the spacing is unknown. */
export function hint(count: number | null, s: Spacing): string | null {
  const cell = cellM2(s);
  if (cell === null) return null;
  const by = `${s.plant} × ${s.row ?? s.plant} cm`;
  const area = count ? suggestArea(count, s) : null;
  return area !== null
    ? `About ${area} m² for ${count} plants at ${by}`
    : `Each plant needs about ${Math.round(cell * 10_000) / 10_000} m² (${by})`;
}
