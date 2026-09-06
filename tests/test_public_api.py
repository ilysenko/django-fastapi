from importlib.metadata import version

import pytest

import django_fastapi


def test_public_version_comes_from_package_metadata() -> None:
    assert django_fastapi.__version__ == version("django-fastapi")


def test_auth_contract_types_are_publicly_exported() -> None:
    assert django_fastapi.AuthUser is not None
    assert django_fastapi.AuthResolver is not None
    assert django_fastapi.AuthResolverResult is not None
    assert django_fastapi.WebSocketAuth is not None
    assert callable(django_fastapi.resolve_websocket_auth)
    assert callable(django_fastapi.require_websocket_user)
    assert callable(django_fastapi.validate_websocket_origin)
    assert callable(django_fastapi.create_websocket_app)


def test_database_boundaries_reject_deferred_function_bodies() -> None:
    def generator_dependency():
        yield 1

    async def async_operation():
        return 1

    async def async_generator_dependency():
        yield 1

    for operation in (
        generator_dependency,
        async_operation,
        async_generator_dependency,
    ):
        for wrapper in (
            django_fastapi.django_db,
            django_fastapi.database_sync_to_async,
        ):
            with pytest.raises(TypeError, match="synchronous, non-generator"):
                wrapper(operation)
