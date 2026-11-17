# DAEMON ACE ROS Workspace Compatibility Analyzer

Analyzer version: 1.0.0  
Report schema: `daemon-ace.ros2-workspace-report.v1`

Local-first ROS 2 engineering utility. It inventories package manifests, checks build metadata, applies a versioned API migration rule set, inspects DDS/QoS configuration patterns and can optionally build the workspace inside official ROS distribution containers.

## Static review
```bash
python3 ros2/workspace_analyzer/analyze.py ./my_ros_ws --distro humble --distro jazzy --distro lyrical
```
Writes versioned JSON and Markdown reports to `daemon-ace-report/`.

## Actual per-distribution builds
Requires Docker, network access, and a workspace with packages under `src/`:
```bash
python3 ros2/workspace_analyzer/analyze.py ./my_ros_ws --build --distro humble --distro jazzy --distro lyrical --distro rolling
```
Each selected distro uses `ros:<distro>-ros-base`, installs rosdep/colcon, resolves dependencies and runs `colcon build`. The workspace mount is writable for build/install/log output. Builds are never implied by static-only mode.

## Checks
- Package inventory and declared dependency extraction from package.xml.
- CMake inspection for catkin remnants and ament target dependency signals.
- Versioned API migration pattern checks in api-migration-rules.json.
- DDS/QoS source/config pattern review for reliability, durability, history/depth and system defaults.
- Optional real rosdep + colcon build matrix; passed only on successful process exit.

## Evidence boundary
Static matches are heuristic review signals, not proof of runtime behavior. External dependency availability is determined by rosdep during builds. QoS pattern checks are not live DDS interoperability tests. A successful build does not establish application correctness, simulator fidelity, hardware readiness, real-time performance or safety certification. Reports include a workspace SHA-256, analyzer/rule versions, target distributions, findings, build outcomes and limitations. Human engineering review remains required.
