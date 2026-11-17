#!/usr/bin/env bash
set -euo pipefail
sudo systemctl disable --now daemon-ace-edge.service 2>/dev/null || true
sudo apt-get remove -y daemon-ace-edge
sudo systemctl daemon-reload
echo "DAEMON ACE Edge Agent removed. No robot firmware or model files were changed."
