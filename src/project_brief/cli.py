#!/usr/bin/env python3
"""Compact project orientation: docs, commands, launchers, and build systems."""

from __future__ import annotations

import argparse
from collections import Counter
import json
import os
import re
import shutil
import subprocess
import sys
import tomllib
from urllib.error import URLError
from urllib.request import Request, urlopen
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Command:
    command: str
    description: str


@dataclass(frozen=True)
class LockedPackage:
    ecosystem: str
    name: str
    version: str
    source: Path


@dataclass(frozen=True)
class Render:
    color: bool
    icons: bool

    def style(self, code: str, text: str) -> str:
        return f"\033[{code}m{text}\033[0m" if self.color else text

    def title(self, text: str) -> str:
        return self.style("1;36", text)

    def section(self, text: str) -> str:
        icon = {
            "docs": "📖 ", "systems": "⚙️  ", "launch": "🚀 ", "scripts": "🧰 ",
            "components": "🧩 ", "notable": "⚠️  ", "commands": "▶️  ", "hint": "💡 ",
        }.get(text, "") if self.icons else ""
        return self.style("1;34", icon + text)

    def command(self, text: str) -> str:
        return self.style("32", text)

    def muted(self, text: str) -> str:
        return self.style("2", text)

    def separator(self) -> str:
        return self.muted("─" * 72)


DOC_NAMES = ("README*", "INSTALL*", "DEVELOPMENT*", "CONTRIBUTING*", "AGENTS.md", "CLAUDE.md", "ARCHITECTURE*")


def existing(root: Path, names: tuple[str, ...]) -> list[Path]:
    paths: set[Path] = set()
    for name in names:
        paths.update(path for path in root.glob(name) if path.is_file())
    return sorted(paths, key=lambda path: path.name.lower())


def document_paths(root: Path) -> list[Path]:
    paths = existing(root, DOC_NAMES)
    docs = root / "docs"
    if docs.is_dir():
        paths.extend(path for path in docs.iterdir() if path.is_file() and path.suffix.lower() in {".md", ".txt", ".rst"})
    return sorted(set(paths), key=lambda path: str(path).lower())


def read_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def uses_uv(root: Path) -> bool:
    if (root / "uv.lock").is_file():
        return True
    pyproject = root / "pyproject.toml"
    if not pyproject.is_file():
        return False
    try:
        data = tomllib.loads(pyproject.read_text())
    except (OSError, tomllib.TOMLDecodeError):
        return False
    return isinstance(data, dict) and isinstance(data.get("tool"), dict) and "uv" in data["tool"]


def manifest_commands(root: Path) -> tuple[str | None, list[Command], list[str]]:
    commands: list[Command] = []
    systems: list[str] = []
    name: str | None = None
    package = root / "package.json"
    if package.is_file():
        data = read_json(package)
        name = data.get("name") if isinstance(data.get("name"), str) else name
        systems.append("Node.js (package.json)")
        scripts = data.get("scripts", {})
        if isinstance(scripts, dict):
            for script, value in scripts.items():
                if isinstance(script, str) and isinstance(value, str):
                    commands.append(Command(f"npm run {script}", value))

    pyproject = root / "pyproject.toml"
    if pyproject.is_file():
        try:
            data = tomllib.loads(pyproject.read_text())
        except (OSError, tomllib.TOMLDecodeError):
            data = {}
        project = data.get("project", {}) if isinstance(data, dict) else {}
        if isinstance(project, dict) and isinstance(project.get("name"), str):
            name = project["name"]
        systems.append("Python (pyproject.toml)")
        if (root / "pytest.ini").exists() or "pytest" in pyproject.read_text(errors="ignore"):
            commands.append(Command("pytest", "run tests"))
        commands.append(Command("python -m build", "build distribution"))
        if uses_uv(root):
            systems.append("uv")
            commands.extend((Command("uv sync", "install locked dependencies"), Command("uv lock", "update lockfile")))

    if (root / "Cargo.toml").is_file():
        systems.append("Rust (Cargo)")
        commands.extend((Command("cargo build", "build"), Command("cargo test", "test"), Command("cargo run", "run")))
    if (root / "go.mod").is_file():
        systems.append("Go modules")
        commands.extend((Command("go build ./...", "build"), Command("go test ./...", "test"), Command("go run .", "run")))
    if (root / "pubspec.yaml").is_file():
        systems.append("Flutter/Dart (pubspec.yaml)")
        commands.extend((
            Command("flutter pub get", "install dependencies"),
            Command("flutter analyze", "analyze"),
            Command("flutter test", "test"),
            Command("flutter run", "run on a selected target"),
            Command("flutter build linux", "build Linux app"),
            Command("flutter build apk", "build Android APK"),
        ))
    if (root / "pom.xml").is_file():
        systems.append("Maven")
        commands.extend((Command("mvn package", "build"), Command("mvn test", "test")))
    if (root / "build.gradle").is_file() or (root / "build.gradle.kts").is_file():
        systems.append("Gradle")
        gradle = "./gradlew" if (root / "gradlew").is_file() else "gradle"
        commands.extend((Command(f"{gradle} build", "build"), Command(f"{gradle} test", "test")))
    if (root / "CMakeLists.txt").is_file():
        systems.append("CMake")
        commands.extend((Command("cmake -S . -B build", "configure"), Command("cmake --build build", "build"), Command("ctest --test-dir build", "test")))
    if (root / "meson.build").is_file():
        systems.append("Meson")
        commands.extend((Command("meson setup build", "configure"), Command("meson compile -C build", "build"), Command("meson test -C build", "test")))
    if (root / "Dockerfile").is_file():
        systems.append("Docker")
        commands.append(Command("docker build .", "build container"))
    if (root / ".project").is_file() or (root / ".classpath").is_file():
        systems.append("Eclipse")
    return name, dedupe(commands), systems


