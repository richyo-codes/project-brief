#!/usr/bin/env bash
set -euo pipefail
shopt -s extglob

usage() {
    cat >&2 <<'EOF'
usage: demo-gif.sh PROJECT OUTPUT.gif [PLAYBACK_SPEED] [OPTIONS]

Options:
  --include PARTS  Comma-separated scenes: overview,components,security,ai,ci,authors
  --tape PATH      Keep the VHS tape at PATH (default: OUTPUT.tape)
  -h, --help       Show this help
EOF
}

if [[ ${1:-} == "-h" || ${1:-} == "--help" ]]; then
    usage
    exit 0
fi

if (($# < 2)); then
    usage
    exit 2
fi

project=$1
output=$2
shift 2

playback_speed=1
include="overview,components,security"
tape=""

if (($# > 0)) && [[ $1 != --* ]]; then
    playback_speed=$1
    shift
fi

while (($# > 0)); do
    case $1 in
        --include)
            if (($# < 2)); then
                echo "error: --include needs a comma-separated scene list" >&2
                exit 2
            fi
            include=$2
            shift 2
            ;;
        --tape)
            if (($# < 2)); then
                echo "error: --tape needs a path" >&2
                exit 2
            fi
            tape=$2
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "error: unknown argument: $1" >&2
            usage
            exit 2
            ;;
    esac
done

project=$(CDPATH= cd -- "$project" && pwd)
output_dir=$(dirname -- "$output")
mkdir -p "$output_dir"
output_dir=$(CDPATH= cd -- "$output_dir" && pwd)
output="$output_dir/$(basename -- "$output")"

if [[ -z $tape ]]; then
    tape="${output%.gif}.tape"
elif [[ $tape != /* ]]; then
    tape="$PWD/$tape"
fi

tape_dir=$(dirname -- "$tape")
mkdir -p "$output_dir" "$tape_dir"

if ! command -v vhs >/dev/null 2>&1; then
    echo "error: VHS is required; install it from https://github.com/charmbracelet/vhs" >&2
    exit 1
fi

repo_root=$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
if command -v project-brief >/dev/null 2>&1; then
    project_brief_cmd=project-brief
else
    project_brief_cmd="python3 $repo_root/src/project_brief/cli.py"
fi
printf -v project_arg '%q' "$project"

cat > "$tape" <<EOF
Output "$output"
Set FontSize 24
Set Width 1500
Set Height 850
Set Padding 24
Set PlaybackSpeed $playback_speed
Set TypingSpeed 18ms
EOF

add_scene() {
    local scene=$1
    case $scene in
        overview)
            printf '\nType "%s --root %s --color always --icons"\nSleep 300ms\nEnter\nSleep 2s\n' \
                "$project_brief_cmd" "$project_arg" >> "$tape"
            ;;
        components)
            printf '\nType "%s --root %s --components"\nSleep 300ms\nEnter\nSleep 2s\n' \
                "$project_brief_cmd" "$project_arg" >> "$tape"
            ;;
        security)
            printf '\nType "%s --root %s --security --offline --all"\nSleep 300ms\nEnter\nSleep 3s\n' \
                "$project_brief_cmd" "$project_arg" >> "$tape"
            ;;
        ai)
            printf '\nType "%s --root %s --ai"\nSleep 300ms\nEnter\nSleep 2s\n' \
                "$project_brief_cmd" "$project_arg" >> "$tape"
            ;;
        ci)
            printf '\nType "%s --root %s --ci"\nSleep 300ms\nEnter\nSleep 2s\n' \
                "$project_brief_cmd" "$project_arg" >> "$tape"
            ;;
        authors)
            printf '\nType "%s --root %s --authors"\nSleep 300ms\nEnter\nSleep 2s\n' \
                "$project_brief_cmd" "$project_arg" >> "$tape"
            ;;
        *)
            echo "error: unknown scene: $scene" >&2
            echo "available scenes: overview, components, security, ai, ci, authors" >&2
            exit 2
            ;;
    esac
}

IFS=',' read -r -a scenes <<< "$include"
for scene in "${scenes[@]}"; do
    scene=${scene##+([[:space:]])}
    scene=${scene%%+([[:space:]])}
    add_scene "$scene"
done

vhs "$tape"
echo "wrote $output"
echo "kept tape $tape"
