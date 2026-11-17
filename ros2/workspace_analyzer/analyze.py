#!/usr/bin/env python3
"""DAEMON ACE ROS workspace analyzer: static review plus optional Docker/colcon builds."""
from __future__ import annotations
import argparse, hashlib, json, re, shutil, subprocess, sys, xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

SCHEMA="daemon-ace.ros2-workspace-report.v1"
VERSION="1.0.0"
DISTROS=("humble","jazzy","lyrical","rolling")
SKIP={".git","build","install","log",".venv","__pycache__"}
SUFFIX={".py",".cpp",".cc",".cxx",".hpp",".h",".yaml",".yml",".xml",".cmake",".txt"}
HERE=Path(__file__).resolve().parent

def files(root):
    return sorted(p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in SUFFIX and not any(x in SKIP for x in p.parts))
def manifests(root):
    return sorted(p for p in root.rglob("package.xml") if not any(x in SKIP for x in p.parts))
def finding(out,severity,category,code,message,path=None,recommendation="",evidence=""):
    out.append({"severity":severity,"category":category,"code":code,"message":message,"path":path,"recommendation":recommendation,"evidence":evidence[:240]})
def workspace_hash(root):
    h=hashlib.sha256()
    for p in sorted(x for x in root.rglob("*") if x.is_file() and not any(z in SKIP for z in x.parts)):
        try: h.update(p.relative_to(root).as_posix().encode()+p.read_bytes())
        except OSError: pass
    return h.hexdigest()
def package_inventory(root,out):
    result=[]
    for p in manifests(root):
        try:
            node=ET.parse(p).getroot()
            name=(node.findtext("name") or p.parent.name).strip()
            deps=sorted({(x.text or "").strip() for x in node if x.tag.endswith("_depend") or x.tag=="depend"})
            result.append({"name":name,"path":p.parent.relative_to(root).as_posix(),"version":(node.findtext("version") or "").strip(),"dependencies":deps})
            for dep in deps:
                if dep not in {"ament_cmake","ament_python","cmake","rosidl_default_generators","rosidl_default_runtime","rclcpp","rclpy","std_msgs","sensor_msgs","geometry_msgs","nav_msgs","tf2","tf2_ros","launch","launch_ros"}:
                    finding(out,"info","dependency","ROS-DEP-EXT-001",f"External dependency '{dep}' requires target-distro resolution.",p.relative_to(root).as_posix(),"Resolve this key with rosdep for each selected ROS distribution.",dep)
        except (ET.ParseError,OSError) as e:
            finding(out,"high","dependency","ROS-PKG-XML-001",f"Unable to parse package manifest: {e}",p.relative_to(root).as_posix(),"Repair package.xml.")
    if not result: finding(out,"high","workspace","ROS-WS-001","No package.xml files were found.","workspace","Provide a workspace containing one or more ROS packages.")
    return result
def inspect_build(root,out):
    for p in root.rglob("CMakeLists.txt"):
        if any(x in SKIP for x in p.parts): continue
        body=p.read_text(errors="replace")
        if re.search(r"find_package\s*\(\s*catkin|\bcatkin_package\s*\(",body):
            finding(out,"high","migration","ROS-BUILD-CATKIN-001","ROS 1 catkin build metadata detected.",p.relative_to(root).as_posix(),"Migrate ROS 2-native packages to ament or document an intentional ROS 1 bridge.")
        if "find_package(ament_cmake" in body and "ament_target_dependencies" not in body:
            finding(out,"medium","build","ROS-BUILD-AMENT-001","ament_cmake found without ament_target_dependencies.",p.relative_to(root).as_posix(),"Review target dependency declarations; this heuristic may not fit every layout.")
def inspect_api(root,out):
    try: rules=json.loads((HERE/"api-migration-rules.json").read_text())["rules"]
    except Exception: rules=[]
    for p in files(root):
        body=p.read_text(errors="replace")
        for r in rules:
            if re.search(r["pattern"],body,re.MULTILINE):
                finding(out,r.get("severity","medium"),"api-migration",r["id"],r["message"],p.relative_to(root).as_posix(),r["recommendation"],r.get("evidence",""))
def inspect_qos(root,out):
    rules=[
      (r"\b(system_default|unknown)\b","medium","ROS-QOS-DEFAULT-001","System-default or unknown QoS policy detected.","Make reliability, durability, history and depth explicit."),
      (r"\b(best_effort|BEST_EFFORT)\b","info","ROS-QOS-RELIABILITY-001","Best-effort reliability policy detected.","Confirm loss tolerance and subscriber compatibility."),
      (r"\b(reliable|RELIABLE)\b","info","ROS-QOS-RELIABILITY-002","Reliable QoS policy detected.","Review latency, retransmission and resource implications."),
      (r"\b(transient_local|TRANSIENT_LOCAL)\b","info","ROS-QOS-DURABILITY-001","Transient-local durability detected.","Confirm publisher lifetime and late-joining subscriber expectations."),
      (r"\b(depth\s*[:=]\s*[0-9]+|keep_last)\b","info","ROS-QOS-HISTORY-001","QoS history/depth configuration detected.","Validate queue depth against message rate, latency and memory.")
    ]
    for p in files(root):
        body=p.read_text(errors="replace")
        for pattern,sev,code,msg,rec in rules:
            m=re.search(pattern,body,re.I)
            if m: finding(out,sev,"dds-qos",code,msg,p.relative_to(root).as_posix(),rec,m.group(0))
