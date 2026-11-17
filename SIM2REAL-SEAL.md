# DAEMON ACE Simulation-to-Reality Seal

## Purpose

Bind a preflight configuration fingerprint to a stored DAEMON ACE receipt, then compare the exact configuration presented at a downstream gate. A byte-level mismatch is rejected.

## Current Worker endpoints

### Create a preflight fingerprint

`POST /api/preflight`

The existing endpoint accepts JSON with `goal`, `manifest`, and optional `fileName`. It stores the submitted manifest's SHA-256 digest in `receipt.config_integrity.digest`.

The digest covers the exact UTF-8 bytes of the submitted manifest. Do not reformat YAML, change line endings, trim whitespace, or add a newline between fingerprinting and verification.

### Verify the exact configuration

Configure a high-entropy Cloudflare Worker secret named `ACE_ADMISSION_TOKEN`. Never put its value in source control or browser code.

`POST /api/sim2real/verify`

Headers:
- `Content-Type: application/json`
- `Authorization: Bearer <ACE_ADMISSION_TOKEN>`

Body:
```json
{
  "receipt_id": "the-preflight-receipt-uuid",
  "manifest": "the exact original manifest string"
}
```

A changed manifest returns HTTP 409 with `reason: CONFIGURATION_DRIFT`. A matching digest still returns HTTP 409 until the receipt contains a trusted `sim2real_attestation.simulation_status = "passed"` and `sim2real_attestation.human_signoff = true`. Missing secrets, receipts, evidence, or approvals fail closed.

## Critical integration boundary

This endpoint is a receipt verifier, not a native Kubernetes AdmissionReview implementation. It does not independently block Kubernetes scheduling, Jetson boot, motor power, or GPU job launch. A separately deployed validating admission controller or edge agent must call this verifier and deny execution unless the response is explicitly eligible. That enforcement adapter is not included or claimed as shipped here.

The current repository's ROS 2 CI check is a talker/listener messaging smoke test, not Gazebo/Isaac Sim physics validation. The rubric is a versioned specification; the physical safety thresholds must be approved for each robot and operating envelope. A SHA-256 digest is not a digital signature. Production authenticity requires managed signing keys and a signature verification policy.

## Rubric

See [rubric-v1-sim2real.json](./rubric-v1-sim2real.json).
