#!/usr/bin/env python3
"""DAEMON Reflex Guard: fail-closed egress decisions and containment planning.

This reference implementation evaluates destinations and produces an incident plan.
It does NOT install firewall rules, mutate Kubernetes, isolate ROS 2 devices, or deploy
rollback artifacts. A production adapter must be explicitly integrated and authorized.
"""
from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import re
from pathlib import Path
from typing import Any


def destination_allowed(destination: str, allowlist: list[str]) -> tuple[bool, str]:
    """Allow an exact hostname or an IP inside an explicitly configured CIDR."""
    candidate = destination.strip().lower().rstrip(".")
    if not candidate or not allowlist:
        return False, "DEFAULT_DENY_NO_APPROVED_DESTINATION"
    if candidate in {entry.strip().lower().rstrip(".") for entry in allowlist if "/" not in entry}:
        return True, "EXACT_HOST_ALLOWLIST_MATCH"
    try:
        address = ipaddress.ip_address(candidate)
    except ValueError:
        return False, "DENY_HOST_NOT_EXPLICITLY_ALLOWLISTED"
    for entry in allowlist:
        try:
            if "/" in entry and address in ipaddress.ip_network(entry.strip(), strict=False):
                return True, "CIDR_ALLOWLIST_MATCH"
        except ValueError:
            continue
    return False, "DENY_IP_NOT_IN_EGRESS_ALLOWLIST"


def sha256_file(path: str | None) -> str | None:
    if not path:
        return None
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def incident_plan(event: str, baseline_sha256: str | None, observed_sha256: str | None,
                  baseline_available: bool) -> dict[str, Any]:
    drift = bool(baseline_sha256 and observed_sha256 and
                 re.fullmatch(r"[a-fA-F0-9]{64}", baseline_sha256) and
                 re.fullmatch(r"[a-fA-F0-9]{64}", observed_sha256) and
                 baseline_sha256.lower() != observed_sha256.lower())
    containment = event in {"unauthorized-egress", "config-drift", "compromised-container"}
    return {
        "incident": event,
        "containment": {
            "status": "QUARANTINE_PLAN_READY" if containment else "NO_CONTAINMENT_TRIGGER",
            "proposed_actions": [
                "Apply namespace-scoped default-deny egress policy to the affected workload",
                "Restrict workload identity and preserve forensic telemetry",
                "For a compromised node, request operator-approved cordon/isolation through the cluster adapter",
                "For ROS 2 edge devices, block non-allowlisted routes at the device/network boundary"
            ] if containment else [],
            "executed": False,
            "adapter_status": "NOT_CONFIGURED"
        },
        "baseline": {
            "expected_sha256": baseline_sha256,
            "observed_sha256": observed_sha256,
            "drift_detected": drift,
            "rollback_status": (
                "ROLLBACK_CANDIDATE_REQUIRES_HUMAN_APPROVAL"
                if drift and baseline_available else
                "HOLD_BASELINE_ARTIFACT_NOT_AVAILABLE"
                if drift else "NO_VERIFIED_DRIFT"
            ),
            "restoration_executed": False
        },
        "release_gate": "HUMAN_APPROVAL_REQUIRED" if containment or drift else "REVIEW",
        "note": "Receipt of Safety is evidence of this policy decision, not proof of live containment or a completed rollback."
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate DAEMON ACE default-deny egress and containment decisions.")
    parser.add_argument("--destination", "--outbound-telemetry-ip", dest="destination", action="append", default=[], help="Outbound destination IP or hostname to evaluate.")
    parser.add_argument("--allow", "--approved-destination", dest="allow", action="append", default=[], help="Approved exact hostname or CIDR; repeat as needed.")
    parser.add_argument("--event", choices=["none", "unauthorized-egress", "config-drift", "compromised-container"], default="none")
    parser.add_argument("--baseline-artifact", help="Path to last-known-clean artifact (hash only; never deployed).")
    parser.add_argument("--observed-artifact", help="Path to currently observed artifact (hash only).")
    args = parser.parse_args()

    egress = [
        {"destination": item, "decision": "ALLOW" if (decision := destination_allowed(item, args.allow))[0] else "DENY",
         "reason": decision[1]}
        for item in args.destination
    ]
    baseline_hash = sha256_file(args.baseline_artifact)
    observed_hash = sha256_file(args.observed_artifact)
    incident = incident_plan(
        args.event, baseline_hash, observed_hash, bool(args.baseline_artifact and baseline_hash)
    )
    result = {
        "engine": "DaemonReflexGuard",
        "policy": "DEFAULT_DENY_EGRESS",
        "egress_decisions": egress,
        "incident_response": incident,
        "execution": {"network_rules_applied": False, "cluster_mutated": False, "device_mutated": False},
    }
    print(json.dumps(result, indent=2))
    denied = any(item["decision"] == "DENY" for item in egress)
    return 1 if denied or incident["release_gate"] == "HUMAN_APPROVAL_REQUIRED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
