# Changelog

Notable changes to the public source snapshots are recorded here. Source version
metadata does not imply that a Git tag or PyPI release has been published.

## [Unreleased] — 0.2.0

### Added

- Separate WebSocket applications, Django session authentication helpers, strict
  Host/Origin validation, and exact WebSocket mounting with controlled rejection.
- Root routes and composed root/HTTP lifespans with partial-startup cleanup.
- `django_db`, `database_sync_to_async`, and `aclose_db_connections` for explicit
  thread-owned ORM boundaries and cleanup during errors and cancellation.
- Pure ASGI HTTP middleware with per-request thread-sensitive connection cleanup
  and session persistence before response headers, without buffering streams.
- Optional HTTP `SESSION_MIDDLEWARE` with async request and response hooks.

### Fixed

- Preserve yielded root/HTTP lifespan state, with root values winning collisions.
- Normalize WebSocket request schemes for secure-request checks and absolute URLs.
- Preserve multiple cookies, `Vary`, and bodyless response headers during session
  persistence; propagate session backend errors instead of treating them as logout.
- Close adapted Django async streaming iterators in their consuming task on
  completion, disconnect, and send failure, preserving ContextVar ownership.
- Preserve active atomic blocks and healthy persistent DB connections at cleanup.
- Apply discovery endpoint configuration to the separate WebSocket app.

### Documentation

- Document source installation, ORM boundaries, session hooks, WebSocket limits,
  ASGI composition, and streaming cleanup; align executable ORM examples.

## [0.1.0 source snapshot] — 2026-08-23

- Settings-driven FastAPI creation and ASGI mounting beside Django.
- Django request, session user, authenticated-user, and staff-user dependencies.
- Pluggable sync/async authentication resolvers and Django CSRF protection.
- Session persistence, Django response conversion, and JSON exception handlers.

[Unreleased]: https://github.com/ilysenko/django-fastapi/compare/e0ef6939c91a97c089b67281c7f4b642c7977052...main
[0.1.0 source snapshot]: https://github.com/ilysenko/django-fastapi/commit/0e9bf85f424be15d7367ed5de153b8c5ef1fac15
