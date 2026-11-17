#!/usr/bin/env python3
"""Offline-first ROS 2 workspace analyzer for DAEMON ACE.

Static findings are advisory. A distribution build is only marked passed when
Docker actually completes rosdep + colcon successfully for that target.
"""
from __future__ import annotations
import argparse, hashlib, json, re, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parent
RULES = json.loads((ROOT / "compatibility-rules.json").read_text(encoding="utf-8"))
SKIP = {"build", "install", "log", ".git", ".venv", "venv", "node_modules"}
SOURCE_SUFFIXES = {".cpp", ".cc", ".cxx", ".h", ".hpp", ".hh", ".py", ".cmake", ".txt", ".yaml", ".yml"}

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

def workspace_files(root: Path):
    for path in root.rglob("*"):
        if not path.is_file() or any(part in SKIP for part in path.relative_to(root).parts):
            continue
        if path.suffix.lower() in SOURCE_SUFFIXES or path.name in {"package.xml", "CMakeLists.txt"}:
            yield path

def parse_packages(root: Path):
    packages, issues = [], []
    for manifest in root.rglob("package.xml"):
        if any(part in SKIP for part in manifest.relative_to(root).parts):
            continue
        try:
            node = ET.parse(manifest).getroot()
            name = (node.findtext("name") or "").strip()
            if not name:
                raise ValueError("missing <name>")
            deps = []
            for tag in ("depend", "build_depend", "build_export_depend", "exec_depend",
                        "run_depend", "test_depend", "buildtool_depend"):
                deps.extend((x.text or "").strip() for x in node.findall(tag) if (x.text or "").strip())
            packages.append({"name": name, "path": manifest.parent.relative_to(root).as_posix(),
                             "version": (node.findtext("version") or "").strip(),
                             "build_type": (node.findtext("./export/build_type") or "ament_cmake").strip(),
                             "dependencies": sorted(set(deps))})
        except Exception as exc:
            issues.append({"severity": "error", "code": "PACKAGE_XML_PARSE",
                           "file": manifest.relative_to(root).as_posix(), "message": str(exc),
                           "recommendation": "Correct the package manifest XML before attempting a workspace build."})
    names = [p["name"] for p in packages]
    for name in sorted(set(x for x in names if names.count(x) > 1)):
        issues.append({"severity": "error", "code": "DUPLICATE_PACKAGE_NAME", "file": "",
                       "message": f"Package name appears more than once: {name}",
                       "recommendation": "Give each workspace package a unique package name."})
    return sorted(packages, key=lambda p: p["name"]), issues

def scan_sources(root: Path):
    findings = []
    for path in workspace_files(root):
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        rel = path.relative_to(root).as_posix()
        for rule in RULES["api_patterns"]:
            if re.search(rule["pattern"], content, re.MULTILINE):
                findings.append({"severity": rule["severity"], "code": rule["id"], "file": rel,
                                 "message": rule["message"], "recommendation": rule["recommendation"],
                                 "classification": "static-pattern/manual-confirmation"})
        if path.suffix.lower() in {".yaml", ".yml"}:
            low = content.lower()
            if "reliability:" in low or "durability:" in low or "history:" in low:
                if "depth:" not in low and ("keep_last" in low or "keep_all" in low):
                    findings.append({"severity": "warning", "code": "QOS_DEPTH_NOT_EXPLICIT", "file": rel,
                                     "message": "QoS history is declared but depth is not explicit.",
                                     "recommendation": "Set and validate a depth appropriate to the message rate, latency budget and memory constraints.",
                                     "classification": "static-pattern/manual-confirmation"})
            if "best_effort" in low and "reliable" in low:
                findings.append({"severity": "review", "code": "QOS_RELIABILITY_MIX", "file": rel,
                                 "message": "Both BEST_EFFORT and RELIABLE appear in this file; endpoint pairing is not inferred.",
                                 "recommendation": "Check offered/requested QoS compatibility for every publisher/subscriber pair. A BEST_EFFORT offer cannot satisfy a RELIABLE request.",
                                 "classification": "static-pattern/manual-confirmation"})
            if "transient_local" in low and "volatile" in low:
                findings.append({"severity": "review", "code": "QOS_DURABILITY_MIX", "file": rel,
                                 "message": "Both TRANSIENT_LOCAL and VOLATILE appear in this file; endpoint pairing is not inferred.",
                                 "recommendation": "Check publisher-offered versus subscriber-requested durability and late-joiner behavior.",
                                 "classification": "static-pattern/manual-confirmation"})
    return findings

def docker_build(root: Path, distro: str, timeout: int):
    if not (root / "src").is_dir():
        return {"status": "not-run", "reason": "Expected workspace/src directory was not found."}
    command = [
        "docker", "run", "--rm", "-v", f"{root.resolve()}:/workspace", "-w", "/workspace",
        f"ros:{distro}-ros-base", "bash", "-lc",
        "set -euo pipefail; apt-get update -qq; "
        "DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends "
        "python3-rosdep python3-colcon-common-extensions; "
        "rosdep init 2>/dev/null || true; rosdep update; "
        "rosdep install --from-paths src --ignore-src -r -y; "
        f"source /opt/ros/{distro}/setup.bash; colcon build --event-handlers console_direct+"
    ]
    try:
        result = subprocess.run(command, text=True, capture_output=True, timeout=timeout)
        log = (result.stdout + "\n" + result.stderr)[-16000:]
        return {"status": "passed" if result.returncode == 0 else "failed",
                "exit_code": result.returncode, "log_tail": log}
    except FileNotFoundError:
        return {"status": "not-run", "reason": "Docker CLI was not found. Install/start Docker Desktop and retry."}
    except subprocess.TimeoutExpired as exc:
        return {"status": "timed-out", "reason": f"Build exceeded {timeout} seconds.",
                "log_tail": str(exc.stdout or "")[-8000:]}

