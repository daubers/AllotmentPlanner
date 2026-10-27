export type Kind = "bed" | "path" | "shed" | "tree" | "water" | "compost" | "boundary" | "other";
export const KINDS: Kind[] = ["bed", "path", "shed", "tree", "water", "compost", "boundary", "other"];

export const KIND_COLOURS: Record<Kind, string> = {
  bed: "#3f8f3f",
  path: "#a08c6a",
  shed: "#8a5a3c",
  tree: "#1f6b3a",
  water: "#2f7fc1",
  compost: "#6b4f2a",
  boundary: "#444444",
  other: "#7a5ea8",
};

export function colourFor(kind: string | undefined): string {
  return KIND_COLOURS[kind as Kind] ?? KIND_COLOURS.other;
}
