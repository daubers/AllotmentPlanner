from urllib.parse import urlencode

import structlog
from flask import current_app, make_response, redirect, request
from flask.views import MethodView
from flask_jwt_extended import jwt_required
from flask_smorest import Blueprint, abort

from .. import events, sso
from ..extensions import db
from ..models import OidcIdentity
from ..schemas import AuthMethodsSchema, OidcExchangeSchema, OidcLinkStartSchema, TokenSchema
from ..security import current_user
from .auth import _tokens

log = structlog.get_logger(__name__)

blp = Blueprint(
    "oidc",
    __name__,
    url_prefix="/api/v1/auth/oidc",
    description="Sign in with an OpenID Connect provider (single sign-on)",
)

BINDER_COOKIE = "oidc_binder"
REDIRECT_DOC = {"302": {"description": "Redirects to the provider, or back to the app"}}


def _allowed_back(url: str) -> bool:
    """Whether the phone app may be sent to this address after signing in."""
    for allowed in current_app.config["OIDC_MOBILE_REDIRECTS"]:
        if url == allowed or url.startswith((f"{allowed}/", f"{allowed}?")):
            return True
    return False


def _back_to(client: str, back: str, *, linking: bool = False, **params) -> str:
    """The address to finish on: the web app's own page, or the phone app's deep link."""
    query = urlencode({k: v for k, v in params.items() if v})
    if client == "mobile":
        return f"{back}{'&' if '?' in back else '?'}{query}"
    if linking:  # the person is signed in already: back to their account page
        return f"/account?{query}"
    page = "/auth/callback" if "code" in params else "/login"
    return f"{page}?{query}"


@blp.route("/<provider_id>/login")
class OidcLogin(MethodView):
    @blp.doc(
        responses=REDIRECT_DOC,
        parameters=[
            {
                "in": "query",
                "name": "client",
                "schema": {"type": "string", "enum": ["web", "mobile"]},
            },
            {"in": "query", "name": "invite", "schema": {"type": "string"}},
            {"in": "query", "name": "redirect", "schema": {"type": "string"}},
            {"in": "query", "name": "link", "schema": {"type": "string"}},
        ],
    )
    def get(self, provider_id):
        """Send the browser to the provider to sign in (or, with `link`, to link a login)."""
        prov = sso.provider(provider_id)
        if prov is None:
            abort(404, message="Unknown sign-in provider")
        client = request.args.get("client", "web")
        if client not in ("web", "mobile"):
            abort(422, message="client must be web or mobile")
        back = request.args.get("redirect", "")
        if client == "mobile" and not _allowed_back(back):
            abort(422, message="That redirect is not allowed")
        link_user_id = None
        if request.args.get("link"):
            if client != "web":
                abort(422, message="Linking is done from the web app")
            # Spend the link code now: the user it names is who the callback will link to.
            linking_user = sso.redeem_code(request.args["link"], "link")
            if linking_user is None:
                return redirect(_back_to(client, back, linking=True, error="link_expired"))
            link_user_id = linking_user.id
        try:
            url, binder = sso.start(
                prov,
                request.url_root,
                client=client,
                invite=request.args.get("invite", ""),
                back=back,
                link_user_id=link_user_id,
            )
        except sso.OidcError as exc:
            log.warning("oidc_start_failed", provider=provider_id, code=exc.code, detail=str(exc))
            return redirect(_back_to(client, back, linking=bool(link_user_id), error=exc.code))
        response = make_response(redirect(url))
        response.set_cookie(
            BINDER_COOKIE,
            binder,
            max_age=current_app.config["OIDC_STATE_TTL_SECONDS"],
            httponly=True,
            samesite="Lax",
            secure=request.is_secure,
            path="/api/v1/auth/oidc",
        )
        return response


