from datetime import UTC, datetime

from flask import Response, current_app, request
from flask.views import MethodView
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    get_jwt_identity,
    jwt_required,
)
from flask_smorest import Blueprint, abort
from itsdangerous import BadSignature, URLSafeTimedSerializer

from .. import events, sso
from ..allotment_ops import remove_allotment_files, stage_allotment_delete
from ..extensions import db
from ..invites import read_invite
from ..models import AccountExport, Allotment, Membership, User
from ..schemas import (
    AccessTokenSchema,
    AccountExportSchema,
    AuthConfigSchema,
    DeleteAccountSchema,
    LoginSchema,
    RegisterSchema,
    TokenSchema,
    UserSchema,
)
from ..security import current_user, hash_password, verify_password
from ..storage import get_storage, safe_delete_prefix
from ..tasks import build_account_export

blp = Blueprint("auth", __name__, url_prefix="/api/v1/auth", description="Authentication")


def _tokens(user: User) -> dict:
    identity = str(user.id)
    return {
        "access_token": create_access_token(identity),
        "refresh_token": create_refresh_token(identity),
        "user": user,
    }


@blp.route("/config")
class AuthConfig(MethodView):
    @blp.response(200, AuthConfigSchema)
    def get(self):
        """How accounts can be created here, so the sign-in page can ask for an invite code."""
        return {
            "registration": current_app.config["REGISTRATION"],
            "oidc": [
                {"id": p["id"], "name": p["name"]} for p in current_app.config["OIDC_PROVIDERS"]
            ],
        }


@blp.route("/register")
class Register(MethodView):
    @blp.arguments(RegisterSchema)
    @blp.response(201, TokenSchema)
    def post(self, data):
        email = data["email"].lower()
        invite = None
        if data.get("invite_code"):
            invite = read_invite(data["invite_code"])
            if invite is None or invite["e"] != email:
                abort(403, message="This invite is invalid, expired or for a different email")
            if db.session.get(Allotment, invite["a"]) is None:
                abort(403, message="This invite is no longer valid")
        elif current_app.config["REGISTRATION"] == "invite" and db.session.query(User.id).first():
            abort(403, message="Registration is by invitation only")
        if db.session.query(User).filter_by(email=email).first():
            abort(409, message="Email already registered")
        user = User(
            email=email,
            display_name=data["display_name"],
            password_hash=hash_password(data["password"]),
        )
        db.session.add(user)
        db.session.flush()
        if invite:
            db.session.add(Membership(user_id=user.id, allotment_id=invite["a"], role=invite["r"]))
        db.session.commit()
        events.emit("user.registered", actor_id=user.id, subject={"user_id": user.id})
        if invite:
            events.emit(
                "member.added",
                actor_id=invite["i"],
                allotment_id=invite["a"],
                subject={"user_id": user.id},
                payload={"role": invite["r"], "via": "invite"},
            )
        return _tokens(user)


@blp.route("/login")
class Login(MethodView):
    @blp.arguments(LoginSchema)
    @blp.response(200, TokenSchema)
    def post(self, data):
        user = db.session.query(User).filter_by(email=data["email"].lower()).one_or_none()
        if user is None or not verify_password(user.password_hash, data["password"]):
            events.emit("user.login_failed", payload={"email": data["email"].lower()})
            abort(401, message="Invalid email or password")
        events.emit("user.logged_in", actor_id=user.id)
        return _tokens(user)


@blp.route("/refresh")
class Refresh(MethodView):
    @jwt_required(refresh=True)
    @blp.response(200, AccessTokenSchema)
    def post(self):
        return {"access_token": create_access_token(get_jwt_identity())}


