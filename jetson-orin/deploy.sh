#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname -- "${BASH_SOURCE[0]}")"
[[ "$(uname -m)" == "aarch64" ]] || { echo "Install on a Jetson ARM64 device only." >&2; exit 2; }
[[ -f /etc/nv_tegra_release ]] || { echo "NVIDIA Jetson Linux marker not found." >&2; exit 2; }
sudo apt-get update
sudo apt-get install -y software-properties-common curl gnupg
sudo add-apt-repository -y universe
sudo curl -fsSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key -o /usr/share/keyrings/ros-archive-keyring.gpg
echo "deb [arch=arm64 signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu noble main" | sudo tee /etc/apt/sources.list.d/ros2.list
sudo apt-get update
sudo apt-get install -y ./daemon-ace-edge_0.1.0_arm64.deb
sudo systemctl status daemon-ace-edge --no-pager
echo "DAEMON ACE Edge Agent installed. Verify /daemon_ace/edge/heartbeat."
