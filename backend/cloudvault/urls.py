from django.urls import include, path
from django.http import JsonResponse


urlpatterns = [
    path("api/health/", lambda request: JsonResponse({"status": "ok"})),
    path("api/v1/auth/", include("accounts.urls")),
]
