import json

from django.contrib.auth import authenticate, login
from django.http import HttpRequest, JsonResponse
from django.middleware.csrf import get_token
from django.urls import path


def django_health(_request: HttpRequest) -> JsonResponse:
    return JsonResponse({"status": "ok", "served_by": "django"})


def demo_login(request: HttpRequest) -> JsonResponse:
    """Small CSRF-protected login used only by the standalone example."""
    if request.method == "GET":
        return JsonResponse({"csrf_token": get_token(request)})
    if request.method != "POST":
        return JsonResponse({"detail": "Method not allowed."}, status=405)

    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"detail": "Invalid JSON."}, status=400)
    user = authenticate(
        request,
        username=payload.get("username"),
        password=payload.get("password"),
    )
    if user is None:
        return JsonResponse({"detail": "Invalid credentials."}, status=401)
    login(request, user)
    return JsonResponse({"username": user.get_username()})


urlpatterns = [
    path("django-health/", django_health),
    path("demo/login/", demo_login),
]
