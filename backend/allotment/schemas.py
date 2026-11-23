from marshmallow import Schema, ValidationError, fields, validate, validates_schema

from .equipment_kinds import KINDS
from .equipment_kinds import STATUSES as EQUIPMENT_STATUSES
from .models import FeatureKind
from .plan import MAX_SUCCESSION, PLAN_STATUSES
from .plantings import METHODS
from .plantings import STATUSES as PLANTING_STATUSES
from .seeds import ACTIVITIES, CELL_STATUSES, MAX_TRAY_SIDE, STOCK_LEVELS, SUN_LEVELS
from .task_series import UNITS

ROLES = ["viewer", "editor", "owner"]


class RegisterSchema(Schema):
    email = fields.Email(required=True)
    display_name = fields.String(required=True, validate=validate.Length(min=1, max=100))
    password = fields.String(
        required=True, load_only=True, validate=validate.Length(min=8, max=128)
    )
    invite_code = fields.String(
        load_default=None,
        metadata={
            "description": "From an allotment owner; needed when registration is invite-only"
        },
    )


class LoginSchema(Schema):
    email = fields.Email(required=True)
    password = fields.String(required=True, load_only=True)


class DeleteAccountSchema(Schema):
    """Proof it is the owner: their password, or the `reauth` code from a provider login."""

    password = fields.String(load_only=True)
    reauth_code = fields.String(load_only=True)


class AccountExportSchema(Schema):
    id = fields.Integer(dump_only=True)
    status = fields.String(dump_only=True)  # pending, ready or failed
    size_bytes = fields.Integer(dump_only=True, allow_none=True)
    created_at = fields.DateTime(dump_only=True)
    expires_at = fields.DateTime(dump_only=True, allow_none=True)
    url = fields.String(dump_only=True, allow_none=True)  # signed download link, when ready


class UserSchema(Schema):
    id = fields.Integer(dump_only=True)
    email = fields.Email(dump_only=True)
    display_name = fields.String(dump_only=True)
    is_admin = fields.Boolean(dump_only=True)


class TokenSchema(Schema):
    access_token = fields.String()
    refresh_token = fields.String()
    user = fields.Nested(UserSchema)


class AccessTokenSchema(Schema):
    access_token = fields.String()


class AllotmentCreateSchema(Schema):
    name = fields.String(required=True, validate=validate.Length(min=1, max=120))
    description = fields.String(load_default="")


LENGTH_UNITS = ["m", "cm", "ft_in"]


class AllotmentUpdateSchema(Schema):
    name = fields.String(validate=validate.Length(min=1, max=120))
    description = fields.String()
    length_unit = fields.String(validate=validate.OneOf(LENGTH_UNITS))


class AllotmentSchema(Schema):
    id = fields.Integer(dump_only=True)
    name = fields.String()
    description = fields.String()
    length_unit = fields.String(dump_only=True, validate=validate.OneOf(LENGTH_UNITS))
    role = fields.String(dump_only=True, validate=validate.OneOf(ROLES))


class MemberAddSchema(Schema):
    email = fields.Email(required=True)
    role = fields.String(load_default="viewer", validate=validate.OneOf(ROLES))


class InviteCreateSchema(Schema):
    email = fields.Email(required=True)
    role = fields.String(load_default="viewer", validate=validate.OneOf(ROLES))


class InviteSchema(Schema):
    email = fields.Email()
    role = fields.String()
    invite_code = fields.String(
        metadata={"description": "Give this to the invitee; works only with their email"}
    )
    expires_in_days = fields.Integer()


class OidcProviderSchema(Schema):
    id = fields.String(metadata={"description": "Used in /auth/oidc/<id>/login"})
    name = fields.String(metadata={"description": "What the sign-in button says"})


class AuthConfigSchema(Schema):
    registration = fields.String(metadata={"description": "open or invite"})
    oidc = fields.List(
        fields.Nested(OidcProviderSchema), metadata={"description": "Single sign-on providers"}
    )


class OidcIdentitySchema(Schema):
    id = fields.Integer()
    provider = fields.String()
    provider_name = fields.String(
        allow_none=True,
        metadata={"description": "Null when the server no longer offers this provider"},
    )
    email = fields.String(allow_none=True)
    created_at = fields.DateTime()


class AuthMethodsSchema(Schema):
    has_password = fields.Boolean()
    identities = fields.List(fields.Nested(OidcIdentitySchema))


class OidcLinkStartSchema(Schema):
    url = fields.String(
        metadata={"description": "Send the browser here to link; works once, briefly"}
    )


class OidcExchangeSchema(Schema):
    code = fields.String(required=True, validate=validate.Length(min=1, max=200))


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
    tray_id = fields.Integer(load_default=None, allow_none=True)
    planting_id = fields.Integer(load_default=None, allow_none=True)
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
    tray_id = fields.Integer(allow_none=True)
    planting_id = fields.Integer(allow_none=True)
    location = fields.Dict(allow_none=True)


class TaskQuerySchema(Schema):
    status = fields.String(validate=validate.OneOf(TASK_STATUSES))
    open = fields.Boolean(metadata={"description": "true: only todo/doing; false: only done"})
    due_on = fields.Date()
    due_by = fields.Date(metadata={"description": "Due on or before this date (includes overdue)"})
    feature_id = fields.Integer()
    tray_id = fields.Integer()
    planting_id = fields.Integer()
    assignee_id = fields.Integer()
    priority = fields.String(validate=validate.OneOf(TASK_PRIORITIES))
    q = fields.String(metadata={"description": "Words in the title or notes (case-insensitive)"})


