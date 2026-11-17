"""Single sign-on with OpenID Connect (authorization code flow with PKCE).

This module holds the protocol and account logic; `api/oidc.py` is the HTTP layer on top.

Accounts are never created from nothing: a sign-in must match an identity already linked to a user,
a user with the same *verified* email, or carry a valid invite for that email. That keeps an
invite-only server invite-only.
"""

import hashlib
import secrets
import time
from datetime import UTC, datetime, timedelta

import requests
import structlog
from authlib.integrations.requests_client import OAuth2Session
from flask import current_app
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from joserfc import jwt
from joserfc.errors import JoseError
from joserfc.jwk import KeySet
from joserfc.jwt import JWTClaimsRegistry
from sqlalchemy import delete

from . import events
from .extensions import db
from .invites import read_invite
from .models import Allotment, Membership, OidcIdentity, OidcLoginCode, User

log = structlog.get_logger(__name__)

TIMEOUT = 10
DISCOVERY_TTL = 3600
# Asymmetric only: never let a token pick HS256 and be "verified" with a public key.
ALGORITHMS = [
    "RS256",
    "RS384",
    "RS512",
    "PS256",
    "PS384",
    "PS512",
    "ES256",
    "ES384",
    "ES512",
    "EdDSA",
]
_discovery_cache: dict[str, tuple[float, dict]] = {}


class OidcError(Exception):
    """A sign-in that cannot go ahead. `code` is safe to show: it goes back to the login page."""

    def __init__(self, code: str, detail: str = ""):
        super().__init__(detail or code)
        self.code = code


def providers() -> list[dict]:
    return current_app.config["OIDC_PROVIDERS"]


def provider(provider_id: str) -> dict | None:
    return next((p for p in providers() if p["id"] == provider_id), None)


def _signer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(current_app.config["JWT_SECRET_KEY"], salt="oidc-state")


def discovery(prov: dict) -> dict:
    """The provider's published endpoints (cached for an hour)."""
    cached = _discovery_cache.get(prov["issuer"])
    if cached and time.monotonic() - cached[0] < DISCOVERY_TTL:
        return cached[1]
    try:
        res = requests.get(f"{prov['issuer']}/.well-known/openid-configuration", timeout=TIMEOUT)
        res.raise_for_status()
        meta = res.json()
    except (requests.RequestException, ValueError) as exc:
        raise OidcError("provider_unreachable", str(exc)) from exc
    for key in ("issuer", "authorization_endpoint", "token_endpoint", "jwks_uri"):
        if key not in meta:
            raise OidcError("provider_invalid", f"discovery has no {key}")
    _discovery_cache[prov["issuer"]] = (time.monotonic(), meta)
    return meta


def clear_discovery_cache() -> None:
    _discovery_cache.clear()


def redirect_uri(prov: dict, url_root: str) -> str:
    base = current_app.config["PUBLIC_URL"] or url_root.rstrip("/")
    return f"{base}/api/v1/auth/oidc/{prov['id']}/callback"


def _client(prov: dict, uri: str, meta: dict) -> OAuth2Session:
    methods = meta.get("token_endpoint_auth_methods_supported") or ["client_secret_basic"]
    method = "client_secret_basic" if "client_secret_basic" in methods else "client_secret_post"
    return OAuth2Session(
        prov["client_id"],
        prov["client_secret"],
        scope=prov["scopes"],
        redirect_uri=uri,
        code_challenge_method="S256",
        token_endpoint_auth_method=method,
        timeout=TIMEOUT,
    )


def start(
    prov: dict,
    url_root: str,
    *,
    client: str,
    invite: str = "",
    back: str = "",
    link_user_id: int | None = None,
) -> tuple[str, str]:
    """Where to send the person to sign in, and the secret that ties it to their browser."""
    meta = discovery(prov)
    nonce = secrets.token_urlsafe(24)
    verifier = secrets.token_urlsafe(48)
    binder = secrets.token_urlsafe(16)
    state = _signer().dumps(
        {
            "p": prov["id"],
            "n": nonce,
            "v": verifier,
            "c": client,
            "i": invite,
            "r": back,
            "b": binder,
            "l": link_user_id,
        }
    )
    url, _ = _client(prov, redirect_uri(prov, url_root), meta).create_authorization_url(
        meta["authorization_endpoint"], state=state, nonce=nonce, code_verifier=verifier
    )
    return url, binder


def read_state(state: str, binder: str | None) -> dict:
    """The sign-in this state belongs to, if it is genuine, fresh and was begun in this browser."""
    try:
        data = _signer().loads(state, max_age=current_app.config["OIDC_STATE_TTL_SECONDS"])
    except SignatureExpired as exc:
        raise OidcError("expired", "the sign-in took too long") from exc
    except BadSignature as exc:
        raise OidcError("invalid_state", "state is not genuine") from exc
    if not binder or not secrets.compare_digest(str(data.get("b", "")), binder):
        raise OidcError("invalid_state", "sign-in was not started in this browser")
    return data


