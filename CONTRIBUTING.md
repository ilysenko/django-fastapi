# Contributing

Thank you for helping improve `django-fastapi`.

## Set up a development environment

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[test,lint,docs,release]"
```

Run the local checks before opening a pull request:

```bash
pytest --cov
ruff check .
ruff format --check .
mypy
mkdocs build --strict
python -m build
twine check dist/*
```

Keep changes focused, add the smallest tests that cover meaningful behavior,
and update the documentation when a public interface or deployment pattern
changes. Never include real credentials, private domains, production settings,
customer data, or code copied from a private application.

Pull requests are imported into the canonical development tree by the
maintainer and then synchronized back to this repository. A maintainer may
close a pull request after its commits have been incorporated through that
workflow rather than using GitHub's merge button directly.

By participating, you agree to follow the [Code of Conduct](CODE_OF_CONDUCT.md).