class TaskSuggestionSchema(Schema):
    key = fields.String(metadata={"description": "Stable id, so a suggestion is added only once"})
    title = fields.String()
    description = fields.String()
    due_date = fields.Date()
    added = fields.Boolean(metadata={"description": "A task for this suggestion already exists"})


class TaskBulkSchema(Schema):
    ids = fields.List(fields.Integer(), required=True, validate=validate.Length(min=1, max=200))
    action = fields.String(
        required=True, validate=validate.OneOf(["complete", "reopen", "delete", "reschedule"])
    )
    due_date = fields.Date(
        allow_none=True, metadata={"description": "For reschedule; null clears the date"}
    )


class TaskBulkResultSchema(Schema):
    tasks = fields.List(fields.Nested(lambda: TaskSchema()))
    deleted = fields.List(fields.Integer())


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
    tray_id = fields.Integer(allow_none=True)
    planting_id = fields.Integer(allow_none=True)
    series_id = fields.Integer(
        allow_none=True, metadata={"description": "The schedule it is part of"}
    )
    plan_item_id = fields.Integer(
        allow_none=True, metadata={"description": "The crop plan item it is about"}
    )
    location = fields.Dict(allow_none=True)
    completed_at = fields.DateTime(allow_none=True)
    completed_by = fields.Integer(allow_none=True)
    created_at = fields.DateTime()
    spawned_task_id = fields.Integer(
        allow_none=True, metadata={"description": "Set when completing a recurring task"}
    )


class TaskSeriesInSchema(Schema):
    """A job that repeats: every N days, weeks or months from a start until an end."""

    title = fields.String(required=True, validate=validate.Length(min=1, max=200))
    description = fields.String(load_default="")
    priority = fields.String(load_default="normal", validate=validate.OneOf(TASK_PRIORITIES))
    assignee_id = fields.Integer(load_default=None, allow_none=True)
    feature_id = fields.Integer(load_default=None, allow_none=True)
    every_n = fields.Integer(
        load_default=1,
        validate=validate.Range(min=1, max=365),
        metadata={"description": "Every N units"},
    )
    unit = fields.String(required=True, validate=validate.OneOf(UNITS))
    starts_on = fields.Date(required=True)
    until_on = fields.Date(required=True)


class TaskSeriesPatchSchema(Schema):
    title = fields.String(validate=validate.Length(min=1, max=200))
    description = fields.String()
    priority = fields.String(validate=validate.OneOf(TASK_PRIORITIES))
    assignee_id = fields.Integer(allow_none=True)
    feature_id = fields.Integer(allow_none=True)
    every_n = fields.Integer(validate=validate.Range(min=1, max=365))
    unit = fields.String(validate=validate.OneOf(UNITS))
    starts_on = fields.Date()
    until_on = fields.Date()


class TaskSeriesSchema(Schema):
    id = fields.Integer()
    title = fields.String()
    description = fields.String()
    priority = fields.String()
    assignee_id = fields.Integer(allow_none=True)
    feature_id = fields.Integer(allow_none=True)
    every_n = fields.Integer()
    unit = fields.String(validate=validate.OneOf(UNITS))
    starts_on = fields.Date()
    until_on = fields.Date()
    rule = fields.String(metadata={"description": 'e.g. "every 2 weeks"'})
    open_tasks = fields.Integer(metadata={"description": "Occurrences not yet done"})
    done_tasks = fields.Integer()
    next_due = fields.Date(allow_none=True, metadata={"description": "The next open occurrence"})
    created_at = fields.DateTime()


class EquipmentPatchSchema(Schema):
    name = fields.String(validate=validate.Length(min=1, max=120))
    kind = fields.String(allow_none=True, validate=validate.OneOf(list(KINDS)))
    quantity = fields.Integer(validate=validate.Range(min=1, max=100000))
    notes = fields.String(validate=validate.Length(max=5000))
    used_for = fields.String(
        validate=validate.Length(max=1000),
        metadata={
            "description": "Words or phrases that make it suggested for a task, comma separated"
        },
    )
    status = fields.String(validate=validate.OneOf(EQUIPMENT_STATUSES))
    location_feature_id = fields.Integer(
        allow_none=True, metadata={"description": "Where it lives"}
    )


class EquipmentInSchema(EquipmentPatchSchema):
    name = fields.String(required=True, validate=validate.Length(min=1, max=120))
    kind = fields.String(load_default=None, allow_none=True, validate=validate.OneOf(list(KINDS)))
    quantity = fields.Integer(load_default=1, validate=validate.Range(min=1, max=100000))
    notes = fields.String(load_default="", validate=validate.Length(max=5000))
    used_for = fields.String(load_default="", validate=validate.Length(max=1000))
    status = fields.String(load_default="in_service", validate=validate.OneOf(EQUIPMENT_STATUSES))
    location_feature_id = fields.Integer(load_default=None, allow_none=True)


class EquipmentQuerySchema(Schema):
    q = fields.String(metadata={"description": "Search the name, notes and used-for words"})
    kind = fields.String(validate=validate.OneOf(list(KINDS)))
    status = fields.String(validate=validate.OneOf(EQUIPMENT_STATUSES))


