from drf_spectacular.extensions import OpenApiAuthenticationExtension
from drf_spectacular.openapi import AutoSchema


class EsquemaAlmacenamiento(AutoSchema):
    def _get_request_for_media_type(self, serializer, direction="request"):
        schema, obligatorio = super()._get_request_for_media_type(serializer, direction)
        if isinstance(serializer, dict):
            obligatorio = bool(schema.get("required"))
        return schema, obligatorio


class CloudVaultBearerScheme(OpenApiAuthenticationExtension):
    target_class = "auth_workspaces.authentication.CloudVaultJWTAuthentication"
    name = "CloudVaultBearerAuth"

    def get_security_definition(self, auto_schema):
        return {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}
