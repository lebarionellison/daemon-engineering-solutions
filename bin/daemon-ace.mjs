#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";

const args = process.argv.slice(2);
const command = args.shift();
const jsonOutput = args.includes("--json");
const value = (flag) => {
  const index = args.indexOf(flag);
  return index >= 0 ? args[index + 1] : undefined;
};
const usage = () => {
  console.log(`DAEMON ACE CLI

Usage:
  daemon-ace preflight ./deploy.yaml [--json]
  daemon-ace fix ./deploy.yaml --goal "Harden this Kubernetes deployment" [--environment staging] [--json]

Commands:
  preflight  Run local text-pattern checks. No API call is made.
  fix        Send the file to the authenticated DAEMON ACE proposal API and save
             a complete proposed replacement beside the source file.

Required for fix:
  DAEMON_ACE_API_TOKEN  Private pilot API token
Optional:
  DAEMON_ACE_API_URL    Worker origin (default: https://daemon-engineering-solutions.lebarionellison.workers.dev)

Fix creates a proposal only. It does not deploy, modify clusters, or approve changes.`);
};
if (!command || command === "--help" || command === "help") { usage(); process.exit(0); }
const file = args.find(x => !x.startsWith("--") && x !== value("--goal") && x !== value("--environment"));
if (!file) { usage(); process.exit(2); }
let manifest;
try { manifest = fs.readFileSync(path.resolve(file), "utf8"); }
catch (error) { console.error("Cannot read manifest:", error.message); process.exit(2); }
if (!manifest.trim() || manifest.length > 18000) { console.error("Configuration must contain 1–18,000 characters."); process.exit(2); }

if (command === "fix") {
  const goal = value("--goal");
  const token = process.env.DAEMON_ACE_API_TOKEN;
  const baseUrl = (process.env.DAEMON_ACE_API_URL || "https://daemon-engineering-solutions.lebarionellison.workers.dev").replace(/\/$/, "");
  if (!goal) { console.error('The --goal argument is required.'); process.exit(2); }
  if (!token) { console.error("Set DAEMON_ACE_API_TOKEN in your shell before running fix."); process.exit(2); }
  let response, data;
  try {
    response = await fetch(baseUrl + "/api/generate", {
      method: "POST",
      headers: { "Authorization": "Bearer " + token, "Content-Type": "application/json" },
      body: JSON.stringify({
        goal,
        currentConfig: manifest,
        environment: value("--environment") || "staging",
        fileName: path.basename(file)
      })
    });
    data = await response.json();
  } catch (error) {
    console.error("DAEMON ACE API request failed:", error.message);
    process.exit(2);
  }
  if (!response.ok || !data?.receipt?.proposed_config) {
    console.error(data?.error || "The proposal service did not return a complete configuration.");
    process.exit(2);
  }
  const receipt = data.receipt;
  const outputPath = path.resolve(file + ".daemon-ace.proposed");
  try {
    fs.writeFileSync(outputPath, receipt.proposed_config, { encoding: "utf8", flag: "wx" });
  } catch (error) {
    console.error("Could not create proposal file (it may already exist):", error.message);
    console.error("Move the existing proposal or choose another source filename, then retry.");
    process.exit(2);
  }
  if (jsonOutput) {
    console.log(JSON.stringify({ receipt, proposed_file: outputPath }, null, 2));
  } else {
    console.log("\nDAEMON ACE · AI PROPOSAL RECEIPT");
    console.log("Receipt:", receipt.id);
    console.log("Status:", receipt.status);
    console.log("Gatekeeper:", receipt.gatekeeper.status);
    console.log("Policy patterns:", receipt.gatekeeper.violations.length);
    console.log("Proposed file:", outputPath);
    console.log("Estimated monthly savings:", receipt.plan.estimated_monthly_savings_usd == null ? "Not calculated — baseline required" : "$" + receipt.plan.estimated_monthly_savings_usd);
    console.log("\nHuman review is required. No deployment or live infrastructure change was performed.");
  }
  process.exit(receipt.gatekeeper.violations.length ? 1 : 0);
}