class EquipmentSchema(Schema):
    id = fields.Integer()
    name = fields.String()
    kind = fields.String(allow_none=True)
    kind_label = fields.String(metadata={"description": '"Spade"; "Other" when it has no kind'})
    quantity = fields.Integer()
    notes = fields.String()
    used_for = fields.String()
    keywords = fields.List(fields.String(), metadata={"description": "used_for, tidied"})
    status = fields.String(validate=validate.OneOf(EQUIPMENT_STATUSES))
    location_feature_id = fields.Integer(allow_none=True)
    location_name = fields.String(allow_none=True)
    last_serviced_on = fields.Date(allow_none=True)
    created_at = fields.DateTime()
    updated_at = fields.DateTime()


class EquipmentKindSchema(Schema):
    key = fields.String()
    label = fields.String()


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
    title = fields.String(allow_none=True, metadata={"description": "The day list's name, if any"})


class MediaUploadFormSchema(Schema):
    # Documented here for OpenAPI; the view reads the actual file from request.files.
    file = fields.Raw(load_default=None, metadata={"type": "string", "format": "binary"})
    feature_id = fields.Integer(load_default=None)
    task_id = fields.Integer(load_default=None)
    packet_id = fields.Integer(load_default=None, metadata={"description": "A seed packet's photo"})
    tray_id = fields.Integer(load_default=None, metadata={"description": "A seed tray's photo"})
    planting_id = fields.Integer(load_default=None, metadata={"description": "A planting's photo"})
    read_packet = fields.Boolean(
        load_default=False,
        metadata={"description": "Read this photo as the back of a seed packet into a draft"},
    )
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
    packet_id = fields.Integer()
    tray_id = fields.Integer()
    planting_id = fields.Integer()
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
    packet_id = fields.Integer(allow_none=True)
    tray_id = fields.Integer(allow_none=True)
    planting_id = fields.Integer(allow_none=True)
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
    packet_id = fields.Integer(allow_none=True)
    tray_id = fields.Integer(allow_none=True)
    planting_id = fields.Integer(allow_none=True)
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
    boundary = fields.Dict(
        load_default=None,
        allow_none=True,
        metadata={
            "description": "Optional plot boundary as a GeoJSON Polygon (see boundary-from-gpx): "
            "objects outside it are left out, and it is offered as the Plot boundary suggestion"
        },
    )
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
    boundary = fields.Dict(allow_none=True)
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


class CropQuerySchema(Schema):
    q = fields.String(metadata={"description": "Search the crop's name, key or family"})


class CropSchema(Schema):
    """A built-in crop: typical spacing, timings and sowing windows (months 1 to 12)."""

    key = fields.String()
    name = fields.String()
    family = fields.String()
    category = fields.String()
    method_default = fields.String(validate=validate.OneOf(["direct_sow", "transplant"]))
    spacing_plant_cm = fields.Integer()
    spacing_row_cm = fields.Integer()
    germinate_days = fields.Integer()
    maturity_days_min = fields.Integer()
    maturity_days_max = fields.Integer()
    sow_depth_mm = fields.Integer()
    sow_months = fields.List(fields.Integer())
    plant_out_months = fields.List(fields.Integer())
    harvest_months = fields.List(fields.Integer())
    succession_days = fields.Integer(allow_none=True)
    notes = fields.String()


class SightingSchema(Schema):
    media_id = fields.Integer()
    outline = fields.List(
        fields.List(fields.Float()),
        metadata={"description": "[x, y] points, 0 to 1 across and down the picture"},
    )
    score = fields.Float()
    at_s = fields.Float(
        allow_none=True, metadata={"description": "Seconds into the video, if it is a video"}
    )
    kind = fields.String(metadata={"description": "photo or video"})
    still_url = fields.String(
        allow_none=True, metadata={"description": "Signed link to a still of the video frame"}
    )
    url = fields.String(metadata={"description": "Signed link to the full photo or video"})
    thumb_url = fields.String(allow_none=True)
    width = fields.Integer(allow_none=True)
    height = fields.Integer(allow_none=True)


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
    sightings = fields.List(
        fields.Nested(SightingSchema), metadata={"description": "The photos it was seen in"}
    )


class SuggestionQuerySchema(Schema):
    status = fields.String(
        load_default="pending", validate=validate.OneOf(["pending", "accepted", "dismissed"])
    )


class SuggestionPatchSchema(Schema):
    name = fields.String(validate=validate.Length(min=1, max=120))
    kind = fields.String(validate=validate.OneOf([k.value for k in FeatureKind]))
    geometry = fields.Dict(
        metadata={"description": "Moved or reshaped: GeoJSON of the same type as before"}
    )
    radius_m = fields.Float(validate=validate.Range(min=0.01, max=1000))


class SuggestionIdsSchema(Schema):
    ids = fields.List(fields.Integer(), required=True, validate=validate.Length(min=1, max=200))


class MeasurementSchema(Schema):
    id = fields.Integer()
    feature_id = fields.Integer()
    feature_name = fields.String()
    feature_kind = fields.String()
    kind = fields.String(validate=validate.OneOf(["edge", "diagonal", "radius", "custom"]))
    a = fields.Integer(metadata={"description": "Corner number, counting from 0"})
    b = fields.Integer()
    label = fields.String(
        metadata={"description": "For people: corners counted from 1, e.g. '1 to 2'"}
    )
    drawn_m = fields.Float(allow_none=True, metadata={"description": "Its length on the map now"})
    value_m = fields.Float(allow_none=True)
    note = fields.String()
    skipped = fields.Boolean()
    stale = fields.Boolean()
    measured_at = fields.DateTime(allow_none=True)
    measured_by = fields.Integer(allow_none=True)


class MeasurementFeatureSchema(Schema):
    id = fields.Integer()
    name = fields.String()
    kind = fields.String()
    corners = fields.Integer()
    measured = fields.Integer()
    total = fields.Integer()