def build(root,distro,timeout):
    if not shutil.which("docker"): return {"distro":distro,"status":"not-run","reason":"Docker executable not found."}
    cmd=["docker","run","--rm","-v",f"{root.resolve()}:/ws","-w","/ws",f"ros:{distro}-ros-base","bash","-lc",
      "set -euo pipefail; apt-get update -qq; apt-get install -y --no-install-recommends python3-colcon-common-extensions python3-rosdep; rosdep init 2>/dev/null || true; rosdep update --rosdistro "+distro+" --include-eol-distros; set +u; source /opt/ros/"+distro+"/setup.bash; set -u; rosdep install --from-paths src --ignore-src -r -y --rosdistro "+distro+"; colcon build --event-handlers console_direct+"]
    try:
        p=subprocess.run(cmd,capture_output=True,text=True,timeout=timeout)
        return {"distro":distro,"status":"passed" if p.returncode==0 else "failed","exit_code":p.returncode,"log_tail":(p.stdout+"\n"+p.stderr)[-10000:]}
    except subprocess.TimeoutExpired: return {"distro":distro,"status":"failed","reason":f"Timed out after {timeout}s."}
    except OSError as e: return {"distro":distro,"status":"not-run","reason":str(e)}
def disposition(findings,builds):
    if any(x["severity"]=="high" for x in findings) or any(x["status"]=="failed" for x in builds): return "action-required"
    if any(x["severity"]=="medium" for x in findings): return "review-recommended"
    if builds and all(x["status"]=="passed" for x in builds): return "build-matrix-passed"
    return "static-review-complete"
def markdown(r):
    lines=["# DAEMON ACE ROS Workspace Compatibility Report","",f"- Schema: `{r['schema']}` · version `{r['report_version']}`",f"- Generated: {r['generated_at']}",f"- Workspace SHA-256: `{r['workspace']['sha256']}`",f"- Disposition: **{r['summary']['disposition']}**",f"- Packages: {len(r['workspace']['packages'])}","","## Distribution build matrix","","| Distribution | Result | Detail |","|---|---|---|"]
    for b in r["build_matrix"]: lines.append(f"| {b['distro']} | {b['status']} | {b.get('reason',b.get('exit_code','static-only'))} |")
    lines += ["","## Findings",""]
    for f in r["findings"]: lines += [f"### [{f['severity'].upper()}] {f['code']} — {f['message']}",f"- File: `{f.get('path') or 'workspace'}`",f"- Recommendation: {f['recommendation']}",f"- Evidence: `{f['evidence']}`",""]
    if not r["findings"]: lines.append("No findings from enabled static checks.")
    lines += ["## Validation boundary","","Static checks are heuristics. A distribution is marked passed only when its containerized rosdep and colcon build exits successfully. DDS interoperability, runtime QoS, simulation, hardware, real-time performance and safety qualification require separate tests."]
    return "\n".join(lines)+"\n"
def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("workspace"); ap.add_argument("--distro",dest="distros",action="append",choices=DISTROS)
    ap.add_argument("--build",action="store_true",help="Run rosdep + colcon in official ROS Docker containers.")
    ap.add_argument("--timeout",type=int,default=1800); ap.add_argument("--output",default="daemon-ace-report")
    a=ap.parse_args(); root=Path(a.workspace).resolve()
    if not root.is_dir(): ap.error("workspace directory does not exist")
    distros=a.distros or (list(DISTROS) if a.build else [])
    findings=[]; packages=package_inventory(root,findings); inspect_build(root,findings); inspect_api(root,findings); inspect_qos(root,findings)
    builds=[build(root,d,a.timeout) for d in distros] if a.build else [{"distro":d,"status":"not-run","reason":"Use --build to execute a containerized build."} for d in distros]
    r={"schema":SCHEMA,"report_version":VERSION,"generated_at":datetime.now(timezone.utc).isoformat(),"analyzer":{"name":"DAEMON ACE ROS Workspace Compatibility Analyzer","version":VERSION},"workspace":{"path_label":root.name,"sha256":workspace_hash(root),"packages":packages,"source_file_count":len(files(root))},"targets":distros,"build_matrix":builds,"findings":findings,"summary":{"disposition":disposition(findings,builds),"high":sum(x["severity"]=="high" for x in findings),"medium":sum(x["severity"]=="medium" for x in findings),"info":sum(x["severity"]=="info" for x in findings),"builds_passed":sum(x["status"]=="passed" for x in builds),"builds_failed":sum(x["status"]=="failed" for x in builds),"builds_not_run":sum(x["status"]=="not-run" for x in builds)},"limitations":["Static API and QoS rules are heuristic.","External dependencies require per-distro rosdep resolution.","QoS pattern detection is not live middleware testing.","No simulator, hardware, real-time or safety certification is performed."]}
    out=Path(a.output); out.mkdir(parents=True,exist_ok=True)
    (out/"ros-workspace-compatibility-report.json").write_text(json.dumps(r,indent=2)+"\n")
    (out/"ros-workspace-compatibility-report.md").write_text(markdown(r))
    print(json.dumps({"disposition":r["summary"]["disposition"],"packages":len(packages),"findings":len(findings),"build_matrix":builds,"output":str(out)},indent=2))
    return 1 if r["summary"]["disposition"]=="action-required" else 0
if __name__=="__main__": sys.exit(main())
