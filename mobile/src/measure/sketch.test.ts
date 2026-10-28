import { layout, layoutTogether, toLocal } from "./sketch";

test("corners become metres from the middle, north up", () => {
  const pts = toLocal([[-1, 51], [-1, 51.001], [-0.999, 51.001], [-0.999, 51]]);
  expect(pts[1].y - pts[0].y).toBeCloseTo(111.2, 0);
  expect(pts[2].x - pts[1].x).toBeCloseTo(69.9, 0);
});

test("a shape fits its drawing with its proportions kept and north at the top", () => {
  const l = layout([{ x: 0, y: 0 }, { x: 10, y: 0 }, { x: 10, y: 5 }, { x: 0, y: 5 }], 300, 200);
  const [a, b, c] = l.points;
  expect(b.x - a.x).toBeCloseTo(2 * (c.y === a.y ? 1 : a.y - c.y), 1); // twice as wide as tall
  expect(c.y).toBeLessThan(b.y); // y=5 (north) is drawn higher up
  for (const p of l.points) {
    expect(p.x).toBeGreaterThanOrEqual(0);
    expect(p.x).toBeLessThanOrEqual(300);
    expect(p.y).toBeGreaterThanOrEqual(0);
    expect(p.y).toBeLessThanOrEqual(200);
  }
});

test("numbers sit outside the shape, away from its middle", () => {
  const l = layout([{ x: 0, y: 0 }, { x: 10, y: 0 }, { x: 10, y: 10 }, { x: 0, y: 10 }], 200, 200);
  const cx = 100;
  const cy = 100;
  l.points.forEach((p, i) => {
    const before = Math.hypot(p.x - cx, p.y - cy);
    const after = Math.hypot(l.labels[i].x - cx, l.labels[i].y - cy);
    expect(after).toBeGreaterThan(before);
  });
});

test("a single point and a flat line don't blow up", () => {
  expect(layout([{ x: 1, y: 1 }], 100, 100).points[0].x).toBeCloseTo(50, 0);
  const flat = layout([{ x: 0, y: 0 }, { x: 5, y: 0 }], 100, 100);
  expect(Number.isFinite(flat.points[1].x)).toBe(true);
});

test("two outlines share one scale so they can be compared", () => {
  const small = [{ x: 0, y: 0 }, { x: 5, y: 0 }, { x: 5, y: 5 }];
  const big = [{ x: 0, y: 0 }, { x: 10, y: 0 }, { x: 10, y: 10 }];
  const [a, b] = layoutTogether([small, big], 300, 300);
  const widthA = a.points[1].x - a.points[0].x;
  const widthB = b.points[1].x - b.points[0].x;
  expect(widthB).toBeCloseTo(2 * widthA, 3);
});
