from flask import Flask
from flask_jwt_extended import JWTManager
from flask_smorest import Api

from . import events, health, models  # noqa: F401 - models register with SQLAlchemy metadata
from .api import allotments, auth, features, tasks, todo
from .config import Config
from .extensions import db, migrate
from .logging import configure_logging, init_request_logging
from .metrics import count_event, init_metrics
from .tracing import init_tracing


def create_app(config: type = Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config)

    configure_logging(app.config["LOG_LEVEL"])
    db.init_app(app)
    migrate.init_app(app, db)
    JWTManager(app)
    api = Api(app)
    api.register_blueprint(auth.blp)
    api.register_blueprint(allotments.blp)
    api.register_blueprint(features.blp)
    api.register_blueprint(tasks.blp)
    api.register_blueprint(todo.blp)

    init_request_logging(app)
    init_metrics(app)
    init_tracing(app)
    app.register_blueprint(health.bp)

    events.clear_subscribers()
    events.subscribe(events.WILDCARD, count_event)
    return app
