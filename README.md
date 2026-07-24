# project-brief

`project-brief` gives a compact terminal overview of a source tree: docs, build and test commands, scripts, editor launchers, subprojects, notable repository wiring, CI/CD, and locked dependency vulnerability matches.

## Run

```sh
project-brief
project-brief --components
project-brief --ci
project-brief --security
```

Use `--all` for full command and advisory lists, `--security --offline` to inventory packages without network access, and `--color always --icons` for an interactive display. The default layout separates the summary, commands, and hint with blank lines; use `--compact` for a dense view.

## Output contract

File references should use `path:line` so VS Code and Zed terminals can open them with Ctrl/Cmd-click. The tool also supports OSC 8 links with `--links`.
