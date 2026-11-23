"""What to bring on a visit, worked out from its tasks. Pure, no database.

The list is the equipment on the visit's tasks that are still to do. A task with none of its own
borrows the first couple of suggestions, so a visit is useful before anyone has ticked a tool.
Then hand-made changes apply: an extra is added, a removed one is hidden wherever it came from.
"""

from dataclasses import dataclass

MAX_SUGGESTED_PER_TASK = 2
SOURCE_ORDER = {"task": 0, "suggested": 1, "extra": 2}


@dataclass(frozen=True)
class TaskNeed:
    """What one pegged task asks for."""

    task_id: int
    done: bool
    own: tuple[int, ...] = ()  # equipment ids on the task
    suggested: tuple[int, ...] = ()  # best first; only looked at when ``own`` is empty


def compute_bring(
    tasks: list[TaskNeed], extras: dict[int, str], catalog: dict[int, dict]
) -> list[dict]:
    """The bring list: one entry per item with its ``source`` (task, suggested or extra).

    ``extras`` maps an equipment id to "add" or "remove". ``catalog`` maps ids to the item's
    brief (id, name, kind, kind_label, quantity, status); ids it does not know are ignored, which
    is how an item deleted since is dropped.
    """
    found: dict[int, dict] = {}

    def note(item_id: int, source: str, task_id: int | None) -> None:
        if item_id not in catalog:
            return
        row = found.get(item_id)
        if row is None:
            row = found[item_id] = {**catalog[item_id], "source": source, "task_ids": set()}
        elif SOURCE_ORDER[source] < SOURCE_ORDER[row["source"]]:
            row["source"] = source
        if task_id is not None:
            row["task_ids"].add(task_id)

    for task in tasks:
        if task.done:
            continue  # nothing to bring for a job already finished
        if task.own:
            for item_id in task.own:
                note(item_id, "task", task.task_id)
        else:
            for item_id in task.suggested[:MAX_SUGGESTED_PER_TASK]:
                note(item_id, "suggested", task.task_id)
    for item_id, mode in extras.items():
        if mode == "add":
            note(item_id, "extra", None)
    for item_id, mode in extras.items():
        if mode == "remove":
            found.pop(item_id, None)
    out = [{**row, "task_ids": sorted(row["task_ids"])} for row in found.values()]
    return sorted(out, key=lambda r: (SOURCE_ORDER[r["source"]], r["name"].lower(), r["id"]))
