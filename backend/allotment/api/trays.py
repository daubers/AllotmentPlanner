from datetime import date

from flask.views import MethodView
from flask_smorest import Blueprint, abort
from sqlalchemy import func

from .. import events
from ..extensions import db
from ..models import Media, Planting, Role, SeedPacket, Tray, TrayCell
from ..plantings import PlantOutError, plant_out_groups
from ..schemas import (
    CellsUpdateSchema,
    PlantOutResultSchema,
    PlantOutSchema,
    TaskSchema,
    TaskSuggestionSchema,
    TrayInSchema,
    TrayPatchSchema,
    TrayQuerySchema,
    TraySchema,
    TraySummarySchema,
)
from ..security import require_role
from ..seeds import (
    MAX_TRAY_CELLS,
    CellChangeError,
    apply_cell_change,
    cells_outside,
    normalise_calendar,
    tray_counts,
    tray_kinds,
)
from ..task_suggestions import Sowing, suggest_for_tray
from .media import media_to_dict
from .tasks import add_suggested, suggestions_with_state, task_to_dict

blp = Blueprint(
    "trays",
    __name__,
    url_prefix="/api/v1/allotments/<int:allotment_id>/trays",
    description="Seed trays: a grid of cells, each sown with a packet",
)

TRAY_FIELDS = ("name", "rows", "cols", "tray_type", "sown_on", "location", "notes", "status")
CELL_FIELDS = ("packet_id", "count", "status", "sown_on", "germinated_on", "note")


def _kinds(cells: list[TrayCell], packets: dict[int, SeedPacket]) -> list[dict]:
    out = []
    for k in tray_kinds(cells):
        packet = packets.get(k["packet_id"])
        out.append(
            {
                **k,
                "name": packet.name if packet else "",
                "variety": packet.variety if packet else "",
            }
        )
    return out


def _packets(packet_ids: set[int]) -> dict[int, SeedPacket]:
    if not packet_ids:
        return {}
    rows = db.session.query(SeedPacket).filter(SeedPacket.id.in_(packet_ids)).all()
    return {p.id: p for p in rows}


def _taken(m: Media):
    return m.taken_at or m.created_at


def _thumbs(tray_ids: list[int]) -> dict[int, str]:
    """The newest photo with a thumbnail for each tray, as its thumbnail link, in one query."""
    out: dict[int, str] = {}
    if tray_ids:
        rows = (
            db.session.query(Media)
            .filter(Media.tray_id.in_(tray_ids), Media.thumb_key.isnot(None))
            .order_by(func.coalesce(Media.taken_at, Media.created_at), Media.id)
            .all()
        )
        for m in rows:  # oldest first, so the newest overwrites
            out[m.tray_id] = media_to_dict(m)["thumb_url"]
    return out


def tray_to_dict(
    t: Tray,
    packets: dict[int, SeedPacket],
    detail: bool = False,
    thumbs: dict[int, str] | None = None,
) -> dict:
    out = {
        "id": t.id,
        **{f: getattr(t, f) for f in TRAY_FIELDS},
        "counts": tray_counts(t.rows, t.cols, t.cells),
        "kinds": _kinds(t.cells, packets),
        "created_at": t.created_at,
        "updated_at": t.updated_at,
        "thumb_url": (thumbs or {}).get(t.id),
    }
    if detail:
        photos = db.session.query(Media).filter_by(tray_id=t.id).order_by(Media.taken_at, Media.id)
        out["cells"] = [
            {
                "row": c.row,
                "col": c.col,
                **{f: getattr(c, f) for f in CELL_FIELDS},
                "planting_id": c.planting_id,
            }
            for c in t.cells
        ]
        photos = photos.all()
        out["photos"] = [media_to_dict(m) for m in photos]
        ready = [m for m in photos if m.thumb_key]
        if ready:
            newest = max(ready, key=lambda m: (_taken(m), m.id))
            out["thumb_url"] = media_to_dict(newest)["thumb_url"]
    return out


def _detail(t: Tray) -> dict:
    return tray_to_dict(t, _packets({c.packet_id for c in t.cells if c.packet_id}), detail=True)


def _get(allotment, tray_id: int) -> Tray:
    tray = db.session.get(Tray, tray_id)
    if tray is None or tray.allotment_id != allotment.id:
        abort(404, message="Tray not found")
    return tray


def _check_size(rows: int, cols: int) -> None:
    if rows * cols > MAX_TRAY_CELLS:
        abort(422, message=f"A tray can have at most {MAX_TRAY_CELLS} cells")