def make_commands(root: Path) -> list[Command]:
    makefile = next((path for path in (root / "Makefile", root / "makefile", root / "GNUmakefile") if path.is_file()), None)
    if not makefile:
        return []
    targets: list[Command] = []
    for line in makefile.read_text(errors="ignore").splitlines():
        match = re.match(r"^([A-Za-z0-9][A-Za-z0-9_.-]*)\s*:(?![=])", line)
        if match and not match.group(1).startswith("."):
            targets.append(Command(f"make {match.group(1)}", "Makefile target"))
    return dedupe(targets)


def just_commands(root: Path) -> list[Command]:
    justfile = next((path for path in (root / "justfile", root / ".justfile") if path.is_file()), None)
    if not justfile:
        return []
    targets: list[Command] = []
    for line in justfile.read_text(errors="ignore").splitlines():
        match = re.match(r"^@?([A-Za-z][A-Za-z0-9_-]*)(?:\s+[^:=]*)?\s*:(?!=)", line)
        if match:
            targets.append(Command(f"just {match.group(1)}", "justfile recipe"))
    return dedupe(targets)


def script_commands(root: Path) -> list[Command]:
    directory = root / "scripts"
    if not directory.is_dir():
        return []
    commands: list[Command] = []
    for path in sorted((item for item in directory.iterdir() if item.is_file()), key=lambda item: item.name.lower()):
        relative = path.relative_to(root)
        if path.stat().st_mode & 0o111:
            commands.append(Command(f"./{relative}", "project script"))
        elif path.suffix in {".sh", ".bash", ".zsh"}:
            commands.append(Command(f"sh {relative}", "shell script"))
    return commands


def components(root: Path) -> list[tuple[Path, list[str], list[str]]]:
    markers = {
        "Cargo.toml": "Rust/Cargo",
        "package.json": "Node.js",
        "pyproject.toml": "Python",
        "setup.py": "Python",
        "go.mod": "Go modules",
        "pubspec.yaml": "Flutter/Dart",
        "CMakeLists.txt": "CMake",
        "meson.build": "Meson",
        "pom.xml": "Maven",
        "build.gradle": "Gradle",
        "build.gradle.kts": "Gradle",
        "uv.lock": "uv",
        ".project": "Eclipse",
        ".classpath": "Eclipse",
    }
    grouped: dict[Path, tuple[set[str], set[str]]] = {}
    for path in project_files(root, max_depth=5):
        kind = markers.get(path.name)
        if path.name.startswith("requirements") and path.suffix == ".txt":
            kind = "Python requirements"
        if not kind:
            continue
        types, files = grouped.setdefault(path.parent, (set(), set()))
        types.add(kind)
        files.add(path.name)
    return [(directory, sorted(types), sorted(files)) for directory, (types, files) in sorted(grouped.items(), key=lambda item: str(item[0]))]


def component_label(root: Path, component: tuple[Path, list[str], list[str]], links: bool = False) -> str:
    directory, types, files = component
    relative = directory.relative_to(root)
    location = "." if str(relative) == "." else str(relative)
    manifest_references = ", ".join(link(directory / file, root, links) for file in files)
    return f"{location} [{', '.join(types)}]  {manifest_references}"