class MeasurementListSchema(Schema):
    length_unit = fields.String()
    items = fields.List(fields.Nested(MeasurementSchema))
    features = fields.List(fields.Nested(MeasurementFeatureSchema))
    total = fields.Integer(metadata={"description": "Distances to take, not counting skipped ones"})
    measured = fields.Integer()


class MeasurementPatchSchema(Schema):
    value_m = fields.Float(
        allow_none=True,
        validate=validate.Range(min=0.01, max=1000),
        metadata={"description": "Metres; null clears it"},
    )
    note = fields.String(validate=validate.Length(max=300))
    skipped = fields.Boolean()


class MeasurementCustomSchema(Schema):
    feature_id = fields.Integer(required=True)
    a = fields.Integer(required=True, validate=validate.Range(min=0))
    b = fields.Integer(required=True, validate=validate.Range(min=0))


class FitQuerySchema(Schema):
    preview = fields.Boolean(
        load_default=True,
        metadata={"description": "true: only show the result; false: change the map"},
    )


class FitFeatureSchema(Schema):
    feature_id = fields.Integer()
    name = fields.String()
    changed = fields.Boolean()
    rms_before_m = fields.Float()
    rms_after_m = fields.Float()
    max_move_m = fields.Float(metadata={"description": "Furthest any corner moves"})
    missing = fields.Integer(metadata={"description": "More measurements needed to fix the shape"})
    recheck = fields.List(
        fields.Integer(), metadata={"description": "Measurement ids to re-measure"}
    )
    geometry = fields.Raw(metadata={"description": "The corrected GeoJSON geometry"})
    drawn_geometry = fields.Raw()
    radius_m = fields.Float(allow_none=True)
    error = fields.String(allow_none=True)


class FitResultSchema(Schema):
    applied = fields.Boolean()
    features = fields.List(fields.Nested(FitFeatureSchema))


def _months() -> fields.List:
    return fields.List(fields.Integer(validate=validate.Range(min=1, max=12)), load_default=list)


class CalendarSchema(Schema):
    sow_indoors = _months()
    sow_outdoors = _months()
    plant_out = _months()
    harvest = _months()


def _count(low: int, high: int, **kw) -> fields.Integer:
    return fields.Integer(validate=validate.Range(min=low, max=high), allow_none=True, **kw)


class PacketPatchSchema(Schema):
    """Every field of a packet, all optional: used as is for edits."""

    name = fields.String(validate=validate.Length(min=1, max=200))
    variety = fields.String(validate=validate.Length(max=200))
    supplier = fields.String(validate=validate.Length(max=200))
    latin_name = fields.String(validate=validate.Length(max=200))
    notes = fields.String(validate=validate.Length(max=5000))
    raw_text = fields.String(validate=validate.Length(max=20000))
    sow_depth_mm = _count(0, 1000)
    spacing_plant_cm = _count(0, 1000)
    spacing_row_cm = _count(0, 1000)
    germinate_days_min = _count(0, 1000)
    germinate_days_max = _count(0, 1000)
    maturity_days_min = _count(0, 2000)
    maturity_days_max = _count(0, 2000)
    sun = fields.String(allow_none=True, validate=validate.OneOf(SUN_LEVELS))
    stock = fields.String(validate=validate.OneOf(STOCK_LEVELS))
    best_before_year = _count(2000, 2100)
    seeds_in_packet = _count(1, 100000)
    status = fields.String(validate=validate.OneOf(["active"]))  # saving a draft makes it active
    calendar = fields.Nested(CalendarSchema)


class PacketInSchema(PacketPatchSchema):
    name = fields.String(required=True, validate=validate.Length(min=1, max=200))


class PacketQuerySchema(Schema):
    q = fields.String(metadata={"description": "Search name, variety, supplier, latin name, notes"})
    stock = fields.String(validate=validate.OneOf(STOCK_LEVELS))
    status = fields.String(validate=validate.OneOf(["draft", "active"]))
    month = fields.Integer(
        validate=validate.Range(min=1, max=12),
        metadata={"description": "Only packets with the activity in this month (1 to 12)"},
    )
    activity = fields.String(
        load_default="sow",
        validate=validate.OneOf(["sow", *ACTIVITIES]),
        metadata={"description": "With month: sow (indoors or outdoors) or one activity"},
    )


class PacketSchema(Schema):
    id = fields.Integer()
    status = fields.String()
    name = fields.String()
    variety = fields.String()
    supplier = fields.String()
    latin_name = fields.String()
    notes = fields.String()
    raw_text = fields.String()
    sow_depth_mm = fields.Integer(allow_none=True)
    spacing_plant_cm = fields.Integer(allow_none=True)
    spacing_row_cm = fields.Integer(allow_none=True)
    germinate_days_min = fields.Integer(allow_none=True)
    germinate_days_max = fields.Integer(allow_none=True)
    maturity_days_min = fields.Integer(allow_none=True)
    maturity_days_max = fields.Integer(allow_none=True)
    sun = fields.String(allow_none=True)
    stock = fields.String()
    best_before_year = fields.Integer(allow_none=True)
    seeds_in_packet = fields.Integer(allow_none=True)
    calendar = fields.Nested(CalendarSchema)
    photos = fields.List(fields.Nested(MediaSchema))
    created_by = fields.Integer(allow_none=True)
    created_at = fields.DateTime()
    updated_at = fields.DateTime()


TRAY_STATUSES = ["active", "planted_out", "finished"]


