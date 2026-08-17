#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)"
source_dir="$repo_root/ip/blocks/analog/wireline_serdes/phase_interpolator"
scratch_root="${SVALBARD_SCRATCH:-$repo_root/scratch}"
image_ref="docker.io/hpretl/iic-osic-tools@sha256:89641950bbf247c522188629992b6271e391e38372ca0f8e3c850480874948a3"
expected_image_id="sha256:bd7a702bef0b85f5ebf67efca449f270fbeb185380ead204559fcd2457959305"
minimum_free_kib=$((100 * 1024 * 1024))
minimum_available_memory_kib=$((8 * 1024 * 1024))

free_kib() { df -Pk "$1" | awk 'NR == 2 { print $4 }'; }
for command_name in docker flock timeout mktemp awk df; do
  command -v "$command_name" >/dev/null 2>&1 || { printf 'phase-interpolator: missing host command: %s\n' "$command_name" >&2; exit 2; }
done
for checked_path in "$repo_root" "$(docker info --format '{{.DockerRootDir}}')"; do
  (( $(free_kib "$checked_path") >= minimum_free_kib )) || { printf 'phase-interpolator: less than 100 GiB free at %s\n' "$checked_path" >&2; exit 2; }
done
available_memory_kib="$(awk '/^MemAvailable:/ { print $2 }' /proc/meminfo)"
(( available_memory_kib >= minimum_available_memory_kib )) || { printf 'phase-interpolator: less than 8 GiB available memory\n' >&2; exit 2; }
actual_image_id="$(docker image inspect "$image_ref" --format '{{.Id}}')"
actual_architecture="$(docker image inspect "$image_ref" --format '{{.Architecture}}')"
[[ "$actual_image_id" == "$expected_image_id" && "$actual_architecture" == "arm64" ]] || { printf 'phase-interpolator: pinned ARM64 analog image is missing or mismatched\n' >&2; exit 2; }

mkdir -p "$scratch_root"
run_dir="$(mktemp -d "$scratch_root/phase-interpolator.XXXXXXXX")"
chmod 700 "$run_dir"
completed=0
finish() {
  if (( completed == 1 )); then find "$run_dir" -depth -delete; else printf 'phase-interpolator: failed outputs retained at %s\n' "$run_dir" >&2; fi
}
trap finish EXIT
exec 9>"$scratch_root/heavy-job.lock"
flock -n 9 || { printf 'phase-interpolator: another bounded heavy job is running\n' >&2; exit 2; }

timeout --kill-after=30s 180m docker run --rm --cpus=2 --memory=4g --memory-swap=4g --pids-limit=256 \
  --network=none --read-only --cap-drop=ALL --security-opt=no-new-privileges \
  --user "$(id -u):$(id -g)" --env HOME=/tmp --env PDK=gf180mcuD \
  --env PDKPATH=/foss/pdks/gf180mcuD --workdir /work \
  --mount "type=bind,src=$source_dir,dst=/src,readonly" \
  --mount "type=bind,src=$run_dir,dst=/work" \
  --tmpfs /tmp:size=256m,mode=1777 \
  --tmpfs /headless/.data-default:size=16m,mode=0700,uid="$(id -u)",gid="$(id -g)" \
  --entrypoint /bin/bash "$image_ref" -lc /src/container_flow.sh

cp "$run_dir/result.json" "$scratch_root/phase-interpolator-last.json"
cp "$run_dir/phase_interpolator-layout.png" "$scratch_root/phase-interpolator-layout-last.png"
chmod 600 "$scratch_root/phase-interpolator-last.json" "$scratch_root/phase-interpolator-layout-last.png"
completed=1
printf 'phase-interpolator: PASS\nphase-interpolator: result %s\nphase-interpolator: render %s\n' \
  "$scratch_root/phase-interpolator-last.json" "$scratch_root/phase-interpolator-layout-last.png"
