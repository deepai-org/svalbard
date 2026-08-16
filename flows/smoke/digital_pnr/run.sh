#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
source_dir="$repo_root/flows/smoke/digital_pnr"
scratch_root="${SVALBARD_SCRATCH:-$repo_root/scratch}"
image_ref="svalbard/librelane-gf180-canary:2026.08"
expected_image_id="sha256:9253a51f5fdcc7202a164aa26274b4b95533ecdedeb7eb47d6605f5881bfef17"
minimum_free_kib=$((100 * 1024 * 1024))

free_kib() { df -Pk "$1" | awk 'NR == 2 { print $4 }'; }

for command_name in docker flock timeout mktemp awk df date; do
  command -v "$command_name" >/dev/null 2>&1 || {
    printf 'digital-pnr-smoke: required host command is missing: %s\n' "$command_name" >&2
    exit 2
  }
done
docker_root="$(docker info --format '{{.DockerRootDir}}')"
for path in "$repo_root" "$docker_root"; do
  if (( $(free_kib "$path") < minimum_free_kib )); then
    printf 'digital-pnr-smoke: refusing below 100 GiB free at %s\n' "$path" >&2
    exit 2
  fi
done
if (( $(awk '/^MemAvailable:/ { print $2 }' /proc/meminfo) < 8 * 1024 * 1024 )); then
  printf 'digital-pnr-smoke: refusing below 8 GiB available memory\n' >&2
  exit 2
fi

actual_image_id="$(docker image inspect "$image_ref" --format '{{.Id}}')"
actual_architecture="$(docker image inspect "$image_ref" --format '{{.Architecture}}')"
if [[ "$actual_image_id" != "$expected_image_id" || "$actual_architecture" != "arm64" ]]; then
  printf 'digital-pnr-smoke: locked ARM64 image is missing; run make digital-image\n' >&2
  exit 2
fi

mkdir -p "$scratch_root"
run_dir="$(mktemp -d "$scratch_root/digital-pnr-smoke.XXXXXXXX")"
chmod 700 "$run_dir"
completed=0
finish() {
  if (( completed == 1 )); then
    find "$run_dir" -depth -delete
  else
    printf 'digital-pnr-smoke: failed outputs retained at %s\n' "$run_dir" >&2
  fi
}
trap finish EXIT

exec 9>"$scratch_root/heavy-job.lock"
flock -n 9 || { printf 'digital-pnr-smoke: another bounded heavy job holds the lock\n' >&2; exit 2; }

run_start_utc="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
timeout 20m docker run --rm \
  --cpus=2 --memory=4g --memory-swap=4g --pids-limit=512 \
  --network=none --read-only --cap-drop=ALL --security-opt=no-new-privileges \
  --user "$(id -u):$(id -g)" --env HOME=/work/home --env TMPDIR=/work/tmp \
  --env "RUN_START_UTC=$run_start_utc" \
  --mount "type=bind,src=$source_dir,dst=/src,readonly" \
  --mount "type=bind,src=$run_dir,dst=/work" \
  --tmpfs /tmp:size=128m,mode=1777 \
  --entrypoint /bin/sh "$image_ref" /src/container_smoke.sh

cp "$run_dir/result.json" "$scratch_root/digital-pnr-smoke-last.json"
chmod 600 "$scratch_root/digital-pnr-smoke-last.json"
completed=1
printf 'digital-pnr-smoke: PASS\n'
