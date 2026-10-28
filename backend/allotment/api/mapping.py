from datetime import UTC, datetime

from flask import Response, current_app, request
from flask.views import MethodView
from flask_smorest import Blueprint, abort
from itsdangerous import BadSignature, URLSafeTimedSerializer

from .. import events
from ..extensions import db
from ..mapping_video import estimated_frames
from ..models import MapJob, MapLayer, Media, Role
from ..schemas import (
    MapJobInSchema,
    MapJobSchema,
    MapLayerPatchSchema,
    MapLayerSchema,
)
from ..security import require_role
from ..storage import get_storage, safe_delete_prefix

blp = Blueprint(
    "mapping",
    __name__,
    url_prefix="/api/v1/allotments/<int:allotment_id>",
    description="Build map layers from photos and video, and show them",
)
tiles_blp = Blueprint(
    "layer-tiles", __name__, url_prefix="/api/v1/layers", description="Map tiles (signed links)"
)

ACTIVE = ("queued", "running")
MIN_IMAGES = 5
MIN_GEOTAGGED = 3
# A 1x1 transparent PNG, served for tiles that don't exist so the map shows nothing, not errors.
EMPTY_TILE = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d49444154789c6360000002000001e221bc330000000049454e44ae426082"
)


def _signer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(current_app.config["JWT_SECRET_KEY"], salt="layer-tiles")


def job_to_dict(job: MapJob, layer_id: int | None = None, detail: bool = False) -> dict:
    return {
        "id": job.id,
        "name": job.name,
        "status": job.status,
        "stage": job.stage,
        "view": job.view,
        "camera_height_m": job.camera_height_m,
        "media_count": len(job.media_ids or []),
        "shots_total": job.shots_total,
        "shots_used": job.shots_used,
        "error": job.error,
        "log": job.log if detail else "",
        "layer_id": layer_id,
        "cancel_requested": job.cancel_requested,
        "created_at": job.created_at,
        "started_at": job.started_at,
        "finished_at": job.finished_at,
    }


def layer_to_dict(layer: MapLayer) -> dict:
    token = _signer().dumps(layer.id)
    return {
        "id": layer.id,
        "name": layer.name,
        "job_id": layer.job_id,
        "bounds": [layer.west, layer.south, layer.east, layer.north],
        "min_zoom": layer.min_zoom,
        "max_zoom": layer.max_zoom,
        "tile_count": layer.tile_count,
        "opacity": layer.opacity,
        "visible": layer.visible,
        "tile_url": f"/api/v1/layers/{layer.id}/tiles/{{z}}/{{x}}/{{y}}.png?t={token}",
        "created_at": layer.created_at,
    }


def _layer_ids(job_ids: list[int]) -> dict[int, int]:
    rows = db.session.query(MapLayer.job_id, MapLayer.id).filter(MapLayer.job_id.in_(job_ids))
    return dict(rows.all())


def _get_job(allotment, job_id: int) -> MapJob:
    job = db.session.get(MapJob, job_id)
    if job is None or job.allotment_id != allotment.id:
        abort(404, message="Job not found")
    return job


@blp.route("/map-jobs")
class MapJobList(MethodView):
    @require_role(Role.EDITOR)
    @blp.response(200, MapJobSchema(many=True))
    def get(self, allotment, membership):
        jobs = (
            db.session.query(MapJob)
            .filter_by(allotment_id=allotment.id)
            .order_by(MapJob.id.desc())
            .limit(30)
            .all()
        )
        layers = _layer_ids([j.id for j in jobs])
        return [job_to_dict(j, layers.get(j.id)) for j in jobs]

    @require_role(Role.EDITOR)
    @blp.arguments(MapJobInSchema)
    @blp.response(202, MapJobSchema)
    def post(self, data, allotment, membership):
        """Queue a map build from photos and videos.

        Needs about 5+ overlapping images (a video counts as the frames sampled from it, about
        one a second) and 3+ photos with a location, which place and scale the map."""
        if (
            db.session.query(MapJob)
            .filter(MapJob.allotment_id == allotment.id, MapJob.status.in_(ACTIVE))
            .first()
        ):
            abort(409, message="A map is already being built for this allotment")
        query = db.session.query(Media).filter(
            Media.allotment_id == allotment.id, Media.status == "ready"
        )
        if data["media_ids"] is None:
            query = query.filter(Media.kind.in_(["photo", "video"]))
        else:
            query = query.filter(Media.id.in_(data["media_ids"]))
        media = query.order_by(Media.taken_at, Media.id).all()
        if data["media_ids"] is not None and len(media) != len(set(data["media_ids"])):
            abort(422, message="Some of those files aren't ready or aren't in this allotment")
        cfg = current_app.config
        images = sum(
            1
            if m.kind == "photo"
            else estimated_frames(
                m.duration_s,
                cfg["MAPPING_VIDEO_FRAMES_PER_SECOND"],
                cfg["MAPPING_MAX_FRAMES_PER_VIDEO"],
            )
            for m in media
        )
        if images < MIN_IMAGES:
            abort(
                422,
                message=f"Pick at least {MIN_IMAGES} photos (or a video long enough for that many "
                "frames) that overlap each other",
            )
        if images > cfg["MAPPING_MAX_IMAGES"]:
            abort(
                422,
                message=f"That is about {images} images; pick at most {cfg['MAPPING_MAX_IMAGES']} "
                "photos or seconds of video for one map",
            )
        located = sum(1 for m in media if m.kind == "photo" and m.lat is not None)
        if located < MIN_GEOTAGGED:
            abort(
                422,
                message=f"At least {MIN_GEOTAGGED} of the photos need a location to place the map "
                f"({located} have one). A video has only one location, so it can't place the map "
                "by itself",
            )
        job = MapJob(
            allotment_id=allotment.id,
            name=data["name"].strip() or f"Map {datetime.now(UTC):%d %b %Y}",
            media_ids=[m.id for m in media],
            view=data["view"],
            camera_height_m=data["camera_height_m"],
            created_by=membership.user_id,
        )
        db.session.add(job)
        db.session.commit()
        from ..tasks import run_map_job

        run_map_job.apply_async(args=[job.id])
        events.emit(
            "map_job.created",
            actor_id=membership.user_id,
            allotment_id=allotment.id,
            subject={"map_job_id": job.id},
            payload={"media": len(job.media_ids), "view": job.view},
        )
        db.session.refresh(job)
        return job_to_dict(job)


