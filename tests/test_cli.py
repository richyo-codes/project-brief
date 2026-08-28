import os
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
TOOL = [sys.executable, str(PROJECT / "src" / "project_brief" / "cli.py")]
FIXTURE = PROJECT / "tests" / "fixtures" / "sample-project"
ECLIPSE_FIXTURE = PROJECT / "tests" / "fixtures" / "eclipse-project"
VISUAL_STUDIO_FIXTURE = PROJECT / "tests" / "fixtures" / "visual-studio-project"
NPM_SECURITY_FIXTURE = PROJECT / "tests" / "fixtures" / "npm-security-project"
GODOT_FIXTURE = PROJECT / "tests" / "fixtures" / "godot-project"
RUBY_FIXTURE = PROJECT / "tests" / "fixtures" / "ruby-project"
JAVA_FIXTURE = PROJECT / "tests" / "fixtures" / "java-project"
ANDROID_FIXTURE = PROJECT / "tests" / "fixtures" / "android-studio-project"
JETBRAINS_FIXTURE = PROJECT / "tests" / "fixtures" / "jetbrains-project"
AUTOTOOLS_FIXTURE = PROJECT / "tests" / "fixtures" / "autotools-project"
CONAN_FIXTURE = PROJECT / "tests" / "fixtures" / "conan-project"
VCPKG_FIXTURE = PROJECT / "tests" / "fixtures" / "vcpkg-project"
MAVEN_FIXTURE = PROJECT / "tests" / "fixtures" / "maven-project"
AI_FIXTURE = PROJECT / "tests" / "fixtures" / "ai-project"
SCONS_FIXTURE = PROJECT / "tests" / "fixtures" / "scons-project"
BAZEL_FIXTURE = PROJECT / "tests" / "fixtures" / "bazel-project"
ZIG_FIXTURE = PROJECT / "tests" / "fixtures" / "zig-project"
PLATFORMIO_FIXTURE = PROJECT / "tests" / "fixtures" / "platformio-project"
CONTAINER_FIXTURE = PROJECT / "tests" / "fixtures" / "container-project"


