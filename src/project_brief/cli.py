#!/usr/bin/env python3
"""Compact project orientation: docs, commands, launchers, and build systems."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tomllib
import unicodedata
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen


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
            "components": "🧩 ", "notable": "⚠️  ", "branches": "🌿 ", "commands": "▶️  ",
        }.get(text, "") if self.icons else ""
        return self.style("1;34", icon + text)

    def command(self, text: str) -> str:
        return self.style("32", text)

    def muted(self, text: str) -> str:
        return self.style("2", text)

DOC_NAMES = (
    "README*", "INSTALL*", "USAGE*", "DEVELOPMENT*", "CONTRIBUTING*", "AGENTS.md", "CLAUDE.md", "ARCHITECTURE*",
    "TEST.md", "TESTING.md", "test.md", "testing.md", "Testing.md", "Testing*.md",
)
AI_FILE_NAMES = {"AGENTS.md", "CLAUDE.md", "GEMINI.md", ".cursorrules", ".clinerules", ".roomodes", "copilot-instructions.md"}
AI_RULE_DIRECTORIES = {".cursor/rules", ".windsurf/rules", ".clinerules", ".roo/rules", ".github/instructions"}
IGNORED_DIRECTORIES = {".git", "node_modules", ".venv", "venv", ".dart_tool", "build", "dist", "target", "__pycache__"}
SHELL_SCRIPT_EXTENSIONS = {".sh", ".bash", ".zsh", ".fish"}
WINDOWS_SCRIPT_EXTENSIONS = {".ps1", ".bat", ".cmd"}
VISUAL_STUDIO_FILES = {".sln", ".csproj", ".fsproj", ".vbproj", ".vcxproj"}
SHELL_FENCE_LANGUAGES = {"", "bash", "console", "sh", "shell", "zsh"}
COMMAND_PREFIXES = (
    "bun", "cargo", "cmake", "curl", "deno", "docker", "dotnet", "flutter", "git", "go", "gradle",
    "make", "mvn", "npm", "npx", "pip", "poetry", "pnpm", "project-brief", "pytest", "python", "ruby",
    "sh", "just", "uv", "yarn", "./", "../",
)


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


def ai_paths(root: Path) -> list[Path]:
    found: list[Path] = []
    for path in project_files(root, max_depth=5):
        relative = path.relative_to(root)
        relative_directory = "/".join(relative.parts[:-1])
        if path.name in AI_FILE_NAMES or any(relative_directory == directory or relative_directory.startswith(f"{directory}/") for directory in AI_RULE_DIRECTORIES):
            found.append(path)
    return sorted(found, key=lambda path: str(path).lower())


def is_shell_command(line: str) -> bool:
    """Return whether a Markdown code example looks like a shell command."""
    candidate = line.strip()
    if candidate.startswith(("$ ", "> ")):
        candidate = candidate[2:].lstrip()
    if not candidate or candidate.startswith(("#", ">")):
        return False
    first_word = candidate.split(maxsplit=1)[0]
    return first_word.startswith(("./", "../")) or first_word in {prefix.strip() for prefix in COMMAND_PREFIXES}


def markdown_commands(root: Path) -> list[Command]:
    """Extract shell examples from root README, INSTALL, and USAGE documents."""
    commands: list[Command] = []
    for path in existing(root, ("README*", "INSTALL*", "USAGE*")):
        lines = path.read_text(errors="ignore").splitlines()
        in_fence = False
        fence_language = ""
        for line_number, line in enumerate(lines, start=1):
            fence = re.match(r"^\s*(`{3,}|~{3,})\s*([\w+-]*)", line)
            if fence:
                if not in_fence:
                    in_fence = True
                    fence_language = fence.group(2).lower()
                else:
                    in_fence = False
                continue
            if in_fence:
                if fence_language in SHELL_FENCE_LANGUAGES and is_shell_command(line):
                    command = line.strip()
                    if command.startswith(("$ ", "> ")):
                        command = command[2:].lstrip()
                    commands.append(Command(command, f"{path.name}:{line_number} example"))
                continue
            for match in re.finditer(r"(?P<ticks>`{1,3})(?P<text>[^`\n]+?)(?P=ticks)", line):
                if is_shell_command(match.group("text")):
                    commands.append(Command(match.group("text").strip(), f"{path.name}:{line_number} example"))
    return dedupe(commands)


def read_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def npmrc_settings(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    settings: dict[str, str] = {}
    for line in path.read_text(errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith(("#", ";")) or "=" not in line:
            continue
        key, value = line.split("=", 1)
        settings[key.strip().lower()] = value.strip().lower()
    return settings


def npm_install_script_packages(lockfile: Path) -> list[str]:
    data = read_json(lockfile)
    packages = data.get("packages", {})
    if not isinstance(packages, dict):
        return []
    names: list[str] = []
    for location, package in packages.items():
        if not location or not isinstance(package, dict) or not package.get("hasInstallScript"):
            continue
        names.append(str(package.get("name") or location.rsplit("node_modules/", 1)[-1]))
    return sorted(set(names))


def npm_script_policy_findings(root: Path) -> list[str]:
    findings: list[str] = []
    for package in project_files(root, max_depth=5):
        if package.name != "package.json":
            continue
        lockfile = package.with_name("package-lock.json")
        script_packages = npm_install_script_packages(lockfile)
        data = read_json(package)
        npmrc = npmrc_settings(package.with_name(".npmrc"))
        relative = package.parent.relative_to(root)
        label = "npm install scripts" if str(relative) == "." else f"{relative} npm install scripts"
        allow_scripts = data.get("allowScripts")
        dangerously_allow_all = npmrc.get("dangerously-allow-all-scripts") == "true"
        ignore_scripts = npmrc.get("ignore-scripts") == "true"
        strict_allow_scripts = npmrc.get("strict-allow-scripts") == "true"
        configured_allow_scripts = npmrc.get("allow-scripts")
        if dangerously_allow_all:
            findings.append(f"{label}: all dependency scripts enabled (dangerously-allow-all-scripts=true)")
        elif ignore_scripts:
            findings.append(f"{label}: disabled (ignore-scripts=true)")
        elif isinstance(allow_scripts, dict) or configured_allow_scripts:
            allowed = sum(value is True for value in allow_scripts.values()) if isinstance(allow_scripts, dict) else len(configured_allow_scripts.split(","))
            denied = sum(value is False for value in allow_scripts.values()) if isinstance(allow_scripts, dict) else 0
            policy = f"{allowed} approved" + (f", {denied} denied" if denied else "")
            strict = "; strict" if strict_allow_scripts else ""
            findings.append(f"{label}: policy configured ({policy}{strict})")
        elif script_packages:
            findings.append(f"{label}: {len(script_packages)} dependency script packages need review for npm v12; run npm install-scripts ls")
    return findings


def dependency_override_findings(root: Path) -> list[str]:
    findings: list[str] = []
    for path in project_files(root, max_depth=5):
        relative = path.relative_to(root)
        if path.name == "pubspec.yaml":
            text = path.read_text(errors="ignore")
            if re.search(r"^dependency_overrides:\s*$", text, re.MULTILINE):
                findings.append(f"Dart dependency overrides: {relative}")
        elif path.name == "pubspec_overrides.yaml":
            findings.append(f"Dart dependency overrides: {relative}")
        elif path.name == "go.mod":
            text = path.read_text(errors="ignore")
            if re.search(r"^\s*replace(?:\s|\()", text, re.MULTILINE):
                replacements = len(re.findall(r"=>", text))
                findings.append(f"Go module replacements: {relative} ({replacements} replace directive{'s' if replacements != 1 else ''})")
    return findings


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


def flutter_workspace_members(root: Path) -> list[Path]:
    """Return declared Dart workspace packages, ignoring generated and vendored trees."""
    pubspec = root / "pubspec.yaml"
    if not pubspec.is_file():
        return []
    lines = pubspec.read_text(errors="ignore").splitlines()
    members: list[Path] = []
    in_workspace = False
    for line in lines:
        if re.match(r"^workspace:\s*$", line):
            in_workspace = True
            continue
        if in_workspace:
            match = re.match(r"^\s+-\s+([^#]+?)\s*$", line)
            if match:
                member = match.group(1).strip().strip("'\"")
                path = root / member
                if (path / "pubspec.yaml").is_file():
                    members.append(path)
                continue
            if line.strip() and not line.lstrip().startswith("#"):
                break
    return sorted(set(members), key=lambda path: str(path.relative_to(root)).lower())


def gn_output_directories(root: Path, max_depth: int = 4) -> list[Path]:
    """Find configured GN output directories without walking generated output."""
    outputs: list[Path] = []
    for current, directories, _ in os.walk(root):
        current_path = Path(current)
        relative = current_path.relative_to(root)
        if len(relative.parts) >= max_depth:
            directories[:] = []
            continue
        directories[:] = [directory for directory in directories if directory not in IGNORED_DIRECTORIES]
        if "out" not in directories:
            continue
        directories.remove("out")
        output_root = current_path / "out"
        try:
            candidates = list(output_root.iterdir())
        except OSError:
            continue
        outputs.extend(path for path in candidates if path.is_dir() and (path / "args.gn").is_file())
    return sorted(set(outputs), key=lambda path: str(path.relative_to(root)).lower())


def flutter_gn_wrapper(root: Path) -> Path | None:
    wrapper = root / "engine" / "src" / "flutter" / "tools" / "gn"
    return wrapper if wrapper.is_file() else None


def flutter_gn_commands(root: Path) -> tuple[Path | None, list[Command]]:
    wrapper = flutter_gn_wrapper(root)
    if not wrapper:
        return None, []
    relative = wrapper.relative_to(root)
    prefix = f"python3 {relative}"
    modes = re.search(r"--runtime-mode[\s\S]{0,300}?choices=\[([^]]+)\]", wrapper.read_text(errors="ignore"))
    runtime_modes = re.findall(r"['\"]([A-Za-z0-9_-]+)['\"]", modes.group(1)) if modes else ["debug", "profile", "release"]
    commands = [Command(f"{prefix} --help", "show Flutter engine GN options")]
    commands.extend(Command(f"{prefix} --runtime-mode {mode}", f"generate {mode} engine GN files") for mode in runtime_modes)
    return wrapper, commands


def aosp_project(root: Path) -> bool:
    return (root / "build" / "envsetup.sh").is_file() or (
        (root / "build" / "soong").is_dir() and (root / "Android.bp").is_file()
    ) or (root / ".repo" / "manifest.xml").is_file()


def yocto_configurations(root: Path, max_depth: int = 4) -> list[Path]:
    configurations: list[Path] = []
    for current, directories, files in os.walk(root):
        current_path = Path(current)
        relative = current_path.relative_to(root)
        if len(relative.parts) >= max_depth:
            directories[:] = []
        directories[:] = [directory for directory in directories if directory not in IGNORED_DIRECTORIES - {"build"}]
        if "local.conf" in files and "bblayers.conf" in files and current_path.name == "conf":
            configurations.append(current_path.parent)
    return sorted(set(configurations), key=lambda path: str(path.relative_to(root)).lower())


def makefile_variable(path: Path, name: str) -> str | None:
    if not path.is_file():
        return None
    match = re.search(rf"^\s*{re.escape(name)}\s*(?:\?|\+)?=\s*\"?([^\"#\n]+)", path.read_text(errors="ignore"), re.MULTILINE)
    return match.group(1).strip() if match else None


def buildroot_project(root: Path) -> bool:
    return (root / "Config.in").is_file() and (root / "package").is_dir() and (root / "configs").is_dir()


def dagger_project(root: Path) -> bool:
    return any((root / filename).is_file() for filename in ("dagger.json", "dagger.toml", "dagger-module.toml")) or (root / ".dagger").is_dir()


def ansible_files(root: Path) -> tuple[list[Path], list[Path]]:
    playbooks: list[Path] = []
    configs: list[Path] = []
    for path in project_files(root, max_depth=3):
        if path.name in {"ansible.cfg", ".ansible-lint", "requirements.yml", "requirements.yaml"}:
            configs.append(path)
        elif path.suffix.lower() in {".yml", ".yaml"}:
            text = path.read_text(errors="ignore")
            if re.search(r"^\s*(hosts|tasks|roles|collections):", text, re.MULTILINE):
                playbooks.append(path)
    return sorted(set(playbooks)), sorted(set(configs))


def kubernetes_files(root: Path) -> tuple[list[Path], list[Path], list[Path]]:
    manifests: list[Path] = []
    kustomizations: list[Path] = []
    charts: list[Path] = []
    for path in project_files(root, max_depth=3):
        if path.name in {"kustomization.yaml", "kustomization.yml"}:
            kustomizations.append(path)
        elif path.name == "Chart.yaml" or path.name in {"helmfile.yaml", "helmfile.yml"}:
            charts.append(path)
        elif path.suffix.lower() in {".yml", ".yaml"}:
            text = path.read_text(errors="ignore")
            if re.search(r"^apiVersion:\s*\S+", text, re.MULTILINE) and re.search(r"^kind:\s*\S+", text, re.MULTILINE):
                manifests.append(path)
    return sorted(set(manifests)), sorted(set(kustomizations)), sorted(set(charts))


def nix_project(root: Path) -> bool:
    return any((root / filename).is_file() for filename in ("flake.nix", "flake.lock", "shell.nix", "default.nix"))


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
    is_dagger = dagger_project(root)
    if (root / "go.mod").is_file() or (root / "go.work").is_file():
        systems.append("Go modules" if not is_dagger else "Go modules (Dagger module)")
        if not is_dagger:
            commands.extend((Command("go build ./...", "build"), Command("go test ./...", "test"), Command("go run .", "run")))
    if (root / "build.zig").is_file() or (root / "build.zig.zon").is_file():
        systems.append("Zig")
        commands.extend((Command("zig build", "build"), Command("zig build test", "test")))
    root_gn = (root / ".gn").is_file() or (root / "BUILD.gn").is_file()
    gn_outputs = gn_output_directories(root)
    if root_gn or gn_outputs:
        label = "GN" if not gn_outputs else f"GN ({len(gn_outputs)} configured outputs)"
        systems.append(label)
        if root_gn:
            commands.extend((
                Command("gn gen out", "generate Ninja files"),
                Command("gn check out", "check target dependencies"),
                Command("ninja -C out", "build generated targets"),
            ))
        for output in gn_outputs:
            relative = output.relative_to(root)
            commands.append(Command(f"ninja -C {relative}", "build configured GN output"))
    flutter_wrapper, flutter_commands = flutter_gn_commands(root)
    if flutter_wrapper:
        systems.append("Flutter engine GN wrapper")
        commands.extend(flutter_commands)
    if aosp_project(root):
        systems.append("AOSP / Soong")
        commands.extend((
            Command("source build/envsetup.sh", "initialize AOSP build environment"),
            Command("lunch <product>-<variant>", "select AOSP product and variant"),
            Command("m", "build selected AOSP target"),
            Command("atest", "run AOSP tests"),
        ))
    yocto_builds = yocto_configurations(root)
    if (root / "oe-init-build-env").is_file() or yocto_builds:
        details = []
        if yocto_builds:
            details.append(f"{len(yocto_builds)} configured build directories")
            local_conf = yocto_builds[0] / "conf" / "local.conf"
            machine = makefile_variable(local_conf, "MACHINE")
            distro = makefile_variable(local_conf, "DISTRO")
            if machine:
                details.append(f"MACHINE={machine}")
            if distro:
                details.append(f"DISTRO={distro}")
        systems.append("Yocto / OpenEmbedded" + (f" ({', '.join(details)})" if details else ""))
        if (root / "oe-init-build-env").is_file():
            commands.append(Command("source oe-init-build-env <build-dir>", "initialize BitBake environment"))
        commands.extend((
            Command("bitbake-layers show-layers", "list configured Yocto layers"),
            Command("bitbake <image-target>", "build a configured image"),
        ))
    if buildroot_project(root):
        systems.append("Buildroot")
        commands.extend((
            Command("make menuconfig", "configure Buildroot"),
            Command("make", "build configured root filesystem"),
            Command("make savedefconfig", "save minimal configuration"),
            Command("make legal-info", "collect license information"),
        ))
    if is_dagger:
        systems.append("Dagger module")
        commands.extend((
            Command("dagger functions", "list module functions"),
            Command("dagger call <function>", "call a module function"),
            Command("dagger develop", "generate/update module development files"),
        ))
    playbooks, ansible_configs = ansible_files(root)
    if playbooks or ansible_configs:
        systems.append(f"Ansible ({len(playbooks)} playbooks)")
        if (root / "requirements.yml").is_file() or (root / "requirements.yaml").is_file():
            requirements = "requirements.yml" if (root / "requirements.yml").is_file() else "requirements.yaml"
            commands.append(Command(f"ansible-galaxy install -r {requirements}", "install Ansible collections/roles"))
        commands.extend((
            Command("ansible-inventory --list", "inspect inventory"),
            Command("ansible-playbook <playbook>", "run an Ansible playbook"),
        ))
        if (root / ".ansible-lint").is_file() or shutil.which("ansible-lint"):
            commands.append(Command("ansible-lint", "lint Ansible content"))
    manifests, kustomizations, charts = kubernetes_files(root)
    if manifests or kustomizations or charts:
        details = []
        if manifests:
            details.append(f"{len(manifests)} manifests")
        if kustomizations:
            details.append(f"{len(kustomizations)} Kustomize roots")
        if charts:
            details.append(f"{len(charts)} Helm files")
        systems.append("Kubernetes" + (f" ({', '.join(details)})" if details else ""))
        commands.extend((
            Command("kubectl apply --dry-run=client -f .", "validate Kubernetes manifests"),
            Command("kubectl diff -f .", "review cluster changes"),
        ))
        if kustomizations:
            commands.append(Command("kubectl kustomize .", "render Kustomize output"))
        if any(path.name == "Chart.yaml" for path in charts):
            commands.extend((Command("helm lint .", "lint Helm chart"), Command("helm template .", "render Helm chart")))
    if nix_project(root):
        flake = (root / "flake.nix").is_file()
        systems.append("Nix flakes" if flake else "Nix")
        if flake:
            commands.extend((
                Command("nix develop", "enter the project development shell"),
                Command("nix flake show", "list flake inputs and outputs"),
                Command("nix flake check", "check flake outputs"),
                Command("nix build", "build the default flake output"),
            ))
        else:
            commands.append(Command("nix-shell", "enter the project development shell"))
    if (root / "platformio.ini").is_file():
        systems.append("PlatformIO")
        commands.extend((Command("pio run", "build embedded project"), Command("pio test", "run tests")))
    if (root / "pubspec.yaml").is_file():
        workspace_members = flutter_workspace_members(root)
        if workspace_members:
            systems.append(f"Dart workspace ({len(workspace_members) + 1} packages)")
            commands.extend((
                Command("dart pub get", "resolve workspace dependencies"),
                Command("dart analyze", "analyze workspace"),
                Command("dart test", "run Dart tests"),
            ))
        else:
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
    conan_files = {"conanfile.py", "conanfile.txt", "conan.lock"}
    if any((root / filename).is_file() for filename in conan_files):
        systems.append("Conan")
        if (root / "conanfile.py").is_file() or (root / "conanfile.txt").is_file():
            commands.extend((Command("conan install . --build=missing", "install dependencies"), Command("conan build .", "build")))
    if (root / "vcpkg.json").is_file() or (root / "vcpkg-configuration.json").is_file():
        systems.append("vcpkg")
        commands.append(Command("vcpkg install", "install dependencies"))
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
    if (root / "SConstruct").is_file() or (root / "SConscript").is_file():
        systems.append("SCons")
        commands.append(Command("scons", "build"))
    bazel_files = {"MODULE.bazel", "WORKSPACE", "WORKSPACE.bazel", "BUILD", "BUILD.bazel"}
    if any((root / filename).is_file() for filename in bazel_files):
        systems.append("Bazel")
        commands.extend((Command("bazel build //...", "build"), Command("bazel test //...", "test")))
    autotools_files = {"configure.ac", "configure.in", "Makefile.am", "GNUmakefile.am", "aclocal.m4"}
    if any((root / filename).is_file() for filename in autotools_files):
        systems.append("Autotools")
        if (root / "configure.ac").is_file() or (root / "configure.in").is_file():
            commands.append(Command("autoreconf -fi", "bootstrap build system"))
        if (root / "configure").is_file() or (root / "configure.ac").is_file() or (root / "configure.in").is_file():
            commands.append(Command("./configure", "configure build"))
        commands.extend((Command("make", "build"), Command("make check", "test")))
    if (root / "Dockerfile").is_file() or (root / "Containerfile").is_file():
        systems.append("Docker")
        dockerfile = "Containerfile" if (root / "Containerfile").is_file() and not (root / "Dockerfile").is_file() else "Dockerfile"
        build_command = "docker build ." if dockerfile == "Dockerfile" else "docker build -f Containerfile ."
        commands.append(Command(build_command, "build container"))
    compose_files = [root / filename for filename in ("compose.yml", "compose.yaml", "docker-compose.yml", "docker-compose.yaml") if (root / filename).is_file()]
    if compose_files:
        systems.append("Docker Compose")
        commands.extend((Command("docker compose config", "validate configuration"), Command("docker compose build", "build services")))
    devcontainer = root / ".devcontainer" / "devcontainer.json"
    if devcontainer.is_file() or (root / "devcontainer.json").is_file():
        systems.append("Dev Container")
    ruby_files = {"Gemfile", "Gemfile.lock", "Rakefile"}
    ruby_manifests = [path for path in root.iterdir() if path.is_file() and (path.name in ruby_files or path.suffix.lower() == ".gemspec")]
    if ruby_manifests:
        systems.append("Ruby/Bundler")
        if any(path.name == "Gemfile" for path in ruby_manifests):
            commands.append(Command("bundle install", "install dependencies"))
        if any(path.name == "Rakefile" for path in ruby_manifests):
            commands.append(Command("bundle exec rake", "run tasks"))
    java_source = (root / "src" / "main" / "java").is_dir() or any(path.suffix.lower() == ".java" for path in project_files(root, max_depth=3))
    if java_source:
        systems.append("Java")
    android_manifest = root / "app" / "src" / "main" / "AndroidManifest.xml"
    if android_manifest.is_file() and ((root / "settings.gradle").is_file() or (root / "settings.gradle.kts").is_file()):
        systems.append("Android Studio")
        gradle = "./gradlew" if (root / "gradlew").is_file() else "gradle"
        commands.extend((Command(f"{gradle} assemble", "build Android app"), Command(f"{gradle} test", "test Android app")))
    if (root / ".idea").is_dir() or (root / ".fleet").is_dir() or any(path.suffix.lower() == ".iml" for path in root.iterdir() if path.is_file()):
        systems.append("JetBrains")
    if (root / ".project").is_file() or (root / ".classpath").is_file():
        systems.append("Eclipse")
    visual_studio_files = [path for path in root.iterdir() if path.is_file() and path.suffix.lower() in VISUAL_STUDIO_FILES]
    if visual_studio_files:
        systems.append("Visual Studio")
        if any(path.suffix.lower() in {".sln", ".csproj", ".fsproj", ".vbproj"} for path in visual_studio_files):
            commands.extend((Command("dotnet build", "build"), Command("dotnet test", "test")))
        if any(path.suffix.lower() == ".vcxproj" for path in visual_studio_files):
            commands.append(Command("msbuild", "build"))
    godot_project = root / "project.godot"
    if godot_project.is_file():
        systems.append("Godot")
        godot_text = godot_project.read_text(errors="ignore")
        godot_name = re.search(r'^config/name="([^"]+)"$', godot_text, re.MULTILINE)
        if godot_name:
            name = godot_name.group(1)
        commands.extend((
            Command("godot --editor --path .", "open editor"),
            Command("godot --headless --path . --quit", "validate project"),
        ))
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
    commands: list[Command] = []
    script_directories = ("scripts", "bin", "tool", "tools")

    def add_script(path: Path, description: str) -> None:
        relative = path.relative_to(root)
        suffix = path.suffix.lower()
        if suffix == ".ps1":
            commands.append(Command(f"powershell -File {relative}", description))
        elif suffix in {".bat", ".cmd"}:
            commands.append(Command(f"cmd /c {relative}", description))
        elif path.stat().st_mode & 0o111:
            commands.append(Command(f"./{relative}", description))
        elif suffix in SHELL_SCRIPT_EXTENSIONS:
            commands.append(Command(f"sh {relative}", "shell script"))

    for path in sorted((item for item in root.iterdir() if item.is_file()), key=lambda item: item.name.lower()):
        if path.stat().st_mode & 0o111 or path.suffix.lower() in SHELL_SCRIPT_EXTENSIONS | WINDOWS_SCRIPT_EXTENSIONS:
            add_script(path, "root script")
    for directory_name in script_directories:
        directory = root / directory_name
        if not directory.is_dir():
            continue
        description = "bin command" if directory_name == "bin" else "tool command" if directory_name in {"tool", "tools"} else "project script"
        for path in sorted((item for item in directory.iterdir() if item.is_file()), key=lambda item: item.name.lower()):
            add_script(path, description)
    return commands


def components(root: Path, max_depth: int = 5) -> list[tuple[Path, list[str], list[str]]]:
    markers = {
        "Cargo.toml": "Rust/Cargo",
        "package.json": "Node.js",
        "pyproject.toml": "Python",
        "setup.py": "Python",
        "go.mod": "Go modules",
        "go.work": "Go modules",
        "go.work.sum": "Go modules",
        "build.zig": "Zig",
        "build.zig.zon": "Zig",
        ".gn": "GN",
        "BUILD.gn": "GN",
        "platformio.ini": "PlatformIO",
        "pubspec_overrides.yaml": "Flutter/Dart",
        "Dockerfile": "Docker",
        "Containerfile": "Docker",
        "compose.yml": "Docker Compose",
        "compose.yaml": "Docker Compose",
        "docker-compose.yml": "Docker Compose",
        "docker-compose.yaml": "Docker Compose",
        "devcontainer.json": "Dev Container",
        "pubspec.yaml": "Flutter/Dart",
        "CMakeLists.txt": "CMake",
        "meson.build": "Meson",
        "pom.xml": "Maven",
        "build.gradle": "Gradle",
        "build.gradle.kts": "Gradle",
        "uv.lock": "uv",
        ".project": "Eclipse",
        ".classpath": "Eclipse",
        ".sln": "Visual Studio",
        ".csproj": "Visual Studio",
        ".fsproj": "Visual Studio",
        ".vbproj": "Visual Studio",
        ".vcxproj": "Visual Studio",
        "project.godot": "Godot",
        "export_presets.cfg": "Godot",
        "Gemfile": "Ruby/Bundler",
        "Gemfile.lock": "Ruby/Bundler",
        "Rakefile": "Ruby/Bundler",
        "AndroidManifest.xml": "Android Studio",
        "configure.ac": "Autotools",
        "configure.in": "Autotools",
        "Makefile.am": "Autotools",
        "GNUmakefile.am": "Autotools",
        "aclocal.m4": "Autotools",
        "SConstruct": "SCons",
        "SConscript": "SCons",
        "MODULE.bazel": "Bazel",
        "WORKSPACE": "Bazel",
        "WORKSPACE.bazel": "Bazel",
        "BUILD": "Bazel",
        "BUILD.bazel": "Bazel",
        "Android.bp": "AOSP / Soong",
        "Android.mk": "AOSP / Make",
        "oe-init-build-env": "Yocto / OpenEmbedded",
        "Config.in": "Buildroot",
        "dagger.json": "Dagger",
        "dagger.toml": "Dagger",
        "dagger-module.toml": "Dagger",
        "ansible.cfg": "Ansible",
        ".ansible-lint": "Ansible",
        "requirements.yml": "Ansible",
        "requirements.yaml": "Ansible",
        "kustomization.yaml": "Kubernetes / Kustomize",
        "kustomization.yml": "Kubernetes / Kustomize",
        "Chart.yaml": "Kubernetes / Helm",
        "helmfile.yaml": "Kubernetes / Helmfile",
        "helmfile.yml": "Kubernetes / Helmfile",
        "flake.nix": "Nix flakes",
        "flake.lock": "Nix flakes",
        "shell.nix": "Nix",
        "default.nix": "Nix",
        "conanfile.py": "Conan",
        "conanfile.txt": "Conan",
        "conan.lock": "Conan",
        "vcpkg.json": "vcpkg",
        "vcpkg-configuration.json": "vcpkg",
    }
    workspace_members = flutter_workspace_members(root)
    grouped: dict[Path, tuple[set[str], set[str]]] = {}
    if workspace_members:
        source_paths = [root / "pubspec.yaml", *(path / "pubspec.yaml" for path in workspace_members)]
        source_paths.extend(
            path for path in project_files(root, max_depth=min(3, max_depth + 1))
            if path.name in {".gn", "BUILD.gn"}
        )
    else:
        source_paths = project_files(root, max_depth=max_depth + 1)
    for path in source_paths:
        if in_backup_directory(path, root):
            continue
        if len(path.relative_to(root).parts) - 1 > max_depth:
            continue
        kind = markers.get(path.name)
        if path.suffix.lower() in VISUAL_STUDIO_FILES:
            kind = "Visual Studio"
        if path.suffix.lower() == ".gemspec":
            kind = "Ruby/Bundler"
        if path.suffix.lower() == ".iml":
            kind = "JetBrains"
        if path.suffix.lower() == ".gni":
            kind = "GN"
        if path.suffix.lower() == ".java":
            kind = "Java"
        if path.name.startswith("requirements") and path.suffix == ".txt":
            kind = "Python requirements"
        if not kind:
            continue
        types, files = grouped.setdefault(path.parent, (set(), set()))
        types.add(kind)
        files.add(path.name)
    for directory_name in (".idea", ".fleet"):
        if (root / directory_name).is_dir():
            types, files = grouped.setdefault(root, (set(), set()))
            types.add("JetBrains")
            files.add(directory_name)
    return [(directory, sorted(types), sorted(files)) for directory, (types, files) in sorted(grouped.items(), key=lambda item: str(item[0]))]


def component_label(root: Path, component: tuple[Path, list[str], list[str]], links: bool = False) -> str:
    directory, types, files = component
    relative = directory.relative_to(root)
    location = "." if str(relative) == "." else str(relative)
    manifest_references = ", ".join(link(directory / file, root, links) for file in files)
    return f"{location} [{', '.join(types)}]  {manifest_references}"


def in_backup_directory(path: Path, root: Path) -> bool:
    return any(part.startswith(".backup") for part in path.relative_to(root).parts[:-1])


def inspect_components(root: Path, links: bool, max_depth: int = 5) -> int:
    found = components(root, max_depth)
    if not found:
        print("project-brief: no recognized subproject or library manifests found", file=sys.stderr)
        return 1
    for component in found:
        print(component_label(root, component, links))
    return 0


def inspect_gn(root: Path, links: bool) -> int:
    roots = [path for path in (root / ".gn", root / "BUILD.gn") if path.is_file()]
    outputs = gn_output_directories(root)
    flutter_wrapper, flutter_commands = flutter_gn_commands(root)
    if not roots and not outputs and not flutter_wrapper:
        print("project-brief: no GN root or configured GN output found", file=sys.stderr)
        return 1
    if flutter_wrapper:
        print(f"Flutter engine GN wrapper: {link(flutter_wrapper, root, links)}")
        print("  " + " · ".join(command.command for command in flutter_commands))
    if roots:
        print("GN root: " + ", ".join(link(path, root, links) for path in roots))
    if outputs:
        print(f"configured GN outputs: {len(outputs)}")
        for output in outputs:
            relative = output.relative_to(root)
            print(f"  {link(output / 'args.gn', root, links)}")
            print(f"    gn args {relative} --list")
            print(f"    gn ls {relative} //...")
            print(f"    ninja -C {relative}")
    else:
        print("No configured output found; create one with: gn gen out")
    return 0


def inspect_ai(root: Path, links: bool) -> int:
    found = ai_paths(root)
    if not found:
        print("project-brief: no AI/LLM instruction files found", file=sys.stderr)
        return 1
    for path in found:
        print(link(path, root, links))
    return 0


def task_entries(root: Path) -> list[str]:
    found: list[str] = []
    files = (root / ".vscode" / "tasks.json", root / ".vscode" / "launch.json", root / ".zed" / "tasks.json", root / ".zed" / "debug.json")
    for path in files:
        if path.is_file():
            found.append(str(path.relative_to(root)))
    return found


def project_files(root: Path, max_depth: int = 3):
    for current, directories, files in os.walk(root):
        current_path = Path(current)
        relative = current_path.relative_to(root)
        if len(relative.parts) >= max_depth:
            directories[:] = []
        directories[:] = [directory for directory in directories if directory not in IGNORED_DIRECTORIES]
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
        if current_path != root and ".git" in directories:
            nested_repos.append(str(current_path.relative_to(root)))
            directories.remove(".git")
        directories[:] = [directory for directory in directories if directory not in IGNORED_DIRECTORIES]
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
    findings.extend(npm_script_policy_findings(root))
    findings.extend(dependency_override_findings(root))

    artifact_extensions = {".a", ".aab", ".apk", ".dll", ".dylib", ".exe", ".img", ".ipa", ".iso", ".jar", ".o", ".qcow2", ".so", ".wasm", ".zip"}
    artifacts: list[str] = []
    for path in project_files(root):
        if path.suffix.lower() in artifact_extensions:
            artifacts.append(str(path.relative_to(root)))
            continue
        try:
            with path.open("rb") as stream:
                header = stream.read(4)
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
        check=False,
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


def recent_branches(root: Path, limit: int = 5) -> list[str]:
    result = subprocess.run(
        [
            "git", "-C", str(root), "for-each-ref", "--sort=-committerdate",
            "--format=%(HEAD)\t%(refname:short)\t%(committerdate:relative)", "refs/heads",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        return []
    branches: list[str] = []
    for line in result.stdout.splitlines()[:limit]:
        head, name, activity = line.split("\t", 2)
        marker = "* " if head == "*" else "  "
        branches.append(f"{marker}{name} ({activity})")
    return branches


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


def documented_commands(root: Path) -> list[Command]:
    commands: list[Command] = []
    shell_languages = {"bash", "console", "fish", "ps1", "sh", "shell", "shellsession", "terminal", "zsh"}
    for document in document_paths(root):
        lines = document.read_text(errors="ignore").splitlines()
        in_block = False
        language = ""
        pending = ""
        for line_number, line in enumerate(lines, start=1):
            fence = re.match(r"^\s*```\s*([A-Za-z0-9_-]*)\s*$", line)
            if fence:
                if in_block:
                    in_block = False
                    pending = ""
                elif fence.group(1).lower() in shell_languages:
                    in_block = True
                    language = fence.group(1).lower()
                continue
            if not in_block or line.strip().startswith("#"):
                continue
            command = line.strip()
            if language in {"console", "shellsession", "terminal"}:
                prompt = re.match(r"^(?:\$|#|>)\s+(.+)$", command)
                if not prompt:
                    continue
                command = prompt.group(1)
            if command.endswith("\\"):
                pending = f"{pending}{command[:-1].rstrip()} "
                continue
            command = f"{pending}{command}".strip()
            pending = ""
            if command and not command.startswith(("...", "<", "[")):
                commands.append(Command(command, f"documented in {document.relative_to(root)}:{line_number}"))
    return dedupe(commands)


def discovered_commands(root: Path, include_docs: bool = False) -> list[Command]:
    """Collect the commands shown in the summary, without rendering a brief."""
    _, commands, _ = manifest_commands(root)
    commands.extend(make_commands(root))
    just = just_commands(root)
    if just:
        commands.extend(just)
    commands.extend(script_commands(root))
    if include_docs:
        commands.extend(documented_commands(root))
    return dedupe(commands)


def link(path: Path, root: Path, enabled: bool, line: int = 1) -> str:
    label = f"{path.relative_to(root)}:{line}"
    if not enabled:
        return label
    return f"\033]8;;file://{path}#L{line}\033\\{label}\033]8;;\033\\"


def display_width(text: str) -> int:
    text = re.sub(r"\x1b\][^\x07]*?(?:\x07|\x1b\\)", "", text)
    text = re.sub(r"\x1b\[[0-9;]*m", "", text)
    return sum(0 if unicodedata.combining(char) else 2 if unicodedata.east_asian_width(char) in {"W", "F"} else 1 for char in text)


def print_commands(commands: list[Command], render: Render, indent: str = "") -> None:
    width = min(max((display_width(item.command) for item in commands), default=28), 48)
    width = max(28, width)
    for item in commands:
        padding = " " * max(2, width - display_width(item.command) + 2)
        if display_width(item.command) > width:
            print(indent + render.command(item.command))
            print(indent + "  " + render.muted(item.description))
        else:
            print(indent + render.command(item.command) + padding + render.muted(item.description))


def print_section(title: str, lines: list[str], render: Render, columns: int = 0) -> None:
    if lines:
        if columns <= 0:
            prefix = f"{render.section(title)}  "
            continuation = " " * display_width(prefix)
            row = prefix
            terminal_width = shutil.get_terminal_size((100, 24)).columns
            for item in lines:
                separator = "" if row == prefix or row == continuation else " · "
                if separator and display_width(row + separator + item) > terminal_width:
                    print(row)
                    row = continuation + item
                else:
                    row += separator + item
            print(row)
            return
        print(render.section(title))
        width = max(map(display_width, lines)) + 2
        for start in range(0, len(lines), columns):
            row = lines[start:start + columns]
            padding = [item + " " * (width - display_width(item)) for item in row[:-1]]
            print("  " + "".join([*padding, row[-1]]))


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


def fzf_entries(root: Path) -> list[str]:
    entries: dict[str, str] = {}

    def add(path: Path, kind: str) -> None:
        if path.is_file():
            location = f"{path.relative_to(root)}:1"
            entries[location] = f"{kind}  {location}"

    for path in document_paths(root):
        add(path, "doc")
    for directory_name in ("scripts", "bin", "tool", "tools"):
        scripts = root / directory_name
        if scripts.is_dir():
            for path in scripts.iterdir():
                kind = "script" if directory_name == "scripts" else "bin" if directory_name == "bin" else "tool"
                add(path, kind)
    for path in root.iterdir():
        if path.is_file() and (path.stat().st_mode & 0o111 or path.suffix.lower() in SHELL_SCRIPT_EXTENSIONS | WINDOWS_SCRIPT_EXTENSIONS):
            add(path, "root")
    for directory, _, files in components(root):
        for filename in files:
            add(directory / filename, "manifest")
    for relative in task_entries(root):
        add(root / relative, "task")
    for path in ci_files(root):
        add(path, "CI")
    for path in ai_paths(root):
        add(path, "AI")
    return [f"{location}\t{label}" for location, label in sorted(entries.items())]


def pick_with_fzf(root: Path, query: str | None) -> int:
    fzf = shutil.which("fzf")
    if not fzf:
        print("project-brief: fzf is required for --fzf; install fzf and try again", file=sys.stderr)
        return 2
    entries = fzf_entries(root)
    if not entries:
        print("project-brief: no docs, scripts, manifests, tasks, or CI files found", file=sys.stderr)
        return 1
    command = [fzf, "--delimiter", "\t", "--with-nth", "2..", "--prompt", "project-brief> "]
    if query:
        command.extend(("--filter", query))
    result = subprocess.run(command, input="\n".join(entries) + "\n", text=True, capture_output=True, check=False)
    if result.returncode == 130:
        return 1
    if result.returncode:
        print(f"project-brief: fzf failed: {result.stderr.strip()}", file=sys.stderr)
        return result.returncode
    selected = result.stdout.splitlines()
    if not selected:
        return 1
    print(selected[0].split("\t", 1)[0])
    return 0


def pick_command_with_fzf(root: Path, query: str | None, commands: list[Command]) -> int:
    fzf = shutil.which("fzf")
    if not fzf:
        print("project-brief: fzf is required for --commands --fzf; install fzf and try again", file=sys.stderr)
        return 2
    if not commands:
        print("project-brief: no commands found", file=sys.stderr)
        return 1
    entries = [f"{command.command}\t{command.command}  # {command.description}" for command in commands]
    fzf_command = [fzf, "--delimiter", "\t", "--with-nth", "2..", "--prompt", "run command> "]
    if query:
        fzf_command.extend(("--filter", query))
    result = subprocess.run(fzf_command, input="\n".join(entries) + "\n", text=True, capture_output=True, check=False)
    if result.returncode == 130:
        return 1
    if result.returncode:
        print(f"project-brief: fzf failed: {result.stderr.strip()}", file=sys.stderr)
        return result.returncode
    selected = result.stdout.splitlines()
    if not selected:
        return 1
    selected_command = selected[0].split("\t", 1)[0]
    print(f"Selected: {selected_command}")
    try:
        answer = input("Run this command? [y/N] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return 1
    if answer not in {"y", "yes"}:
        print("Not run.")
        return 0
    return subprocess.call(selected_command, shell=True, cwd=root)


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
    parser.add_argument("--fzf", nargs="?", const="", metavar="QUERY", help="pick a discovered file with fzf and print its path:line")
    parser.add_argument("--commands", action="store_true", help="list all recognized commands; combine with --fzf to select and confirm one to run")
    parser.add_argument("--docs", action="store_true", help="with --commands, include shell commands found in project documentation")
    parser.add_argument("--view", nargs="?", const="", metavar="DOC", help="view README or a discovered document (uses glow when available)")
    parser.add_argument("--ci", action="store_true", help="inspect CI/CD configuration files")
    parser.add_argument("--authors", action="store_true", help="count unique Git commit authors")
    parser.add_argument("--components", action="store_true", help="list project and subproject build manifests")
    parser.add_argument("--component-depth", type=int, default=5, metavar="N", help="limit component discovery to N directory levels (default: 5)")
    parser.add_argument("--gn", action="store_true", help="inspect GN roots and configured build outputs")
    parser.add_argument("--ai", action="store_true", help="list AI/LLM instruction and context files")
    parser.add_argument("--security", action="store_true", help="query OSV for vulnerabilities in locked dependency versions")
    parser.add_argument("--offline", action="store_true", help="with --security, inventory lockfiles without a network request")
    parser.add_argument("--all", action="store_true", help="show every detected command, not just the most useful")
    parser.add_argument("--compact", action="store_true", help="omit blank lines between summary sections")
    parser.add_argument("--columns", type=int, metavar="N", help="lay list sections out in N columns (1 = one item per line)")
    parser.add_argument("--links", action="store_true", help="emit OSC 8 hyperlinks for compatible terminals")
    parser.add_argument("--color", choices=("auto", "always", "never"), default="auto", help="terminal color mode (default: auto)")
    parser.add_argument("--icons", action="store_true", help="prefix summary sections with emoji")
    args = parser.parse_args()
    if args.columns is not None and args.columns < 1:
        parser.error("--columns must be at least 1")
    if args.component_depth < 0:
        parser.error("--component-depth must be at least 0")
    color = args.color == "always" or (args.color == "auto" and sys.stdout.isatty() and "NO_COLOR" not in os.environ)
    render = Render(color=color, icons=args.icons)
    root = args.root.resolve()
    if not root.is_dir():
        print(f"project-brief: project root does not exist: {root}", file=sys.stderr)
        return 2
    if args.grep:
        return grep_docs(root, args.grep, args.links)
    if args.commands:
        commands = discovered_commands(root, args.docs)
        if args.fzf is not None:
            return pick_command_with_fzf(root, args.fzf or None, commands)
        print_commands(commands, render)
        return 0
    if args.fzf is not None:
        return pick_with_fzf(root, args.fzf or None)
    if args.view is not None:
        return view_document(root, args.view or None)
    if args.ci:
        return inspect_ci(root, args.links)
    if args.authors:
        return inspect_authors(root)
    if args.components:
        return inspect_components(root, args.links, args.component_depth)
    if args.gn:
        return inspect_gn(root, args.links)
    if args.ai:
        return inspect_ai(root, args.links)
    if args.security:
        return inspect_security(root, args.offline, args.all)

    name, commands, systems = manifest_commands(root)
    commands.extend(make_commands(root))
    just = just_commands(root)
    if just:
        systems.append("Just (justfile)")
        commands.extend(just)
    scripts = script_commands(root)
    found_components = components(root, args.component_depth)
    commands.extend(markdown_commands(root))
    commands = dedupe(commands)
    docs = document_paths(root)
    task_files = task_entries(root)
    notables = notable_findings(root)
    branches = recent_branches(root)
    print(f"{render.title(f'## {name or root.name}')}  {render.muted(f'({root})')}")
    if not args.compact and (docs or systems or task_files or scripts or found_components or notables):
        print()
    columns = args.columns or 0
    print_section("docs", [link(path, root, args.links) for path in docs], render, columns)
    print_section("systems", systems, render, columns)
    if task_files:
        print_section("launch", [f"launch-config list  [{link(root / path, root, args.links)}]" for path in task_files], render, columns)
    script_lines = [script.command for script in scripts]
    print_section("scripts", script_lines if args.all else compact(script_lines), render, columns)
    component_limit = len(found_components) if args.all else 8
    print_section("components", [component_label(root, component, args.links) for component in found_components[:component_limit]], render, columns)
    if len(found_components) > component_limit:
        print(f"{render.section('components')}  … {len(found_components) - component_limit} more; pass --components")
    print_section("notable", notables, render, columns)
    print_section("branches", branches, render, columns)
    limit = len(commands) if args.all else 10
    if not args.compact and commands:
        print()
    if commands:
        print(render.section("commands"))
        print_commands(commands[:limit], render, "  ")
        if len(commands) > limit:
            print(render.muted(f"  … {len(commands) - limit} more; pass --all"))
    else:
        print(f"{render.section('commands')}  {render.muted('no recognized build/test manifest')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
