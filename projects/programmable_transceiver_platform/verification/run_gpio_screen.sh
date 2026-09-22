#!/usr/bin/env bash
set -euo pipefail
repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)
timeout 60 docker run --rm --network none --read-only --user "$(id -u):$(id -g)" \
  --cap-drop ALL --security-opt no-new-privileges --cpus 2 --memory 1g --pids-limit 128 \
  --mount "type=bind,src=$repo_root,dst=/work,readonly" --entrypoint python3 \
  sha256:9253a51f5fdcc7202a164aa26274b4b95533ecdedeb7eb47d6605f5881bfef17 \
  /work/projects/programmable_transceiver_platform/verification/screen_gpio_liberty.py
