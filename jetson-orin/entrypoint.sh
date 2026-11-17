#!/usr/bin/env bash
set -euo pipefail
source /opt/ros/jazzy/setup.bash
exec python3 /opt/daemon_ace/edge_agent.py
