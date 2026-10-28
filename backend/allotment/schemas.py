from marshmallow import Schema, fields, validate

from .models import FeatureKind

ROLES = ["viewer", "editor", "owner"]


class RegisterSchema(Schema):
    email = fields.Email(required=True)
    display_name = fields.String(required=True, validate=validate.Length(min=1, max=100))
    password = fields.String(
        required=True, load_only=True, validate=validate.Length(min=8, max=128)
    )


class LoginSchema(Schema):
    email = fields.Email(required=True)
    password = fields.String(required=True, load_only=True)


class UserSchema(Schema):
    id = fields.Integer(dump_only=True)
    email = fields.Email(dump_only=True)
    display_name = fields.String(dump_only=True)


class TokenSchema(Schema):
    access_token = fields.String()
    refresh_token = fields.String()
    user = fields.Nested(UserSchema)


class AccessTokenSchema(Schema):
    access_token = fields.String()


class AllotmentCreateSchema(Schema):
    name = fields.String(required=True, validate=validate.Length(min=1, max=120))
    description = fields.String(load_default="")


class AllotmentUpdateSchema(Schema):
    name = fields.String(validate=validate.Length(min=1, max=120))
    description = fields.String()


class AllotmentSchema(Schema):
    id = fields.Integer(dump_only=True)
    name = fields.String()
    description = fields.String()
    role = fields.String(dump_only=True, validate=validate.OneOf(ROLES))


class MemberAddSchema(Schema):
    email = fields.Email(required=True)
    role = fields.String(load_default="viewer", validate=validate.OneOf(ROLES))


class MemberUpdateSchema(Schema):
    role = fields.String(required=True, validate=validate.OneOf(ROLES))


class MemberSchema(Schema):
    user_id = fields.Integer(dump_only=True)
    email = fields.Email(dump_only=True)
    display_name = fields.String(dump_only=True)
    role = fields.String()


class FeatureInSchema(Schema):
    """A GeoJSON Feature. ``id`` is optional and only used by the bulk endpoint."""

    type = fields.String(required=True, validate=validate.Equal("Feature"))
    id = fields.Integer(load_default=None)
    geometry = fields.Dict(required=True)
    properties = fields.Dict(load_default=dict)


class FeaturePatchSchema(Schema):
    geometry = fields.Dict()
    properties = fields.Dict()


class FeatureSchema(Schema):
    type = fields.String()
    id = fields.Integer()
    geometry = fields.Dict()
    properties = fields.Dict()


class FeatureCollectionInSchema(Schema):
    type = fields.String(required=True, validate=validate.Equal("FeatureCollection"))
    features = fields.List(fields.Nested(FeatureInSchema), required=True)


class FeatureCollectionSchema(Schema):
    type = fields.String()
    features = fields.List(fields.Nested(FeatureSchema))


TASK_STATUSES = ["todo", "doing", "done"]
TASK_PRIORITIES = ["low", "normal", "high"]
RECURRENCES = ["daily", "weekly", "monthly"]


class TaskInSchema(Schema):
    title = fields.String(required=True, validate=validate.Length(min=1, max=200))
    description = fields.String(load_default="")
    priority = fields.String(load_default="normal", validate=validate.OneOf(TASK_PRIORITIES))
    status = fields.String(load_default="todo", validate=validate.OneOf(["todo", "doing"]))
    due_date = fields.Date(load_default=None, allow_none=True)
    recurrence = fields.String(
        load_default=None, allow_none=True, validate=validate.OneOf(RECURRENCES)
    )
    assignee_id = fields.Integer(load_default=None, allow_none=True)
    feature_id = fields.Integer(load_default=None, allow_none=True)
    location = fields.Dict(load_default=None, allow_none=True)


class TaskPatchSchema(Schema):
    title = fields.String(validate=validate.Length(min=1, max=200))
    description = fields.String()
    priority = fields.String(validate=validate.OneOf(TASK_PRIORITIES))
    status = fields.String(validate=validate.OneOf(["todo", "doing"]))
    due_date = fields.Date(allow_none=True)
    recurrence = fields.String(allow_none=True, validate=validate.OneOf(RECURRENCES))
    assignee_id = fields.Integer(allow_none=True)
    feature_id = fields.Integer(allow_none=True)
    location = fields.Dict(allow_none=True)