def main():
    ap = argparse.ArgumentParser(description="Analyze a ROS 2 workspace without uploading source files.")
    ap.add_argument("workspace", type=Path)
    ap.add_argument("--targets", default="humble,jazzy,lyrical,rolling")
    ap.add_argument("--build", action="store_true", help="Run rosdep + colcon builds in isolated ROS Docker containers.")
    ap.add_argument("--timeout", type=int, default=1800)
    ap.add_argument("--json-out", type=Path, default=Path("daemon-ace-ros-report.json"))
    ap.add_argument("--markdown-out", type=Path, default=Path("daemon-ace-ros-report.md"))
    args = ap.parse_args()
    root = args.workspace.resolve()
    if not root.is_dir():
        ap.error(f"Workspace directory does not exist: {root}")
    targets = [x.strip().lower() for x in args.targets.split(",") if x.strip()]
    allowed = set(RULES["supported_build_targets"])
    invalid = sorted(set(targets) - allowed)
    if invalid:
        ap.error(f"Unsupported build target(s): {', '.join(invalid)}. Allowed: {', '.join(sorted(allowed))}")
    packages, issues = parse_packages(root)
    findings = scan_sources(root)
    known = {p["name"] for p in packages}
    unresolved = sorted({dep for p in packages for dep in p["dependencies"]
                         if dep not in known and dep not in {"ament_cmake", "ament_python", "cmake", "python3"}})
    for dep in unresolved:
        issues.append({"severity": "review", "code": "EXTERNAL_DEPENDENCY_RESOLUTION",
                       "file": "", "message": f"External dependency requires rosdep/target-environment resolution: {dep}",
                       "recommendation": "Resolve against the selected ROS distribution using rosdep and verify with colcon; static analysis does not assert package availability."})
    builds = {}
    if args.build:
        for distro in targets:
            builds[distro] = docker_build(root, distro, args.timeout)
    files = []
    for path in workspace_files(root):
        try:
            files.append({"path": path.relative_to(root).as_posix(), "sha256": sha256(path)})
        except OSError:
            pass
    report = {
        "schema": "daemon-ace.ros-workspace-compatibility-report.v1",
        "product": "DAEMON ACE ROS Workspace Compatibility Analyzer",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "workspace": root.name,
        "source_handling": "Local analysis only; source files are not uploaded by this CLI.",
        "targets": targets,
        "packages": packages,
        "package_count": len(packages),
        "external_dependencies_requiring_resolution": unresolved,
        "static_findings": issues + findings,
        "static_analysis_boundary": "Heuristic review only. It does not prove API compatibility, dependency availability, runtime behavior, QoS endpoint compatibility, simulator fidelity or hardware safety.",
        "builds": builds if args.build else {d: {"status": "not-run", "reason": "Pass --build to run Docker rosdep + colcon validation."} for d in targets},
        "source_fingerprints": files
    }
    args.json_out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    counts = {level: sum(1 for f in report["static_findings"] if f["severity"] == level)
              for level in ("error", "warning", "review")}
    lines = ["# DAEMON ACE ROS Workspace Compatibility Report", "",
             f"- Generated: {report['generated_at']}", f"- Workspace: {root.name}",
             f"- Packages discovered: {len(packages)}", f"- Targets: {', '.join(targets)}",
             f"- Static findings: {counts}", "", "## Package inventory", ""]
    lines += [f"- **{p['name']}** ({p['build_type']}) — {', '.join(p['dependencies']) or 'no declared dependencies'}" for p in packages] or ["- No package.xml files found."]
    lines += ["", "## Static findings", ""]
    lines += [f"- **{f['severity'].upper()} · {f['code']}** — {f['file']}: {f['message']}\n  - Recommendation: {f['recommendation']}" for f in report["static_findings"]] or ["- No configured static patterns matched."]
    lines += ["", "## Distribution builds", ""]
    lines += [f"- **{distro}: {data['status']}**" + (f" — {data.get('reason','')}" if data.get("reason") else "") for distro, data in report["builds"].items()]
    lines += ["", "## Validation boundary", "", report["static_analysis_boundary"], "",
              "A build passes only when the actual target container completes rosdep and colcon. Review logs, package APIs, DDS/QoS endpoint pairs, simulator tests and hardware qualification separately."]
    args.markdown_out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"json_report": str(args.json_out), "markdown_report": str(args.markdown_out),
                      "packages": len(packages), "findings": counts, "builds": {k:v["status"] for k,v in report["builds"].items()}}, indent=2))
    if any(x["status"] == "failed" for x in builds.values()):
        return 2
    return 0

if __name__ == "__main__":
    sys.exit(main())
