from flask.views import MethodView
from flask_jwt_extended import jwt_required
from flask_smorest import Blueprint

from .. import crops
from ..schemas import CropQuerySchema, CropSchema

blp = Blueprint(
    "crops",
    __name__,
    url_prefix="/api/v1/crops",
    description="Built-in crop reference: typical spacing and timings, for planning",
)


@blp.route("")
class Crops(MethodView):
    @jwt_required()
    @blp.arguments(CropQuerySchema, location="query")
    @blp.response(200, CropSchema(many=True))
    def get(self, args):
        """Crops you can plan without a seed packet, searched by name, key or family."""
        return [crops.to_dict(c) for c in crops.search(args.get("q"))]
