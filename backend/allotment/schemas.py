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
