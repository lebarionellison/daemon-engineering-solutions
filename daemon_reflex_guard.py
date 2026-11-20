#!/usr/bin/env python3
"""DAEMON Reflex Guard: fail-closed destination decisions and containment planning.

This reference evaluator does not install firewall rules, mutate Kubernetes, isolate
ROS 2 devices, redact telemetry, or execute rollback. A production adapter must be
separately integrated, authorized, tested and monitored.
"""
from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


def normalize_destination(destination: str) -> tuple[str | None, str]:
    """Return a safe hostname/IP from a host or HTTP(S) URL; reject ambiguous URLs."""
    raw = destination.strip()
    if not raw:
        return None, "EMPTY_DESTINATION"
    if "://" in raw:
        try:
            parsed = urlsplit(raw)
            if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
                return None, "UNSUPPORTED_OR_INVALID_URL"
            if parsed.username or parsed.password:
                return None, "URL_USERINFO_NOT_ALLOWED"
            return parsed.hostname.lower().rstrip("."), "URL_HOST_EXTRACTED"
        except ValueError:
            return None, "INVALID_URL"
    if any(char in raw for char in "/?#@"):
        return None, "AMBIGUOUS_DESTINATION"
    return raw.lower().rstrip("."), "HOST_INPUT"


def destination_allowed(destination: str, allowlist: list[str]) -> tuple[bool, str]:
    """Allow exact hosts or IPs within explicitly configured CIDRs; default deny."""
    candidate, source = normalize_destination(destination)
    if not candidate:
        return False, source
    if not allowlist:
        return False, "DEFAULT_DENY_NO_APPROVED_DESTINATION"
    for entry in allowlist:
        normalized, _ = normalize_destination(entry)
        if normalized and "/" not in entry and candidate == normalized:
            return True, "EXACT_HOST_ALLOWLIST_MATCH"
        try:
            address = ipaddress.ip_address(candidate)
            if "/" in entry and address in ipaddress.ip_network(entry.strip(), strict=False):
                return True, "CIDR_ALLOWLIST_MATCH"
        except ValueError:
            continue
    return False, "DENY_DESTINATION_NOT_EXPLICITLY_ALLOWLISTED"


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
    containment = event in {
        "unauthorized-egress", "config-drift", "compromised-container",
        "prompt-injection", "shadow-agent", "sensitive-telemetry"
    }
    actions = {
        "unauthorized-egress": [
            "Hold the external tool/webhook request and preserve destination metadata",
            "Apply an operator-approved default-deny egress policy through the configured adapter",
            "Review the agent identity, accessible secrets and data classification"
        ],
        "prompt-injection": [
            "Quarantine the untrusted log, issue or retrieved document from instruction context",
            "Pause affected agent tool execution pending human review",
            "Preserve source and trace metadata with sensitive values redacted"
        ],
        "shadow-agent": [
            "Inventory the unexpected workload and its service-account bindings",
            "Revoke or suspend the affected scoped identity through an authorized identity adapter",
            "Restrict namespace and network reach pending operator review"
        ],
        "sensitive-telemetry": [
            "Pause raw prompt/body/header export through the configured telemetry adapter",
            "Restrict access to affected traces and initiate approved retention review",
            "Preserve redacted incident metadata for investigation"
        ],
        "compromised-container": [
            "Apply namespace-scoped quarantine through the configured cluster adapter",
            "Restrict workload identity and preserve forensic telemetry",
            "Request operator-approved node or ROS 2 edge isolation where warranted"
        ],
        "config-drift": [
            "Hold release and compare the observed artifact with the trusted baseline",
            "Preserve evidence and request human review before restoration"
        ]
    }
    return {
        "incident": event,
        "containment": {
            "status": "QUARANTINE_PLAN_READY" if containment else "NO_CONTAINMENT_TRIGGER",
            "proposed_actions": actions.get(event, []) if containment else [],
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
        "note": "Receipt of Safety records this evaluator's decision and proposed response; it is not proof of live blocking, isolation, redaction or rollback."
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate DAEMON ACE default-deny egress and incident response plans.")
    parser.add_argument("--destination", "--outbound-telemetry-ip", dest="destination", action="append", default=[], help="Outbound host, IP or HTTP(S) webhook/tool URL.")
    parser.add_argument("--allow", "--approved-destination", dest="allow", action="append", default=[], help="Approved exact hostname or CIDR; repeat as needed.")
    parser.add_argument("--event", choices=["none", "unauthorized-egress", "config-drift", "compromised-container", "prompt-injection", "shadow-agent", "sensitive-telemetry"], default="none")
    parser.add_argument("--baseline-artifact", help="Path to last-known-clean artifact (hash only; never deployed).")
    parser.add_argument("--observed-artifact", help="Path to currently observed artifact (hash only).")
    args = parser.parse_args()

    egress = []
    for item in args.destination:
        allowed, reason = destination_allowed(item, args.allow)
        egress.append({"destination": item, "decision": "ALLOW" if allowed else "DENY", "reason": reason})
    baseline_hash = sha256_file(args.baseline_artifact)
    observed_hash = sha256_file(args.observed_artifact)
    incident = incident_plan(args.event, baseline_hash, observed_hash, bool(args.baseline_artifact and baseline_hash))
    result = {
        "engine": "DaemonReflexGuard",
        "policy": "DEFAULT_DENY_EGRESS",
        "egress_decisions": egress,
        "incident_response": incident,
        "execution": {"network_rules_applied": False, "cluster_mutated": False, "device_mutated": False, "telemetry_redacted": False}
    }
    print(json.dumps(result, indent=2))
    denied = any(item["decision"] == "DENY" for item in egress)
    return 1 if denied or incident["release_gate"] == "HUMAN_APPROVAL_REQUIRED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
