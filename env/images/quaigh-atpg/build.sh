#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
context="$repo_root/env/images/quaigh-atpg"
scratch_root="${SVALBARD_SCRATCH:-$repo_root/scratch}"
builder="svalbard-quaigh-bounded"
image_ref="svalbard/quaigh-atpg:0.0.6"
expected_image_id="sha256:871e098d7879729b5130d790cfa29e87d26c7eafc0156612354020bc11f6b381"
buildkit_image="docker.io/moby/buildkit@sha256:5a8cd84cb3fcfd082789a08f92bd36f8e745c6231edd78e24a3bf34fd471a823"
minimum_free_kib=$((100 * 1024 * 1024))

free_kib() { df -Pk "$1" | awk 'NR == 2 { print $4 }'; }

for command_name in docker timeout flock mktemp awk df; do
  command -v "$command_name" >/dev/null 2>&1 || {
    printf 'quaigh-image: required command is missing: %s\n' "$command_name" >&2
    exit 2
  }
done

docker_root="$(docker info --format '{{.DockerRootDir}}')"
for path in "$repo_root" "$docker_root"; do
  if (( $(free_kib "$path") < minimum_free_kib )); then
    printf 'quaigh-image: refusing below 100 GiB free at %s\n' "$path" >&2
    exit 2
  fi
done
if (( $(awk '/^MemAvailable:/ { print $2 }' /proc/meminfo) < 8 * 1024 * 1024 )); then
  printf 'quaigh-image: refusing below 8 GiB available memory\n' >&2
  exit 2
fi

if docker image inspect "$image_ref" >/dev/null 2>&1; then
  actual_image_id="$(docker image inspect "$image_ref" --format '{{.Id}}')"
  actual_architecture="$(docker image inspect "$image_ref" --format '{{.Architecture}}')"
  actual_version="$(timeout 30s docker run --rm \
    --cpus=1 --memory=256m --memory-swap=256m --pids-limit=64 \
    --network=none --read-only --cap-drop=ALL --security-opt=no-new-privileges \
    "$image_ref" --version)"
  if [[ "$actual_image_id" != "$expected_image_id" || \
        "$actual_architecture" != "arm64" || "$actual_version" != "quaigh 0.0.6" ]]; then
    printf 'quaigh-image: existing tag is not the locked ARM64 image\n' >&2
    exit 2
  fi
  printf 'quaigh-image: PASS (locked image already exists)\n'
  exit 0
fi

if docker buildx inspect "$builder" >/dev/null 2>&1; then
  printf 'quaigh-image: refusing to reuse pre-existing builder %s\n' "$builder" >&2
  exit 2
fi

mkdir -p "$scratch_root"
output_dir="$(mktemp -d "$scratch_root/quaigh-image.XXXXXXXX")"
output_tar="$output_dir/image.tar"
cleanup() {
  docker buildx rm "$builder" >/dev/null 2>&1 || true
  find "$output_dir" -depth -delete
}
trap cleanup EXIT

exec 9>"$scratch_root/heavy-job.lock"
flock -n 9 || { printf 'quaigh-image: another bounded heavy job holds the lock\n' >&2; exit 2; }

timeout 5m docker buildx create \
  --name "$builder" \
  --driver docker-container \
  --platform linux/arm64 \
  --driver-opt "image=$buildkit_image,memory=4g,memory-swap=4g,cpu-period=100000,cpu-quota=200000,network=bridge,restart-policy=no" \
  --bootstrap

timeout 20m docker buildx build \
  --builder "$builder" \
  --platform linux/arm64 \
  --build-arg SOURCE_DATE_EPOCH=1718807854 \
  --provenance=false \
  --sbom=false \
  --progress=plain \
  --tag "$image_ref" \
  --output "type=docker,dest=$output_tar,rewrite-timestamp=true" \
  "$context"
docker load --input "$output_tar"

actual_image_id="$(docker image inspect "$image_ref" --format '{{.Id}}')"
actual_architecture="$(docker image inspect "$image_ref" --format '{{.Architecture}}')"
if [[ "$actual_image_id" != "$expected_image_id" || "$actual_architecture" != "arm64" ]]; then
  printf 'quaigh-image: built image identity mismatch: %s %s\n' \
    "$actual_image_id" "$actual_architecture" >&2
  exit 2
fi
printf 'quaigh-image: PASS (%s)\n' "$actual_image_id"
