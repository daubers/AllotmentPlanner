from flask import current_app
from flask.views import MethodView
from flask_jwt_extended import jwt_required
from flask_smorest import Blueprint

from ..schemas import LimitsSchema

blp = Blueprint("limits", __name__, url_prefix="/api/v1/limits", description="Server limits")


@blp.route("")
class Limits(MethodView):
    @jwt_required()
    @blp.response(200, LimitsSchema)
    def get(self):
        """Limits the browser should respect, so it can explain a problem before sending a file."""
        return {"max_upload_bytes": current_app.config["MAX_CONTENT_LENGTH"]}
