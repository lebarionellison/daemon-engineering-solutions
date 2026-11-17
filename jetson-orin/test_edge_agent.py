import json
from edge_agent import build_status_payload

def test_heartbeat_payload_is_explicit_and_serializable():
    payload=build_status_payload()
    assert payload["schema"]=="daemon-ace-edge-heartbeat/v1"
    assert payload["architecture"] and payload["hostname"]
    assert payload["telemetry_scope"]=="os_baseline_only"
    assert payload["hardware_validation"]=="not_attested"
    assert isinstance(payload["timestamp_unix"],int)
    assert payload["uptime_seconds"] is None or payload["uptime_seconds"]>=0
    assert json.loads(json.dumps(payload))["schema"]==payload["schema"]
