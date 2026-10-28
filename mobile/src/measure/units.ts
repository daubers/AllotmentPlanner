/** Reading and showing lengths. The server always stores metres; people type what is on their tape. */

export type LengthUnit = "m" | "cm" | "ft_in";

const M_PER_IN = 0.0254;
const M_PER_FT = 0.3048;

/** Parse what someone typed into metres, or null if it isn't a length.
 *
 *  A bare number is read in the allotment's unit (``fallback``). Accepts ``3.2``, ``3,2``,
 *  ``3.2m``, ``320cm``, ``10ft 6in``, ``10'6"``, ``10 ft``, ``126in``, ``10.5 feet``. */
export function parseLength(input: string, fallback: LengthUnit = "m"): number | null {
  const text = input.trim().toLowerCase().replace(/,/g, ".").replace(/[“”″]/g, '"').replace(/[‘’′]/g, "'");
  if (!text) return null;

  const bare = text.match(/^(\d+(?:\.\d+)?|\.\d+)$/);
  if (bare) {
    const n = parseFloat(bare[1]);
    if (fallback === "cm") return n / 100;
    if (fallback === "ft_in") return n * M_PER_FT; // a bare number in feet-and-inches mode is feet
    return n;
  }

  // Feet and inches in any of the usual spellings: 10ft 6in, 10'6", 10' 6, 10 ft 6.
  const feetInches = text.match(
    /^(\d+(?:\.\d+)?)\s*(?:ft|feet|foot|')\s*(?:(\d+(?:\.\d+)?)\s*(?:in|ins|inch|inches|")?)?$/,
  );
  if (feetInches) {
    const feet = parseFloat(feetInches[1]);
    const inches = feetInches[2] ? parseFloat(feetInches[2]) : 0;
    return feet * M_PER_FT + inches * M_PER_IN;
  }

  const single = text.match(/^(\d+(?:\.\d+)?|\.\d+)\s*(m|cm|mm|in|ins|inch|inches|"|ft|feet|foot|')$/);
  if (single) {
    const n = parseFloat(single[1]);
    switch (single[2]) {
      case "m":
        return n;
      case "cm":
        return n / 100;
      case "mm":
        return n / 1000;
      case "ft":
      case "feet":
      case "foot":
      case "'":
        return n * M_PER_FT;
      default:
        return n * M_PER_IN;
    }
  }
  return null;
}

/** Show metres in the allotment's chosen unit. */
export function formatLength(metres: number, unit: LengthUnit): string {
  if (unit === "cm") return `${Math.round(metres * 100)} cm`;
  if (unit === "ft_in") {
    const totalInches = Math.round(metres / M_PER_IN);
    const feet = Math.floor(totalInches / 12);
    const inches = totalInches - feet * 12;
    return `${feet}' ${inches}"`;
  }
  return `${metres.toFixed(2)} m`;
}

/** The text to put in an entry box for a stored value, in the allotment's unit. */
export function editText(metres: number, unit: LengthUnit): string {
  if (unit === "cm") return String(Math.round(metres * 100));
  if (unit === "ft_in") return formatLength(metres, unit);
  return String(Math.round(metres * 1000) / 1000);
}

export const UNIT_HINT: Record<LengthUnit, string> = {
  m: "metres, e.g. 3.2 or 320cm",
  cm: "centimetres, e.g. 320 or 3.2m",
  ft_in: `feet and inches, e.g. 10' 6"`,
};
