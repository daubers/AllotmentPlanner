# Logo options

Four app-icon concepts (SVG, 512 x 512, rounded square so they drop straight into an Expo icon or a favicon). `options.png` is a contact sheet showing each at 200, 96, 48, 32 and 16 px, in a light and a dark lock-up, and as a browser tab; `preview.html` regenerates it. Colours come from the app's palette (`mobile/src/ui/theme.ts`): green `#17653a`, lighter greens `#2f8a52` / `#74d492`, cream `#f1f4ee`.

| | Idea | Strengths | Weaknesses |
|---|---|---|---|
| **A. Seedling** `option-a-sprout.svg` | A seedling in a mound of soil on the app's green | Clear at every size, even 16 px; friendly; works on light and dark backgrounds | Generic: many gardening apps use a sprout |
| **B. Map pin** `option-b-pin.svg` | A map pin with a seedling in it | Says "place" and "growing" at once, which is what the app does; clear down to about 24 px | Resembles a location-pin app icon at a glance |
| **C. Plot plan** `option-c-plot.svg` | Four beds seen from above, one planted, with a measuring edge on top | Most specific to this app (plan and tape measure); distinctive | Detailed: the ruler and the beds blur at 16 to 32 px |
| **D. Sun and rows** `option-d-rows.svg` | The sun over rows of planting, on a dark ground | Atmospheric and distinctive | Weakest small and the only dark one; reads as a landscape rather than an app |

**Suggestion:** A for the phone icon and favicon (it is the clearest small), with B as the alternative if you want the map idea in the mark. C is a good illustration for the README header or an empty state, but is too detailed as a small icon.

Nothing is wired in yet. Once one is chosen: favicon for the web app, `icon.png`, `adaptive-icon` and splash for the phone app (exported from the SVG), and the README header. The text in the contact sheet uses the system font; a final wordmark would need the lettering drawn as paths.