class TaskQuerySchema(Schema):
    status = fields.String(validate=validate.OneOf(TASK_STATUSES))
    open = fields.Boolean(metadata={"description": "true: only todo/doing; false: only done"})
    due_on = fields.Date()
    due_by = fields.Date(metadata={"description": "Due on or before this date (includes overdue)"})
    feature_id = fields.Integer()
    assignee_id = fields.Integer()


class TaskSchema(Schema):
    id = fields.Integer()
    title = fields.String()
    description = fields.String()
    status = fields.String()
    priority = fields.String()
    due_date = fields.Date(allow_none=True)
    recurrence = fields.String(allow_none=True)
    assignee_id = fields.Integer(allow_none=True)
    feature_id = fields.Integer(allow_none=True)
    location = fields.Dict(allow_none=True)
    completed_at = fields.DateTime(allow_none=True)
    completed_by = fields.Integer(allow_none=True)
    created_at = fields.DateTime()
    spawned_task_id = fields.Integer(
        allow_none=True, metadata={"description": "Set when completing a recurring task"}
    )


class TodoQuerySchema(Schema):
    date = fields.Date(metadata={"description": "Day to plan for; defaults to today (server date)"})
    include_undated = fields.Boolean(load_default=False)


class TodoAllotmentSchema(Schema):
    id = fields.Integer()
    name = fields.String()


class TodoMemberSchema(Schema):
    user_id = fields.Integer()
    display_name = fields.String()


class TodoSchema(Schema):
    date = fields.Date()
    allotment = fields.Nested(TodoAllotmentSchema)
    tasks = fields.List(fields.Nested(TaskSchema))
    features = fields.List(
        fields.Nested(FeatureSchema), metadata={"description": "The whole map, for the sketch"}
    )
    members = fields.List(fields.Nested(TodoMemberSchema))


class MediaUploadFormSchema(Schema):
    # Documented here for OpenAPI; the view reads the actual file from request.files.
    file = fields.Raw(load_default=None, metadata={"type": "string", "format": "binary"})
    feature_id = fields.Integer(load_default=None)
    task_id = fields.Integer(load_default=None)
    caption = fields.String(load_default="", validate=validate.Length(max=500))
    lat = fields.Float(
        load_default=None,
        validate=validate.Range(min=-90, max=90),
        metadata={"description": "Where the phone was (its own GPS). Beats the file's EXIF."},
    )
    lng = fields.Float(load_default=None, validate=validate.Range(min=-180, max=180))
    heading = fields.Float(
        load_default=None,
        validate=validate.Range(min=0, max=360),
        metadata={"description": "Compass heading in degrees, 0 = north"},
    )
    taken_at = fields.DateTime(
        load_default=None, metadata={"description": "When it was taken, if the app knows"}
    )
    capture_session = fields.String(
        load_default=None,
        validate=validate.Length(min=1, max=64),
        metadata={"description": "Groups the photos of one walk-round, to build a map from them"},
    )
    client_id = fields.String(
        load_default=None,
        validate=validate.Length(min=1, max=64),
        metadata={
            "description": "The app's id for this upload: sending it again returns the same item"
        },
    )


class MediaQuerySchema(Schema):
    kind = fields.String(validate=validate.OneOf(["photo", "video"]))
    feature_id = fields.Integer()
    task_id = fields.Integer()
    capture_session = fields.String()
    taken_from = fields.Date(metadata={"description": "On or after this date"})
    taken_to = fields.Date(metadata={"description": "On or before this date"})
    order = fields.String(load_default="desc", validate=validate.OneOf(["asc", "desc"]))
    limit = fields.Integer(load_default=100, validate=validate.Range(min=1, max=500))
    offset = fields.Integer(load_default=0, validate=validate.Range(min=0))


class MediaPatchSchema(Schema):
    caption = fields.String(validate=validate.Length(max=500))
    feature_id = fields.Integer(allow_none=True)
    task_id = fields.Integer(allow_none=True)
    taken_at = fields.DateTime()
    lat = fields.Float(allow_none=True, validate=validate.Range(min=-90, max=90))
    lng = fields.Float(allow_none=True, validate=validate.Range(min=-180, max=180))
    heading = fields.Float(allow_none=True, validate=validate.Range(min=0, max=360))


