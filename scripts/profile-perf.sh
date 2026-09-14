#!/usr/bin/env bash
set -euo pipefail

usage() {
    echo "usage: $0 OUTPUT.svg [OPTIONS] -- [PROJECT_BRIEF_ARGS ...]" >&2
    echo "       $0 OUTPUT.svg --root /path/to/project --all" >&2
    echo "options:" >&2
    echo "  --flamegraph-dir DIR  directory containing FlameGraph Perl scripts" >&2
    echo "  --perf PATH           perf executable (default: PATH lookup)" >&2
    echo "  --python PATH         Python executable (default: python3)" >&2
}

if (($# < 1)) || [[ $1 == "-h" || $1 == "--help" ]]; then
    usage
    exit $(( $# == 0 ? 2 : 0 ))
fi

output=$1
shift
output_dir=$(dirname -- "$output")
mkdir -p "$output_dir"

flamegraph_dir="${PROJECT_BRIEF_FLAMEGRAPH_DIR:-}"
perf_command="${PROJECT_BRIEF_PERF:-}"
python_command="${PROJECT_BRIEF_PYTHON:-python3}"
project_args=()
while (($# > 0)); do
    case $1 in
        --)
            shift
            project_args+=("$@")
            break
            ;;
        --flamegraph-dir)
            if (($# < 2)); then
                echo "profile-perf: --flamegraph-dir needs a path" >&2
                exit 2
            fi
            flamegraph_dir=$2
            shift 2
            ;;
        --perf)
            if (($# < 2)); then
                echo "profile-perf: --perf needs a path" >&2
                exit 2
            fi
            perf_command=$2
            shift 2
            ;;
        --python)
            if (($# < 2)); then
                echo "profile-perf: --python needs a path" >&2
                exit 2
            fi
            python_command=$2
            shift 2
            ;;
        *)
            project_args+=("$1")
            shift
            ;;
    esac
done

if [[ -n $flamegraph_dir ]]; then
    stackcollapse_command="$flamegraph_dir/stackcollapse-perf.pl"
    flamegraph_command="$flamegraph_dir/flamegraph.pl"
else
    stackcollapse_command=$(command -v stackcollapse-perf.pl || true)
    flamegraph_command=$(command -v flamegraph.pl || true)
fi
if [[ -z $perf_command ]]; then
    perf_command=$(command -v perf || true)
fi
for dependency in "$perf_command" "$stackcollapse_command" "$flamegraph_command"; do
    if [[ -z $dependency || ! -x $dependency ]]; then
        echo "profile-perf: required executable not found: ${dependency:-perf/FlameGraph dependency}" >&2
        echo "set --flamegraph-dir, --perf, or the corresponding PROJECT_BRIEF_* environment variable" >&2
        exit 1
    fi
done

repo_root=$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
profile_dir=$(mktemp -d "${TMPDIR:-/tmp}/project-brief-perf.XXXXXX")
trap 'rm -rf "$profile_dir"' EXIT

if ((${#project_args[@]} == 0)); then
    project_args=(--root "$PWD")
fi

echo "recording perf samples..." >&2
"$perf_command" record -F 99 -g --call-graph dwarf -o "$profile_dir/perf.data" \
    "$python_command" "$repo_root/src/project_brief/cli.py" "${project_args[@]}"
echo "writing flamegraph..." >&2
"$perf_command" script -i "$profile_dir/perf.data" \
    | "$stackcollapse_command" \
    | "$flamegraph_command" --title="project-brief perf profile" > "$output"
echo "wrote $output"
