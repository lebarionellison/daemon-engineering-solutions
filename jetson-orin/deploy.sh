#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname -- "${BASH_SOURCE[0]}")"
[[ "$(uname -m)" == "aarch64" ]] || { echo "Deploy on a Jetson ARM64 device only." >&2; exit 2; }
[[ -f /etc/nv_tegra_release ]] || { echo "NVIDIA Jetson Linux marker not found." >&2; exit 2; }
docker info --format '{{json .Runtimes}}' | grep -q '"nvidia"' || { echo "NVIDIA Container Runtime is not registered." >&2; exit 2; }
docker compose version >/dev/null 2>&1 || { echo "Docker Compose v2 is required." >&2; exit 2; }
[[ -f daemon-ace-edge-image.tar ]] || { echo "Image archive missing." >&2; exit 2; }
if docker image inspect daemon-ace-edge:jetson-orin >/dev/null 2>&1; then
 docker tag daemon-ace-edge:jetson-orin daemon-ace-edge:jetson-orin-previous
 echo daemon-ace-edge:jetson-orin-previous > .previous-image
fi
docker load -i daemon-ace-edge-image.tar
docker compose up -d
docker compose ps
echo "Installed. Verify /daemon_ace/edge/heartbeat from an authorized ROS 2 node."
