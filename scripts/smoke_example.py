"""Smoke-test either deployment example through its public HTTP gateway."""

from __future__ import annotations

import argparse
import sys
import time

import httpx


def wait_until_ready(client: httpx.Client, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            django = client.get("/django-health/")
            fastapi = client.get("/api/health")
            if django.status_code == 200 and fastapi.status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(1)
    raise RuntimeError("The example did not become ready before the timeout.")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("base_url", nargs="?", default="http://127.0.0.1:8080")
    parser.add_argument("--timeout", type=float, default=90)
    args = parser.parse_args()

    with httpx.Client(base_url=args.base_url, follow_redirects=True) as client:
        wait_until_ready(client, args.timeout)
        csrf_response = client.get("/demo/login/")
        csrf_response.raise_for_status()
        csrf_token = csrf_response.json()["csrf_token"]
        login_response = client.post(
            "/demo/login/",
            headers={"X-CSRFToken": csrf_token},
            json={
                "username": "reader",
                "password": "local-example-password",
            },
        )
        login_response.raise_for_status()
        api_response = client.get("/api/me")
        api_response.raise_for_status()
        assert api_response.json() == {
            "authenticated": True,
            "username": "reader",
        }
        for route in ("sync", "async", "simple"):
            book_response = client.get(f"/api/books/1/{route}")
            book_response.raise_for_status()
            book = book_response.json()
            assert book["id"] == 1
            assert book["title"]
    print("Django and FastAPI shared a session and served sync/async ORM routes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
