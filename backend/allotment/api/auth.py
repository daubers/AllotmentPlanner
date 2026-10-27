from flask.views import MethodView
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    get_jwt_identity,
    jwt_required,
)
from flask_smorest import Blueprint, abort

from .. import events
from ..extensions import db
from ..models import User
from ..schemas import AccessTokenSchema, LoginSchema, RegisterSchema, TokenSchema, UserSchema
from ..security import current_user, hash_password, verify_password

blp = Blueprint("auth", __name__, url_prefix="/api/v1/auth", description="Authentication")


def _tokens(user: User) -> dict:
    identity = str(user.id)
    return {
        "access_token": create_access_token(identity),
        "refresh_token": create_refresh_token(identity),
        "user": user,
    }


@blp.route("/register")
class Register(MethodView):
    @blp.arguments(RegisterSchema)
    @blp.response(201, TokenSchema)
    def post(self, data):
        email = data["email"].lower()
        if db.session.query(User).filter_by(email=email).first():
            abort(409, message="Email already registered")
        user = User(
            email=email,
            display_name=data["display_name"],
            password_hash=hash_password(data["password"]),
        )
        db.session.add(user)
        db.session.commit()
        events.emit("user.registered", actor_id=user.id, subject={"user_id": user.id})
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