@blp.route("")
class TrayList(MethodView):
    @require_role(Role.VIEWER)
    @blp.arguments(TrayQuerySchema, location="query")
    @blp.response(200, TraySummarySchema(many=True))
    def get(self, args, allotment, membership):
        q = db.session.query(Tray).filter_by(allotment_id=allotment.id)
        if "status" in args:
            q = q.filter(Tray.status == args["status"])
        if "packet_id" in args:
            q = q.filter(Tray.cells.any(TrayCell.packet_id == args["packet_id"]))
        trays = q.order_by(Tray.sown_on.desc().nulls_last(), Tray.id.desc()).all()
        packets = _packets({c.packet_id for t in trays for c in t.cells if c.packet_id})
        thumbs = _thumbs([t.id for t in trays])
        return [tray_to_dict(t, packets, thumbs=thumbs) for t in trays]

    @require_role(Role.EDITOR)
    @blp.arguments(TrayInSchema)
    @blp.response(201, TraySchema)
    def post(self, data, allotment, membership):
        _check_size(data["rows"], data["cols"])
        tray = Tray(allotment_id=allotment.id, created_by=membership.user_id)
        for key in TRAY_FIELDS:
            if key in data:
                setattr(tray, key, data[key])
        db.session.add(tray)
        db.session.commit()
        events.emit(
            "tray.created",
            actor_id=membership.user_id,
            allotment_id=allotment.id,
            subject={"tray_id": tray.id},
            payload={"name": tray.name, "cells": tray.rows * tray.cols},
        )
        return _detail(tray)


@blp.route("/<int:tray_id>")
class TrayDetail(MethodView):
    @require_role(Role.VIEWER)
    @blp.response(200, TraySchema)
    def get(self, allotment, membership, tray_id):
        return _detail(_get(allotment, tray_id))

    @require_role(Role.EDITOR)
    @blp.arguments(TrayPatchSchema)
    @blp.response(200, TraySchema)
    def patch(self, data, allotment, membership, tray_id):
        tray = _get(allotment, tray_id)
        rows, cols = data.get("rows", tray.rows), data.get("cols", tray.cols)
        _check_size(rows, cols)
        lost = cells_outside(tray.cells, rows, cols)
        if lost:
            abort(
                422,
                message=f"Making the tray {rows} x {cols} would drop {len(lost)} sown "
                "cell(s). Clear them first",
            )
        for key in TRAY_FIELDS:
            if key in data:
                setattr(tray, key, data[key])
        db.session.commit()
        events.emit(
            "tray.updated",
            actor_id=membership.user_id,
            allotment_id=allotment.id,
            subject={"tray_id": tray.id},
            payload={"fields": sorted(data)},
        )
        return _detail(tray)

    @require_role(Role.EDITOR)
    @blp.response(204)
    def delete(self, allotment, membership, tray_id):
        """Remove the tray and its cells. Its photos stay in the photo timeline, unlinked."""
        tray = _get(allotment, tray_id)
        db.session.delete(tray)
        db.session.commit()
        events.emit(
            "tray.deleted",
            actor_id=membership.user_id,
            allotment_id=allotment.id,
            subject={"tray_id": tray_id},
        )


@blp.route("/<int:tray_id>/cells")
class TrayCells(MethodView):
    @require_role(Role.EDITOR)
    @blp.arguments(CellsUpdateSchema)
    @blp.response(200, TraySchema)
    def patch(self, data, allotment, membership, tray_id):
        """Sow, germinate, fail or clear the chosen cells in one go. All or nothing."""
        tray = _get(allotment, tray_id)
        change = data["set"]
        refs = sorted({(c["row"], c["col"]) for c in data["cells"]})
        for row, col in refs:
            if row >= tray.rows or col >= tray.cols:
                abort(
                    422,
                    message=f"Row {row + 1}, column {col + 1} is outside this "
                    f"{tray.rows} x {tray.cols} tray",
                )
        if change.get("packet_id") is not None:
            packet = db.session.get(SeedPacket, change["packet_id"])
            if packet is None or packet.allotment_id != allotment.id:
                abort(422, message="packet_id does not belong to this allotment")
        existing = {(c.row, c.col): c for c in tray.cells}
        today = date.today()
        for row, col in refs:
            cell = existing.get((row, col))
            current = {f: getattr(cell, f) for f in CELL_FIELDS} if cell else None
            try:
                new = apply_cell_change(current, change, tray.sown_on, today)
            except CellChangeError as exc:
                db.session.rollback()
                abort(422, message=f"Row {row + 1}, column {col + 1}: {exc}")
            if new is None:
                if cell is not None:
                    tray.cells.remove(cell)  # delete-orphan drops the row
            elif cell is None:
                tray.cells.append(TrayCell(row=row, col=col, **new))
            else:
                for f, v in new.items():
                    setattr(cell, f, v)
        db.session.commit()
        events.emit(
            "tray.cells_updated",
            actor_id=membership.user_id,
            allotment_id=allotment.id,
            subject={"tray_id": tray.id, "packet_id": change.get("packet_id")},
            payload={"cells": len(refs), "status": change.get("status", "sown")},
        )
        return _detail(tray)


