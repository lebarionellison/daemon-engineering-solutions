#!/usr/bin/env python3
"""Live ROS 2 DDS publisher/subscriber QoS interoperability probes."""
from __future__ import annotations
import argparse, json, os, statistics, time, uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import rclpy
    from rclpy.node import Node
    from rclpy.event_handler import SubscriptionEventCallbacks
    from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
    from std_msgs.msg import String
except ImportError as exc:
    raise SystemExit(f"ROS 2 Python package import failed: {exc!r}. Source /opt/ros/<distro>/setup.bash and install rclpy + std_msgs.") from exc

SCENARIOS = {
 "reliable_to_reliable": {"publisher_reliability":"reliable","subscriber_reliability":"reliable","publisher_durability":"volatile","subscriber_durability":"volatile","expected":"compatible","description":"Reliable publisher to reliable subscriber"},
 "reliable_to_best_effort": {"publisher_reliability":"reliable","subscriber_reliability":"best_effort","publisher_durability":"volatile","subscriber_durability":"volatile","expected":"compatible","description":"Reliable offered to best-effort requested"},
 "best_effort_to_reliable": {"publisher_reliability":"best_effort","subscriber_reliability":"reliable","publisher_durability":"volatile","subscriber_durability":"volatile","expected":"incompatible","description":"Best-effort offered to reliable requested"},
 "transient_local_retention": {"publisher_reliability":"reliable","subscriber_reliability":"reliable","publisher_durability":"transient_local","subscriber_durability":"transient_local","expected":"retained_samples","description":"Late-joining transient-local subscriber receives retained samples"},
 "transient_local_to_volatile": {"publisher_reliability":"reliable","subscriber_reliability":"reliable","publisher_durability":"transient_local","subscriber_durability":"volatile","expected":"compatible","description":"Transient-local offered to volatile requested"},
 "volatile_to_transient_local": {"publisher_reliability":"reliable","subscriber_reliability":"reliable","publisher_durability":"volatile","subscriber_durability":"transient_local","expected":"incompatible","description":"Volatile offered to transient-local requested"},
}
REL={"reliable":ReliabilityPolicy.RELIABLE,"best_effort":ReliabilityPolicy.BEST_EFFORT}
DUR={"volatile":DurabilityPolicy.VOLATILE,"transient_local":DurabilityPolicy.TRANSIENT_LOCAL}

def qos(reliability, durability):
    return QoSProfile(history=HistoryPolicy.KEEP_LAST, depth=10, reliability=REL[reliability], durability=DUR[durability])

def run_pair(name, spec, duration):
    token=uuid.uuid4().hex[:10]; topic=f"/daemon_ace/communication_assurance/{name}_{token}"
    pub_node=Node(f"ace_probe_pub_{token}"); sub_node=Node(f"ace_probe_sub_{token}")
    received=[]; latencies=[]; incompatible=[]; sequence=0; publisher=None; subscription=None; timer=None
    def on_message(message):
        try:
            payload=json.loads(message.data); received.append(int(payload["sequence"]))
            latencies.append(max(0.0,(time.monotonic_ns()-int(payload["sent_monotonic_ns"]))/1_000_000))
        except (ValueError,KeyError,TypeError,json.JSONDecodeError): return
    def on_incompatible(event):
        incompatible.append({"total_count":int(getattr(event,"total_count",0)),"total_count_change":int(getattr(event,"total_count_change",0)),"last_policy_kind":int(getattr(event,"last_policy_kind",0))})
    try:
        sub_qos=qos(spec["subscriber_reliability"],spec["subscriber_durability"])
        pub_qos=qos(spec["publisher_reliability"],spec["publisher_durability"])
        subscription=sub_node.create_subscription(String,topic,on_message,sub_qos,event_callbacks=SubscriptionEventCallbacks(incompatible_qos=on_incompatible))
        publisher=pub_node.create_publisher(String,topic,pub_qos)
        def publish():
            nonlocal sequence
            sequence+=1; msg=String(); msg.data=json.dumps({"sequence":sequence,"sent_monotonic_ns":time.monotonic_ns()}); publisher.publish(msg)
        timer=pub_node.create_timer(0.05,publish); started=time.monotonic(); deadline=started+duration
        while time.monotonic()<deadline:
            rclpy.spin_once(pub_node,timeout_sec=0.01); rclpy.spin_once(sub_node,timeout_sec=0.01)
        expected=spec["expected"]
        if expected=="compatible":
            passed=len(received)>0 and len(incompatible)==0
            observed="messages_received" if received else ("incompatible_qos_event" if incompatible else "no_matching_data")
        else:
            passed=len(received)==0 and len(incompatible)>0
            observed="incompatible_qos_event" if incompatible else ("messages_received" if received else "no_incompatibility_event")
        ordered=sorted(latencies)
        p95=round(ordered[max(0,int(len(ordered)*0.95)-1)],3) if ordered else None
        return {"name":name,"description":spec["description"],"topic":topic,
          "publisher":{"reliability":spec["publisher_reliability"],"durability":spec["publisher_durability"]},
          "subscriber":{"reliability":spec["subscriber_reliability"],"durability":spec["subscriber_durability"]},
          "expected":expected,"observed":observed,"passed":passed,"messages_published":sequence,
          "messages_received":len(received),"incompatible_qos_events":len(incompatible),
          "latency_ms":{"sample_count":len(latencies),"median":round(statistics.median(latencies),3) if latencies else None,"p95":p95,
            "measurement_note":"Same-host monotonic publish-to-callback observation; not a network or real-time guarantee."},
          "duration_seconds":round(time.monotonic()-started,3),"incompatible_event_samples":incompatible[:5]}
    finally:
        if timer: pub_node.destroy_timer(timer)
        if publisher: pub_node.destroy_publisher(publisher)
        if subscription: sub_node.destroy_subscription(subscription)
        pub_node.destroy_node(); sub_node.destroy_node()

