#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
context="$repo_root/env/images/librelane-gf180-canary"
builder="svalbard-bounded"
image_ref="svalbard/librelane-gf180-canary:2026.08"
expected_image_id="sha256:9253a51f5fdcc7202a164aa26274b4b95533ecdedeb7eb47d6605f5881bfef17"
buildkit_image="docker.io/moby/buildkit@sha256:5a8cd84cb3fcfd082789a08f92bd36f8e745c6231edd78e24a3bf34fd471a823"
minimum_free_kib=$((100 * 1024 * 1024))

free_kib() { df -Pk "$1" | awk 'NR == 2 { print $4 }'; }

for command_name in docker timeout awk df; do
  command -v "$command_name" >/dev/null 2>&1 || {
    printf 'digital-image: required command is missing: %s\n' "$command_name" >&2
    exit 2
  }
done

if docker image inspect "$image_ref" >/dev/null 2>&1; then
  actual_image_id="$(docker image inspect "$image_ref" --format '{{.Id}}')"
  actual_architecture="$(docker image inspect "$image_ref" --format '{{.Architecture}}')"
  if [[ "$actual_image_id" != "$expected_image_id" || "$actual_architecture" != "arm64" ]]; then
    printf 'digital-image: existing tag is not the locked ARM64 image\n' >&2
    exit 2
  fi
  printf 'digital-image: PASS (locked image already exists)\n'
  exit 0
fi

docker_root="$(docker info --format '{{.DockerRootDir}}')"
for path in "$repo_root" "$docker_root"; do
  if (( $(free_kib "$path") < minimum_free_kib )); then
    printf 'digital-image: refusing below 100 GiB free at %s\n' "$path" >&2
    exit 2
  fi
done
if docker buildx inspect "$builder" >/dev/null 2>&1; then
  printf 'digital-image: refusing to reuse pre-existing builder %s\n' "$builder" >&2
  exit 2
fi

cleanup_builder() {
  docker buildx rm "$builder" >/dev/null 2>&1 || true
}
trap cleanup_builder EXIT

timeout 5m docker buildx create \
  --name "$builder" \
  --driver docker-container \
  --platform linux/arm64 \
  --driver-opt "image=$buildkit_image,memory=4g,memory-swap=4g,cpu-period=100000,cpu-quota=200000,network=bridge,restart-policy=no" \
  --bootstrap

timeout 20m docker buildx build \
  --builder "$builder" \
  --platform linux/arm64 \
  --network=none \
  --load \
  --provenance=false \
  --sbom=false \
  --progress=plain \
  --tag "$image_ref" \
  "$context"

actual_image_id="$(docker image inspect "$image_ref" --format '{{.Id}}')"
actual_architecture="$(docker image inspect "$image_ref" --format '{{.Architecture}}')"
if [[ "$actual_image_id" != "$expected_image_id" || "$actual_architecture" != "arm64" ]]; then
  printf 'digital-image: built image identity mismatch: %s %s\n' \
    "$actual_image_id" "$actual_architecture" >&2
  exit 2
fi
printf 'digital-image: PASS (%s)\n' "$actual_image_id"
