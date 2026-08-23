# Maintainer release guide

Releases use PyPI Trusted Publishing. There is no long-lived PyPI API token in
GitHub Actions.

## One-time repository setup

1. Enable GitHub Pages with **GitHub Actions** as its source.
2. Create a protected `pypi` environment.
3. In PyPI, add a Trusted Publisher for repository
   `ilysenko/django-fastapi`, workflow `release.yml`, environment `pypi`.
4. Enable secret scanning, push protection, private vulnerability reporting,
   Dependabot alerts, and branch protection for `main`.
5. Require CI before merging external pull requests. Disable force pushes and
   branch deletion.

## Release checklist

1. Update `CHANGELOG.md` and `project.version` in `pyproject.toml`.
2. Merge the tested snapshot to `main` and wait for every required check.
3. Tag the exact commit as `vX.Y.Z` and push the tag.
4. The release workflow compares the tag to package metadata, builds a fresh
   wheel and sdist, checks both, records SHA-256 hashes, creates build
   provenance, and publishes through OIDC.
5. Install the published version in a new Django project and run the
   five-minute quickstart.

Never rebuild or manually upload artifacts after the workflow completes. A
different build with the same version cannot be meaningfully audited.
