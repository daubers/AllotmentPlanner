from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def include_object(obj, name, type_, reflected, compare_to):
    """Keep autogenerate away from tables we don't own (PostGIS tiger/topology, spatial_ref_sys)."""
    if reflected and compare_to is None:
        table = obj if type_ == "table" else getattr(obj, "table", None)
        return table is not None and table.name in db.metadata.tables
    return True


migrate = Migrate(include_object=include_object, compare_type=True)