class TrayPatchSchema(Schema):
    name = fields.String(validate=validate.Length(min=1, max=200))
    rows = fields.Integer(validate=validate.Range(min=1, max=MAX_TRAY_SIDE))
    cols = fields.Integer(validate=validate.Range(min=1, max=MAX_TRAY_SIDE))
    tray_type = fields.String(validate=validate.Length(max=100))
    sown_on = fields.Date(allow_none=True)
    location = fields.String(validate=validate.Length(max=200))
    notes = fields.String(validate=validate.Length(max=5000))
    status = fields.String(validate=validate.OneOf(TRAY_STATUSES))


class TrayInSchema(TrayPatchSchema):
    name = fields.String(required=True, validate=validate.Length(min=1, max=200))
    rows = fields.Integer(required=True, validate=validate.Range(min=1, max=MAX_TRAY_SIDE))
    cols = fields.Integer(required=True, validate=validate.Range(min=1, max=MAX_TRAY_SIDE))


class TrayQuerySchema(Schema):
    status = fields.String(validate=validate.OneOf(TRAY_STATUSES))
    packet_id = fields.Integer(metadata={"description": "Only trays with this packet sown in them"})


class CellRefSchema(Schema):
    row = fields.Integer(required=True, validate=validate.Range(min=0, max=MAX_TRAY_SIDE - 1))
    col = fields.Integer(required=True, validate=validate.Range(min=0, max=MAX_TRAY_SIDE - 1))


class CellSetSchema(Schema):
    """What to do to the chosen cells. Only the fields sent change."""

    status = fields.String(validate=validate.OneOf(["empty", "sown", "germinated", "failed"]))
    packet_id = fields.Integer(allow_none=True)
    count = fields.Integer(allow_none=True, validate=validate.Range(min=1, max=1000))
    sown_on = fields.Date(allow_none=True)
    germinated_on = fields.Date(allow_none=True)
    note = fields.String(validate=validate.Length(max=500))


class CellsUpdateSchema(Schema):
    cells = fields.List(
        fields.Nested(CellRefSchema), required=True, validate=validate.Length(min=1, max=900)
    )
    set = fields.Nested(CellSetSchema, required=True)


class TrayCellSchema(Schema):
    row = fields.Integer()
    col = fields.Integer()
    packet_id = fields.Integer(allow_none=True)
    count = fields.Integer(allow_none=True)
    status = fields.String(validate=validate.OneOf(CELL_STATUSES))
    sown_on = fields.Date(allow_none=True)
    germinated_on = fields.Date(allow_none=True)
    note = fields.String()
    planting_id = fields.Integer(allow_none=True, metadata={"description": "Where it went"})


class TrayCountsSchema(Schema):
    empty = fields.Integer()
    sown = fields.Integer()
    germinated = fields.Integer()
    failed = fields.Integer()
    planted_out = fields.Integer()


class TrayKindSchema(Schema):
    packet_id = fields.Integer()
    name = fields.String()
    variety = fields.String()
    cells = fields.Integer()
    seeds = fields.Integer()


class TraySummarySchema(Schema):
    id = fields.Integer()
    name = fields.String()
    rows = fields.Integer()
    cols = fields.Integer()
    tray_type = fields.String()
    sown_on = fields.Date(allow_none=True)
    location = fields.String()
    notes = fields.String()
    status = fields.String()
    counts = fields.Nested(TrayCountsSchema)
    kinds = fields.List(fields.Nested(TrayKindSchema))
    thumb_url = fields.String(
        allow_none=True, metadata={"description": "Thumbnail of the tray's newest photo, if any"}
    )
    created_at = fields.DateTime()
    updated_at = fields.DateTime()


class TraySchema(TraySummarySchema):
    cells = fields.List(fields.Nested(TrayCellSchema))
    photos = fields.List(fields.Nested(MediaSchema))


class PacketScanInSchema(Schema):
    media_id = fields.Integer(
        required=True, metadata={"description": "An uploaded photo of the back of a packet"}
    )


class PacketScanSchema(Schema):
    id = fields.Integer()
    status = fields.String()
    error = fields.String(allow_none=True)
    media_id = fields.Integer(allow_none=True)
    packet_id = fields.Integer(
        allow_none=True, metadata={"description": "The draft packet, once ready"}
    )
    calendar_source = fields.String(allow_none=True, metadata={"description": "graphic or words"})
    rotation = fields.Integer()
    missing = fields.List(
        fields.String(), metadata={"description": "Fields the reader could not find"}
    )
    crop = fields.Nested(
        MediaSchema, allow_none=True, metadata={"description": "The calendar as read"}
    )
    created_at = fields.DateTime()
    finished_at = fields.DateTime(allow_none=True)


class PlantingInSchema(Schema):
    """A direct sow: seed put straight into the ground in a drawn region of a bed."""

    feature_id = fields.Integer(required=True, metadata={"description": "The bed"})
    packet_id = fields.Integer(load_default=None, allow_none=True)
    region = fields.Dict(required=True, metadata={"description": "GeoJSON Polygon inside the bed"})
    count = fields.Integer(
        load_default=None, allow_none=True, validate=validate.Range(min=1, max=100000)
    )
    sown_on = fields.Date(load_default=None, allow_none=True)
    notes = fields.String(load_default="", validate=validate.Length(max=5000))
    plan_item_id = fields.Integer(
        load_default=None,
        allow_none=True,
        metadata={"description": "The planned crop this carries out; it is marked done"},
    )


