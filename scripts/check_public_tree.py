"""Scan a public source or unpacked distribution for private project patterns."""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
from pathlib import Path

SKIPPED_DIRECTORIES = {".git", ".mypy_cache", ".pytest_cache", ".ruff_cache"}


def load_patterns(encoded: str) -> list[re.Pattern[str]]:
    try:
        raw_patterns = json.loads(base64.b64decode(encoded).decode())
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("The encoded pattern list is invalid.") from exc
    if not isinstance(raw_patterns, list) or not all(
        isinstance(pattern, str) and pattern for pattern in raw_patterns
    ):
        raise ValueError("Patterns must decode to a non-empty JSON string list.")
    return [re.compile(pattern, re.IGNORECASE) for pattern in raw_patterns]


def scan(root: Path, patterns: list[re.Pattern[str]]) -> list[str]:
    findings: list[str] = []
    for path in sorted(root.rglob("*")):
        if any(part in SKIPPED_DIRECTORIES for part in path.parts):
            continue
        relative_path = path.relative_to(root)
        if path.is_symlink():
            findings.append(f"symlink is not allowed: {relative_path}")
            continue
        if not path.is_file():
            continue
        for pattern in patterns:
            if pattern.search(relative_path.as_posix()):
                findings.append(f"path matches a forbidden pattern: {relative_path}")
        data = path.read_bytes()
        if b"\0" in data:
            findings.append(f"binary file is not allowed: {relative_path}")
            continue
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            findings.append(f"non-UTF-8 file is not allowed: {relative_path}")
            continue
        for line_number, line in enumerate(text.splitlines(), start=1):
            for pattern in patterns:
                if pattern.search(line):
                    findings.append(
                        f"forbidden pattern in {relative_path}:{line_number}"
                    )
    return findings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", type=Path, default=Path.cwd())
    parser.add_argument(
        "--patterns-base64",
        default=os.environ.get("PUBLIC_LEAK_PATTERNS_B64", ""),
    )
    args = parser.parse_args()
    if not args.patterns_base64:
        parser.error("provide --patterns-base64 or set PUBLIC_LEAK_PATTERNS_B64")
    patterns = load_patterns(args.patterns_base64)
    findings = scan(args.root.resolve(), patterns)
    if findings:
        print("Public-tree scan failed:", file=sys.stderr)
        for finding in findings:
            print(f"- {finding}", file=sys.stderr)
        return 1
    print(f"Public-tree scan passed: {args.root}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
