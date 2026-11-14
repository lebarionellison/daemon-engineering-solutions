#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";

const [command, file, ...flags] = process.argv.slice(2);
const jsonOutput = flags.includes("--json");
const usage = () => {
  console.log("DAEMON ACE CLI (local heuristic preview)\n\nUsage:\n  daemon-ace preflight ./deploy.yaml [--json]\n\nThis command reads the file locally. It does not contact a cluster or deploy changes.");
};
if (!command || command === "--help" || command === "help") { usage(); process.exit(0); }
if (command !== "preflight" || !file) { usage(); process.exit(2); }
let manifest;
try { manifest = fs.readFileSync(path.resolve(file), "utf8"); }
catch (error) { console.error("Cannot read manifest:", error.message); process.exit(2); }
if (!manifest.trim() || manifest.length > 20000) { console.error("Manifest must contain 1–20,000 characters."); process.exit(2); }
const lower = manifest.toLowerCase();
const findings = [];
const add = (severity, code, title, recommendation) => findings.push({ severity, code, title, recommendation });
if (/privileged:\s*true/.test(lower)) add("high","PRIVILEGED_CONTAINER","Privileged container enabled","Review whether host-level privileges are required.");
if (/runasnonroot:\s*false/.test(lower) || /runasuser:\s*0\b/.test(lower)) add("high","ROOT_CONTAINER","Container may run as root","Use a non-root identity where supported.");
if (/hostpath:/.test(lower)) add("high","HOST_PATH","HostPath volume detected","Review host filesystem exposure and mount scope.");
if (/image:\s*[^\n]+:latest\b/.test(lower)) add("medium","MUTABLE_IMAGE_TAG","Mutable image tag detected","Pin an image version or digest and verify provenance.");
if (/nodeport|loadbalancer|externalips:/.test(lower)) add("medium","PUBLIC_SERVICE","Potentially exposed service","Review ingress, network policy and external access.");
if (/allowprivilegeescalation:\s*true/.test(lower)) add("medium","PRIVILEGE_ESCALATION","Privilege escalation allowed","Set allowPrivilegeEscalation to false where compatible.");
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