class PlantingPatchSchema(Schema):
    packet_id = fields.Integer(allow_none=True)
    region = fields.Dict()
    count = fields.Integer(allow_none=True, validate=validate.Range(min=1, max=100000))
    status = fields.String(validate=validate.OneOf(PLANTING_STATUSES))
    sown_on = fields.Date(allow_none=True)
    planted_on = fields.Date(allow_none=True)
    harvested_on = fields.Date(allow_none=True)
    notes = fields.String(validate=validate.Length(max=5000))


class PlantingQuerySchema(Schema):
    feature_id = fields.Integer(metadata={"description": "Only this bed"})
    packet_id = fields.Integer()
    tray_id = fields.Integer()
    status = fields.String(validate=validate.OneOf(PLANTING_STATUSES))
    growing = fields.Boolean(metadata={"description": "true: only what still occupies the ground"})


class PlantingSchema(Schema):
    id = fields.Integer()
    feature_id = fields.Integer()
    bed_name = fields.String()
    packet_id = fields.Integer(allow_none=True)
    packet_name = fields.String(allow_none=True)
    packet_variety = fields.String(allow_none=True)
    tray_id = fields.Integer(allow_none=True)
    region = fields.Dict()
    area_m2 = fields.Float()
    count = fields.Integer(allow_none=True)
    method = fields.String(validate=validate.OneOf(METHODS))
    status = fields.String()
    sown_on = fields.Date(allow_none=True)
    planted_on = fields.Date(allow_none=True)
    harvested_on = fields.Date(allow_none=True)
    notes = fields.String()
    warnings = fields.List(
        fields.String(), metadata={"description": "e.g. overlaps another planting"}
    )
    photos = fields.List(fields.Nested(MediaSchema))
    created_at = fields.DateTime()
    updated_at = fields.DateTime()


class PlanItemInSchema(Schema):
    """One crop in one bed for a stretch of time. ``name`` defaults to the packet or crop name."""

    feature_id = fields.Integer(required=True, metadata={"description": "The bed"})
    crop_key = fields.String(load_default=None, allow_none=True, validate=validate.Length(max=40))
    packet_id = fields.Integer(load_default=None, allow_none=True)
    name = fields.String(load_default="", validate=validate.Length(max=120))
    method = fields.String(load_default="direct_sow", validate=validate.OneOf(METHODS))
    area_m2 = fields.Float(
        required=True,
        validate=validate.Range(min=0.01, max=100000),
        metadata={"description": "Space used in square metres"},
    )
    plant_count = fields.Integer(
        load_default=None, allow_none=True, validate=validate.Range(min=1, max=100000)
    )
    sow_on = fields.Date(required=True)
    plant_out_on = fields.Date(
        load_default=None, allow_none=True, metadata={"description": "Transplants only"}
    )
    end_on = fields.Date(required=True, metadata={"description": "The day the bed is free again"})
    notes = fields.String(load_default="", validate=validate.Length(max=5000))


class PlanItemPatchSchema(Schema):
    crop_key = fields.String(allow_none=True, validate=validate.Length(max=40))
    packet_id = fields.Integer(allow_none=True)
    name = fields.String(validate=validate.Length(min=1, max=120))
    method = fields.String(validate=validate.OneOf(METHODS))
    area_m2 = fields.Float(validate=validate.Range(min=0.01, max=100000))
    plant_count = fields.Integer(allow_none=True, validate=validate.Range(min=1, max=100000))
    sow_on = fields.Date()
    plant_out_on = fields.Date(allow_none=True)
    end_on = fields.Date()
    notes = fields.String(validate=validate.Length(max=5000))
    status = fields.String(validate=validate.OneOf(PLAN_STATUSES))


class PlanSuccessionSchema(Schema):
    item = fields.Nested(PlanItemInSchema, required=True)
    interval_days = fields.Integer(required=True, validate=validate.Range(min=1, max=365))
    count = fields.Integer(
        required=True,
        validate=validate.Range(min=1, max=MAX_SUCCESSION),
        metadata={"description": "How many sowings in all, the first being the item itself"},
    )


class PlanQuerySchema(Schema):
    start = fields.Date(data_key="from", load_default=None)
    to = fields.Date(load_default=None)
    feature_id = fields.Integer(load_default=None)


class PlanItemSchema(Schema):
    id = fields.Integer()
    feature_id = fields.Integer()
    crop_key = fields.String(allow_none=True)
    packet_id = fields.Integer(allow_none=True)
    name = fields.String()
    method = fields.String(validate=validate.OneOf(METHODS))
    area_m2 = fields.Float()
    plant_count = fields.Integer(allow_none=True)
    sow_on = fields.Date()
    plant_out_on = fields.Date(allow_none=True)
    end_on = fields.Date()
    series_key = fields.String(allow_none=True)
    notes = fields.String()
    status = fields.String(validate=validate.OneOf(PLAN_STATUSES))
    planting_id = fields.Integer(allow_none=True)
    created_at = fields.DateTime()


class PlanConflictSchema(Schema):
    start = fields.Date(data_key="from")
    to = fields.Date(metadata={"description": "The first day it is no longer overbooked"})
    used_m2 = fields.Float()
    over_m2 = fields.Float()
    item_ids = fields.List(fields.Integer())


class PlanBedSchema(Schema):
    feature_id = fields.Integer()
    name = fields.String()
    area_m2 = fields.Float(allow_none=True, metadata={"description": "Null if the bed has no area"})
    items = fields.List(fields.Nested(PlanItemSchema))
    conflicts = fields.List(fields.Nested(PlanConflictSchema))


