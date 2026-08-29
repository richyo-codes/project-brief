# project-brief

`project-brief` gives a compact terminal overview of a source tree: docs, build and test commands, scripts, editor launchers, subprojects, notable repository wiring, CI/CD, and locked dependency vulnerability matches.

See [INSTALL.md](INSTALL.md) for user-wide installation with `uv`.
See [COMPILING.md](COMPILING.md) for the native executable options considered for the project.
See [PUBLISHING.md](PUBLISHING.md) for the PyPI release checklist.

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

## Demo GIFs

With [VHS](https://github.com/charmbracelet/vhs) installed, generate a short
animated terminal inspection demo for any local checkout:

```sh
scripts/demo-gif.sh /path/to/project dist/project-brief-demo.gif
```

The GIF cycles through the project overview, recognized components, and an
offline dependency-security inventory. VHS records the actual terminal
interaction, including the typed commands and rendered output. The script only
inspects the supplied directory; it does not clone or download a project.

Good demo candidates include [uv](https://github.com/astral-sh/uv),
[ripgrep](https://github.com/BurntSushi/ripgrep),
[GitHub CLI](https://github.com/cli/cli),
[Neovim](https://github.com/neovim/neovim), and
[Godot](https://github.com/godotengine/godot). They exercise different
language, build, IDE, CI, and dependency-lockfile detectors.

## Output contract

File references should use `path:line` so VS Code and Zed terminals can open them with Ctrl/Cmd-click. The tool also supports OSC 8 links with `--links`.
