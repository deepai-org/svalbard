#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
source_dir="$repo_root/flows/smoke/inverter"
scratch_root="${SVALBARD_SCRATCH:-$repo_root/scratch}"
image_ref="hpretl/iic-osic-tools@sha256:89641950bbf247c522188629992b6271e391e38372ca0f8e3c850480874948a3"
expected_image_id="sha256:bd7a702bef0b85f5ebf67efca449f270fbeb185380ead204559fcd2457959305"
# This two-CPU smoke test writes only a bounded temporary work directory.  A
# 32-GiB reserve is ample for the image and a failed retained run; callers may
# raise the site policy without modifying the flow.
minimum_free_gib="${SVALBARD_MIN_FREE_GIB:-32}"
[[ "$minimum_free_gib" =~ ^[1-9][0-9]*$ ]] || {
  printf 'smoke: SVALBARD_MIN_FREE_GIB must be a positive integer\n' >&2
  exit 2
}
minimum_free_kib=$((minimum_free_gib * 1024 * 1024))
minimum_available_memory_kib=$((8 * 1024 * 1024))

free_kib() {
  df -Pk "$1" | awk 'NR == 2 { print $4 }'
}

require_headroom() {
  local path=$1
  local label=$2
  local available
  available="$(free_kib "$path")"
  if (( available < minimum_free_kib )); then
    printf 'smoke: insufficient %s space: %s KiB available, %s GiB required\n' \
      "$label" "$available" "$minimum_free_gib" >&2
    exit 2
  fi
}

for command_name in docker flock timeout mktemp awk df; do
  if ! command -v "$command_name" >/dev/null 2>&1; then
    printf 'smoke: required host command is missing: %s\n' "$command_name" >&2
    exit 2
  fi
done

require_headroom "$repo_root" repository
docker_root="$(docker info --format '{{.DockerRootDir}}')"
require_headroom "$docker_root" Docker

available_memory_kib="$(awk '/^MemAvailable:/ { print $2 }' /proc/meminfo)"
if (( available_memory_kib < minimum_available_memory_kib )); then
  printf 'smoke: insufficient available memory: %s KiB available, %s KiB required\n' \
    "$available_memory_kib" "$minimum_available_memory_kib" >&2
  exit 2
fi

actual_image_id="$(docker image inspect "$image_ref" --format '{{.Id}}')"
actual_architecture="$(docker image inspect "$image_ref" --format '{{.Architecture}}')"
if [[ "$actual_image_id" != "$expected_image_id" || "$actual_architecture" != "arm64" ]]; then
  printf 'smoke: pinned ARM64 image is missing or does not match env/images.lock\n' >&2
  exit 2
fi

mkdir -p "$scratch_root"
run_dir="$(mktemp -d "$scratch_root/chain1.XXXXXXXX")"
chmod 700 "$run_dir"
lock_file="$scratch_root/heavy-job.lock"
result_file="$scratch_root/smoke-last.json"
completed=0

finish() {
  if (( completed == 1 )); then
    find "$run_dir" -depth -delete
  else
    printf 'smoke: failed outputs retained at %s\n' "$run_dir" >&2
  fi
}
trap finish EXIT

exec 9>"$lock_file"
if ! flock -n 9; then
  printf 'smoke: another bounded heavy job holds %s\n' "$lock_file" >&2
  exit 2
fi

if ! timeout 10m docker run --rm \
  --cpus=2 \
  --memory=4g \
  --memory-swap=4g \
  --pids-limit=256 \
  --network=none \
  --read-only \
  --cap-drop=ALL \
  --security-opt=no-new-privileges \
  --user "$(id -u):$(id -g)" \
  --env HOME=/tmp \
  --env PDK=gf180mcuD \
  --env PDKPATH=/foss/pdks/gf180mcuD \
  --env STD_CELL_LIBRARY=gf180mcu_fd_sc_mcu7t5v0 \
  --workdir /work \
  --mount "type=bind,src=$source_dir,dst=/src,readonly" \
  --mount "type=bind,src=$run_dir,dst=/work" \
  --tmpfs /tmp:size=256m,mode=1777 \
  --tmpfs /headless/.data-default:size=16m,mode=0700,uid="$(id -u)",gid="$(id -g)" \
  --entrypoint /bin/bash \
  "$image_ref" -lc /src/container_smoke.sh; then
  exit 1
fi

cp "$run_dir/result.json" "$result_file"
chmod 600 "$result_file"
completed=1
printf 'smoke: PASS\n'
printf 'smoke: compact result written to %s\n' "$result_file"
