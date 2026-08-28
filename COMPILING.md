# Compiling project-brief

`project-brief` is currently distributed as a normal Python package through
`uv`. A native executable could make installation easier on machines that do
not already have a suitable Python environment, but it would add a platform-
specific build and release process.

## Options considered

### Nuitka

Nuitka is the best fit for producing a standalone executable. It translates
Python to C/C++ and bundles the required Python runtime and standard-library
modules.

```sh
uv tool install nuitka
nuitka \
  --onefile \
  --output-dir=dist \
  --output-filename=project-brief \
  src/project_brief/cli.py
```

The result is `dist/project-brief`. Building requires a C compiler, and a
separate executable must be produced for each target platform and
architecture.

### mypyc

mypyc was a reasonable first thought because it compiles typed Python modules
to C extensions. It is not the best first choice for this project, however:

- It produces extension modules, not normally a standalone executable.
- The package would still need a Python installation and a packaging layer.
- It benefits most from code with thorough static type annotations.
- The CLI currently relies on ordinary dynamic Python behavior and standard
  library integration rather than CPU-heavy code.

mypyc could still be useful later if profiling identifies expensive, typed
helpers—such as large-tree scanning—as a meaningful bottleneck. It would be a
targeted optimization, not the primary distribution format.

### PyInstaller

PyInstaller is useful when the goal is simply a self-contained executable. It
bundles the Python interpreter and application rather than compiling the
program into native machine code. It may be simpler operationally than
Nuitka, but generally produces larger artifacts.

### Cython

Cython can compile selected modules and can produce extension modules or
executables, but it usually requires more source changes and explicit type
annotations. It is more appropriate when native speedups are the goal than
when the goal is a portable CLI artifact.

## Suggested path

Keep `uv tool install .` as the primary installation method. If native
artifacts become useful, add a documented Nuitka release build that produces
one executable per supported platform. Keep the Python package as the source
of truth and compare the native build against the existing test suite.

Before adopting native artifacts, measure:

1. startup time;
2. executable size;
3. scan performance on large repositories;
4. behavior on projects containing unusual files or symlinks; and
5. release complexity across Linux, macOS, and Windows.
