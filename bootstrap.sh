#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
minimum_free_gib=100

free_gib() {
  df -Pk "$1" | awk 'NR == 2 { print int($4 / 1024 / 1024) }'
}

doctor() {
  local failed=0
  local architecture
  architecture="$(uname -m)"
  printf 'repository: %s\n' "$repo_root"
  printf 'architecture: %s\n' "$architecture"
  if [[ "$architecture" != "aarch64" ]]; then
    printf 'WARN: plan baseline is aarch64; observed %s\n' "$architecture"
  fi

  for command_name in git python3 make docker timeout flock; do
    if command -v "$command_name" >/dev/null 2>&1; then
      printf 'tool %-8s OK\n' "$command_name"
    else
      printf 'tool %-8s MISSING\n' "$command_name"
      failed=1
    fi
  done

  local repo_free
  repo_free="$(free_gib "$repo_root")"
  printf 'repository filesystem free: %s GiB (heavy-job floor: %s GiB)\n' "$repo_free" "$minimum_free_gib"
  if (( repo_free < minimum_free_gib )); then
    printf 'FAIL: insufficient free space for a heavy job\n' >&2
    failed=1
  fi

  if docker info --format '{{.DockerRootDir}}' >/tmp/svalbard-docker-root.$$ 2>/dev/null; then
    local docker_root docker_free
    docker_root="$(< /tmp/svalbard-docker-root.$$)"
    rm -f "/tmp/svalbard-docker-root.$$"
    docker_free="$(free_gib "$docker_root")"
    printf 'docker filesystem free: %s GiB at %s\n' "$docker_free" "$docker_root"
    if (( docker_free < minimum_free_gib )); then
      printf 'FAIL: insufficient Docker storage for a heavy job\n' >&2
      failed=1
    fi
  else
    rm -f "/tmp/svalbard-docker-root.$$"
    printf 'FAIL: Docker daemon is unavailable\n' >&2
    failed=1
  fi

  return "$failed"
}

scratch_report() {
  local scratch_path="${SVALBARD_SCRATCH:-$repo_root/scratch}"
  printf 'scratch path: %s\n' "$scratch_path"
  if [[ -e "$scratch_path" ]]; then
    du -sh "$scratch_path"
    df -h "$scratch_path"
  else
    printf 'scratch path does not exist; no space is allocated\n'
    df -h "$repo_root"
  fi
}

pull() {
  local project=""
  if [[ "${1:-}" == "--project" ]]; then
    if [[ $# -ne 2 ]]; then
      printf 'usage: %s pull [--project pcie_gen1_endpoint]\n' "$0" >&2
      return 64
    fi
    project=$2
    if [[ "$project" != "pcie_gen1_endpoint" ]]; then
      printf 'pull: project is not instantiated in this repository slice: %s\n' "$project" >&2
      return 64
    fi
  elif [[ $# -ne 0 ]]; then
    printf 'usage: %s pull [--project pcie_gen1_endpoint]\n' "$0" >&2
    return 64
  fi

  local docker_root repo_free docker_free image_ref architecture pull_list
  repo_free="$(free_gib "$repo_root")"
  docker_root="$(docker info --format '{{.DockerRootDir}}')"
  docker_free="$(free_gib "$docker_root")"
  if (( repo_free < minimum_free_gib || docker_free < minimum_free_gib )); then
    printf 'pull: refusing below the %s GiB free-space floor (repo=%s GiB, docker=%s GiB)\n' \
      "$minimum_free_gib" "$repo_free" "$docker_free" >&2
    return 2
  fi

  mkdir -p "$repo_root/scratch"
  exec 9>"$repo_root/scratch/image-pull.lock"
  if ! flock -n 9; then
    printf 'pull: another image pull holds the repository lock\n' >&2
    return 2
  fi

  if ! pull_list="$(python3 "$repo_root/scripts/image_lock.py" pull-list)"; then
    printf 'pull: image lock validation failed\n' >&2
    return 2
  fi
  if [[ -z "$pull_list" ]]; then
    printf 'pull: image lock resolved no images\n' >&2
    return 2
  fi
  mapfile -t image_refs <<<"$pull_list"
  for image_ref in "${image_refs[@]}"; do
    docker_free="$(free_gib "$docker_root")"
    if (( docker_free < minimum_free_gib )); then
      printf 'pull: refusing %s below the %s GiB Docker free-space floor\n' \
        "$image_ref" "$minimum_free_gib" >&2
      return 2
    fi
    printf 'pull: %s\n' "$image_ref"
    timeout 20m docker pull "$image_ref"
    architecture="$(docker image inspect "$image_ref" --format '{{.Architecture}}')"
    if [[ "$architecture" != "arm64" ]]; then
      printf 'pull: %s resolved to unexpected architecture %s\n' "$image_ref" "$architecture" >&2
      return 2
    fi
  done
  printf 'pull: PASS (%s digest-pinned ARM64 images)\n' "${#image_refs[@]}"
}

case "${1:-doctor}" in
  doctor) doctor ;;
  scratch-report) scratch_report ;;
  pull) shift; pull "$@" ;;
  *) printf 'usage: %s {doctor|scratch-report|pull}\n' "$0" >&2; exit 64 ;;
esac
