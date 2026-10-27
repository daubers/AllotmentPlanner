from marshmallow import Schema, fields, validate

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
