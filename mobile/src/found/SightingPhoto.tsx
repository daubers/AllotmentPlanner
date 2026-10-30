import React from "react";
import { Image, View } from "react-native";
import Svg, { Polygon } from "react-native-svg";
import { usePalette } from "../ui/theme";
import { useMediaUrl } from "../seeds/hooks";
import { outlinePoints, pictureOf, type Sighting } from "./model";

/** A photo with the found object outlined. The outline is 0..1 of the picture, so the SVG covers
 *  the picture exactly and it lines up at any size. */
export default function SightingPhoto({ sighting, full = false, label }: { sighting: Sighting; full?: boolean; label: string }) {
  const p = usePalette();
  const mediaUrl = useMediaUrl();
  const uri = mediaUrl(pictureOf(sighting, full));
  const ratio = sighting.width && sighting.height ? sighting.width / sighting.height : 4 / 3;
  return (
    <View style={{ aspectRatio: ratio, width: "100%", borderRadius: 8, overflow: "hidden", backgroundColor: p.surfaceAlt }} accessibilityRole="image" accessibilityLabel={label}>
      {uri ? <Image source={{ uri }} style={{ width: "100%", height: "100%" }} resizeMode="stretch" /> : null}
      <Svg viewBox="0 0 1 1" preserveAspectRatio="none" style={{ position: "absolute", top: 0, left: 0, width: "100%", height: "100%" }}>
        <Polygon points={outlinePoints(sighting.outline)} fill={p.accent} fillOpacity={0.2} stroke="#ffd400" strokeWidth={0.008} strokeLinejoin="round" />
      </Svg>
    </View>
  );
}
