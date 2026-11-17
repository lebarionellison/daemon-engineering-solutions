# DAEMON ACE — Jetson Orin native edge release

## Target baseline
- NVIDIA Jetson Orin family; initial board profile: Orin Nano
- JetPack 7.2.1 / Jetson Linux 39.2.1
- Ubuntu 24.04 / ARM64
- ROS 2 Jazzy LTS
- Native ARM64 Debian package; systemd-managed ROS 2 service

## Included behavior
The edge agent publishes a one-second ROS 2 heartbeat to `/daemon_ace/edge/heartbeat`. Its JSON payload reports hostname, architecture, OS, uptime and memory totals. It explicitly labels the data `os_baseline_only`; it does not claim GPU, camera, sensor, actuator, thermal, power or model-inference telemetry.

## Build and test
The workflow runs on a native ARM64 Ubuntu 24.04 GitHub runner, installs ROS 2 Jazzy, runs Python tests, smoke-tests ROS 2 node startup, assembles an ARM64 Debian package and uploads a release bundle. This validates the software on ARM64; it is not a physical Jetson board test.

## Install
1. Provision a Jetson Orin with JetPack 7.2.1 / Jetson Linux 39.2.1.
2. Ensure the device has network access to the ROS 2 package repository.
3. Extract the release bundle on the device.
4. Run `chmod +x deploy.sh rollback.sh && ./deploy.sh`.
5. Check `systemctl status daemon-ace-edge` and inspect `/daemon_ace/edge/heartbeat` from an authorized ROS 2 node.
6. Remove the service and package with `./rollback.sh`.

## Production boundary
This is a deployable ROS 2 edge-agent reference package, not a complete autonomous robot application. It does not flash firmware, run customer models, command actuators, install OTA updates, enroll devices in a cloud fleet manager, or certify functional safety. Physical GPU inference, camera/sensor integration, power/thermal behavior, carrier-board qualification and production acceptance require real target hardware and must be tested separately. Jetson developer kits are pre-production validation devices; production shipments must be qualified on the selected production module and carrier system.
