# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-08-23

### Added

- Settings-driven FastAPI application creation and ASGI mounting beside Django.
- Django request, session user, authenticated-user, and staff-user dependencies.
- Pluggable synchronous and asynchronous authentication resolvers.
- Django CSRF protection for unsafe FastAPI operations.
- Django session persistence and Django response conversion.
- Django `Http404` and `PermissionDenied` exception handlers.

[Unreleased]: https://github.com/ilysenko/django-fastapi/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/ilysenko/django-fastapi/releases/tag/v0.1.0
