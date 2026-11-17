import json, platform, time
import rclpy
from rclpy.node import Node
from std_msgs.msg import String

def build_status_payload():
    uptime = None
    try:
        with open("/proc/uptime", encoding="utf-8") as f: uptime = int(float(f.read().split()[0]))
    except (OSError, ValueError, IndexError): pass
    total = available = None
    try:
        with open("/proc/meminfo", encoding="utf-8") as f:
            data = {}
            for line in f:
                key, value = line.split(":", 1)
                if key in ("MemTotal", "MemAvailable"): data[key] = int(value.strip().split()[0])
            total, available = data.get("MemTotal"), data.get("MemAvailable")
    except (OSError, ValueError): pass
    return {"schema":"daemon-ace-edge-heartbeat/v1","timestamp_unix":int(time.time()),
      "hostname":platform.node(),"architecture":platform.machine(),"os":platform.platform(),
      "uptime_seconds":uptime,"memory_total_kb":total,"memory_available_kb":available,
      "telemetry_scope":"os_baseline_only","hardware_validation":"not_attested"}

class EdgeHeartbeat(Node):
    def __init__(self):
        super().__init__("daemon_ace_edge_agent")
        self.publisher=self.create_publisher(String,"/daemon_ace/edge/heartbeat",10)
        self.timer=self.create_timer(1.0,self.publish_heartbeat)
        self.get_logger().info("DAEMON_ACE_EDGE_READY topic=/daemon_ace/edge/heartbeat scope=os_baseline_only")
    def publish_heartbeat(self):
        msg=String(); msg.data=json.dumps(build_status_payload(),separators=(",",":")); self.publisher.publish(msg)

def main():
    rclpy.init(); node=EdgeHeartbeat()
    try: rclpy.spin(node)
    except KeyboardInterrupt: pass
    finally: node.destroy_node(); rclpy.shutdown()
if __name__=="__main__": main()