def main():
    project_summary = subprocess.run([*TOOL], text=True, capture_output=True, check=True).stdout
    assert "systems" in project_summary and "uv" in project_summary and "uv sync" in project_summary, project_summary
    assert "branches" in project_summary, project_summary
    eclipse_summary = subprocess.run([*TOOL, "--root", ECLIPSE_FIXTURE], text=True, capture_output=True, check=True).stdout
    assert "Eclipse" in eclipse_summary and ".project" in eclipse_summary, eclipse_summary
    visual_studio_summary = subprocess.run([*TOOL, "--root", VISUAL_STUDIO_FIXTURE], text=True, capture_output=True, check=True).stdout
    assert "Visual Studio" in visual_studio_summary and "MyApp.csproj" in visual_studio_summary and "dotnet build" in visual_studio_summary, visual_studio_summary
    npm_security_summary = subprocess.run([*TOOL, "--root", NPM_SECURITY_FIXTURE], text=True, capture_output=True, check=True).stdout
    assert "npm install scripts: 2 dependency script packages need review for npm v12" in npm_security_summary, npm_security_summary
    godot_summary = subprocess.run([*TOOL, "--root", GODOT_FIXTURE], text=True, capture_output=True, check=True).stdout
    assert "## Godot Fixture" in godot_summary and "Godot" in godot_summary and "project.godot" in godot_summary and "godot --editor --path ." in godot_summary, godot_summary
    ruby_summary = subprocess.run([*TOOL, "--root", RUBY_FIXTURE], text=True, capture_output=True, check=True).stdout
    assert "Ruby/Bundler" in ruby_summary and "Gemfile" in ruby_summary and "bundle install" in ruby_summary, ruby_summary
    java_summary = subprocess.run([*TOOL, "--root", JAVA_FIXTURE], text=True, capture_output=True, check=True).stdout
    assert "Java" in java_summary and "Main.java" in java_summary, java_summary
    android_summary = subprocess.run([*TOOL, "--root", ANDROID_FIXTURE], text=True, capture_output=True, check=True).stdout
    assert "Android Studio" in android_summary and "AndroidManifest.xml" in android_summary and "assemble" in android_summary, android_summary
    jetbrains_summary = subprocess.run([*TOOL, "--root", JETBRAINS_FIXTURE], text=True, capture_output=True, check=True).stdout
    assert "JetBrains" in jetbrains_summary and ".idea" in jetbrains_summary, jetbrains_summary
    autotools_summary = subprocess.run([*TOOL, "--root", AUTOTOOLS_FIXTURE], text=True, capture_output=True, check=True).stdout
    assert "Autotools" in autotools_summary and "configure.ac" in autotools_summary and "autoreconf -fi" in autotools_summary and "make check" in autotools_summary, autotools_summary
    conan_summary = subprocess.run([*TOOL, "--root", CONAN_FIXTURE], text=True, capture_output=True, check=True).stdout
    assert "Conan" in conan_summary and "conanfile.py" in conan_summary and "conan install" in conan_summary, conan_summary
    vcpkg_summary = subprocess.run([*TOOL, "--root", VCPKG_FIXTURE], text=True, capture_output=True, check=True).stdout
    assert "vcpkg" in vcpkg_summary and "vcpkg.json" in vcpkg_summary and "vcpkg install" in vcpkg_summary, vcpkg_summary
    maven_summary = subprocess.run([*TOOL, "--root", MAVEN_FIXTURE], text=True, capture_output=True, check=True).stdout
    assert "Maven" in maven_summary and "pom.xml" in maven_summary and "mvn package" in maven_summary, maven_summary
    ai_summary = subprocess.run([*TOOL, "--root", AI_FIXTURE, "--ai"], text=True, capture_output=True, check=True).stdout
    assert "AGENTS.md:1" in ai_summary and ".cursor/rules/style.md:1" in ai_summary, ai_summary
    scons_summary = subprocess.run([*TOOL, "--root", SCONS_FIXTURE], text=True, capture_output=True, check=True).stdout
    assert "SCons" in scons_summary and "SConstruct" in scons_summary and "scons" in scons_summary, scons_summary
    bazel_summary = subprocess.run([*TOOL, "--root", BAZEL_FIXTURE], text=True, capture_output=True, check=True).stdout
    assert "Bazel" in bazel_summary and "MODULE.bazel" in bazel_summary and "bazel build //..." in bazel_summary, bazel_summary
    zig_summary = subprocess.run([*TOOL, "--root", ZIG_FIXTURE], text=True, capture_output=True, check=True).stdout
    assert "Zig" in zig_summary and "build.zig" in zig_summary and "zig build test" in zig_summary, zig_summary
    platformio_summary = subprocess.run([*TOOL, "--root", PLATFORMIO_FIXTURE], text=True, capture_output=True, check=True).stdout
    assert "PlatformIO" in platformio_summary and "platformio.ini" in platformio_summary and "pio run" in platformio_summary, platformio_summary
    container_summary = subprocess.run([*TOOL, "--root", CONTAINER_FIXTURE], text=True, capture_output=True, check=True).stdout
    assert "Docker" in container_summary and "Containerfile" in container_summary and "Docker Compose" in container_summary and "Dev Container" in container_summary and "docker compose config" in container_summary, container_summary
    if shutil.which("fzf"):
        picked_script = subprocess.run([*TOOL, "--root", FIXTURE, "--fzf", "build-all"], text=True, capture_output=True, check=True).stdout.strip()
        assert picked_script == "scripts/build-all.sh:1", picked_script
        picked_bin = subprocess.run([*TOOL, "--root", FIXTURE, "--fzf", "project-check"], text=True, capture_output=True, check=True).stdout.strip()
        assert picked_bin == "bin/project-check.sh:1", picked_bin
        picked_tool = subprocess.run([*TOOL, "--root", FIXTURE, "--fzf", "project-report"], text=True, capture_output=True, check=True).stdout.strip()
        assert picked_tool == "tools/project-report.sh:1", picked_tool
    summary = subprocess.run([*TOOL, "--root", FIXTURE], text=True, capture_output=True, check=True).stdout
    assert "## sample-project" in summary and "\n\ndocs" in summary and "\n\ncommands" in summary, summary
    for expected in ("sample-project", "README.md", "docs/development.md", "Node.js (package.json)", "Just (justfile)", "npm run test", "make check", "just build", "launch-config list", "./scripts/build-all.sh", "sh scripts/generate.sh", "git hooks: .githooks", "git submodules: .gitmodules", "editor/IDE files: .idea, .vscode", "CI: .github/workflows", "local environment files: .env", "binary/artifact files: artifacts/demo.apk", "packages/web [Node.js]", "libs/engine [Rust/Cargo]", "services/api [Python requirements]", "native [CMake]"):
        assert expected in summary, summary
    grep = subprocess.run([*TOOL, "--root", FIXTURE, "--grep", "install"], text=True, capture_output=True, check=True).stdout
    assert "README.md:3: ## Install" in grep, grep
    viewed = subprocess.run([*TOOL, "--root", FIXTURE, "--view"], text=True, capture_output=True, check=True).stdout
    assert "# Sample Project" in viewed, viewed
    environment = os.environ | {"PATH": f"{FIXTURE}/fake-bin:{os.environ['PATH']}"}
    rendered = subprocess.run([*TOOL, "--root", FIXTURE, "--view", "README.md"], text=True, capture_output=True, check=True, env=environment).stdout
    assert "glow-rendered:" in rendered and "README.md" in rendered, rendered
    ci = subprocess.run([*TOOL, "--root", FIXTURE, "--ci"], text=True, capture_output=True, check=True).stdout
    assert "check.yml:1  Check · triggers=pull_request,push · jobs=test,build" in ci, ci
    component_output = subprocess.run([*TOOL, "--root", FIXTURE, "--components"], text=True, capture_output=True, check=True).stdout
    assert "libs/engine [Rust/Cargo]  libs/engine/Cargo.toml:1" in component_output, component_output
    offline_security = subprocess.run([*TOOL, "--root", FIXTURE, "--security", "--offline", "--all"], text=True, capture_output=True, check=True).stdout
    assert "3 unique locked package versions" in offline_security and "fastapi@0.100.0" in offline_security, offline_security
    decorated = subprocess.run([*TOOL, "--root", FIXTURE, "--color", "always", "--icons"], text=True, capture_output=True, check=True).stdout
    assert "\x1b[" in decorated and "📖 docs" in decorated, decorated
    print("project-brief test passed")


if __name__ == "__main__":
    main()
