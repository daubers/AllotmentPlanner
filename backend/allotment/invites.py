"""Signed, email-bound invitations to an allotment.

Stateless: the code is a signed token naming the allotment, role and the invitee's email. It is
useless to anyone registering with another address and stops working once that address has an
account, so it is effectively single-use without a table.
"""

from flask import current_app
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer


def _signer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(current_app.config["JWT_SECRET_KEY"], salt="allotment-invite")


def make_invite(allotment_id: int, email: str, role: str, inviter_id: int) -> str:
    return _signer().dumps({"a": allotment_id, "e": email.lower(), "r": role, "i": inviter_id})


def read_invite(code: str) -> dict | None:
    """The invite's contents, or None if the code is forged, expired or malformed."""
    max_age = current_app.config["INVITE_TTL_DAYS"] * 86400
    try:
        data = _signer().loads(code, max_age=max_age)
    except (BadSignature, SignatureExpired):
        return None
    if not isinstance(data, dict) or not {"a", "e", "r", "i"} <= data.keys():
        return None
    return data