def tray_sowings(tray: Tray) -> list[Sowing]:
    """One sowing per packet still in the tray, dated by its earliest sown cell."""
    live = [c for c in tray.cells if c.packet_id and c.status in ("sown", "germinated")]
    packets = _packets({c.packet_id for c in live})
    sowings = []
    for packet_id, packet in sorted(packets.items()):
        cells = [c for c in live if c.packet_id == packet_id]
        dates = [c.sown_on or tray.sown_on for c in cells if c.sown_on or tray.sown_on]
        if not dates:
            continue  # nothing to count from
        cal = normalise_calendar(packet.calendar)
        sowings.append(
            Sowing(
                packet_id=packet_id,
                name=packet.name,
                sown_on=min(dates),
                germinated=all(c.status == "germinated" for c in cells),
                germinate_days_min=packet.germinate_days_min,
                maturity_days_min=packet.maturity_days_min,
                plant_out_months=tuple(cal["plant_out"]),
                harvest_months=tuple(cal["harvest"]),
            )
        )
    return sowings


def _tray_suggestions(tray: Tray):
    return suggest_for_tray(tray.id, tray.name, tray_sowings(tray), date.today())


@blp.route("/<int:tray_id>/suggested-tasks")
class TraySuggestedTasks(MethodView):
    @require_role(Role.VIEWER)
    @blp.response(200, TaskSuggestionSchema(many=True))
    def get(self, allotment, membership, tray_id):
        """Jobs the packets' dates suggest for this tray, marked if already added."""
        return suggestions_with_state(allotment, _tray_suggestions(_get(allotment, tray_id)))

    @require_role(Role.EDITOR)
    @blp.response(201, TaskSchema(many=True))
    def post(self, allotment, membership, tray_id):
        """Add every suggestion not yet added as a task pinned to this tray."""
        tray = _get(allotment, tray_id)
        tasks = add_suggested(allotment, membership, _tray_suggestions(tray), tray_id=tray.id)
        return [task_to_dict(t) for t in tasks]


@blp.route("/<int:tray_id>/plant-out")
class TrayPlantOut(MethodView):
    @require_role(Role.EDITOR)
    @blp.arguments(PlantOutSchema)
    @blp.response(200, PlantOutResultSchema)
    def post(self, data, allotment, membership, tray_id):
        """Plant the chosen cells out into a region of a bed, all or nothing.

        One planting is made per packet among the cells, each filling the chosen region; the cells
        become planted out and point at their planting. The region must lie inside the bed.
        """
        from datetime import date

        from .plantings import check_region, get_bed, parse_region, planting_to_dict

        tray = _get(allotment, tray_id)
        bed = get_bed(allotment, data["feature_id"])
        check_region(bed, data["region"])
        existing = {(c.row, c.col): c for c in tray.cells}
        refs = sorted({(c["row"], c["col"]) for c in data["cells"]})
        chosen = []
        for row, col in refs:
            cell = existing.get((row, col))
            chosen.append(
                {
                    "row": row,
                    "col": col,
                    "status": cell.status if cell else None,
                    "packet_id": cell.packet_id if cell else None,
                    "cell": cell,
                }
            )
        try:
            groups = plant_out_groups(chosen)
        except PlantOutError as exc:
            abort(422, message=str(exc))
        planted_on = data["planted_on"] or date.today()
        plantings = []
        for packet_id, members in groups.items():
            cells = [m["cell"] for m in members]
            planting = Planting(
                allotment_id=allotment.id,
                feature_id=bed.id,
                packet_id=packet_id,
                tray_id=tray.id,
                region=parse_region(data["region"]),
                count=sum(c.count or 1 for c in cells),
                method="transplant",
                status="growing",
                sown_on=min((c.sown_on for c in cells if c.sown_on), default=None),
                planted_on=planted_on,
                notes=data["notes"],
                created_by=membership.user_id,
            )
            db.session.add(planting)
            db.session.flush()
            for cell in cells:
                cell.status = "planted_out"
                cell.planting_id = planting.id
            plantings.append(planting)
        if not any(c.status in ("sown", "germinated") for c in tray.cells):
            tray.status = "planted_out"
        db.session.commit()
        events.emit(
            "tray.planted_out",
            actor_id=membership.user_id,
            allotment_id=allotment.id,
            subject={"tray_id": tray.id, "feature_id": bed.id},
            payload={"cells": len(refs), "plantings": len(plantings), "bed": bed.name},
        )
        return {"plantings": [planting_to_dict(p) for p in plantings], "tray": _detail(tray)}