class MediaSchema(Schema):
    id = fields.Integer()
    kind = fields.String()
    filename = fields.String()
    content_type = fields.String()
    size_bytes = fields.Integer()
    width = fields.Integer(allow_none=True)
    height = fields.Integer(allow_none=True)
    duration_s = fields.Float(allow_none=True)
    taken_at = fields.DateTime()
    taken_at_source = fields.String()
    lat = fields.Float(allow_none=True)
    lng = fields.Float(allow_none=True)
    heading = fields.Float(allow_none=True)
    position_source = fields.String(allow_none=True)
    capture_session = fields.String(allow_none=True)
    feature_id = fields.Integer(allow_none=True)
    task_id = fields.Integer(allow_none=True)
    caption = fields.String()
    status = fields.String()
    error = fields.String(allow_none=True)
    url = fields.String(metadata={"description": "Signed, short-lived link to the file"})
    thumb_url = fields.String(allow_none=True)
    uploaded_by = fields.Integer(allow_none=True)
    created_at = fields.DateTime()


class OverviewQuerySchema(Schema):
    days = fields.Integer(
        load_default=90,
        validate=validate.Range(min=7, max=366),
        metadata={"description": "Length of the daily history window, ending today (UTC)"},
    )
    today = fields.Date(metadata={"description": "Treat this as today (UTC); mainly for tests"})


class OverviewDaySchema(Schema):
    date = fields.Date()
    tasks_done = fields.Integer()
    tasks_added = fields.Integer()
    photos_added = fields.Integer()
    map_edits = fields.Integer()
    total = fields.Integer()


class OverviewCountsSchema(Schema):
    tasks_done = fields.Integer()
    tasks_added = fields.Integer()
    photos_added = fields.Integer()
    map_edits = fields.Integer()
    active_days = fields.Integer()


class OverviewStreakSchema(Schema):
    current = fields.Integer(
        metadata={"description": "Consecutive active days up to today or yesterday"}
    )
    longest = fields.Integer()


class OverviewSchema(Schema):
    days = fields.List(fields.Nested(OverviewDaySchema))
    this_week = fields.Nested(OverviewCountsSchema)
    last_week = fields.Nested(OverviewCountsSchema)
    totals = fields.Nested(OverviewCountsSchema)
    streak = fields.Nested(OverviewStreakSchema)
    open_tasks = fields.Integer()
    recent_photos = fields.List(fields.Nested(MediaSchema))
    recent_done = fields.List(
        fields.Dict(), metadata={"description": "Latest completed tasks: id, title, completed_at"}
    )


class MastodonSettingsInSchema(Schema):
    instance_url = fields.String(required=True, validate=validate.Length(min=1, max=300))
    access_token = fields.String(
        load_default=None,
        validate=validate.Length(min=10, max=500),
        metadata={"description": "Needed when connecting or changing instance; never returned"},
    )
    visibility = fields.String(
        load_default="unlisted", validate=validate.OneOf(["public", "unlisted", "private"])
    )
    enabled = fields.Boolean(load_default=False)
    on_task_completed = fields.Boolean(load_default=False)
    on_photos = fields.Boolean(load_default=False)
    daily_digest = fields.Boolean(load_default=False)


class MastodonSettingsSchema(Schema):
    configured = fields.Boolean()
    instance_url = fields.String(allow_none=True)
    handle = fields.String(allow_none=True)
    token_set = fields.Boolean()
    visibility = fields.String()
    enabled = fields.Boolean()
    on_task_completed = fields.Boolean()
    on_photos = fields.Boolean()
    daily_digest = fields.Boolean()


class MastodonPostSchema(Schema):
    id = fields.Integer()
    kind = fields.String()
    text = fields.String()
    media_count = fields.Integer()
    status = fields.String()
    attempts = fields.Integer()
    error = fields.String(allow_none=True)
    remote_url = fields.String(allow_none=True)
    created_at = fields.DateTime()
    send_after = fields.DateTime()
    posted_at = fields.DateTime(allow_none=True)


