# DAEMON ACE ROS 2 Communication Assurance

A live ROS 2 publisher/subscriber diagnostic for selected DDS QoS reliability and durability contracts. It exercises real rclpy endpoints using the active ROS distribution and RMW implementation and writes a versioned JSON evidence report.

## Scope in v1.0.0

| Scenario | Expected behavior |
|---|---|
| Reliable → Reliable | Compatible; samples received |
| Reliable → Best Effort | Compatible; samples received |
| Best Effort → Reliable | Incompatible; incompatible-QoS event observed |
| Transient Local late joiner | Subscriber receives samples retained before it joined |
| Transient Local → Volatile | Compatible; samples received |
| Volatile → Transient Local | Incompatible; incompatible-QoS event observed |

The incompatible cases are intentional negative tests. A test passes when observed behavior matches the expected DDS request/offered compatibility behavior.

## Requirements

- A ROS 2 environment with rclpy and std_msgs installed.
- The selected RMW implementation installed and available.
- A sourced ROS environment, e.g. source /opt/ros/humble/setup.bash.

## Run

    source /opt/ros/$ROS_DISTRO/setup.bash
    python3 ros2/communication_assurance/qos_probe.py \
      --scenario all --duration 3 \
      --output daemon-ace-communication-report.json

Run one scenario:

    python3 ros2/communication_assurance/qos_probe.py \
      --scenario best_effort_to_reliable \
      --output qos-negative-test.json

Select an installed RMW implementation:

    RMW_IMPLEMENTATION=rmw_cyclonedds_cpp \
      python3 ros2/communication_assurance/qos_probe.py --scenario all

Exit status is 0 only when every selected scenario matches its expected behavior; otherwise it is 1. The report records ROS distribution, RMW implementation, ROS domain settings, scenario expectations/observations, message counts, incompatible-QoS events, and same-host publish-to-callback timing observations where applicable.

## CI coverage

The workflow .github/workflows/ros2-communication-assurance.yml runs the probe across Humble, Jazzy, Lyrical and Rolling with Fast DDS (rmw_fastrtps_cpp) and Cyclone DDS (rmw_cyclonedds_cpp). Each job uploads its JSON report and logs. A green matrix means the six listed scenarios passed in those exact CI container/RMW combinations.

## Evidence boundaries

- This tests two ROS 2 endpoints on one CI host. It is not a multi-host network or production-fleet qualification.
- Timing is measured with a monotonic clock in the same process/host. It is diagnostic only, not synchronized one-way network latency or a real-time guarantee.
- It does not exhaustively test DDS discovery, all QoS policies, security, multicast, packet loss, congestion, failover, ROS actions/services, or vendor-specific tuning.
- It does not test Gazebo/Isaac simulation, robot dynamics, sensors, actuators, physical hardware, functional safety or production deployment.
- Results are scoped to the recorded ROS distribution, RMW implementation, environment and scenarios. Do not infer complete ROS compatibility from a passing probe.

DAEMON ACE is an engineering assurance layer above upstream ROS 2, not a ROS 2 fork or a ROS 3 distribution.
