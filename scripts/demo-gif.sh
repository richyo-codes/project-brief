#!/usr/bin/env bash
set -euo pipefail

usage() {
    echo "usage: $0 PROJECT OUTPUT.gif" >&2
    echo "       $0 PROJECT OUTPUT.gif [PLAYBACK_SPEED]" >&2
}

if [[ $# -lt 2 || $# -gt 3 ]]; then
    usage
    exit 2
fi

project=$(CDPATH= cd -- "$1" && pwd)
output=$(CDPATH= cd -- "$(dirname -- "$2")" && pwd)/$(basename -- "$2")
playback_speed=${3:-1}
if [[ ! -d $project ]]; then
    echo "demo-gif: project directory not found: $project" >&2
    exit 2
fi
if ! command -v vhs >/dev/null 2>&1; then
    echo "demo-gif: VHS is required; see https://github.com/charmbracelet/vhs#installation" >&2
    exit 2
fi

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
repo_root=$(CDPATH= cd -- "$script_dir/.." && pwd)
if command -v project-brief >/dev/null 2>&1; then
    project_brief=project-brief
else
    project_brief="python3 $repo_root/src/project_brief/cli.py"
fi

mkdir -p "$(dirname -- "$output")"
work_dir=$(mktemp -d "${TMPDIR:-/tmp}/project-brief-demo.XXXXXX")
trap 'rm -rf "$work_dir"' EXIT
tape="$work_dir/demo.tape"

cat > "$tape" <<EOF
Output "$output"
Set FontSize 24
Set Width 1500
Set Height 850
Set Padding 24
Set PlaybackSpeed $playback_speed
Set TypingSpeed 18ms

Type "$project_brief --root '$project' --color always --icons"
Sleep 300ms
Enter
Sleep 2s

Type "$project_brief --root '$project' --components"
Sleep 300ms
Enter
Sleep 2s

Type "$project_brief --root '$project' --security --offline --all"
Sleep 300ms
Enter
Sleep 3s
EOF

vhs "$tape"
echo "wrote $output"
