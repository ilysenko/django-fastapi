import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "acme.settings")

from django_fastapi import get_django_fastapi_application

application = get_django_fastapi_application()
