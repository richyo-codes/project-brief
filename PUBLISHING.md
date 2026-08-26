# Publishing to PyPI

The package metadata and build configuration are ready for a first PyPI
release. Before publishing, confirm that the distribution name
`project-brief` is available on PyPI and choose the version to release.

## Local release checklist

Run the checks and build both standard artifacts:

```sh
uv sync
uv run ruff check .
uv run python tests/test_cli.py
uv build
```

Inspect the contents of `dist/`, especially the source distribution, before
uploading. The version comes from `pyproject.toml`; update it for every
release and regenerate `uv.lock` if project metadata changes.

## Publishing manually

For a one-off release, configure a PyPI API token and publish with:

```sh
export UV_PUBLISH_TOKEN='pypi-...'
uv publish
```

Do not commit the token or place it in a repository file. Test first with the
same artifacts against TestPyPI if desired, using the TestPyPI repository
option supported by `uv publish`.

## Recommended GitHub release flow

For repeatable releases, configure PyPI Trusted Publishing for this GitHub
repository and its release workflow. The workflow should:

1. run the CI checks;
2. build the sdist and wheel in a separate job;
3. publish only from a reviewed version tag such as `v0.1.0`; and
4. grant `id-token: write` only to the publish job.

This avoids storing a long-lived PyPI token in GitHub Secrets. A future
release workflow can use `uv publish` with the GitHub OIDC identity.