def inspect_components(root: Path, links: bool) -> int:
    found = components(root)
    if not found:
        print("project-brief: no recognized subproject or library manifests found", file=sys.stderr)
        return 1
    for component in found:
        print(component_label(root, component, links))
    return 0


def task_entries(root: Path) -> list[str]:
    found: list[str] = []
    files = (root / ".vscode" / "tasks.json", root / ".vscode" / "launch.json", root / ".zed" / "tasks.json", root / ".zed" / "debug.json")
    for path in files:
        if path.is_file():
            found.append(str(path.relative_to(root)))
    return found


def project_files(root: Path, max_depth: int = 3):
    ignored = {".git", "node_modules", ".venv", "venv", ".dart_tool", "build", "dist", "target", "__pycache__"}
    for current, directories, files in os.walk(root):
        current_path = Path(current)
        relative = current_path.relative_to(root)
        if len(relative.parts) >= max_depth:
            directories[:] = []
        directories[:] = [directory for directory in directories if directory not in ignored]
        for filename in files:
            yield current_path / filename


def notable_findings(root: Path) -> list[str]:
    findings: list[str] = []
    hook_paths = [path for path in (root / ".githooks", root / ".husky", root / ".pre-commit-config.yaml", root / ".pre-commit-config.yml") if path.exists()]
    git_hooks = root / ".git" / "hooks"
    if git_hooks.is_dir():
        hook_paths.extend(path for path in git_hooks.iterdir() if path.is_file() and not path.name.endswith(".sample"))
    if hook_paths:
        findings.append("git hooks: " + ", ".join(str(path.relative_to(root)) for path in hook_paths))
    if (root / ".gitmodules").is_file():
        findings.append("git submodules: .gitmodules")

    nested_repos: list[str] = []
    for path in project_files(root):
        if path.name == ".git" and path.parent != root:
            nested_repos.append(str(path.parent.relative_to(root)))
    for current, directories, _ in os.walk(root):
        current_path = Path(current)
        if current_path == root:
            continue
        if ".git" in directories:
            nested_repos.append(str(current_path.relative_to(root)))
            directories.remove(".git")
    if nested_repos:
        findings.append("nested Git repos: " + ", ".join(compact(sorted(set(nested_repos)), 4)))

    ide_paths: list[str] = []
    for name in (".vscode", ".zed", ".idea", ".fleet", ".vs", ".devcontainer", ".settings"):
        if (root / name).exists():
            ide_paths.append(name)
    for pattern in ("*.code-workspace", "*.sln", "*.xcodeproj", "*.xcworkspace"):
        ide_paths.extend(path.name for path in root.glob(pattern))
    if ide_paths:
        findings.append("editor/IDE files: " + ", ".join(sorted(set(ide_paths))))

    ci_paths: list[str] = []
    for path in (root / ".github" / "workflows", root / ".gitlab-ci.yml", root / ".circleci", root / ".buildkite", root / "azure-pipelines.yml", root / "Jenkinsfile"):
        if path.exists():
            ci_paths.append(str(path.relative_to(root)))
    if ci_paths:
        findings.append("CI: " + ", ".join(ci_paths))

    toolchain = [name for name in ("flake.nix", "shell.nix", "devenv.nix", ".envrc", ".tool-versions", ".mise.toml", "mise.toml", ".nvmrc", ".node-version", ".python-version", "rust-toolchain.toml") if (root / name).exists()]
    if toolchain:
        findings.append("toolchain config: " + ", ".join(toolchain))
    environment_files = [path.name for path in root.glob(".env*") if path.is_file() and path.name not in {".env.example", ".env.sample", ".env.template"}]
    if environment_files:
        findings.append("local environment files: " + ", ".join(sorted(environment_files)))
    if (root / ".gitattributes").is_file() and "filter=lfs" in (root / ".gitattributes").read_text(errors="ignore"):
        findings.append("Git LFS: .gitattributes")

    artifact_extensions = {".a", ".aab", ".apk", ".dll", ".dylib", ".exe", ".img", ".ipa", ".iso", ".jar", ".o", ".qcow2", ".so", ".wasm", ".zip"}
    artifacts: list[str] = []
    for path in project_files(root):
        if path.suffix.lower() in artifact_extensions:
            artifacts.append(str(path.relative_to(root)))
            continue
        try:
            header = path.read_bytes()[:4]
        except OSError:
            continue
        if header in {b"\x7fELF", b"MZ\x90\x00", b"\xca\xfe\xba\xbe"}:
            artifacts.append(str(path.relative_to(root)))
    if artifacts:
        findings.append("binary/artifact files: " + ", ".join(compact(sorted(set(artifacts)), 5)))
    return findings


