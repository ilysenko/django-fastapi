from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

SECRET_KEY = "standalone-tests-only-not-for-production"
DEBUG = False
ALLOWED_HOSTS = ["testserver"]
ROOT_URLCONF = "django_fastapi_testproject.urls"

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django_fastapi_testproject.books",
]

MIDDLEWARE: list[str] = []

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "test.sqlite3",
    }
}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "django-fastapi-tests",
    }
}

SESSION_ENGINE = "django.contrib.sessions.backends.db"
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

DJANGO_FASTAPI = {
    "PREFIX": "/api",
    "AUTH_RESOLVERS": ["django_fastapi.auth.session_auth_resolver"],
    "CSRF": {"ENABLED": True, "EXEMPT_PATHS": []},
}
