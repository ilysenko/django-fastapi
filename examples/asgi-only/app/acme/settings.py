import os

SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "local-example-only-change-in-production",
)
DEBUG = False
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "app", "nginx", "testserver"]
ROOT_URLCONF = "acme.urls"

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "books",
]
MIDDLEWARE = [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
]

if database_host := os.environ.get("DATABASE_HOST"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "HOST": database_host,
            "PORT": os.environ.get("DATABASE_PORT", "5432"),
            "NAME": os.environ.get("DATABASE_NAME", "books"),
            "USER": os.environ.get("DATABASE_USER", "postgres"),
            "PASSWORD": os.environ.get("DATABASE_PASSWORD", ""),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": os.environ.get("DATABASE_PATH", "/tmp/example.sqlite3"),
        }
    }

SESSION_ENGINE = "django.contrib.sessions.backends.db"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

DJANGO_FASTAPI = {
    "PREFIX": "/api",
    "TITLE": "Acme Books API",
    "ROUTERS": ["books.api.router"],
}
