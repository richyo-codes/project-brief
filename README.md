# project-brief

`project-brief` gives a compact terminal overview of a source tree: docs, build and test commands, scripts, editor launchers, subprojects, notable repository wiring, CI/CD, and locked dependency vulnerability matches.

See [INSTALL.md](INSTALL.md) for user-wide installation with `uv`.

## Run

Install the project and its locked environment with [uv](https://docs.astral.sh/uv/):

```sh
uv sync
```

Run the CLI through the managed environment:

```sh
uv run project-brief
uv run project-brief --components
uv run project-brief --ci
uv run project-brief --security
```

Run the test suite with:

```sh
uv run python tests/test_cli.py
```

The lockfile is `uv.lock`; update it after changing project metadata or dependencies with `uv lock`.

The installed command is also available directly after activating the environment:

```sh
source .venv/bin/activate
project-brief
project-brief --components
project-brief --ci
project-brief --security
```

Use `--all` for full command and advisory lists, `--security --offline` to inventory packages without network access, and `--color always --icons` for an interactive display. The default layout separates the summary, commands, and hint with blank lines; use `--compact` for a dense view.

## Output contract

File references should use `path:line` so VS Code and Zed terminals can open them with Ctrl/Cmd-click. The tool also supports OSC 8 links with `--links`.