class PlanSchema(Schema):
    start = fields.Date(data_key="from")
    to = fields.Date()
    beds = fields.List(fields.Nested(PlanBedSchema))


class PlanTaskSuggestionSchema(Schema):
    key = fields.String(metadata={"description": "Stable id, so a task is made only once"})
    title = fields.String()
    description = fields.String()
    due_date = fields.Date()
    feature_id = fields.Integer(metadata={"description": "The bed"})
    plan_item_id = fields.Integer()
    added = fields.Boolean(metadata={"description": "A task for this already exists"})


class PlanTasksSchema(Schema):
    suggestions = fields.List(fields.Nested(PlanTaskSuggestionSchema))
    stale = fields.Integer(
        metadata={"description": "Tasks made from the plan that no longer match it"}
    )


class PlanTasksQuerySchema(Schema):
    feature_id = fields.Integer(load_default=None, metadata={"description": "Only this bed"})


class PlanTasksAddSchema(Schema):
    feature_id = fields.Integer(load_default=None, allow_none=True)
    keys = fields.List(
        fields.String(),
        load_default=None,
        allow_none=True,
        metadata={"description": "Only these suggestions; leave out for every one not yet added"},
    )


class PlanTasksSyncResultSchema(Schema):
    updated = fields.Integer()
    removed = fields.Integer()


class PlantOutSchema(Schema):
    cells = fields.List(
        fields.Nested(CellRefSchema), required=True, validate=validate.Length(min=1, max=900)
    )
    feature_id = fields.Integer(required=True, metadata={"description": "The bed they go into"})
    region = fields.Dict(required=True, metadata={"description": "GeoJSON Polygon inside the bed"})
    planted_on = fields.Date(
        load_default=None, allow_none=True, metadata={"description": "Default: today"}
    )
    notes = fields.String(load_default="", validate=validate.Length(max=5000))


class PlantOutResultSchema(Schema):
    plantings = fields.List(fields.Nested(PlantingSchema))
    tray = fields.Nested(TraySchema)


class GpxUploadFormSchema(Schema):
    # Documented here for OpenAPI; the view reads the actual file from request.files.
    file = fields.Raw(load_default=None, metadata={"type": "string", "format": "binary"})


class BoundaryFromGpxSchema(Schema):
    polygon = fields.Dict(metadata={"description": "GeoJSON Polygon, counter-clockwise"})
    area_m2 = fields.Float()
    perimeter_m = fields.Float()
    gap_m = fields.Float(metadata={"description": "How far apart the walk's ends were"})
    points_in = fields.Integer()
    points_out = fields.Integer()
    warnings = fields.List(fields.String())


class ActiveTaskSchema(Schema):
    id = fields.String()
    name = fields.String()
    running_seconds = fields.Float(allow_none=True)


class WorkerSchema(Schema):
    name = fields.String(metadata={"description": "Celery node name, e.g. celery@host"})
    queues = fields.List(fields.String())
    concurrency = fields.Integer(allow_none=True)
    pid = fields.Integer(allow_none=True)
    uptime_seconds = fields.Integer(allow_none=True)
    processed = fields.Integer(allow_none=True, metadata={"description": "Tasks since it started"})
    reserved = fields.Integer(metadata={"description": "Tasks fetched and waiting for a slot"})
    active = fields.List(fields.Nested(ActiveTaskSchema))
    version = fields.String(allow_none=True)
    gpu = fields.String(allow_none=True, metadata={"description": "Name of the GPU, if it has one"})


class QueueSchema(Schema):
    name = fields.String()
    depth = fields.Integer(
        allow_none=True, metadata={"description": "Tasks waiting (null: unknown)"}
    )
    consumers = fields.Integer(metadata={"description": "Workers listening to this queue"})


class BeatEntrySchema(Schema):
    name = fields.String()
    task = fields.String()
    schedule = fields.String()
    last_run = fields.DateTime(allow_none=True)
    last_state = fields.String(allow_none=True)


class WorkersSchema(Schema):
    workers = fields.List(fields.Nested(WorkerSchema))
    queues = fields.List(fields.Nested(QueueSchema))
    beat = fields.List(fields.Nested(BeatEntrySchema))
    error = fields.String(
        allow_none=True, metadata={"description": "Why the workers could not be asked"}
    )
    checked_at = fields.DateTime()


class SystemSchema(Schema):
    version = fields.String()
    server_time = fields.DateTime()
    checks = fields.Dict(keys=fields.String(), values=fields.String())
    users = fields.Integer()
    allotments = fields.Integer()
    log_rows = fields.Integer()
    log_retention_days = fields.Integer()


class JobSchema(Schema):
    kind = fields.String(metadata={"description": "map | scan | mastodon"})
    id = fields.Integer()
    label = fields.String()
    status = fields.String()
    stage = fields.String(allow_none=True)
    error = fields.String(allow_none=True)
    allotment_id = fields.Integer()
    allotment_name = fields.String(allow_none=True)
    created_at = fields.DateTime()
    started_at = fields.DateTime(allow_none=True)
    finished_at = fields.DateTime(allow_none=True)


class JobCountSchema(Schema):
    kind = fields.String()
    waiting = fields.Integer(metadata={"description": "Queued or running now"})
    failed_24h = fields.Integer()


class JobsSchema(Schema):
    jobs = fields.List(fields.Nested(JobSchema))
    counts = fields.List(fields.Nested(JobCountSchema))