@blp.route("/me")
class Me(MethodView):
    @jwt_required()
    @blp.response(200, UserSchema)
    def get(self):
        return current_user()

    @jwt_required()
    @blp.arguments(DeleteAccountSchema)
    @blp.response(204)
    def delete(self, data):
        """Delete the signed-in account.

        Needs the password, or for an account without one a `reauth_code` from a provider login.
        Allotments only this person belongs to are deleted with their files. Refused (409) while
        they are the only owner of an allotment that has other members: hand it over first.
        Anything else they added stays, no longer attributed to them.
        """
        user = current_user()
        if user.password_hash:
            if not verify_password(user.password_hash, data.get("password", "")):
                abort(403, message="That password is not right")
        else:
            confirmed = sso.redeem_code(data.get("reauth_code", ""), "reauth")
            if confirmed is None or confirmed.id != user.id:
                abort(403, message="Confirm with your sign-in provider first")

        sole, shared = [], []
        for m in user.memberships:
            if m.role != "owner":
                continue
            owners = db.session.query(Membership).filter_by(
                allotment_id=m.allotment_id, role="owner"
            )
            if owners.count() > 1:
                continue
            members = db.session.query(Membership).filter_by(allotment_id=m.allotment_id).count()
            (shared if members > 1 else sole).append(m.allotment)
        if shared:
            abort(
                409,
                message="You are the only owner of allotments shared with others. Make someone "
                "else an owner, or delete them, first.",
                errors={"allotments": [{"id": a.id, "name": a.name} for a in shared]},
            )

        user_id = user.id
        cleanup = [stage_allotment_delete(a) for a in sole]
        db.session.delete(user)
        db.session.commit()
        for allotment_id, keys in cleanup:
            remove_allotment_files(allotment_id, keys)
        safe_delete_prefix(f"exports/{user_id}")
        events.emit("user.deleted", payload={"allotments_deleted": len(cleanup)})


def _export_signer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(current_app.config["JWT_SECRET_KEY"], salt="export-url")


def _export_dict(export: AccountExport) -> dict:
    ready = export.status == "ready" and export.expires_at and export.expires_at > datetime.now(UTC)
    return {
        "id": export.id,
        "status": export.status if ready or export.status != "ready" else "expired",
        "size_bytes": export.size_bytes,
        "created_at": export.created_at,
        "expires_at": export.expires_at,
        "url": f"/api/v1/auth/me/export/{export.id}/file?t={_export_signer().dumps(export.id)}"
        if ready
        else None,
    }


@blp.route("/me/export")
class MeExport(MethodView):
    @jwt_required()
    @blp.response(202, AccountExportSchema)
    def post(self):
        """Ask for a zip of your data: your content as JSON plus the files you uploaded.

        It is built in the background; poll `GET /me/export/{id}` until `status` is `ready`.
        A request already being built is returned instead of starting another.
        """
        user = current_user()
        pending = (
            db.session.query(AccountExport).filter_by(user_id=user.id, status="pending").first()
        )
        if pending:
            return _export_dict(pending)
        export = AccountExport(user_id=user.id)
        db.session.add(export)
        db.session.commit()
        events.emit("user.export_requested", actor_id=user.id)
        build_account_export.delay(export.id)
        db.session.refresh(export)
        return _export_dict(export)


@blp.route("/me/export/<int:export_id>")
class MeExportStatus(MethodView):
    @jwt_required()
    @blp.response(200, AccountExportSchema)
    def get(self, export_id):
        """Where a data export has got to, with a download link once it is ready."""
        export = db.session.get(AccountExport, export_id)
        if export is None or export.user_id != current_user().id:
            abort(404, message="No such export")
        return _export_dict(export)


@blp.route("/me/export/<int:export_id>/file")
class MeExportFile(MethodView):
    @blp.doc(
        parameters=[{"in": "query", "name": "t", "required": True, "schema": {"type": "string"}}],
        responses={"200": {"description": "The zip", "content": {"application/zip": {}}}},
    )
    @blp.response(200)
    def get(self, export_id):
        """Download the zip. The link carries its own signature, so a browser can follow it."""
        try:
            signed = _export_signer().loads(request.args.get("t", ""), max_age=48 * 3600)
        except BadSignature:
            abort(403, message="This link is invalid or has expired")
        export = db.session.get(AccountExport, export_id)
        if signed != export_id or export is None or export.status != "ready":
            abort(404, message="No such export")
        if export.expires_at is None or export.expires_at <= datetime.now(UTC):
            abort(410, message="This export has expired; request a new one")
        storage = get_storage()
        size = storage.size(export.storage_key)
        response = Response(
            storage.read_range(export.storage_key, 0, size - 1),
            mimetype="application/zip",
            direct_passthrough=True,
        )
        response.headers["Content-Length"] = str(size)
        response.headers["Content-Disposition"] = 'attachment; filename="allotment-data.zip"'
        response.headers["Cache-Control"] = "private, no-store"
        return response
