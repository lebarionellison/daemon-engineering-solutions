# DAEMON ACE ROS Workspace Compatibility Analyzer

Analyzer version: 1.1.0  
Report schema: \`daemon-ace.ros2-workspace-report.v2\`

Local-first ROS 2 engineering utility. It inventories package manifests, checks build metadata, applies a versioned API migration rule set, inspects DDS/QoS source patterns and can optionally build the workspace inside official ROS distribution containers.

## Static review
\`\`\`bash
python3 ros2/workspace_analyzer/analyze.py ./candidate_ws --distro humble --distro jazzy --distro lyrical
\`\`\`
Writes versioned JSON and Markdown reports to \`daemon-ace-report/\`.

## Compare a candidate workspace to a baseline
Pass the current/candidate workspace as the positional argument and the before/baseline workspace to \`--compare-to\`:
\`\`\`bash
python3 ros2/workspace_analyzer/analyze.py ./candidate_ws \\
  --compare-to ./baseline_ws \\
  --distro humble --distro jazzy --distro lyrical --distro rolling
\`\`\`
The report compares:
- ROS package additions and removals.
- Package version changes and manifest dependency additions/removals.
- CMake \`find_package\` dependency additions/removals.
- Changes in occurrence counts for the versioned API migration patterns, including source locations in the candidate.
This is a source/workspace delta, not a binary ABI diff or a comparison of upstream ROS SDK headers. Rules are heuristic and need engineer review.

## Structured DDS/QoS profile validation
The analyzer accepts the DAEMON ACE JSON profile contract:
\`\`\`bash
python3 ros2/workspace_analyzer/analyze.py ./candidate_ws \\
  --qos-profile ros2/workspace_analyzer/examples/qos-profile.example.json
\`\`\`
Contract and example:
- \`qos-profile.schema.json\`
- \`examples/qos-profile.example.json\`

The validator checks required fields, supported reliability/durability/history/liveliness values, positive \`keep_last\` depth, non-negative timing fields, duplicate topic endpoints, and ROS 2 request/offered compatibility for reliability and durability when both publisher and subscriber are described. It does not parse arbitrary ROS parameter YAML, inspect a running RMW/DDS graph, or prove runtime interoperability.

## Actual per-distribution builds
Requires Docker, network access, and a workspace with packages under \`src/\`:
\`\`\`bash
python3 ros2/workspace_analyzer/analyze.py ./candidate_ws --build \\
  --distro humble --distro jazzy --distro lyrical --distro rolling
\`\`\`
Each selected distro uses \`ros:<distro>-ros-base\`, installs rosdep/colcon, resolves dependencies and runs \`colcon build\`. The workspace mount is writable for build/install/log output. Builds are never implied by static-only mode.

## Report evidence
JSON and Markdown reports include the report schema/version, analyzer/rule versions, workspace SHA-256, package inventory, target distributions, build outcomes, findings, optional baseline diff, optional QoS profile validation and limitations. A distro is marked passed only on successful rosdep + colcon exit.

## Evidence boundary
Static matches are heuristic review signals, not proof of runtime behavior. The workspace diff compares manifests, CMake dependency declarations and configured API pattern counts; it is not an upstream API/ABI header diff. External dependency availability is determined by rosdep during builds. QoS profile validation checks the DAEMON ACE profile contract and selected request/offered rules, not live DDS interoperability. A successful build does not establish application correctness, simulator fidelity, hardware readiness, real-time performance or safety certification. Human engineering review remains required.