def run_retention(name,spec,duration):
    token=uuid.uuid4().hex[:10]; topic=f"/daemon_ace/communication_assurance/{name}_{token}"
    pub_node=Node(f"ace_probe_late_pub_{token}"); sub_node=None; publisher=None; timer=None; received=[]; incompatible=[]; sequence=0
    def publish():
        nonlocal sequence
        sequence+=1; msg=String(); msg.data=f"retained-{sequence}"; publisher.publish(msg)
    try:
        publisher=pub_node.create_publisher(String,topic,qos(spec["publisher_reliability"],spec["publisher_durability"]))
        timer=pub_node.create_timer(0.05,publish); warmup=time.monotonic()+1.0
        while time.monotonic()<warmup: rclpy.spin_once(pub_node,timeout_sec=0.02)
        sub_node=Node(f"ace_probe_late_sub_{token}")
        def on_message(msg): received.append(msg.data)
        def on_incompatible(event): incompatible.append(int(getattr(event,"total_count_change",0)))
        subscription=sub_node.create_subscription(String,topic,on_message,qos(spec["subscriber_reliability"],spec["subscriber_durability"]),event_callbacks=SubscriptionEventCallbacks(incompatible_qos=on_incompatible))
        deadline=time.monotonic()+max(2.0,duration)
        while time.monotonic()<deadline:
            rclpy.spin_once(pub_node,timeout_sec=0.01); rclpy.spin_once(sub_node,timeout_sec=0.01)
        return {"name":name,"description":spec["description"],"topic":topic,
          "publisher":{"reliability":spec["publisher_reliability"],"durability":spec["publisher_durability"]},
          "subscriber":{"reliability":spec["subscriber_reliability"],"durability":spec["subscriber_durability"]},
          "expected":"retained_samples","observed":"retained_samples_received" if received else "no_retained_samples",
          "passed":bool(received) and not incompatible,"messages_published_before_and_after_join":sequence,
          "messages_received":len(received),"messages_received_after_subscriber_join":len(received),"incompatible_qos_events":len(incompatible),
          "latency_ms":{"sample_count":0,"median":None,"p95":None,"measurement_note":"Late-joiner retention probe; latency is not measured."}}
    finally:
        if timer: pub_node.destroy_timer(timer)
        if publisher: pub_node.destroy_publisher(publisher)
        if sub_node: sub_node.destroy_node()
        pub_node.destroy_node()

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario",choices=["all",*SCENARIOS],default="all")
    parser.add_argument("--duration",type=float,default=3.0)
    parser.add_argument("--output",type=Path,default=Path("daemon-ace-communication-report.json"))
    args=parser.parse_args()
    if args.duration<1: parser.error("--duration must be at least 1 second")
    selected=list(SCENARIOS) if args.scenario=="all" else [args.scenario]
    rclpy.init()
    try:
        results=[]
        for name in selected:
            spec=SCENARIOS[name]
            results.append(run_retention(name,spec,args.duration) if spec["expected"]=="retained_samples" else run_pair(name,spec,args.duration))
        passed=sum(bool(item["passed"]) for item in results)
        report={"schema":"daemon-ace.ros2-communication-assurance.v1","report_version":"1.0.0",
          "generated_at":datetime.now(timezone.utc).isoformat(),
          "environment":{"ros_distro":os.getenv("ROS_DISTRO","unknown"),"rmw_implementation":os.getenv("RMW_IMPLEMENTATION","default"),
            "ros_domain_id":os.getenv("ROS_DOMAIN_ID","unset"),"ros_localhost_only":os.getenv("ROS_LOCALHOST_ONLY","unset")},
          "summary":{"scenarios_total":len(results),"scenarios_passed":passed,"scenarios_failed":len(results)-passed,"disposition":"PASS" if passed==len(results) else "REVIEW_REQUIRED"},
          "scenarios":results,
          "limitations":[
            "Tests exercise ROS 2 publisher/subscriber endpoints on one host using the selected RMW implementation; they are not a distributed network qualification.",
            "Publish-to-callback latency is a same-host monotonic diagnostic observation, not synchronized one-way network latency or a real-time guarantee.",
            "Only listed reliability and durability scenarios are tested; this is not exhaustive DDS QoS, discovery, security, multicast, congestion, packet-loss, or failover coverage.",
            "No simulator, robot dynamics, sensors, actuators, physical hardware, safety function, or production fleet is tested.",
            "A passing result applies only to the recorded ROS distribution, container/environment, RMW implementation, and scenarios."]}
        args.output.parent.mkdir(parents=True,exist_ok=True); args.output.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
        print(json.dumps(report,indent=2))
        return 0 if report["summary"]["disposition"]=="PASS" else 1
    finally: rclpy.shutdown()

if __name__=="__main__": raise SystemExit(main())