def claims_for(prov: dict, url_root: str, code: str, state: dict) -> dict:
    """Swap the code for tokens and return the validated ID token's claims."""
    meta = discovery(prov)
    try:
        token = _client(prov, redirect_uri(prov, url_root), meta).fetch_token(
            meta["token_endpoint"],
            code=code,
            grant_type="authorization_code",
            code_verifier=state["v"],
        )
    except Exception as exc:  # authlib raises several types; all mean the provider said no
        raise OidcError("token_exchange_failed", f"{exc.__class__.__name__}: {exc}") from exc
    id_token = token.get("id_token")
    if not id_token:
        raise OidcError("no_id_token")
    try:
        res = requests.get(meta["jwks_uri"], timeout=TIMEOUT)
        res.raise_for_status()
        token_obj = jwt.decode(id_token, KeySet.import_key_set(res.json()), algorithms=ALGORITHMS)
        claims = token_obj.claims
        JWTClaimsRegistry(
            leeway=60,
            iss={"essential": True, "value": meta["issuer"]},
            aud={"essential": True, "value": prov["client_id"]},
            exp={"essential": True},
            sub={"essential": True},
        ).validate(claims)
    except (requests.RequestException, ValueError, JoseError) as exc:
        raise OidcError("invalid_id_token", f"{exc.__class__.__name__}: {exc}") from exc
    if not secrets.compare_digest(str(claims.get("nonce", "")), state["n"]):
        raise OidcError("invalid_id_token", "nonce does not match")
    return dict(claims)


def _name_for(claims: dict, email: str) -> str:
    name = claims.get("name") or claims.get("preferred_username") or email.split("@")[0]
    return str(name).strip()[:100] or email.split("@")[0]


def resolve_user(prov: dict, claims: dict, invite_code: str) -> User:
    """The user this sign-in is for. Links or creates only as the module docstring allows."""
    subject = str(claims["sub"])
    identity = (
        db.session.query(OidcIdentity).filter_by(provider=prov["id"], subject=subject).one_or_none()
    )
    if identity is not None:
        user = db.session.get(User, identity.user_id)
        if user is not None:
            return user

    email = str(claims.get("email") or "").lower()
    if not email:
        raise OidcError("no_email", "the provider did not share an email address")
    if claims.get("email_verified") is not True:
        # Linking on an unverified address would let anyone claim an account by typing its email.
        raise OidcError("email_unverified", f"{prov['id']} has not verified {email}")

    user = db.session.query(User).filter_by(email=email).one_or_none()
    invite = None
    if user is None:
        invite = read_invite(invite_code) if invite_code else None
        if invite is None or invite["e"] != email or db.session.get(Allotment, invite["a"]) is None:
            raise OidcError("not_invited", f"no account or invite for {email}")
        user = User(email=email, display_name=_name_for(claims, email), password_hash=None)
        db.session.add(user)
        db.session.flush()
        db.session.add(Membership(user_id=user.id, allotment_id=invite["a"], role=invite["r"]))

    db.session.add(OidcIdentity(user_id=user.id, provider=prov["id"], subject=subject, email=email))
    db.session.commit()
    if invite:
        events.emit("user.registered", actor_id=user.id, subject={"user_id": user.id})
        events.emit(
            "member.added",
            actor_id=invite["i"],
            allotment_id=invite["a"],
            subject={"user_id": user.id},
            payload={"role": invite["r"], "via": "invite"},
        )
    events.emit("user.oidc_linked", actor_id=user.id, payload={"provider": prov["id"]})
    return user


def _hash(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


def issue_code(user: User, purpose: str = "login") -> str:
    """A one-time code for this user, good for a minute and only for `purpose`."""
    now = datetime.now(UTC)
    db.session.execute(delete(OidcLoginCode).where(OidcLoginCode.expires_at < now))  # tidy up
    code = secrets.token_urlsafe(32)
    expires = now + timedelta(seconds=current_app.config["OIDC_CODE_TTL_SECONDS"])
    db.session.add(
        OidcLoginCode(code_hash=_hash(code), user_id=user.id, purpose=purpose, expires_at=expires)
    )
    db.session.commit()
    return code


def redeem_code(code: str, purpose: str = "login") -> User | None:
    """The user a code was issued to, if it is for this purpose. It works once."""
    row = db.session.execute(
        delete(OidcLoginCode)
        .where(OidcLoginCode.code_hash == _hash(code), OidcLoginCode.purpose == purpose)
        .returning(OidcLoginCode.user_id, OidcLoginCode.expires_at)
    ).one_or_none()
    db.session.commit()
    if row is None:
        return None
    user_id, expires_at = row
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    return db.session.get(User, user_id) if expires_at > datetime.now(UTC) else None


def link_identity(prov: dict, claims: dict, user_id: int) -> None:
    """Tie this provider login to a user who is already signed in and asked for it.

    No email match is needed: the person proved who they are to us, and now to the provider.
    What is refused is taking over someone else's login, or holding two at one provider.
    """
    subject = str(claims["sub"])
    existing = (
        db.session.query(OidcIdentity).filter_by(provider=prov["id"], subject=subject).one_or_none()
    )
    if existing is not None:
        if existing.user_id == user_id:
            return  # already linked: nothing to do
        raise OidcError("already_linked", f"{prov['id']} login belongs to another account")
    if db.session.query(OidcIdentity).filter_by(user_id=user_id, provider=prov["id"]).first():
        raise OidcError("provider_already_linked", f"user already has a {prov['id']} login")
    email = str(claims.get("email") or "").lower() or None
    db.session.add(OidcIdentity(user_id=user_id, provider=prov["id"], subject=subject, email=email))
    db.session.commit()
    events.emit("user.oidc_linked", actor_id=user_id, payload={"provider": prov["id"]})
