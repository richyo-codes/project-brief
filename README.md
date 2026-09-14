# project-brief

`project-brief` gives a compact terminal overview of a source tree: docs, build and test commands, scripts, editor launchers, subprojects, notable repository wiring, CI/CD, and locked dependency vulnerability matches.

See [INSTALL.md](INSTALL.md) for user-wide installation with `uv`.
See [COMPILING.md](COMPILING.md) for the native executable options considered for the project.
See [PUBLISHING.md](PUBLISHING.md) for the PyPI release checklist.

## Profiling with perf

With Linux `perf` and Brendan Gregg's `FlameGraph` scripts on `PATH`, profile
an invocation and write an SVG flamegraph:

```sh
scripts/profile-perf.sh /tmp/project-brief.svg --root /path/to/project --all
```

If the FlameGraph scripts or `perf` are not on `PATH`, provide their
locations explicitly. Put `--` before arguments that should be passed to
project-brief:

```sh
scripts/profile-perf.sh /tmp/project-brief.svg \
  --flamegraph-dir /opt/FlameGraph \
  --perf /usr/bin/perf \
  -- --root /path/to/project --all
```

The same settings can be supplied with `PROJECT_BRIEF_FLAMEGRAPH_DIR`,
`PROJECT_BRIEF_PERF`, and `PROJECT_BRIEF_PYTHON`.

The wrapper uses DWARF call graphs and removes temporary `perf` data after the
SVG is written. Linux kernel permissions may require adjusting
`kernel.perf_event_paranoid` or running the command in an environment where
performance counters are allowed. For Python line-level profiling, use a
Python-aware profiler such as `py-spy`; `perf` primarily shows native/Python
interpreter stack activity.

## Run

After installation, run the command directly:

```sh
project-brief
project-brief --components
project-brief --ci
project-brief --security
project-brief --commands
project-brief --gn
```

Use `--all` for full command and advisory lists, `--security --offline` to inventory packages without network access, and `--color always --icons` for an interactive display. Use `--compact` for a dense view.

Limit component discovery when inspecting a large monorepo with
`--component-depth 1` for the root and immediate child directories. The
default depth is 5.

The default joins short lists onto one line and wraps longer lists between
items to fit the terminal. Paths and commands remain intact. Long commands
show their descriptions on the next line. Use `--columns` when you want a
more readable layout: `--columns 1` puts every item on its own line, while
larger values create a fixed-width grid. `--columns` does not change the
default item limits; combine it with `--all` to show every item.

Use `--commands` when you want only the recognized commands, including scripts,
Make/Just targets, and package-manager tasks. Add `--fzf` to select one and
confirm before running it:

```sh
project-brief --commands --fzf
project-brief --commands --fzf test
```

The command is run from the selected project root and only after answering
`y`/`yes` at the confirmation prompt.

Include commands documented in shell code blocks with:

```sh
project-brief --commands --docs
project-brief --commands --docs --fzf flutter
```

Documented entries include their source document and line number, and can be
selected and confirmed through the same fzf workflow.

For GN/Ninja projects, `--gn` lists existing configured outputs discovered from
`out/*/args.gn`, together with exact commands to inspect effective arguments,
list resolved targets, and build each output. It does not guess initial GN
arguments from `BUILD.gn` files.

Flutter engine checkouts get an additional wrapper summary when
`engine/src/flutter/tools/gn` is present. Its runtime-mode choices are read
from the wrapper itself, so commands such as `--runtime-mode debug` and
`--runtime-mode release` stay aligned with that checkout.

AOSP/Soong, Yocto/OpenEmbedded, and Buildroot roots are also recognized. Their
environment-dependent commands are shown with placeholders for the product,
machine, image, or build directory where the repository does not provide a
safe value to infer.

Ansible, Kubernetes/Kustomize/Helm, and Nix projects are recognized as well.
Nix flakes report `nix develop`, `nix flake show`, `nix flake check`, and
`nix build`, making the flake’s development and build entry points visible in
the compact summary.

Dagger modules are recognized from `dagger-module.toml`, `dagger.json`,
`dagger.toml`, or `.dagger/`. A Go module with Dagger metadata is labeled as a
Dagger module and shows `dagger functions`, `dagger call <function>`, and
`dagger develop` rather than generic Go commands. See the [Dagger Go SDK
guide](https://docs.dagger.io/sdks/go/) for the module model.

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
interaction, including the typed commands and rendered output. The script keeps
the editable tape at `dist/project-brief-demo.tape` by default:

```sh
scripts/demo-gif.sh /path/to/project dist/project-brief-demo.gif \
  --include overview,components,ci,ai \
  --tape demos/project-brief.tape
```

Available scenes are `overview`, `components`, `security`, `ai`, `ci`, and
`authors`. The script only inspects the supplied directory; it does not clone
or download a project.

Good demo candidates include [uv](https://github.com/astral-sh/uv),
[ripgrep](https://github.com/BurntSushi/ripgrep),
[GitHub CLI](https://github.com/cli/cli),
[Neovim](https://github.com/neovim/neovim), and
[Godot](https://github.com/godotengine/godot). They exercise different
language, build, IDE, CI, and dependency-lockfile detectors.

## Output contract

File references should use `path:line` so VS Code and Zed terminals can open them with Ctrl/Cmd-click. The tool also supports OSC 8 links with `--links`.
