# DAEMON ACE ROS 2 Evolution Engineering

**Purpose:** keep customer robotics workspaces buildable and testable as upstream ROS 2 distributions evolve. DAEMON ACE is an engineering and validation layer above ROS 2; it is not a ROS fork or competing middleware distribution.

## Upstream lifecycle snapshot — 2026-11-17

| Distribution | Upstream status | Release | Upstream EOL | DAEMON ACE position |
|---|---|---:|---:|---|
| Lyrical Luth | LTS | 2026-05-22 | May 2031 | Primary forward baseline; pending matrix validation |
| Makoa Mata-mata | Planned non-LTS | May 2027 (planned) | December 2028 (planned) | Pre-release readiness target; not yet released |
| Rolling Ridley | Development | Continuous | N/A | Early-warning lane, not production support |
| Jazzy Jalisco | LTS | 2024-05-23 | May 2029 | Customer compatibility baseline |
| Humble Hawksbill | LTS | 2022-05-23 | May 2027 | Legacy customer baseline; existing Humble messaging smoke test passed previously |

Official upstream sources:
- [ROS 2 distributions and future release schedule](https://github.com/ros2/ros2_documentation/blob/rolling/source/Releases.rst)
- [Makoa release page](https://docs.ros.org/en/rolling/Releases/Release-Makoa-Mata-mata.html)
- [ROS 2 upstream releases](https://github.com/ros2/ros2/releases)

The upstream schedule can change. Makoa is planned for May 2027 and must not be described as released or supported before upstream packages are published and DAEMON ACE tests pass.

## Automated CI coverage

Workflow: `.github/workflows/ros2-evolution.yml`

The workflow runs the official ROS 2 `demo_nodes_cpp` talker and listener in isolated containers for:
- Humble
- Jazzy
- Lyrical
- Rolling

It installs the distro-matched `ros-<distro>-demo-nodes-cpp` package, starts a talker and listener on a dedicated ROS domain, and checks both publish and receive logs. It runs on relevant pull requests, pushes to main, a weekly schedule, and manual dispatch.

**Interpretation:** a green job demonstrates only that this basic ROS 2 messaging sample exchanged messages in that CI container. It does not certify every package, API, RMW implementation, DDS QoS profile, simulator, robot model, hardware target, real-time requirement, functional-safety property or production deployment.

## Validation maturity

1. **Messaging smoke test — automated:** basic publisher/subscriber exchange.
2. **Workspace build and dependency validation — next:** build representative customer workspaces per distro.
3. **API/message/QoS compatibility — planned:** detect changed interfaces and validate specified DDS policies.
4. **Simulation regression — planned:** compare deterministic scenarios in named Gazebo / Isaac Sim versions.
5. **Hardware qualification — customer-specific:** separately authorized lab testing on identified platforms with recorded safety procedures.

## Release policy

- Keep upstream release status separate from DAEMON ACE validation status.
- Do not infer Lyrical compatibility, Makoa readiness or Rolling support from a container pull or upstream announcement.
- Publish distro, image tag/digest, workflow run, test coverage, limitations and known failures with each compatibility statement.
- Do not advertise physics simulation, hardware validation, ros2_control/Nav2 coverage, real-time qualification or safety certification unless those exact tests have been implemented and passed.
