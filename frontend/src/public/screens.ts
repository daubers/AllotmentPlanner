/** The screenshots the public pages use, all under /screens. Regenerate them as docs/screenshots.md says. */
export const SCREENS = {
  map: { file: "map.png", alt: "The map editor showing beds, a path, a shed and a tree drawn on a street map, with the Found in your photos list beside it" },
  found: { file: "found.png", alt: "A photo of a garden with the detected raised bed outlined in yellow" },
  seeds: { file: "seeds.png", alt: "The seed packets list with what to sow this month" },
  trays: { file: "trays.png", alt: "A seed tray with each cell marked as sown or come up" },
  phone: { file: "phone.png", alt: "The phone app's home screen with Photograph the plot and Measure the plot" },
} as const;

export const screenUrl = (key: keyof typeof SCREENS) => `/screens/${SCREENS[key].file}`;
