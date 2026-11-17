#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname -- "${BASH_SOURCE[0]}")"
if [[ ! -f .previous-image ]]; then docker compose down; echo "No previous image recorded; service stopped."; exit 0; fi
previous="$(cat .previous-image)"
docker image inspect "$previous" >/dev/null
docker tag "$previous" daemon-ace-edge:jetson-orin
docker compose up -d
docker compose ps
echo "Previous DAEMON ACE image restored."
