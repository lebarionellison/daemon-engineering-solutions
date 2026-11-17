# DAEMON ACE ROS 2 Evolution Engineering

**Purpose:** keep customer robotics workspaces buildable and testable as upstream ROS 2 distributions evolve. DAEMON ACE is an engineering and validation layer above ROS 2; it is not a ROS fork or competing middleware distribution.

## Upstream lifecycle snapshot — 2026-11-17

| Distribution | Upstream status | Release | Upstream EOL | DAEMON ACE position |
|---|---|---:|---:|---|
| Lyrical Luth | LTS | 2026-05-22 | May 2031 | Basic messaging smoke test passed; broader compatibility pending |
| Makoa Mata-mata | Planned non-LTS | May 2027 (planned) | December 2028 (planned) | Pre-release readiness target; not yet released |
| Rolling Ridley | Development | Continuous | N/A | Basic messaging smoke test passed; early-warning lane, not production support |
| Jazzy Jalisco | LTS | 2024-05-23 | May 2029 | Basic messaging smoke test passed; broader compatibility pending |
| Humble Hawksbill | LTS | 2022-05-23 | May 2027 | Basic messaging smoke test passed; legacy customer baseline |

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
3. **Selected live DDS QoS assurance — implemented in v1.0.0:** run six reliability/durability endpoint scenarios and observe incompatible-QoS events across tested RMW implementations. This is not exhaustive DDS qualification.
4. **Simulation regression — planned:** compare deterministic scenarios in named Gazebo / Isaac Sim versions.
5. **Hardware qualification — customer-specific:** separately authorized lab testing on identified platforms with recorded safety procedures.

## Release policy

- Keep upstream release status separate from DAEMON ACE validation status.
- Do not infer Lyrical compatibility, Makoa readiness or Rolling support from a container pull or upstream announcement.
- Publish distro, image tag/digest, workflow run, test coverage, limitations and known failures with each compatibility statement.
- Do not advertise physics simulation, hardware validation, ros2_control/Nav2 coverage, real-time qualification or safety certification unless those exact tests have been implemented and passed.


## First expanded matrix result

**PASS — November 17, 2026:** [DAEMON ACE Pre-Flight run #44111443506](https://github.com/lebarionellison/daemon-engineering-solutions/actions/runs/44111443506)

All four container jobs passed the basic `demo_nodes_cpp` talker/listener exchange:
- Humble — passed
- Jazzy — passed
- Lyrical — passed
- Rolling — passed

The lifecycle metadata guard and DAEMON ACE pre-flight receipt job also passed. This is a messaging smoke-test result, not full distribution compatibility certification. Makoa remains planned and is not yet testable as a released distribution.

## Live DDS QoS Communication Assurance — v1.0.0

Tool: ros2/communication_assurance/qos_probe.py  
Runbook: ros2/communication_assurance/README.md  
Report contract: ros2/communication_assurance/report.schema.v1.json  
Workflow: .github/workflows/ros2-communication-assurance.yml

The probe creates ROS 2 publisher/subscriber endpoints and runs six selected scenarios:
- Reliable publisher → reliable subscriber (positive message-flow test).
- Reliable publisher → best-effort subscriber (compatible request/offered test).
- Best-effort publisher → reliable subscriber (negative compatibility test; expects incompatible-QoS event and no samples).
- Transient-local late-joining subscriber (expects retained samples).
- Transient-local publisher → volatile subscriber (compatible durability test).
- Volatile publisher → transient-local subscriber (negative compatibility test; expects incompatible-QoS event and no samples).

The CI matrix targets Humble, Jazzy, Lyrical and Rolling with rmw_fastrtps_cpp and rmw_cyclonedds_cpp. Reports record exact ROS/RMW environment, expected and observed outcomes, sample counts, incompatible-QoS events and same-host publish-to-callback timing observations.

**Evidence boundary:** this is a single-host endpoint probe, not multi-host network qualification. Timing is diagnostic and not a real-time guarantee. It does not exhaustively test DDS discovery, all QoS policies, security, packet loss, congestion, failover, simulation, hardware, safety or production fleets. Publish compatibility claims only for exact matrix combinations whose jobs have passed; never infer full ROS distribution support from this probe.