if (command !== "preflight") { usage(); process.exit(2); }
const lower = manifest.toLowerCase();
const findings = [];
const add = (severity, code, title, recommendation) => findings.push({ severity, code, title, recommendation });
if (/privileged:\s*true/.test(lower)) add("high","PRIVILEGED_CONTAINER","Privileged container enabled","Review whether host-level privileges are required.");
if (/runasnonroot:\s*false/.test(lower) || /runasuser:\s*0\b/.test(lower)) add("high","ROOT_CONTAINER","Container may run as root","Use a non-root identity where supported.");
if (/hostpath:/.test(lower)) add("high","HOST_PATH","HostPath volume detected","Review host filesystem exposure and mount scope.");
if (/image:\s*[^\n]+:latest\b/.test(lower)) add("medium","MUTABLE_IMAGE_TAG","Mutable image tag detected","Pin an image version or digest and verify provenance.");
if (/nodeport|loadbalancer|externalips:/.test(lower)) add("medium","PUBLIC_SERVICE","Potentially exposed service","Review ingress, network policy and external access.");
if (/allowprivilegeescalation:\s*true/.test(lower)) add("medium","PRIVILEGE_ESCALATION","Privilege escalation allowed","Set allowPrivilegeEscalation to false where compatible.");
if (/automountserviceaccounttoken:\s*true/.test(lower)) add("high","SERVICEACCOUNT_TOKEN_AUTOMOUNT","ServiceAccount token auto-mount enabled","Disable automatic token mounting unless required; use a dedicated least-privilege identity.");
if (/(?:AWS_SECRET_ACCESS_KEY|OPENAI_API_KEY|GITHUB_TOKEN|API_KEY|ACCESS_TOKEN|CLIENT_SECRET|SECRET_KEY|PASSWORD)\s*[:=]\s*["']?(?!YOUR_|CHANGEME|REPLACE_ME|<)[A-Za-z0-9_./+=-]{16,}|name:\s*(?:AWS_SECRET_ACCESS_KEY|OPENAI_API_KEY|GITHUB_TOKEN|API_KEY|ACCESS_TOKEN|CLIENT_SECRET|SECRET_KEY|PASSWORD)\s*\n\s*value:\s*["']?(?!YOUR_|CHANGEME|REPLACE_ME|<)[A-Za-z0-9_./+=-]{16,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----/i.test(manifest)) add("high","PLAINTEXT_SECRET_EXPOSURE","Possible hardcoded API key, credential or private key","Remove and rotate the credential; use an approved secret manager. The scanner does not print the value.");
if (/(?:redis|mongodb|postgres(?:ql)?|mysql):\/\//i.test(manifest)) add("high","DATASTORE_TLS_UNVERIFIED","Plaintext datastore URI scheme detected","Use TLS-enabled endpoints and verify certificate validation.");
if (/(?:cluster-admin|resources:\s*\[[^]]*['"]?\*|verbs:\s*\[[^]]*['"]?\*)/i.test(manifest)) add("high","SHADOW_AGENT_EXCESSIVE_RBAC","Potential cluster-wide or wildcard RBAC permissions","Replace broad permissions with namespace-scoped, task-specific roles.");
if (/kind:\s*(deployment|pod|statefulset|daemonset)\b/i.test(manifest) && !/kind:\s*networkpolicy\b/i.test(manifest)) add("high","EGRESS_DEFAULT_DENY_MISSING","No NetworkPolicy egress boundary detected","Generate and review a default-deny egress policy with explicit approved destinations; verify CNI enforcement.");
if (!/resources:/.test(lower) && /kind:\s*(deployment|pod|statefulset)/.test(lower)) add("medium","MISSING_RESOURCES","Resource settings not detected","Define CPU and memory requests and evaluate limits.");
if (!findings.length) add("info","NO_MATCHING_PATTERNS","No listed patterns detected","This does not establish that the manifest is secure.");
const score = Math.max(0,100-findings.reduce((n,f)=>n+(f.severity==="high"?25:f.severity==="medium"?12:0),0));
const receipt = { schema:"daemon-ace.receipt-of-safety.v1", record_type:"local_cli_heuristic_sample", generated_at:new Date().toISOString(), source_file:path.basename(file), analysis:{mode:"text_pattern_heuristics",score,findings}, scope:{live_cluster_connected:false,tests_executed:false,production_change_authorized:false}, proposed_diff_available:false, limitations:["Heuristic text checks only; not a YAML parser","No cluster connection or live scan","No vulnerability scanner","No deployment performed"] };
if (jsonOutput) console.log(JSON.stringify(receipt,null,2));
else {
  console.log("\nDAEMON ACE · PRE-FLIGHT RECEIPT");
  console.log("File:", path.basename(file));
  console.log("Heuristic score:", score + "/100");
  console.log("Findings:", findings.length);
  for (const f of findings) console.log("\n[" + f.severity.toUpperCase() + "] " + f.title + "\n  " + f.recommendation);
  console.log("\nNo live infrastructure was contacted. No deployment was performed. This is not a security rating.");
}
process.exit(findings.some(f=>f.severity==="high")?1:0);
