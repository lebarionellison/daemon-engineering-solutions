# DAEMON ACE Control Plane Foundation

This repository contains the first shared control-plane interfaces and a private AI proposal path.

## Current interfaces

- **Web:** public Pre-Flight X-Ray performs browser-side text-pattern checks and stores a server-side heuristic receipt.
- **AI proposal API:** authenticated `POST /api/generate` calls the configured OpenAI API to produce a complete proposed replacement configuration and records a locked Receipt of Safety in D1.
- **CLI:** `daemon-ace preflight ./deploy.yaml` performs local heuristic checks; `daemon-ace fix ./deploy.yaml --goal "..."` calls the private proposal API and writes a separate proposed file.
- **Human review:** authenticated dashboard approvals record a decision for manual review only.
- **GitHub:** a pull-request workflow runs the CLI and uploads a JSON receipt artifact. It does not approve, merge, or deploy a pull request.
- **Deployment:** `POST /api/deployments` deliberately returns HTTP 501 until a real deployment adapter, authorization policy, audit controls and rollback path are implemented.
- **Slack / Microsoft Teams:** integration contract and setup checklist are documented; delivery is not active until workspace identity and signing controls are configured.

## API

All endpoints are served by the Cloudflare Worker.

- `POST /api/preflight` — JSON body `{"manifest":"..."}`; stores a heuristic receipt in D1.
- `POST /api/generate` — requires `Authorization: Bearer <ACE_GENERATION_TOKEN>`; JSON body includes `goal`, `currentConfig`, optional `environment`, `fileName`, and optional customer-provided `costBaseline`. Calls the configured OpenAI Chat Completions endpoint and stores the proposed complete file plus a locked receipt in D1.
- `GET /api/receipts/{uuid}` — retrieves a stored receipt; AI-generated configuration proposal receipts require an authenticated dashboard session.
- `POST /api/approvals` — requires the authenticated private dashboard session; body contains `receipt_id`, `decision` (`approved_for_manual_review` or `rejected`), and optional `note`.
- `POST /api/deployments` — returns HTTP 501. No deployment adapter is connected.

### Required Worker secrets

Configure these through Cloudflare Worker settings; never commit them to Git:

- `OPENAI_API_KEY` — API key for the model provider.
- `ACE_GENERATION_TOKEN` — private pilot token required by `POST /api/generate` and the CLI.
- `OPENAI_MODEL` — optional model override; defaults to `gpt-4.1`.

The API key remains server-side. The generation token is a temporary private-pilot access control, not a customer identity, subscription, or metered multi-tenant entitlement system. Rotate it if exposed. Add per-customer identity, rate limits, usage metering and billing before offering public self-service generation.

## Proposal and safety semantics

The AI writer produces a **proposal**, not a production-ready or verified configuration. The current gatekeeper performs limited text-pattern checks only. A clean pattern screen is labeled `POLICY_REVIEW_REQUIRED`, never “verified safe.” Known policy patterns are marked `BLOCKED_BY_POLICY_PATTERN`.

Every AI proposal receipt starts in `PENDING_HUMAN_APPROVAL` with `execution_locked: true`. AI proposal receipts are private to authenticated dashboard sessions when retrieved by ID. The approval endpoint blocks approval-for-review while gatekeeper patterns remain unresolved and records a human decision for manual review only; it does not unlock an execution runner. The deployment endpoint remains disabled. No live infrastructure change can be made through this release.

The current checks are not a YAML/Terraform parser, OPA policy evaluation, Kubernetes server-side dry-run, Terraform plan, vulnerability scan, or test execution. Do not rely on them as a complete security gate.

Savings are returned as a modeled estimate only when sufficient customer baseline data is supplied. Otherwise the estimate is null and the missing assumptions are described. No savings are guaranteed.

## CLI

From this repository:

```bash
node ./bin/daemon-ace.mjs preflight ./deploy.yaml
node ./bin/daemon-ace.mjs preflight ./deploy.yaml --json
```

Private pilot proposal command:

```bash
# Set these in your shell; do not commit the token.
export DAEMON_ACE_API_TOKEN="your-private-pilot-token"
export DAEMON_ACE_API_URL="https://daemon-engineering-solutions.lebarionellison.workers.dev"

node ./bin/daemon-ace.mjs fix ./deploy.yaml --goal "Harden this Kubernetes deployment" --environment staging
```

The command writes `deploy.yaml.daemon-ace.proposed` and prints the Receipt of Safety summary. It never overwrites the source file or deploys changes. If the output file already exists, the command stops rather than overwriting it.

The npm package is currently a repository package, not confirmed as published. Publishing requires registry ownership, authentication, package-name availability and a release process. The Python command `pip install daemon-ace` is not implemented or published by this repository.

## GitHub Pull Request integration

The workflow at `.github/workflows/daemon-ace-preflight.yml` runs the CLI and uploads a machine-readable receipt artifact. It does not approve, merge, or deploy a pull request. A GitHub App, webhook signature verification, scoped installation permissions and authenticated PR/check-run integration are still required for the planned end-to-end PR workflow.

## Paid download / Stripe

The intended commercial model is free heuristic scanning with paid access to a hardened proposal bundle. Stripe Payment Links, webhook verification, one-time purchase fulfillment, signed download entitlements and customer-specific CLI credentials are not configured in this repository. Do not expose a shared generation token or deliver paid files based only on a browser redirect. The payment integration must verify Stripe webhook signatures server-side before issuing a time-limited download entitlement.

## D1 migration

Apply `migrations/0002_create_receipts_and_approvals.sql` to the production D1 database before using the receipt and approval API endpoints. Keep the existing leads migration intact.

## Release checklist

1. Configure and test Worker secrets in a non-production environment.
2. Add a real YAML/Terraform parser and deterministic policy engine; add Kubernetes server-side dry-run and Terraform plan in isolated test environments.
3. Add authenticated customer identities, rate limits, usage controls and per-customer API tokens.
4. Connect Stripe Payment Links and verified webhook fulfillment before charging for bundles.
5. Publish the npm CLI only after registry validation, package review and a reproducible release workflow. Build and publish a separate Python distribution only if a `pip install` experience is required.
6. Implement GitHub PR checks and a deployment adapter with least-privilege credentials, immutable artifact hashes, approval identity, policy versioning, expiry, audit trail, rollback plan and explicit customer authorization.
7. Keep production deployment disabled until the complete authorization and validation path is tested end to end.

## Safety and maturity

No live cluster telemetry, production deployment adapter, public paid-download flow, customer billing entitlement, full parser, OPA-backed policy evaluation, Kubernetes dry-run, Terraform plan, or automated rollback is connected by this release.
