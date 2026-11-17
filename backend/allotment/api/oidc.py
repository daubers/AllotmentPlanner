from urllib.parse import urlencode

import structlog
from flask import current_app, make_response, redirect, request
from flask.views import MethodView
from flask_smorest import Blueprint, abort

from .. import events, sso
from ..schemas import OidcExchangeSchema, TokenSchema
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


def _back_to(client: str, back: str, **params) -> str:
    """The address to finish on: the web app's own page, or the phone app's deep link."""
    query = urlencode({k: v for k, v in params.items() if v})
    if client == "mobile":
        return f"{back}{'&' if '?' in back else '?'}{query}"
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
        ],
    )
    def get(self, provider_id):
        """Send the browser to the provider to sign in."""
        prov = sso.provider(provider_id)
        if prov is None:
            abort(404, message="Unknown sign-in provider")
        client = request.args.get("client", "web")
        if client not in ("web", "mobile"):
            abort(422, message="client must be web or mobile")
        back = request.args.get("redirect", "")
        if client == "mobile" and not _allowed_back(back):
            abort(422, message="That redirect is not allowed")
        try:
            url, binder = sso.start(
                prov,
                request.url_root,
                client=client,
                invite=request.args.get("invite", ""),
                back=back,
            )
        except sso.OidcError as exc:
            log.warning("oidc_start_failed", provider=provider_id, code=exc.code, detail=str(exc))
            return redirect(_back_to(client, back, error=exc.code))
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
            user = sso.resolve_user(prov, claims, state.get("i", ""))
            code = sso.issue_code(user)
        except sso.OidcError as exc:
            log.warning("oidc_signin_failed", provider=provider_id, code=exc.code, detail=str(exc))
            events.emit("user.login_failed", payload={"provider": provider_id, "reason": exc.code})
            client, back = state.get("c", "web"), state.get("r", "")
            if client == "mobile" and not _allowed_back(back):
                client = "web"
            response = make_response(redirect(_back_to(client, back, error=exc.code)))
        else:
            response = make_response(redirect(_back_to(state["c"], state["r"], code=code)))
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
