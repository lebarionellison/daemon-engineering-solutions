# DAEMON ACE Control Plane Foundation

This repository now contains the first shared control-plane interfaces:

- **Web:** existing Pre-Flight Twin experience plus server-recorded receipt endpoints.
- **CLI:** `daemon-ace preflight ./deploy.yaml` performs local heuristic checks.
- **GitHub:** a pull-request workflow runs the CLI and uploads a JSON receipt artifact.
- **Slack / Microsoft Teams:** integration contract and setup checklist are documented below; delivery is not active until a workspace webhook/connector and signing/identity controls are configured.

## API

All endpoints are served by the Cloudflare Worker.

- `POST /api/preflight` — JSON body `{"manifest":"..."}`; stores a heuristic receipt in D1.
- `GET /api/receipts/{uuid}` — retrieves a stored receipt.
- `POST /api/approvals` — requires the authenticated private dashboard session; body contains `receipt_id`, `decision` (`approved_for_manual_review` or `rejected`), and optional `note`.
- `POST /api/deployments` — deliberately returns HTTP 501 until a real deployment adapter, authorization policy, audit controls and rollback path are implemented.

An approval is a recorded human decision for manual review only. It does not deploy infrastructure.

## CLI

From this repository:

```bash
node ./bin/daemon-ace.mjs preflight ./deploy.yaml
node ./bin/daemon-ace.mjs preflight ./deploy.yaml --json
```

To make the command available globally while developing from a local clone, run `npm link` in the repository root. After publishing the package to a package registry, the intended global command is:

```bash
daemon-ace preflight ./deploy.yaml
```

The current CLI has no runtime dependencies and performs local text-pattern checks only. It does not parse full YAML, contact a cluster, call external services, or deploy.

## GitHub Pull Request integration

The workflow at `.github/workflows/daemon-ace-preflight.yml` runs the CLI on pull requests and uploads a machine-readable receipt artifact. It does not approve, merge, or deploy a pull request.

## Slack and Microsoft Teams

The shared receipt schema is the payload contract for future workspace notifications. To activate either integration, configure a verified workspace app/webhook, secret storage, signature verification, workspace/channel allowlists, and an authenticated approval callback. Do not place webhook secrets in source control. The current repository does not claim that Slack or Teams notifications are connected.

## D1 migration

Apply `migrations/0002_create_receipts_and_approvals.sql` to the production D1 database before using the receipt and approval API endpoints. Keep the existing leads migration intact.

## Safety and maturity

The current checks are heuristics, not a YAML parser or security scanner. Receipts disclose these limits. No live cluster telemetry, test execution, customer environment access, or deployment adapter is connected by this release.
