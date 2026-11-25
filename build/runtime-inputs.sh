#!/usr/bin/env bash
# Fingerprint the repository files consumed by the runtime Dockerfile.
# Pass a Git revision to fingerprint that tree instead of the working copy.
set -euo pipefail
inputs=(Dockerfile entrypoint.sh .dockerignore)
for path in "${inputs[@]}"; do
  if [[ $# -eq 0 ]]; then
    git hash-object --no-filters "$path"
  else
    git rev-parse --verify "$1:$path"
  fi
done | git hash-object --stdin
