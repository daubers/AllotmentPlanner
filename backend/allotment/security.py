from functools import wraps

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from flask import abort
from flask_jwt_extended import get_jwt_identity, jwt_required

from .extensions import db
from .models import Allotment, Membership, Role, User

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    if not password_hash:  # signs in through an OIDC provider only
        return False
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def current_user() -> User:
    user = db.session.get(User, int(get_jwt_identity()))
    if user is None:
        abort(401, description="User no longer exists")
    return user


def require_role(minimum: Role):
    """Require the caller to hold at least ``minimum`` on the ``allotment_id`` URL argument.

    Non-members get 404 so allotment IDs can't be probed. The view receives the
    ``allotment`` and the caller's ``membership`` as keyword arguments.
    """

    def decorator(fn):
        @wraps(fn)
        @jwt_required()
        def wrapper(*args, allotment_id: int, **kwargs):
            user = current_user()
            allotment = db.session.get(Allotment, allotment_id)
            membership = (
                db.session.query(Membership)
                .filter_by(user_id=user.id, allotment_id=allotment_id)
                .one_or_none()
                if allotment
                else None
            )
            if membership is None:
                abort(404, description="Allotment not found")
            if Role(membership.role).rank < minimum.rank:
                abort(403, description=f"Requires {minimum.value} role")
            return fn(*args, allotment=allotment, membership=membership, **kwargs)

        return wrapper

    return decorator


def require_admin(fn):
    """Only site admins (``User.is_admin``) may call this; everyone else gets 403."""

    @wraps(fn)
    @jwt_required()
    def wrapper(*args, **kwargs):
        if not current_user().is_admin:
            abort(403, description="Requires a site admin")
        return fn(*args, **kwargs)

    return wrapper
