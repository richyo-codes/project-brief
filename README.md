# project-brief

`project-brief` gives a compact terminal overview of a source tree: docs, build and test commands, scripts, editor launchers, subprojects, notable repository wiring, CI/CD, and locked dependency vulnerability matches.

See [INSTALL.md](INSTALL.md) for user-wide installation with `uv`.
See [COMPILING.md](COMPILING.md) for the native executable options considered for the project.

## Run

After installation, run the command directly:

```sh
project-brief
project-brief --components
project-brief --ci
project-brief --security
```

Use `--all` for full command and advisory lists, `--security --offline` to inventory packages without network access, and `--color always --icons` for an interactive display. Use `--compact` for a dense view.

With [fzf](https://github.com/junegunn/fzf) installed, choose a discovered document, script, manifest, task, or CI file and print a terminal-clickable location:

```sh
project-brief --fzf
project-brief --fzf README
```

For development, install the local environment and run the tests with:

```sh
uv sync
uv run python tests/test_cli.py
```

Update the lockfile after changing project metadata or dependencies with `uv lock`.

## Output contract

File references should use `path:line` so VS Code and Zed terminals can open them with Ctrl/Cmd-click. The tool also supports OSC 8 links with `--links`.
