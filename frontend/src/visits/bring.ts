import type { components } from "../api/schema";

type Task = components["schemas"]["Task"];
type BringItem = components["schemas"]["BringItem"];

export type BringRow = { id: number; name: string; source: "task" | "suggested" | "extra"; outOfAction: boolean };
/** A visit's hand-made changes: equipment to add beyond the tasks, and equipment to leave off. */
export type Extras = { adds: number[]; removes: number[] };

const ORDER = { task: 0, suggested: 1, extra: 2 } as const;

/**
 * What the bring list will be, from the tasks picked in the dialog: the equipment on those tasks, the
 * suggestions the server made for tasks with none (when still picked), then the hand-made changes.
 * `names` gives the name of any equipment id (for ones added by hand).
 */
export function previewBring(
  picked: Task[],
  serverBring: BringItem[] | undefined,
  extras: Extras,
  names: (id: number) => { name: string; outOfAction: boolean } | undefined,
): BringRow[] {
  const found = new Map<number, BringRow>();
  const note = (id: number, name: string, source: BringRow["source"], outOfAction: boolean) => {
    const have = found.get(id);
    if (!have) found.set(id, { id, name, source, outOfAction });
    else if (ORDER[source] < ORDER[have.source]) have.source = source;
  };
  const pickedIds = new Set(picked.map((t) => t.id!));
  for (const t of picked) {
    if (t.status === "done") continue;
    for (const e of t.equipment ?? []) note(e.id!, e.name!, "task", e.status === "out_of_action");
  }
  for (const b of serverBring ?? []) {
    // suggestions were made for tasks as they were when the visit was saved
    if (b.source === "suggested" && (b.task_ids ?? []).some((id) => pickedIds.has(id))) {
      note(b.id!, b.name!, "suggested", b.status === "out_of_action");
    }
  }
  for (const id of extras.adds) {
    const n = names(id);
    if (n) note(id, n.name, "extra", n.outOfAction);
  }
  for (const id of extras.removes) found.delete(id);
  return [...found.values()].sort((a, b) => ORDER[a.source] - ORDER[b.source] || a.name.localeCompare(b.name) || a.id - b.id);
}

/** Take something off the list: a hand-added one is simply un-added; one a task needs is hidden. */
export function removeTool(extras: Extras, id: number): Extras {
  if (extras.adds.includes(id)) return { ...extras, adds: extras.adds.filter((x) => x !== id) };
  return extras.removes.includes(id) ? extras : { ...extras, removes: [...extras.removes, id] };
}

/** Put something on the list: it stops being hidden, and is added by hand if nothing else brings it. */
export function addTool(extras: Extras, id: number, alreadyListed: boolean): Extras {
  const removes = extras.removes.filter((x) => x !== id);
  const adds = alreadyListed || extras.adds.includes(id) ? extras.adds : [...extras.adds, id];
  return { adds, removes };
}

export const extrasOf = (v?: { equipment_extras?: { equipment_id?: number; mode?: "add" | "remove" }[] }): Extras => ({
  adds: (v?.equipment_extras ?? []).filter((e) => e.mode === "add").map((e) => e.equipment_id!),
  removes: (v?.equipment_extras ?? []).filter((e) => e.mode === "remove").map((e) => e.equipment_id!),
});

/** "Spade, Fork, Dibber +2": the first few names and how many more. */
export function bringSummary(bring: { name?: string }[] | undefined, show = 3): string {
  const list = (bring ?? []).map((b) => b.name ?? "").filter(Boolean);
  if (list.length <= show) return list.join(", ");
  return `${list.slice(0, show).join(", ")} +${list.length - show}`;
}
