#!/bin/sh
# Builds the worker image for the GPU machine from this repository (see README, "GPU worker").
# A plain `docker build` rather than compose's `build:`, because newer Compose refuses a Dockerfile
# (worker/Dockerfile) that sits outside the build context (backend/).
#
#   ./build-gpu-worker.sh [env file]        # default: .env.gpu-worker; reads TORCH_INDEX and TAG
set -eu
cd "$(dirname "$0")"
env_file="${1:-.env.gpu-worker}"
pick() { [ -f "$env_file" ] && sed -n "s/^$1=//p" "$env_file" | tail -n 1 || true; }
torch_index="$(pick TORCH_INDEX)"
tag="$(pick TAG)"
echo "Building allotment-worker-gpu:${tag:-local} with PyTorch '${torch_index:-cpu}' (this takes a while)"
exec docker build -f ../worker/Dockerfile \
  --build-arg "TORCH_INDEX=${torch_index:-cpu}" \
  -t "allotment-worker-gpu:${tag:-local}" ../backend