def ci_files(root: Path) -> list[Path]:
    files: list[Path] = []
    workflows = root / ".github" / "workflows"
    if workflows.is_dir():
        files.extend(sorted(path for path in workflows.iterdir() if path.suffix in {".yml", ".yaml"}))
    files.extend(path for path in (root / ".gitlab-ci.yml", root / "azure-pipelines.yml", root / "Jenkinsfile", root / ".circleci" / "config.yml", root / ".buildkite" / "pipeline.yml") if path.is_file())
    return files


def inspect_ci(root: Path, links: bool) -> int:
    files = ci_files(root)
    if not files:
        print("project-brief: no supported CI/CD files found", file=sys.stderr)
        return 1
    for path in files:
        relative = link(path, root, links)
        if ".github/workflows/" not in str(path.relative_to(root)):
            print(f"{relative}")
            continue
        lines = path.read_text(errors="ignore").splitlines()
        name = next((match.group(1).strip(" '\"") for line in lines if (match := re.match(r"^name:\s*(.+)$", line))), path.stem)
        triggers: list[str] = []
        jobs: list[str] = []
        in_jobs = False
        for line in lines:
            if re.match(r"^jobs:\s*$", line):
                in_jobs = True
                continue
            if in_jobs and (match := re.match(r"^  ([A-Za-z0-9_-]+):\s*$", line)):
                jobs.append(match.group(1))
            if (match := re.match(r"^on:\s*\[?([^\]]+)\]?\s*$", line)):
                triggers.extend(item.strip(" '\"") for item in match.group(1).split(","))
            elif re.match(r"^  (push|pull_request|pull_request_target|workflow_dispatch|schedule|release):", line):
                triggers.append(line.strip().rstrip(":"))
        details = [name]
        if triggers:
            details.append("triggers=" + ",".join(sorted(set(triggers))))
        if jobs:
            details.append("jobs=" + ",".join(jobs))
        print(f"{relative}  " + " · ".join(details))
    return 0


def inspect_authors(root: Path) -> int:
    result = subprocess.run(
        ["git", "-C", str(root), "log", "--format=%aN <%aE>"],
        text=True,
        capture_output=True,
    )
    if result.returncode:
        print("project-brief: not a Git repository with commit history", file=sys.stderr)
        return 1
    authors = [line for line in result.stdout.splitlines() if line]
    if not authors:
        print("project-brief: no commits found", file=sys.stderr)
        return 1
    counts = Counter(authors)
    print(f"{len(authors)} commits · {len(counts)} unique authors")
    for author, count in counts.most_common():
        print(f"  {count:>4}  {author}")
    return 0


def locked_packages(root: Path) -> list[LockedPackage]:
    packages: list[LockedPackage] = []
    for path in project_files(root, max_depth=5):
        if path.name in {"package-lock.json", "npm-shrinkwrap.json"}:
            data = read_json(path)
            entries = data.get("packages", {})
            if isinstance(entries, dict):
                for location, entry in entries.items():
                    if not location or not isinstance(entry, dict):
                        continue
                    name = entry.get("name") or str(location).rsplit("node_modules/", 1)[-1]
                    version = entry.get("version")
                    if isinstance(name, str) and isinstance(version, str):
                        packages.append(LockedPackage("npm", name, version, path))
        elif path.name == "Cargo.lock":
            try:
                data = tomllib.loads(path.read_text())
            except (OSError, tomllib.TOMLDecodeError):
                data = {}
            for entry in data.get("package", []) if isinstance(data, dict) else []:
                if isinstance(entry, dict) and isinstance(entry.get("name"), str) and isinstance(entry.get("version"), str):
                    packages.append(LockedPackage("crates.io", entry["name"], entry["version"], path))
        elif path.name in {"poetry.lock", "uv.lock"}:
            try:
                data = tomllib.loads(path.read_text())
            except (OSError, tomllib.TOMLDecodeError):
                data = {}
            for entry in data.get("package", []) if isinstance(data, dict) else []:
                if isinstance(entry, dict) and isinstance(entry.get("name"), str) and isinstance(entry.get("version"), str):
                    packages.append(LockedPackage("PyPI", entry["name"], entry["version"], path))
        elif path.name.startswith("requirements") and path.suffix == ".txt":
            for line in path.read_text(errors="ignore").splitlines():
                match = re.match(r"^\s*([A-Za-z0-9_.-]+)(?:\[[^]]+\])?\s*==\s*([^\s;#]+)", line)
                if match:
                    packages.append(LockedPackage("PyPI", match.group(1), match.group(2), path))
    return packages