@blp.route("/map-jobs/<int:job_id>")
class MapJobDetail(MethodView):
    @require_role(Role.EDITOR)
    @blp.response(200, MapJobSchema)
    def get(self, allotment, membership, job_id):
        job = _get_job(allotment, job_id)
        return job_to_dict(job, _layer_ids([job.id]).get(job.id), detail=True)

    @require_role(Role.EDITOR)
    @blp.response(204)
    def delete(self, allotment, membership, job_id):
        """Remove a finished job's record. Its layer, if any, stays until deleted itself."""
        job = _get_job(allotment, job_id)
        if job.status in ACTIVE:
            abort(409, message="Cancel the job first")
        db.session.delete(job)
        db.session.commit()


@blp.route("/map-jobs/<int:job_id>/cancel")
class MapJobCancel(MethodView):
    @require_role(Role.EDITOR)
    @blp.response(202, MapJobSchema)
    def post(self, allotment, membership, job_id):
        """Stop a job: at once if it is still queued, within about ten seconds if running."""
        job = _get_job(allotment, job_id)
        if job.status not in ACTIVE:
            abort(409, message=f"A {job.status} job can't be cancelled")
        job.cancel_requested = True
        if job.status == "queued":
            job.status, job.finished_at = "cancelled", datetime.now(UTC)
        db.session.commit()
        return job_to_dict(job)


@blp.route("/layers")
class LayerList(MethodView):
    @require_role(Role.VIEWER)
    @blp.response(200, MapLayerSchema(many=True))
    def get(self, allotment, membership):
        layers = (
            db.session.query(MapLayer).filter_by(allotment_id=allotment.id).order_by(MapLayer.id)
        )
        return [layer_to_dict(layer) for layer in layers]


@blp.route("/layers/<int:layer_id>")
class LayerDetail(MethodView):
    def _get(self, allotment, layer_id: int) -> MapLayer:
        layer = db.session.get(MapLayer, layer_id)
        if layer is None or layer.allotment_id != allotment.id:
            abort(404, message="Layer not found")
        return layer

    @require_role(Role.EDITOR)
    @blp.arguments(MapLayerPatchSchema)
    @blp.response(200, MapLayerSchema)
    def patch(self, data, allotment, membership, layer_id):
        layer = self._get(allotment, layer_id)
        for key, value in data.items():
            setattr(layer, key, value)
        db.session.commit()
        return layer_to_dict(layer)

    @require_role(Role.EDITOR)
    @blp.response(204)
    def delete(self, allotment, membership, layer_id):
        layer = self._get(allotment, layer_id)
        prefix = layer.tile_prefix.rsplit("/", 1)[0]  # the layer's whole folder
        db.session.delete(layer)
        db.session.commit()
        safe_delete_prefix(prefix)
        events.emit(
            "layer.deleted",
            actor_id=membership.user_id,
            allotment_id=allotment.id,
            subject={"layer_id": layer_id},
        )


@tiles_blp.route("/<int:layer_id>/tiles/<int:z>/<int:x>/<int:y>.png")
class LayerTile(MethodView):
    @tiles_blp.doc(
        parameters=[{"in": "query", "name": "t", "required": True, "schema": {"type": "string"}}]
    )
    @tiles_blp.response(200)
    def get(self, layer_id, z, x, y):
        """One map tile. Authorised by the signed ``t`` token from the layer JSON."""
        try:
            token_id = _signer().loads(
                request.args.get("t", ""),
                max_age=current_app.config["MAPPING_TILE_TOKEN_TTL_SECONDS"],
            )
        except BadSignature:
            abort(403, message="Invalid or expired link")
        layer = db.session.get(MapLayer, layer_id)
        if layer is None or token_id != layer_id:
            abort(404, message="Layer not found")
        data = get_storage().get_bytes(f"{layer.tile_prefix}/{z}/{x}/{y}.png")
        found = data is not None
        response = Response(data if found else EMPTY_TILE, mimetype="image/png")
        response.headers["Cache-Control"] = (
            "private, max-age=3600" if found else "private, max-age=60"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response