@blp.route("/<provider_id>/callback")
class OidcCallback(MethodView):
    @blp.doc(responses=REDIRECT_DOC)
    def get(self, provider_id):
        """Where the provider sends the browser back; ends by redirecting with a one-time code."""
        prov = sso.provider(provider_id)
        if prov is None:
            abort(404, message="Unknown sign-in provider")
        state: dict = {}
        try:
            state = sso.read_state(
                request.args.get("state", ""), request.cookies.get(BINDER_COOKIE)
            )
            if state["p"] != provider_id:
                raise sso.OidcError("invalid_state", "state is for another provider")
            if request.args.get("error"):
                raise sso.OidcError(
                    "denied", request.args.get("error_description", "") or request.args["error"]
                )
            if not request.args.get("code"):
                raise sso.OidcError("invalid_state", "no code")
            claims = sso.claims_for(prov, request.url_root, request.args["code"], state)
            if state.get("l"):
                sso.link_identity(prov, claims, state["l"])
                code = None
            else:
                user = sso.resolve_user(prov, claims, state.get("i", ""))
                code = sso.issue_code(user)
        except sso.OidcError as exc:
            linking = bool(state.get("l"))
            log.warning("oidc_signin_failed", provider=provider_id, code=exc.code, detail=str(exc))
            if not linking:
                events.emit(
                    "user.login_failed", payload={"provider": provider_id, "reason": exc.code}
                )
            client, back = state.get("c", "web"), state.get("r", "")
            if client == "mobile" and not _allowed_back(back):
                client = "web"
            response = make_response(
                redirect(_back_to(client, back, linking=linking, error=exc.code))
            )
        else:
            if code is None:
                target = _back_to("web", "", linking=True, linked=provider_id)
            else:
                target = _back_to(state["c"], state["r"], code=code)
            response = make_response(redirect(target))
        response.delete_cookie(BINDER_COOKIE, path="/api/v1/auth/oidc")
        return response


@blp.route("/exchange")
class OidcExchange(MethodView):
    @blp.arguments(OidcExchangeSchema)
    @blp.response(200, TokenSchema)
    def post(self, data):
        """Swap the one-time code from the redirect for the app's own tokens."""
        user = sso.redeem_code(data["code"])
        if user is None:
            abort(401, message="That sign-in code is invalid or has expired")
        events.emit("user.logged_in", actor_id=user.id, payload={"via": "oidc"})
        return _tokens(user)


def _methods(user) -> dict:
    """How this user can sign in: whether they have a password, and the providers they linked."""
    names = {p["id"]: p["name"] for p in sso.providers()}
    rows = (
        db.session.query(OidcIdentity)
        .filter_by(user_id=user.id)
        .order_by(OidcIdentity.created_at, OidcIdentity.id)
        .all()
    )
    return {
        "has_password": bool(user.password_hash),
        "identities": [
            {
                "id": r.id,
                "provider": r.provider,
                "provider_name": names.get(r.provider),
                "email": r.email,
                "created_at": r.created_at,
            }
            for r in rows
        ],
    }


@blp.route("/identities")
class OidcIdentities(MethodView):
    @jwt_required()
    @blp.response(200, AuthMethodsSchema)
    def get(self):
        """The ways the signed-in user can sign in."""
        return _methods(current_user())


@blp.route("/identities/<int:identity_id>")
class OidcIdentityView(MethodView):
    @jwt_required()
    @blp.response(204)
    def delete(self, identity_id):
        """Unlink a provider. Refused if it is the only way left to sign in."""
        user = current_user()
        identity = db.session.get(OidcIdentity, identity_id)
        if identity is None or identity.user_id != user.id:
            abort(404, message="That sign-in method is not linked to your account")
        others = (
            db.session.query(OidcIdentity)
            .filter(OidcIdentity.user_id == user.id, OidcIdentity.id != identity.id)
            .count()
        )
        if not user.password_hash and others == 0:
            abort(
                409,
                message="This is the only way you can sign in, so it can't be unlinked. "
                "Link another provider first.",
            )
        provider = identity.provider
        db.session.delete(identity)
        db.session.commit()
        events.emit("user.oidc_unlinked", actor_id=user.id, payload={"provider": provider})


@blp.route("/<provider_id>/link")
class OidcLink(MethodView):
    @jwt_required()
    @blp.response(200, OidcLinkStartSchema)
    def post(self, provider_id):
        """Begin linking a provider to the signed-in account; go to the returned `url`."""
        prov = sso.provider(provider_id)
        if prov is None:
            abort(404, message="Unknown sign-in provider")
        user = current_user()
        if db.session.query(OidcIdentity).filter_by(user_id=user.id, provider=provider_id).first():
            abort(409, message=f"{prov['name']} is already linked to your account")
        code = sso.issue_code(user, purpose="link")
        return {"url": f"/api/v1/auth/oidc/{provider_id}/login?client=web&link={code}"}
