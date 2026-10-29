from flask import current_app
from flask.views import MethodView
from flask_smorest import Blueprint, abort

from ..celery_app import celery
from ..extensions import db
from ..models import Media, PacketScan, Role
from ..schemas import PacketScanInSchema, PacketScanSchema
from ..security import require_role
from .media import media_to_dict

blp = Blueprint(
    "packet_scans",
    __name__,
    url_prefix="/api/v1/allotments/<int:allotment_id>/packet-scans",
    description="Reading a photo of a seed packet into a draft packet",
)


def scan_to_dict(scan: PacketScan) -> dict:
    crop = db.session.get(Media, scan.crop_media_id) if scan.crop_media_id else None
    return {
        "id": scan.id,
        "status": scan.status,
        "error": scan.error,
        "media_id": scan.media_id,
        "packet_id": scan.packet_id,
        "calendar_source": scan.calendar_source,
        "rotation": scan.rotation,
        "missing": scan.missing or [],
        "crop": media_to_dict(crop) if crop else None,
        "created_at": scan.created_at,
        "finished_at": scan.finished_at,
    }


def _get(allotment, scan_id: int) -> PacketScan:
    scan = db.session.get(PacketScan, scan_id)
    if scan is None or scan.allotment_id != allotment.id:
        abort(404, message="Scan not found")
    return scan


def _enqueue(scan: PacketScan) -> None:
    from ..tasks import run_packet_scan

    try:
        run_packet_scan.apply_async(args=[scan.id])
    except Exception:  # noqa: BLE001 - broker down: it stays queued, retry via /retry
        current_app.logger.exception("could not queue packet scan")
    if celery.conf.task_always_eager:
        db.session.expire_all()  # the eager task committed through its own session


@blp.route("")
class ScanList(MethodView):
    @require_role(Role.VIEWER)
    @blp.response(200, PacketScanSchema(many=True))
    def get(self, allotment, membership):
        scans = (
            db.session.query(PacketScan)
            .filter_by(allotment_id=allotment.id)
            .order_by(PacketScan.id.desc())
            .limit(50)
            .all()
        )
        return [scan_to_dict(s) for s in scans]

    @require_role(Role.EDITOR)
    @blp.arguments(PacketScanInSchema)
    @blp.response(202, PacketScanSchema)
    def post(self, data, allotment, membership):
        """Start reading a photo already uploaded to the allotment. The result is a draft packet."""
        media = db.session.get(Media, data["media_id"])
        if media is None or media.allotment_id != allotment.id:
            abort(422, message="media_id does not belong to this allotment")
        if media.kind != "photo":
            abort(422, message="Only photos can be read")
        scan = PacketScan(
            allotment_id=allotment.id, media_id=media.id, created_by=membership.user_id
        )
        db.session.add(scan)
        db.session.commit()
        _enqueue(scan)
        return scan_to_dict(scan)


@blp.route("/<int:scan_id>")
class ScanDetail(MethodView):
    @require_role(Role.VIEWER)
    @blp.response(200, PacketScanSchema)
    def get(self, allotment, membership, scan_id):
        return scan_to_dict(_get(allotment, scan_id))


@blp.route("/<int:scan_id>/retry")
class ScanRetry(MethodView):
    @require_role(Role.EDITOR)
    @blp.response(202, PacketScanSchema)
    def post(self, allotment, membership, scan_id):
        """Run a failed (or stuck queued) scan again."""
        scan = _get(allotment, scan_id)
        if scan.status not in ("failed", "queued"):
            abort(409, message="Only a failed scan can be retried")
        scan.status, scan.error = "queued", None
        db.session.commit()
        _enqueue(scan)
        return scan_to_dict(scan)
