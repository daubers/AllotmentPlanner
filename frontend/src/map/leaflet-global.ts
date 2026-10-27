// leaflet-geoman is a classic plugin that looks up Leaflet as the global `L`; the ES module
// build of Leaflet doesn't create one. Import this *before* the plugin.
import L from "leaflet";

(window as unknown as { L: typeof L }).L = L;
