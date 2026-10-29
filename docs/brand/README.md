# Logo

**Chosen: B, the map pin** (`logo.svg`). It is wired into the web favicon and apple-touch icon, the phone app's icon (iOS), adaptive icon layers (Android: foreground, background and a themed monochrome), splash screen, sign-in screen (`mobile/src/ui/Logo.tsx`) and the README. The files in `source/` are what the app icons are made from; `sh docs/brand/build-assets.sh` regenerates every PNG (macOS with Chrome). Only the four options below were considered.

## The options

Four app-icon concepts (SVG, 512 x 512, rounded square so they drop straight into an Expo icon or a favicon). `options.png` is a contact sheet showing each at 200, 96, 48, 32 and 16 px, in a light and a dark lock-up, and as a browser tab; `preview.html` regenerates it. Colours come from the app's palette (`mobile/src/ui/theme.ts`): green `#17653a`, lighter greens `#2f8a52` / `#74d492`, cream `#f1f4ee`.

| | Idea | Strengths | Weaknesses |
|---|---|---|---|
| **A. Seedling** `option-a-sprout.svg` | A seedling in a mound of soil on the app's green | Clear at every size, even 16 px; friendly; works on light and dark backgrounds | Generic: many gardening apps use a sprout |
| **B. Map pin** `option-b-pin.svg` | A map pin with a seedling in it | Says "place" and "growing" at once, which is what the app does; clear down to about 24 px | Resembles a location-pin app icon at a glance |
| **C. Plot plan** `option-c-plot.svg` | Four beds seen from above, one planted, with a measuring edge on top | Most specific to this app (plan and tape measure); distinctive | Detailed: the ruler and the beds blur at 16 to 32 px |
| **D. Sun and rows** `option-d-rows.svg` | The sun over rows of planting, on a dark ground | Atmospheric and distinctive | Weakest small and the only dark one; reads as a landscape rather than an app |

**Suggestion made at the time:** A for the smallest sizes, with B if you want the map idea in the mark; B was chosen. C would make a good illustration for an empty state but is too detailed as a small icon.

The text in the contact sheet uses the system font; a final wordmark would need the lettering drawn as paths. After the choice the leaves were tucked inside the pin's circle (they touched its rim in the original sketch).
