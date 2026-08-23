# Operations

## Health checks

Expose separate meanings rather than one check that does everything:

- **startup**: process initialization has completed;
- **readiness**: this replica can receive traffic;
- **liveness**: the process is stuck and must be restarted.

Avoid slow external calls in liveness checks. A database outage should not
create an uncontrolled restart storm.

## Scaling and database capacity

Track requests, latency, event-loop delay, thread utilization, and database
connections per workload. ASGI concurrency can exceed database capacity long
before CPU is exhausted.

Disable persistent Django connections in genuinely asynchronous ORM paths when
required by the supported Django version, and use a backend pooler sized for
total in-flight query concurrency.

## Reverse-proxy behavior

Verify these with an external smoke test:

- original host and scheme reach Django;
- `/api` is preserved exactly;
- request bodies are not truncated;
- timeouts exceed legitimate request duration;
- response buffering remains enabled for normal JSON;
- buffering is disabled only for SSE or streaming endpoints;
- WebSocket headers are added only to WebSocket locations.

## Graceful shutdown

1. Mark the replica unready.
2. Allow the load balancer to stop sending new requests.
3. Let the ASGI server drain requests and cancel long-lived connections.
4. Give cleanup less time than the orchestrator termination grace period.
5. Force termination only after the grace period.

## Observability

Use structured logs with request method, normalized route, response status,
duration, request ID, and service role (`wsgi` or `asgi`). Correlate the same
request ID through reverse proxy, application, database tracing, and external
HTTP calls.

Export metrics and distributed traces with a vendor-neutral standard such as
OpenTelemetry, and send uncaught exceptions to an error-reporting service with
request IDs and release versions. Scrub sensitive headers, cookies, query
parameters, and local variables before export.

Never log:

- `Authorization` headers;
- session or CSRF cookies;
- request bodies by default;
- passwords, tokens, private keys, or full database URLs.

Monitor at least:

- request rate, error rate, and latency by route;
- ASGI event-loop delay and long-lived connection count;
- sync thread queue/usage;
- WSGI worker saturation;
- database pool usage and query latency;
- authentication and CSRF failures without sensitive values.
