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


def _validated_networks(values: list[str]) -> list[ipaddress._BaseNetwork]:
    networks: list[ipaddress._BaseNetwork] = []
    for value in values:
        try:
            networks.append(ipaddress.ip_network(value.strip(), strict=False))
        except ValueError as exc:
            raise ValueError(f"Invalid approved CIDR/IP '{value}': {exc}") from exc
    if not networks:
        raise ValueError("At least one approved CIDR/IP is required to emit an allow-list policy.")
    return networks


def render_kubernetes_policies(namespace: str, selector: dict[str, str],
                               approved_cidrs: list[str]) -> str:
    """Render additive deny-by-default and approved-destination policies for selected pods."""
    if not re.fullmatch(r"[a-z0-9]([-a-z0-9]*[a-z0-9])?", namespace):
        raise ValueError("Namespace must be a valid lowercase Kubernetes DNS label.")
    if not selector or any(not re.fullmatch(r"[A-Za-z0-9./_-]+", k) or
                           not re.fullmatch(r"[A-Za-z0-9._-]+", v)
                           for k, v in selector.items()):
        raise ValueError("Provide at least one simple pod label selector (key=value).")
    networks = _validated_networks(approved_cidrs)
    labels = "\n".join(f"      {key}: {value}" for key, value in sorted(selector.items()))
    lines = [
        "apiVersion: networking.k8s.io/v1", "kind: NetworkPolicy",
        "metadata:", "  name: daemon-ace-default-deny-egress",
        f"  namespace: {namespace}", "spec:", "  podSelector:",
        "    matchLabels:", labels, "  policyTypes:", "    - Egress",
        "  egress: []", "---", "apiVersion: networking.k8s.io/v1",
        "kind: NetworkPolicy", "metadata:",
        "  name: daemon-ace-approved-egress", f"  namespace: {namespace}",
        "spec:", "  podSelector:", "    matchLabels:", labels,
        "  policyTypes:", "    - Egress", "  egress:"
    ]
    # DNS is explicitly limited to kube-dns pods in kube-system. CNI support must be verified.
    lines += [
        "    - to:", "        - namespaceSelector:",
        "            matchLabels:", "              kubernetes.io/metadata.name: kube-system",
        "          podSelector:", "            matchLabels:", "              k8s-app: kube-dns",
        "      ports:", "        - protocol: UDP", "          port: 53",
        "        - protocol: TCP", "          port: 53"
    ]
    for network in networks:
        field = "ipBlock" if network.version == 4 else "ipBlock"
        lines += [
            "    - to:", f"        - {field}:",
            f"            cidr: {network.with_prefixlen}"
        ]
    lines += [
        "# Review before applying. NetworkPolicy is additive and requires a supporting CNI.",
        "# This policy does not govern hostNetwork pods, node traffic, or ROS 2 edge hosts."
    ]
    return "\n".join(lines) + "\n"


def render_edge_nftables(approved_cidrs: list[str], management_cidrs: list[str] | None = None) -> str:
    """Render a review-only nftables output-chain policy for ROS 2 edge hosts."""
    networks = _validated_networks(approved_cidrs)
    management = _validated_networks(management_cidrs or []) if management_cidrs else []
    v4 = sorted({n.with_prefixlen for n in networks + management if n.version == 4})
    v6 = sorted({n.with_prefixlen for n in networks + management if n.version == 6})
    lines = [
        "# DAEMON ACE ROS 2 EDGE EGRESS POLICY — REVIEW BEFORE APPLYING",
        "# This file is an example policy artifact, not installed by Reflex Guard.",
        "# Confirm management, DNS, NTP, OTA, ROS 2 discovery and emergency access first.",
        "table inet daemon_ace {", "  chain output {",
        "    type filter hook output priority filter; policy drop;",
        "    ct state established,related accept",
        "    oifname \"lo\" accept"
    ]
    if v4:
        lines.append("    ip daddr { " + ", ".join(v4) + " } accept")
    if v6:
        lines.append("    ip6 daddr { " + ", ".join(v6) + " } accept")
    lines += ["  }", "}"]
    return "\n".join(lines) + "\n"


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
    parser.add_argument("--approved-cidr", action="append", default=[], help="Approved destination IP/CIDR for policy generation; repeat as needed.")
    parser.add_argument("--namespace", default="default", help="Kubernetes namespace for generated NetworkPolicies.")
    parser.add_argument("--pod-label", action="append", default=[], help="Pod label selector key=value; repeat as needed.")
    parser.add_argument("--emit-k8s-policy", help="Write review-only Kubernetes default-deny plus allow-list NetworkPolicies.")
    parser.add_argument("--emit-edge-nftables", help="Write review-only ROS 2 edge nftables egress policy.")
    parser.add_argument("--management-cidr", action="append", default=[], help="Management CIDR to preserve in generated edge policy; repeat as needed.")
    parser.add_argument("--baseline-artifact", help="Path to last-known-clean artifact (hash only; never deployed).")
    parser.add_argument("--observed-artifact", help="Path to currently observed artifact (hash only).")
    args = parser.parse_args()

    if args.emit_k8s_policy or args.emit_edge_nftables:
        try:
            if args.emit_k8s_policy:
                selector = {}
                for pair in args.pod_label:
                    if "=" not in pair:
                        raise ValueError("--pod-label must use key=value.")
                    key, value = pair.split("=", 1)
                    selector[key] = value
                Path(args.emit_k8s_policy).write_text(
                    render_kubernetes_policies(args.namespace, selector, args.approved_cidr),
                    encoding="utf-8"
                )
            if args.emit_edge_nftables:
                Path(args.emit_edge_nftables).write_text(
                    render_edge_nftables(args.approved_cidr, args.management_cidr),
                    encoding="utf-8"
                )
        except (OSError, ValueError) as exc:
            parser.error(str(exc))

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
