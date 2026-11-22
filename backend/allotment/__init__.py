from flask import Flask
from flask_jwt_extended import JWTManager
from flask_smorest import Api

from . import cli, events, health, mastodon_posts, models, ops_log  # noqa: F401 - models register with SQLAlchemy
from .activity import record_activity
from .api import (
    admin,
    allotments,
    auth,
    day_lists,
    features,
    limits,
    mapping,
    mastodon,
    measurements,
    media,
    notes,
    oidc,
    overview,
    packet_scans,
    packets,
    plantings,
    suggestions,
    task_comments,
    tasks,
    todo,
    trays,
    visits,
)
from .celery_app import celery
from .config import Config
from .extensions import db, migrate
from .logging import configure_logging, init_request_logging
from .metrics import count_event, init_metrics
from .tracing import init_tracing


def create_app(config: type = Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config)

    configure_logging(
        app.config["LOG_LEVEL"],
        app.config["SQLALCHEMY_DATABASE_URI"] if app.config["LOG_TO_DB"] else None,
    )
    ops_log.set_service("api")
    celery.conf.task_always_eager = app.config.get("CELERY_ALWAYS_EAGER", False)
    celery.conf.task_eager_propagates = True
    db.init_app(app)
    migrate.init_app(app, db)
    JWTManager(app)
    api = Api(app)
    api.register_blueprint(auth.blp)
    api.register_blueprint(admin.blp)
    api.register_blueprint(allotments.blp)
    api.register_blueprint(features.blp)
    api.register_blueprint(tasks.blp)
    api.register_blueprint(todo.blp)
    api.register_blueprint(day_lists.blp)
    api.register_blueprint(visits.blp)
    api.register_blueprint(visits.calendar_blp)
    api.register_blueprint(media.blp)
    api.register_blueprint(media.files_blp)
    api.register_blueprint(overview.blp)
    api.register_blueprint(packets.blp)
    api.register_blueprint(plantings.blp)
    api.register_blueprint(packet_scans.blp)
    api.register_blueprint(trays.blp)
    api.register_blueprint(mastodon.blp)
    api.register_blueprint(limits.blp)
    api.register_blueprint(suggestions.blp)
    api.register_blueprint(measurements.blp)
    api.register_blueprint(notes.blp)
    api.register_blueprint(oidc.blp)
    api.register_blueprint(task_comments.blp)
    api.register_blueprint(mapping.blp)
    api.register_blueprint(mapping.tiles_blp)

    init_request_logging(app)
    init_metrics(app)
    init_tracing(app)
    app.register_blueprint(health.bp)

    events.clear_subscribers()
    events.subscribe(events.WILDCARD, count_event)
    events.subscribe(events.WILDCARD, record_activity)
    mastodon_posts.register(events)
    cli.register(app)
    return app
