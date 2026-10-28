from datetime import UTC, datetime, timedelta

from flask.views import MethodView
from flask_smorest import Blueprint, abort

from .. import events
from ..crypto import encrypt
from ..extensions import db
from ..fediverse import MastodonClient, MastodonError, ensure_public_host, normalise_instance_url
from ..mastodon_posts import enqueue, new_post
from ..models import MastodonAccount, MastodonPost, Role
from ..schemas import (
    MastodonPostQuerySchema,
    MastodonPostSchema,
    MastodonSettingsInSchema,
    MastodonSettingsSchema,
)
from ..security import require_role

blp = Blueprint(
    "mastodon",
    __name__,
    url_prefix="/api/v1/allotments/<int:allotment_id>/mastodon",
    description="Post allotment activity to a Mastodon account",
)

OPT_INS = ("enabled", "on_task_completed", "on_photos", "daily_digest")


def settings_to_dict(account: MastodonAccount | None) -> dict:
    if account is None:
        return {
            "configured": False,
            "instance_url": None,
            "handle": None,
            "token_set": False,
            "visibility": "unlisted",
            **dict.fromkeys(OPT_INS, False),
        }
    return {
        "configured": True,
        "instance_url": account.instance_url,
        "handle": account.handle,
        "token_set": True,
        "visibility": account.visibility,
        **{key: getattr(account, key) for key in OPT_INS},
    }


def post_to_dict(post: MastodonPost) -> dict:
    return {
        "id": post.id,
        "kind": post.kind,
        "text": post.text,
        "media_count": len(post.media_ids or []),
        "status": post.status,
        "attempts": post.attempts,
        "error": post.error,
        "remote_url": post.remote_url,
        "created_at": post.created_at,
        "send_after": post.send_after,
        "posted_at": post.posted_at,
    }


def _account(allotment) -> MastodonAccount | None:
    return db.session.query(MastodonAccount).filter_by(allotment_id=allotment.id).one_or_none()


def _verify(url: str, token: str) -> str:
    try:
        ensure_public_host(url)
        return MastodonClient(url, token).verify_credentials()
    except MastodonError as exc:
        abort(422, message=str(exc))


@blp.route("")
class MastodonSettings(MethodView):
    @require_role(Role.EDITOR)
    @blp.response(200, MastodonSettingsSchema)
    def get(self, allotment, membership):
        return settings_to_dict(_account(allotment))

    @require_role(Role.OWNER)
    @blp.arguments(MastodonSettingsInSchema)
    @blp.response(200, MastodonSettingsSchema)
    def put(self, data, allotment, membership):
        """Connect or update the account. The token is checked against the instance first."""
        try:
            url = normalise_instance_url(data["instance_url"])
        except ValueError as exc:
            abort(422, message=str(exc))
        account = _account(allotment)
        token = data["access_token"]
        if account is None and not token:
            abort(422, message="An access token is required to connect")
        if account is not None and url != account.instance_url and not token:
            abort(422, message="Enter a new access token when changing instance")
        if token:
            handle = _verify(url, token)
            if account is None:
                account = MastodonAccount(allotment_id=allotment.id)
                db.session.add(account)
            account.instance_url, account.handle = url, handle
            account.token_encrypted = encrypt(token)
        account.visibility = data["visibility"]
        for key in OPT_INS:
            setattr(account, key, data[key])
        db.session.commit()
        events.emit(
            "mastodon.configured",
            actor_id=membership.user_id,
            allotment_id=allotment.id,
            payload={"enabled": account.enabled, "instance": account.instance_url},
        )
        return settings_to_dict(account)

    @require_role(Role.OWNER)
    @blp.response(204)
    def delete(self, allotment, membership):
        """Disconnect. Queued posts are dropped; the history stays."""
        account = _account(allotment)
        if account is None:
            abort(404, message="Mastodon isn't connected")
        db.session.query(MastodonPost).filter(
            MastodonPost.allotment_id == allotment.id, MastodonPost.status == "pending"
        ).update({"status": "skipped", "error": "Disconnected"})
        db.session.delete(account)
        db.session.commit()
        events.emit("mastodon.disconnected", actor_id=membership.user_id, allotment_id=allotment.id)


@blp.route("/test")
class MastodonTest(MethodView):
    @require_role(Role.OWNER)
    @blp.response(202, MastodonPostSchema)
    def post(self, allotment, membership):
        """Queue a test status. It is sent as 'direct' (only the account itself sees it)."""
        if _account(allotment) is None:
            abort(409, message="Connect an account first")
        post = new_post(allotment.id, "test", "🌱 Test post from Allotment Planner")
        db.session.commit()
        enqueue(post)
        db.session.refresh(post)
        return post_to_dict(post)


@blp.route("/posts")
class MastodonPosts(MethodView):
    @require_role(Role.EDITOR)
    @blp.arguments(MastodonPostQuerySchema, location="query")
    @blp.response(200, MastodonPostSchema(many=True))
    def get(self, args, allotment, membership):
        q = db.session.query(MastodonPost).filter_by(allotment_id=allotment.id)
        if "status" in args:
            q = q.filter_by(status=args["status"])
        return [post_to_dict(p) for p in q.order_by(MastodonPost.id.desc()).limit(args["limit"])]


@blp.route("/posts/<int:post_id>/retry")
class MastodonPostRetry(MethodView):
    @require_role(Role.OWNER)
    @blp.response(202, MastodonPostSchema)
    def post(self, allotment, membership, post_id):
        """Try a failed post again (or one stuck in 'sending' for over 15 minutes)."""
        post = db.session.get(MastodonPost, post_id)
        if post is None or post.allotment_id != allotment.id:
            abort(404, message="Post not found")
        stale = post.status == "sending" and post.send_after < datetime.now(UTC) - timedelta(
            minutes=15
        )
        if post.status != "failed" and not stale:
            abort(409, message=f"A {post.status} post can't be retried")
        if _account(allotment) is None:
            abort(409, message="Connect an account first")
        post.status, post.error, post.attempts = "pending", None, 0
        post.send_after = datetime.now(UTC)
        db.session.commit()
        enqueue(post)
        db.session.refresh(post)
        return post_to_dict(post)