class MastodonPostQuerySchema(Schema):
    status = fields.String(
        validate=validate.OneOf(["pending", "sending", "sent", "failed", "skipped"])
    )
    limit = fields.Integer(load_default=30, validate=validate.Range(min=1, max=100))


class MapJobInSchema(Schema):
    name = fields.String(load_default="", validate=validate.Length(max=120))
    media_ids = fields.List(
        fields.Integer(),
        load_default=None,
        metadata={"description": "Photos/videos to use; default is every ready photo and video"},
    )
    capture_session = fields.String(
        load_default=None,
        metadata={
            "description": "Use the photos uploaded in this capture session (not with media_ids)"
        },
    )
    view = fields.String(
        load_default="oblique",
        validate=validate.OneOf(["oblique", "overhead"]),
        metadata={
            "description": "oblique: hand-held, camera roughly level; overhead: looking down"
        },
    )
    camera_height_m = fields.Float(
        load_default=1.7,
        validate=validate.Range(min=0.3, max=120),
        metadata={"description": "About how high the camera was held above the ground"},
    )
    detect_objects = fields.Boolean(
        load_default=True,
        metadata={
            "description": "Recognise beds, trees, sheds etc. and propose them as map shapes"
        },
    )
    overlay = fields.Boolean(
        load_default=False,
        metadata={
            "description": "Also build the stitched photo overlay (experimental; best from above)"
        },
    )


class MapJobSchema(Schema):
    id = fields.Integer()
    name = fields.String()
    status = fields.String()
    stage = fields.String()
    view = fields.String()
    camera_height_m = fields.Float()
    media_count = fields.Integer()
    detect_objects = fields.Boolean()
    overlay = fields.Boolean()
    objects_found = fields.Integer(allow_none=True)
    shots_total = fields.Integer(allow_none=True)
    shots_used = fields.Integer(allow_none=True)
    error = fields.String(allow_none=True)
    log = fields.String(metadata={"description": "Tail of the processing log (detail view only)"})
    layer_id = fields.Integer(allow_none=True)
    cancel_requested = fields.Boolean()
    created_at = fields.DateTime()
    started_at = fields.DateTime(allow_none=True)
    finished_at = fields.DateTime(allow_none=True)


class MapLayerSchema(Schema):
    id = fields.Integer()
    name = fields.String()
    job_id = fields.Integer(allow_none=True)
    bounds = fields.List(
        fields.Float(), metadata={"description": "[west, south, east, north] in degrees"}
    )
    min_zoom = fields.Integer()
    max_zoom = fields.Integer()
    tile_count = fields.Integer()
    opacity = fields.Float()
    visible = fields.Boolean()
    tile_url = fields.String(metadata={"description": "XYZ template with a signed, expiring token"})
    created_at = fields.DateTime()


class MapLayerPatchSchema(Schema):
    name = fields.String(validate=validate.Length(min=1, max=120))
    opacity = fields.Float(validate=validate.Range(min=0, max=1))
    visible = fields.Boolean()


class LimitsSchema(Schema):
    max_upload_bytes = fields.Integer(metadata={"description": "Largest accepted upload"})


class SuggestionSchema(Schema):
    id = fields.Integer()
    job_id = fields.Integer(allow_none=True)
    kind = fields.String()
    name = fields.String()
    geometry = fields.Dict(metadata={"description": "GeoJSON Point (with radius_m) or Polygon"})
    radius_m = fields.Float(allow_none=True)
    confidence = fields.Float()
    views = fields.Integer(metadata={"description": "How many photos showed it"})
    status = fields.String()
    feature_id = fields.Integer(allow_none=True)


class SuggestionQuerySchema(Schema):
    status = fields.String(
        load_default="pending", validate=validate.OneOf(["pending", "accepted", "dismissed"])
    )


class SuggestionPatchSchema(Schema):
    name = fields.String(validate=validate.Length(min=1, max=120))
    kind = fields.String(validate=validate.OneOf([k.value for k in FeatureKind]))


class SuggestionIdsSchema(Schema):
    ids = fields.List(fields.Integer(), required=True, validate=validate.Length(min=1, max=200))