def osv_query(packages: list[LockedPackage]) -> list[list[str]]:
    queries = [{"package": {"ecosystem": package.ecosystem, "name": package.name}, "version": package.version} for package in packages]
    request = Request(
        os.environ.get("PROJECT_BRIEF_OSV_URL", "https://api.osv.dev/v1/querybatch"),
        data=json.dumps({"queries": queries}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=20) as response:
            data = json.loads(response.read())
    except (OSError, URLError, json.JSONDecodeError) as error:
        raise RuntimeError(f"OSV query failed: {error}") from error
    results = data.get("results", []) if isinstance(data, dict) else []
    if len(results) != len(packages):
        raise RuntimeError("OSV returned an unexpected number of results")
    return [[vulnerability.get("id", "unknown") for vulnerability in result.get("vulns", []) if isinstance(vulnerability, dict)] if isinstance(result, dict) else [] for result in results]


def inspect_security(root: Path, offline: bool, show_all: bool) -> int:
    raw = locked_packages(root)
    unique: dict[tuple[str, str, str], LockedPackage] = {}
    for package in raw:
        unique[(package.ecosystem, package.name.lower(), package.version)] = package
    packages = list(unique.values())
    lockfiles = sorted({str(package.source.relative_to(root)) for package in packages})
    if not packages:
        print("project-brief: no supported lockfiles or pinned requirements found", file=sys.stderr)
        return 1
    print(f"{len(packages)} unique locked package versions · {len(lockfiles)} dependency files")
    if offline:
        print("offline: skipped OSV lookup (no network request made)")
        if show_all:
            for package in sorted(packages, key=lambda item: (item.ecosystem, item.name.lower())):
                print(f"  {package.ecosystem:<10} {package.name}@{package.version}  [{package.source.relative_to(root)}]")
        return 0
    try:
        results = osv_query(packages)
    except RuntimeError as error:
        print(f"project-brief: {error}", file=sys.stderr)
        return 2
    vulnerable = [(package, ids) for package, ids in zip(packages, results) if ids]
    if not vulnerable:
        print("OSV: no known vulnerabilities matched the scanned locked versions")
        return 0
    print(f"OSV: {len(vulnerable)} vulnerable package versions")
    for package, ids in vulnerable:
        displayed_ids = ids if show_all else compact(ids, 4)
        print(f"  {package.ecosystem:<10} {package.name}@{package.version}  {', '.join(displayed_ids)}  [{package.source.relative_to(root)}]")
    print("Review the advisory IDs for fixed-version guidance before upgrading.")
    return 1


def dedupe(commands: list[Command]) -> list[Command]:
    result: list[Command] = []
    seen: set[str] = set()
    for command in commands:
        if command.command not in seen:
            result.append(command)
            seen.add(command.command)
    return result


def link(path: Path, root: Path, enabled: bool, line: int = 1) -> str:
    label = f"{path.relative_to(root)}:{line}"
    if not enabled:
        return label
    return f"\033]8;;file://{path}#L{line}\033\\{label}\033]8;;\033\\"


def print_section(title: str, lines: list[str], render: Render) -> None:
    if lines:
        print(f"{render.section(title)}  " + " · ".join(lines))


def compact(items: list[str], limit: int = 8) -> list[str]:
    if len(items) <= limit:
        return items
    return [*items[:limit], f"… {len(items) - limit} more"]


def grep_docs(root: Path, pattern: str, links: bool) -> int:
    try:
        regex = re.compile(pattern, re.IGNORECASE)
    except re.error as error:
        print(f"project-brief: invalid regex: {error}", file=sys.stderr)
        return 2
    matches = 0
    for path in document_paths(root):
        for line_number, line in enumerate(path.read_text(errors="ignore").splitlines(), start=1):
            if regex.search(line):
                print(f"{link(path, root, links, line_number)}: {line.strip()}")
                matches += 1
    return 0 if matches else 1


def view_document(root: Path, selection: str | None) -> int:
    docs = document_paths(root)
    if not docs:
        print("project-brief: no project documentation found", file=sys.stderr)
        return 1
    selected: Path | None = None
    if selection:
        exact = [path for path in docs if str(path.relative_to(root)) == selection]
        matches = exact or [path for path in docs if path.name == selection]
        if len(matches) == 1:
            selected = matches[0]
        elif len(matches) > 1:
            print(f"project-brief: document name is ambiguous: {selection}", file=sys.stderr)
            return 2
        else:
            print(f"project-brief: document not found: {selection}", file=sys.stderr)
            return 2
    else:
        selected = next((path for path in docs if path.name.lower().startswith("readme")), docs[0])
    glow = shutil.which("glow")
    if glow:
        return subprocess.call([glow, str(selected)])
    print(selected.read_text(errors="ignore"), end="")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="project-brief", description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="project root (default: current directory)")
    parser.add_argument("--grep", metavar="REGEX", help="search discovered project docs")
    parser.add_argument("--view", nargs="?", const="", metavar="DOC", help="view README or a discovered document (uses glow when available)")
    parser.add_argument("--ci", action="store_true", help="inspect CI/CD configuration files")
    parser.add_argument("--authors", action="store_true", help="count unique Git commit authors")
    parser.add_argument("--components", action="store_true", help="list project and subproject build manifests")
    parser.add_argument("--security", action="store_true", help="query OSV for vulnerabilities in locked dependency versions")
    parser.add_argument("--offline", action="store_true", help="with --security, inventory lockfiles without a network request")
    parser.add_argument("--all", action="store_true", help="show every detected command, not just the most useful")
    parser.add_argument("--compact", action="store_true", help="omit blank lines between summary sections")
    parser.add_argument("--links", action="store_true", help="emit OSC 8 hyperlinks for compatible terminals")
    parser.add_argument("--color", choices=("auto", "always", "never"), default="auto", help="terminal color mode (default: auto)")
    parser.add_argument("--icons", action="store_true", help="prefix summary sections with emoji")
    args = parser.parse_args()
    color = args.color == "always" or (args.color == "auto" and sys.stdout.isatty() and "NO_COLOR" not in os.environ)
    render = Render(color=color, icons=args.icons)
    root = args.root.resolve()
    if not root.is_dir():
        print(f"project-brief: project root does not exist: {root}", file=sys.stderr)
        return 2
    if args.grep:
        return grep_docs(root, args.grep, args.links)
    if args.view is not None:
        return view_document(root, args.view or None)
    if args.ci:
        return inspect_ci(root, args.links)
    if args.authors:
        return inspect_authors(root)
    if args.components:
        return inspect_components(root, args.links)
    if args.security:
        return inspect_security(root, args.offline, args.all)

    name, commands, systems = manifest_commands(root)
    commands.extend(make_commands(root))
    just = just_commands(root)
    if just:
        systems.append("Just (justfile)")
        commands.extend(just)
    scripts = script_commands(root)
    found_components = components(root)
    commands = dedupe(commands)
    docs = document_paths(root)
    task_files = task_entries(root)
    notables = notable_findings(root)
    print(f"{render.title(name or root.name)}  {render.muted(f'({root})')}")
    if not args.compact and (docs or systems or task_files or scripts or found_components or notables):
        print()
        print(render.separator())
        print()
    print_section("docs", [link(path, root, args.links) for path in docs], render)
    print_section("systems", systems, render)
    if task_files:
        print_section("launch", [f"launch-config list  [{link(root / path, root, args.links)}]" for path in task_files], render)
    print_section("scripts", compact([script.command for script in scripts]), render)
    component_limit = len(found_components) if args.all else 8
    print_section("components", [component_label(root, component, args.links) for component in found_components[:component_limit]], render)
    if len(found_components) > component_limit:
        print(f"{render.section('components')}  … {len(found_components) - component_limit} more; pass --components")
    print_section("notable", notables, render)
    limit = len(commands) if args.all else 10
    if not args.compact and commands:
        print()
    if commands:
        print(render.section("commands"))
        for command in commands[:limit]:
            print(f"  {render.command(f'{command.command:<28}')} {render.muted(command.description)}")
        if len(commands) > limit:
            print(render.muted(f"  … {len(commands) - limit} more; pass --all"))
    else:
        print(f"{render.section('commands')}  {render.muted('no recognized build/test manifest')}")
    hint = "project-brief --grep 'install|setup|build'"
    if not args.compact:
        print()
    print(f"{render.section('hint')}  {render.muted(hint)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
