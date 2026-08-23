from importlib.metadata import version

import django_fastapi


def test_public_version_comes_from_package_metadata() -> None:
    assert django_fastapi.__version__ == version("django-fastapi")


def test_auth_contract_types_are_publicly_exported() -> None:
    assert django_fastapi.AuthUser is not None
    assert django_fastapi.AuthResolver is not None
    assert django_fastapi.AuthResolverResult is not None
