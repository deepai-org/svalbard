#!/usr/bin/env bash
# Shared bounded host harness for reproducible GF180 analog flows.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
image_ref="docker.io/hpretl/iic-osic-tools@sha256:89641950bbf247c522188629992b6271e391e38372ca0f8e3c850480874948a3"
expected_image_id="sha256:bd7a702bef0b85f5ebf67efca449f270fbeb185380ead204559fcd2457959305"
minimum_free_kib=$((100 * 1024 * 1024))
minimum_available_memory_kib=$((8 * 1024 * 1024))

label=""
source_rel=""
flow_timeout=""
cpus=""
memory=""
container_command="/src/container_flow.sh"
declare -a copies=()

usage() {
  printf 'usage: %s --label NAME --source-rel PATH --timeout DURATION --cpus N --memory SIZE [--command PATH] --copy RUN_FILE:SCRATCH_FILE ...\n' "$0" >&2
  exit 2
}

while (( $# )); do
  case "$1" in
    --label) label="${2-}"; shift 2 ;;
    --source-rel) source_rel="${2-}"; shift 2 ;;
    --timeout) flow_timeout="${2-}"; shift 2 ;;
    --cpus) cpus="${2-}"; shift 2 ;;
    --memory) memory="${2-}"; shift 2 ;;
    --command) container_command="${2-}"; shift 2 ;;
    --copy) copies+=("${2-}"); shift 2 ;;
    *) usage ;;
  esac
done

[[ -n "$label" && -n "$source_rel" && -n "$flow_timeout" &&
   "$cpus" =~ ^[1-4]$ && "$memory" =~ ^[1-8]g$ && ${#copies[@]} -gt 0 ]] || usage
[[ "$label" =~ ^[a-z0-9][a-z0-9-]*$ && "$flow_timeout" =~ ^[1-9][0-9]*[smh]$ ]] || usage
[[ "$source_rel" != /* && "$source_rel" != *..* ]] || usage
[[ "$container_command" == /src/* ]] || usage
for mapping in "${copies[@]}"; do
  run_file="${mapping%%:*}"
  scratch_file="${mapping#*:}"
  [[ "$mapping" == *:* && -n "$run_file" && -n "$scratch_file" &&
     "$run_file" != /* && "$run_file" != *..* &&
     "$scratch_file" != /* && "$scratch_file" != *..* ]] || usage
done

source_dir="$repo_root/$source_rel"
scratch_root="${SVALBARD_SCRATCH:-$repo_root/scratch}"
[[ -d "$source_dir" ]] || { printf '%s: source directory missing: %s\n' "$label" "$source_dir" >&2; exit 2; }
container_script="$source_dir/${container_command#/src/}"
[[ -f "$container_script" ]] || {
  printf '%s: container command missing from source mount: %s\n' "$label" "$container_command" >&2
  exit 2
}

free_kib() { df -Pk "$1" | awk 'NR == 2 { print $4 }'; }
for command_name in docker flock timeout mktemp awk df; do
  command -v "$command_name" >/dev/null 2>&1 || {
    printf '%s: missing host command: %s\n' "$label" "$command_name" >&2
    exit 2
  }
done
for checked_path in "$repo_root" "$(docker info --format '{{.DockerRootDir}}')"; do
  (( $(free_kib "$checked_path") >= minimum_free_kib )) || {
    printf '%s: less than 100 GiB free at %s\n' "$label" "$checked_path" >&2
    exit 2
  }
done
available_memory_kib="$(awk '/^MemAvailable:/ { print $2 }' /proc/meminfo)"
(( available_memory_kib >= minimum_available_memory_kib )) || {
  printf '%s: less than 8 GiB available memory\n' "$label" >&2
  exit 2
}

actual_image_id="$(docker image inspect "$image_ref" --format '{{.Id}}')"
actual_architecture="$(docker image inspect "$image_ref" --format '{{.Architecture}}')"
[[ "$actual_image_id" == "$expected_image_id" && "$actual_architecture" == "arm64" ]] || {
  printf '%s: pinned ARM64 analog image is missing or mismatched\n' "$label" >&2
  exit 2
}
if [[ "${ANALOG_FLOW_CHECK_ONLY:-0}" == "1" ]]; then
  printf '%s: preflight PASS (%s, %s CPU, %s RAM, timeout %s)\n' \
    "$label" "$container_command" "$cpus" "$memory" "$flow_timeout"
  exit 0
fi

mkdir -p "$scratch_root"
run_dir="$(mktemp -d "$scratch_root/$label.XXXXXXXX")"
chmod 700 "$run_dir"
completed=0
finish() {
  if (( completed == 1 )); then
    find "$run_dir" -depth -delete
  else
    printf '%s: failed outputs retained at %s\n' "$label" "$run_dir" >&2
  fi
}
trap finish EXIT

exec 9>"$scratch_root/heavy-job.lock"
flock -n 9 || { printf '%s: another bounded heavy job is running\n' "$label" >&2; exit 2; }

timeout --kill-after=30s "$flow_timeout" docker run --rm --platform linux/arm64 \
  --cpus="$cpus" --memory="$memory" --memory-swap="$memory" --pids-limit=256 \
  --network=none --read-only --cap-drop=ALL --security-opt=no-new-privileges \
  --user "$(id -u):$(id -g)" --env HOME=/tmp --env PDK=gf180mcuD \
  --env PDKPATH=/foss/pdks/gf180mcuD --workdir /work \
  --mount "type=bind,src=$source_dir,dst=/src,readonly" \
  --mount "type=bind,src=$run_dir,dst=/work" \
  --tmpfs /tmp:size=256m,mode=1777 \
  --tmpfs /headless/.data-default:size=16m,mode=0700,uid="$(id -u)",gid="$(id -g)" \
  --entrypoint /bin/bash "$image_ref" -lc "$container_command"

for mapping in "${copies[@]}"; do
  run_file="${mapping%%:*}"
  scratch_file="${mapping#*:}"
  [[ -f "$run_dir/$run_file" ]] || {
    printf '%s: expected output missing: %s\n' "$label" "$run_file" >&2
    exit 2
  }
  cp "$run_dir/$run_file" "$scratch_root/$scratch_file"
  chmod 600 "$scratch_root/$scratch_file"
done

completed=1
printf '%s: PASS\n' "$label"
for mapping in "${copies[@]}"; do
  printf '%s: output %s\n' "$label" "$scratch_root/${mapping#*:}"
done
