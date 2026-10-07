from drf_spectacular.extensions import OpenApiAuthenticationExtension


class CloudVaultBearerScheme(OpenApiAuthenticationExtension):
    target_class = "auth_workspaces.authentication.CloudVaultJWTAuthentication"
    name = "CloudVaultBearerAuth"

    def get_security_definition(self, auto_schema):
        return {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}
