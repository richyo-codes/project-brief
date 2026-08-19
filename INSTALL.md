# Installation

## Install with uv

From the project directory, install `project-brief` as a user-wide command:

```sh
uv tool install .
uv tool update-shell
```

Restart your shell, then run:

```sh
project-brief
```

`uv tool install .` installs the package in an isolated environment and exposes
the `project-brief` command on your `PATH`.

## Update after local changes

If you change the project and want to reinstall the command:

```sh
uv tool install --force .
```

## Development environment

To install the project into its local development environment instead:

```sh
uv sync
uv run project-brief
```
