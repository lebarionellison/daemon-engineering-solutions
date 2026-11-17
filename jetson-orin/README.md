# DAEMON ACE — Jetson Orin reference release

## Target baseline
- NVIDIA Jetson Orin family; initial board profile: Orin Nano
- JetPack 7.2.1 / Jetson Linux 39.2.1
- Ubuntu 24.04 / ARM64
- ROS 2 Jazzy
- NVIDIA L4T base: nvcr.io/nvidia/l4t-base:r39.2.1

## Included behavior
The edge agent publishes a one-second ROS 2 heartbeat to `/daemon_ace/edge/heartbeat`. Its JSON payload reports hostname, architecture, OS, uptime and memory totals. It explicitly labels the data `os_baseline_only`; no GPU, camera, sensor, actuator, thermal, power or inference telemetry is claimed.

## Build and test
The workflow `.github/workflows/jetson-orin-release.yml` builds the ARM64 L4T image using QEMU/buildx, runs Python payload tests and starts the ROS 2 agent under ARM64 emulation. It uploads an image archive with Compose and local install/rollback scripts. This is cross-architecture CI validation, not a physical Jetson board test.

## Device install
1. Provision a Jetson Orin with the target JetPack baseline.
2. Install Docker, NVIDIA Container Runtime and Docker Compose v2 using NVIDIA's device guidance.
3. Extract the release bundle on the device.
4. Run `chmod +x deploy.sh rollback.sh && ./deploy.sh`.
5. Confirm the process is healthy and inspect `/daemon_ace/edge/heartbeat` from an authorized ROS 2 node.
6. Roll back with `./rollback.sh`.

## Production boundary
This is a deployable ROS 2 edge-agent reference package, not a complete autonomous robot product. It does not flash firmware, run customer models, command actuators, install OTA updates, enroll devices in a cloud fleet manager, or certify functional safety. Physical GPU inference, camera/sensor integration, power/thermal behavior, carrier-board qualification and production acceptance require real target hardware and must be tested separately. Jetson developer kits are pre-production validation devices; production shipments must be qualified on the selected production module and carrier system.
