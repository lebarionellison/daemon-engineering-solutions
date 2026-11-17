#!/usr/bin/env bash
set -euo pipefail
source /opt/ros/jazzy/setup.bash
exec /usr/bin/python3 /opt/daemon-ace-edge/edge_agent.py
