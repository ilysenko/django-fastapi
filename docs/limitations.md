# Limitations

- FastAPI is ASGI-only. A WSGI-only deployment needs an additional ASGI process
  or a migration to a combined ASGI entrypoint.
- The adapted request does not run the complete configured Django middleware
  stack. Session, authentication, and CSRF behavior are installed explicitly.
- Building the adapted Django request buffers the request body in memory.
  Configure edge body limits and treat very large uploads carefully.
- The bridge does not serialize Django models. Define Pydantic request and
  response contracts in the application.
- The bridge does not make synchronous libraries asynchronous.
- Custom authentication and application authorization remain project policy.
- The root composer enters the HTTP FastAPI lifespan and an optional supplied
  root lifespan. WebSocket-app lifespan hooks are not entered separately; put
  shared resources in the root lifespan.
