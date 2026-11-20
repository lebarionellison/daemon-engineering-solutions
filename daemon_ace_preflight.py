#!/usr/bin/env python3
"""DAEMON ACE local pre-flight pattern scanner.

This is a lightweight text-pattern screen, not a YAML parser, ROS simulator,
Kubernetes admission controller, hardware safety certification, or deployment tool.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

RULES = [
    {
        "id": "SEC-001",
        "category": "SECURITY",
        "severity": "CRITICAL",
        "pattern": r"privileged:\s*true",
        "title": "Privileged container execution enabled",
        "remediation": "Set securityContext.privileged to false and scope device access explicitly.",
    },
    {
        "id": "SEC-002",
        "category": "SECURITY",
        "severity": "HIGH",
        "pattern": r"runAsUser:\s*0",
        "title": "Container configured to run as root (UID 0)",
        "remediation": "Enforce runAsNonRoot: true and specify a non-zero UID.",
    },
    {
        "id": "NET-003",
        "category": "NETWORK",
        "severity": "HIGH",
        "pattern": r"hostNetwork:\s*true",
        "title": "Host network namespace shared with pod",
        "remediation": "Disable hostNetwork and enforce explicit Kubernetes NetworkPolicies.",
    },
    {
        "id": "SUP-004",
        "category": "SUPPLY_CHAIN",
        "severity": "MEDIUM",
        "pattern": r":latest\b",
        "title": "Unpinned container image tag (:latest)",
        "remediation": "Pin container and OTA robot images to immutable SHA256 digests.",
    },
    {
        "id": "FIN-005",
        "category": "FINOPS_GPU",
        "severity": "MEDIUM",
        "pattern": r"nvidia\.com/gpu:\s*[1-9]",
        "title": "Dedicated GPU allocation without MIG or autoscaling policy",
        "remediation": "Evaluate NVIDIA MIG partitioning or scale-to-zero rules to eliminate idle GPU spend.",
    },
    {
        "id": "ROB-006",
        "category": "ROBOTICS_SAFETY",
        "severity": "CRITICAL",
        "pattern": r"max_(linear|angular)_velocity:\s*([3-9]|[1-9]\d+)(\.\d+)?",
        "title": "Uncapped or excessive ROS2 actuator velocity threshold detected",
        "remediation": "Clamp max_linear_velocity and max_angular_velocity within verified lab/hardware safety bounds.",
    },
    {
        "id": "ROB-007",
        "category": "ROBOTICS_NETWORK",
        "severity": "HIGH",
        "pattern": r"(ROS_DOMAIN_ID:\s*0\b|dds_discovery_interface:\s*['\"]?0\.0\.0\.0['\"]?)",
        "title": "Unisolated ROS2 DDS discovery domain or public interface exposure",
        "remediation": "Assign an isolated ROS_DOMAIN_ID and bind CycloneDDS/FastDDS discovery to local loopback or VPN.",
    },
    {
        "id": "SEC-008",
        "category": "IDENTITY",
        "severity": "HIGH",
        "pattern": r"automountServiceAccountToken:\s*true",
        "title": "Kubernetes ServiceAccount token auto-mounted",
        "remediation": "Set automountServiceAccountToken: false and mount a narrowly scoped token only when the workload requires Kubernetes API access.",
    },
    {
        "id": "SEC-009",
        "category": "SECRETS",
        "severity": "CRITICAL",
        "pattern": r"(?:AWS_SECRET_ACCESS_KEY|OPENAI_API_KEY|GITHUB_TOKEN|PRIVATE_KEY)\s*[:=]\s*['\"]?[A-Za-z0-9_./+=-]{16,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
        "title": "Possible plaintext credential or private key in configuration",
        "remediation": "Remove the credential from the artifact, rotate/revoke it at its issuer, and load a replacement from an approved secret manager. Do not reuse the exposed value.",
    },
    {
        "id": "AGT-010",
        "category": "UNTRUSTED_AGENT_INPUT",
        "severity": "HIGH",
        "pattern": r"(?:ignore (?:all )?(?:previous|prior) instructions|reveal (?:the )?system prompt|dump (?:the )?(?:environment|env) variables|print (?:the )?(?:api key|secret)|exfiltrat(?:e|ion))",
        "title": "Possible prompt-injection instruction in untrusted text",
        "remediation": "Treat logs, tickets, GitHub issues and retrieved documents as untrusted data. Delimit and label content, prohibit instruction-following from retrieved text, and require policy checks before tool use. This is a keyword heuristic, not semantic prompt-injection detection.",
    },
    {
        "id": "SEC-012",
        "category": "DATASTORE_TRANSPORT",
        "severity": "HIGH",
        "pattern": r"(?:redis|rediss|mongodb|postgres(?:ql)?|mysql)://",
        "title": "Database connection URI requires transport-security review",
        "remediation": "Verify TLS is enabled and certificate-validated for Redis and database connections; use authenticated secret-manager references. The scanner flags URI schemes for review and does not infer server-side TLS configuration.",
    },
    {
        "id": "OBS-013",
        "category": "OBSERVABILITY_PRIVACY",
        "severity": "HIGH",
        "pattern": r"(?:log_prompts|capture_prompt|log_request_body|log_headers|trace_content|debug_payloads|include_secrets)\s*:\s*(?:true|yes|1)\b",
        "title": "Prompt, request or sensitive payload logging appears enabled",
        "remediation": "Disable raw prompt/body/header capture by default; redact secrets and personal data before telemetry export; restrict retention and access; test redaction with synthetic secrets.",
    },
    {
        "id": "IAM-014",
        "category": "IDENTITY_SCOPE",
        "severity": "HIGH",
        "pattern": r"(?:cluster-admin|resources:\s*\[[^]]*['\"]?\*|verbs:\s*\[[^]]*['\"]?\*)",
        "title": "Potential wildcard or cluster-admin authorization",
        "remediation": "Replace wildcard resources/verbs and cluster-admin bindings with namespace-scoped, task-specific roles and short-lived workload identities.",
    },
    {
        "id": "ROB-015",
        "category": "ROBOTICS_SECURITY",
        "severity": "HIGH",
        "pattern": r"(?:ROS_SECURITY_ENABLE\s*[:=]\s*['\"]?false|allow_unauthenticated\s*:\s*true)",
        "title": "ROS 2 security may be disabled or unauthenticated access enabled",
        "remediation": "Review SROS2/DDS-Security identity, permissions and governance files; require authenticated participants and least-privilege topic permissions where supported.",
    },
    {
        "id": "NET-008",
        "category": "EGRESS_CONTROL",
        "severity": "HIGH",
        "pattern": r"(?!)",
        "title": "Workload has no explicit egress NetworkPolicy / default-deny boundary",
        "remediation": "Add a namespace-scoped default-deny egress NetworkPolicy, then explicitly allow only required DNS and approved service destinations. Validate CNI enforcement before relying on it.",
    },
]


def scan_text(text: str) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for rule in RULES:
        if rule["id"] == "NET-008":
            continue
        if re.search(rule["pattern"], text, flags=re.IGNORECASE):
            findings.append(rule)

    # Require an explicit NetworkPolicy egress boundary for Kubernetes workloads.
    has_workload = re.search(r"(?im)^kind:\s*(?:Deployment|Pod|StatefulSet|DaemonSet)\b", text)
    has_egress_policy = re.search(
        r"(?is)kind:\s*NetworkPolicy.*?policyTypes:\s*(?:\[[^]]*Egress[^]]*\]|(?:\n\s*-\s*Ingress)?\n\s*-\s*Egress).*?egress:",
        text,
    )
    if has_workload and not has_egress_policy:
        findings.append(next(rule for rule in RULES if rule["id"] == "NET-008"))
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run DAEMON ACE cloud, GPU and ROS2 robotics text-pattern pre-flight checks."
    )
    parser.add_argument("configuration", type=Path, help="YAML/configuration file to inspect")
    args = parser.parse_args()

    try:
        content = args.configuration.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"ERROR: cannot read {args.configuration}: {exc}", file=sys.stderr)
        return 2

    findings = scan_text(content)
    print(f"DAEMON ACE PRE-FLIGHT · {args.configuration}")
    print(f"Rules loaded: {len(RULES)}")
    print(f"Findings: {len(findings)}")
    print("-" * 72)

    if not findings:
        print("NO MATCHING PATTERNS DETECTED")
        print("This is not proof that the configuration is secure or hardware-safe.")
        return 0

    for finding in findings:
        print(
            f'[{finding["severity"]}] {finding["id"]} · '
            f'{finding["category"]} · {finding["title"]}'
        )
        print(f'  Remediation: {finding["remediation"]}')

    blocking = [f for f in findings if f["severity"] in {"CRITICAL", "HIGH"}]
    print("-" * 72)
    if blocking:
        print(f"BLOCKED: {len(blocking)} CRITICAL/HIGH finding(s) require engineering review.")
        print("No hardware or infrastructure action was performed.")
        return 1

    print("REVIEW: findings detected; no CRITICAL/HIGH pattern was matched.")
    print("No hardware or infrastructure action was performed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
