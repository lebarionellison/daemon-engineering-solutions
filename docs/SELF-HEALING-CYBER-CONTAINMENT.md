# DAEMON ACE — Self-Healing Cyber Containment & Leak Prevention

## Intended control loop

**Detect → Contain → Verify → Human-approved recovery → Record evidence**

### 1. Edge Reflex Guard — egress control

- Treat outbound destinations as denied unless an exact hostname or CIDR is in the approved allow-list.
- Apply Kubernetes egress policy to workload pods and a separate host/device firewall adapter to ROS 2 edge devices.
- Keep DNS, telemetry, model endpoints and ROS 2 discovery on explicit, reviewed destination rules.
- A Kubernetes NetworkPolicy is enforced only when the installed CNI implements NetworkPolicy. It does not automatically control host-network traffic or every device-level route.

The reference manifest at `examples/default-deny-egress-networkpolicy.yaml` denies all pod egress in its namespace. Deploy it only in a dedicated/test namespace after reviewing the impact. Add narrowly scoped allow policies for required services before moving production workloads.

### 2. Checkpoint 3 — drift and containment

On a drift, suspicious egress or compromised-container event, the intended production adapter should:
1. Preserve event metadata and relevant telemetry.
2. Apply a pre-approved quarantine policy to the affected workload; do not assume cordoning a node is equivalent to isolating a pod.
3. Keep forensic evidence and record the action result.
4. Retrieve a last-known-clean artifact by immutable identifier and verify its SHA-256 before proposing restoration.

The current `daemon_reflex_guard.py` is a policy evaluator and containment-plan generator. It does not invoke kubectl, change a firewall, cordon nodes or isolate a ROS 2 device. Runtime enforcement requires a separately deployed, authenticated adapter with scoped permissions, audit logging and an operator-defined emergency policy.

### 3. Checkpoint 1 — identity and secret hygiene

Pre-flight now screens for:
- `automountServiceAccountToken: true`
- Common plaintext credential assignments and private-key headers
- Kubernetes workloads without an explicit NetworkPolicy egress boundary

A detected secret must be removed from the artifact and rotated/revoked at its issuer. DAEMON ACE does not print the detected value or silently rewrite it into a replacement. The Worker also suppresses the optional AI proposal call when a plaintext-secret pattern is detected.

### 4. Pre-Flight Twin™ — verify the clean baseline

- Hash the exact UTF-8 configuration bytes with SHA-256.
- Compare the observed artifact with a separately retained, last-known-clean artifact.
- Re-run the security checks and target-environment validation on the candidate.
- Require a named, authorized human approval before restoration or release.
- Record the observed digest, baseline digest, findings, approvals and adapter outcomes in the Receipt of Safety.

**Receipt storage note:** the current Worker stores pre-flight receipts in the configured D1 `receipts` table. This workflow does not currently retrieve clean artifacts or receipts from Cloudflare KV.

## Current implementation boundary

Implemented in this repository:
- Python text-pattern checks in `daemon_ace_preflight.py`
- Server-side manifest checks in Worker `createPreflight`
- A fail-closed Sim-to-Real verification gate that rejects receipts with unresolved CRITICAL/HIGH findings
- `daemon_reflex_guard.py` destination evaluation and containment-plan output
- Browser-based Pre-Flight Twin cyber-containment scenario with simulated quarantine and baseline hashing

Not yet connected:
- Live Kubernetes NetworkPolicy application or admission enforcement
- Live ROS 2 edge firewall/route enforcement
- Automated node cordon or workload quarantine
- Retrieval and restoration of a signed last-known-clean artifact
- Production simulator attestation, human identity/authorization integration or rollback execution

The browser workbench is a demonstration. A generated Receipt of Safety is evidence of checks performed, not proof that live traffic was blocked, a workload was isolated, or a rollback completed. The system must fail closed when enforcement or evidence adapters are unavailable.
