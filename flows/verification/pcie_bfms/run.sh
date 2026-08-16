#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
runner_dir="$repo_root/flows/verification/pcie_bfms"
scratch_root="${SVALBARD_SCRATCH:-$repo_root/scratch}"
image_ref="docker.io/hpretl/iic-osic-tools@sha256:89641950bbf247c522188629992b6271e391e38372ca0f8e3c850480874948a3"
expected_image_id="sha256:bd7a702bef0b85f5ebf67efca449f270fbeb185380ead204559fcd2457959305"
minimum_free_kib=$((100 * 1024 * 1024))
minimum_available_memory_kib=$((8 * 1024 * 1024))

free_kib() { df -Pk "$1" | awk 'NR == 2 { print $4 }'; }

for command_name in docker flock timeout mktemp awk df; do
  command -v "$command_name" >/dev/null 2>&1 || {
    printf 'bfm-smoke: required host command is missing: %s\n' "$command_name" >&2
    exit 2
  }
done

docker_root="$(docker info --format '{{.DockerRootDir}}')"
for path in "$repo_root" "$docker_root"; do
  available="$(free_kib "$path")"
  if (( available < minimum_free_kib )); then
    printf 'bfm-smoke: refusing below 100 GiB free at %s\n' "$path" >&2
    exit 2
  fi
done
available_memory_kib="$(awk '/^MemAvailable:/ { print $2 }' /proc/meminfo)"
if (( available_memory_kib < minimum_available_memory_kib )); then
  printf 'bfm-smoke: refusing below 8 GiB available memory\n' >&2
  exit 2
fi

python3 "$repo_root/scripts/verification_deps.py" verify >/dev/null
actual_image_id="$(docker image inspect "$image_ref" --format '{{.Id}}')"
actual_architecture="$(docker image inspect "$image_ref" --format '{{.Architecture}}')"
if [[ "$actual_image_id" != "$expected_image_id" || "$actual_architecture" != "arm64" ]]; then
  printf 'bfm-smoke: pinned ARM64 runtime image is missing or mismatched\n' >&2
  exit 2
fi

mkdir -p "$scratch_root"
run_dir="$(mktemp -d "$scratch_root/bfm-smoke.XXXXXXXX")"
chmod 700 "$run_dir"
result_file="$scratch_root/bfm-smoke-last.json"
completed=0
finish() {
  if (( completed == 1 )); then
    find "$run_dir" -depth -delete
  else
    printf 'bfm-smoke: failed outputs retained at %s\n' "$run_dir" >&2
  fi
}
trap finish EXIT

exec 9>"$scratch_root/heavy-job.lock"
flock -n 9 || { printf 'bfm-smoke: another bounded heavy job holds the lock\n' >&2; exit 2; }

python3 "$repo_root/scripts/verification_deps.py" materialize "$run_dir/src" >/dev/null
mv "$run_dir/src/cosim.vproc" "$run_dir/src/vproc"
chmod -R u+rwX "$run_dir"

timeout 10m docker run --rm \
  --cpus=2 --memory=3g --memory-swap=3g --pids-limit=256 \
  --network=none --read-only --cap-drop=ALL --security-opt=no-new-privileges \
  --user "$(id -u):$(id -g)" --env HOME=/tmp \
  --mount "type=bind,src=$runner_dir,dst=/runner,readonly" \
  --mount "type=bind,src=$run_dir,dst=/work" \
  --tmpfs /tmp:size=256m,mode=1777 \
  --tmpfs /headless/.data-default:size=16m,mode=0700,uid="$(id -u)",gid="$(id -g)" \
  --entrypoint /bin/bash "$image_ref" -lc /runner/container_smoke.sh

cp "$run_dir/result.json" "$result_file"
chmod 600 "$result_file"
completed=1
printf 'bfm-smoke: PASS\n'
printf 'bfm-smoke: compact result written to %s\n' "$result_file"