class LogQuerySchema(Schema):
    level = fields.String(
        validate=validate.OneOf(["info", "warning", "error", "critical"]),
        metadata={"description": "This level and worse"},
    )
    service = fields.String()
    q = fields.String(metadata={"description": "Words in the message (case-insensitive)"})
    request_id = fields.String()
    task_id = fields.String()
    before_id = fields.Integer(metadata={"description": "Only entries older than this id"})
    limit = fields.Integer(validate=validate.Range(min=1, max=200), load_default=100)


class LogEntrySchema(Schema):
    id = fields.Integer()
    at = fields.DateTime()
    service = fields.String()
    host = fields.String()
    level = fields.String()
    event = fields.String()
    request_id = fields.String(allow_none=True)
    task_id = fields.String(allow_none=True)
    data = fields.Dict(allow_none=True)


class LogsSchema(Schema):
    entries = fields.List(fields.Nested(LogEntrySchema))
    next_before = fields.Integer(
        allow_none=True, metadata={"description": "Pass as before_id for more"}
    )
    services = fields.List(fields.String())


class DayListInSchema(Schema):
    name = fields.String(required=True, validate=validate.Length(min=1, max=120))
    date = fields.Date(allow_none=True, load_default=None)
    task_ids = fields.List(fields.Integer(), load_default=list)


class DayListPatchSchema(Schema):
    name = fields.String(validate=validate.Length(min=1, max=120))
    date = fields.Date(allow_none=True)


class DayListSchema(Schema):
    id = fields.Integer()
    name = fields.String()
    date = fields.Date(allow_none=True)
    task_ids = fields.List(fields.Integer(), metadata={"description": "Tasks on the list"})
    task_count = fields.Integer()
    done_count = fields.Integer()
    created_at = fields.DateTime()


class DayListTasksSchema(Schema):
    task_ids = fields.List(
        fields.Integer(), required=True, validate=validate.Length(min=1, max=500)
    )


class VisitInSchema(Schema):
    title = fields.String(required=True, validate=validate.Length(min=1, max=200))
    notes = fields.String(load_default="", validate=validate.Length(max=5000))
    starts_at = fields.DateTime(required=True)
    duration_minutes = fields.Integer(load_default=120, validate=validate.Range(min=1, max=1440))
    task_ids = fields.List(fields.Integer(), load_default=list)


class VisitPatchSchema(Schema):
    title = fields.String(validate=validate.Length(min=1, max=200))
    notes = fields.String(validate=validate.Length(max=5000))
    starts_at = fields.DateTime()
    duration_minutes = fields.Integer(validate=validate.Range(min=1, max=1440))


class VisitSchema(Schema):
    id = fields.Integer()
    title = fields.String()
    notes = fields.String()
    starts_at = fields.DateTime()
    duration_minutes = fields.Integer()
    task_ids = fields.List(fields.Integer(), metadata={"description": "Tasks pegged to the visit"})
    created_at = fields.DateTime()
    updated_at = fields.DateTime()


class VisitTasksSchema(Schema):
    task_ids = fields.List(
        fields.Integer(), required=True, validate=validate.Length(min=1, max=500)
    )


class CalendarTokenSchema(Schema):
    token = fields.String(allow_none=True)
    feed_url = fields.String(allow_none=True, metadata={"description": "webcal:// subscribe URL"})


class FeatureNoteInSchema(Schema):
    feature_id = fields.Integer(required=True)
    body = fields.String(required=True, validate=validate.Length(min=1, max=5000))
    noted_at = fields.DateTime(
        load_default=None,
        allow_none=True,
        metadata={"description": "When it is about; now if left out"},
    )


class FeatureNotePatchSchema(Schema):
    body = fields.String(validate=validate.Length(min=1, max=5000))
    noted_at = fields.DateTime()


class FeatureNoteQuerySchema(Schema):
    feature_id = fields.Integer()


class FeatureNoteSchema(Schema):
    id = fields.Integer()
    feature_id = fields.Integer()
    feature_name = fields.String()
    body = fields.String()
    noted_at = fields.DateTime()
    author = fields.String(
        allow_none=True, metadata={"description": "Display name of who wrote it"}
    )
    created_at = fields.DateTime()
    updated_at = fields.DateTime()


class TaskCommentInSchema(Schema):
    body = fields.String(load_default="", validate=validate.Length(max=5000))
    status = fields.String(
        load_default=None,
        allow_none=True,
        validate=validate.OneOf(TASK_STATUSES),
        metadata={"description": "Move the task to this status as part of the comment"},
    )
    progress = fields.String(
        load_default=None,
        allow_none=True,
        validate=validate.Length(max=80),
        metadata={"description": "A short progress label, e.g. 'waiting on seed'"},
    )

    @validates_schema
    def something_to_say(self, data, **kwargs):
        if (
            not (data.get("body") or "").strip()
            and not data.get("status")
            and not (data.get("progress") or "").strip()
        ):
            raise ValidationError("Write something, or give a status or progress")


class TaskCommentPatchSchema(Schema):
    body = fields.String(validate=validate.Length(max=5000))
    progress = fields.String(allow_none=True, validate=validate.Length(max=80))


class TaskCommentSchema(Schema):
    id = fields.Integer()
    task_id = fields.Integer()
    body = fields.String()
    status = fields.String(allow_none=True)
    progress = fields.String(allow_none=True)
    author = fields.String(
        allow_none=True, metadata={"description": "Display name of who wrote it"}
    )
    author_id = fields.Integer(allow_none=True)
    created_at = fields.DateTime()
    updated_at = fields.DateTime()
    edited = fields.Boolean(metadata={"description": "Changed after it was posted"})
