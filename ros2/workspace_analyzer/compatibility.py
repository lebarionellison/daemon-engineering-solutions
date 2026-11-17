"""Workspace-to-workspace API/dependency diffs and structured ROS 2 QoS validation."""
from __future__ import annotations
import json, re, xml.etree.ElementTree as ET
from pathlib import Path

SKIP={".git","build","install","log",".venv","__pycache__"}
SOURCE_SUFFIX={".py",".cpp",".cc",".cxx",".hpp",".h"}

def _manifest_inventory(root):
    packages={}
    for manifest in sorted(root.rglob("package.xml")):
        if any(part in SKIP for part in manifest.parts): continue
        try:
            node=ET.parse(manifest).getroot()
            name=(node.findtext("name") or manifest.parent.name).strip()
            deps=sorted({(child.text or "").strip() for child in node
                         if child.tag.endswith("_depend") or child.tag=="depend" if (child.text or "").strip()})
            packages[name]={"version":(node.findtext("version") or "").strip(),
                            "path":manifest.parent.relative_to(root).as_posix(),
                            "dependencies":deps}
        except (ET.ParseError,OSError):
            continue
    return packages

def _api_inventory(root, rules_path):
    try: rules=json.loads(Path(rules_path).read_text()).get("rules",[])
    except (OSError,ValueError): rules=[]
    result={}
    for rule in rules:
        pattern=rule.get("pattern")
        if not pattern: continue
        hits=[]
        try: rx=re.compile(pattern,re.MULTILINE)
        except re.error: continue
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in SOURCE_SUFFIX or any(x in SKIP for x in path.parts): continue
            try: body=path.read_text(errors="replace")
            except OSError: continue
            count=len(list(rx.finditer(body)))
            if count: hits.append({"path":path.relative_to(root).as_posix(),"count":count})
        if hits: result[rule["id"]]={"message":rule.get("message",""),"occurrences":sum(x["count"] for x in hits),"locations":hits}
    return result

def compare_workspaces(current, baseline, rules_path):
    """Compare current workspace against a baseline directory; baseline is the before state."""
    now=_manifest_inventory(Path(current).resolve())
    before=_manifest_inventory(Path(baseline).resolve())
    added=sorted(set(now)-set(before)); removed=sorted(set(before)-set(now))
    changed=[]
    for name in sorted(set(now)&set(before)):
        old,new=before[name],now[name]
        add_deps=sorted(set(new["dependencies"])-set(old["dependencies"]))
        drop_deps=sorted(set(old["dependencies"])-set(new["dependencies"]))
        if old["version"]!=new["version"] or add_deps or drop_deps:
            changed.append({"package":name,"version":{"before":old["version"],"after":new["version"]},
                            "dependencies_added":add_deps,"dependencies_removed":drop_deps})
    old_api=_api_inventory(Path(baseline).resolve(),rules_path)
    new_api=_api_inventory(Path(current).resolve(),rules_path)
    api=[]
    for rule_id in sorted(set(old_api)|set(new_api)):
        old=old_api.get(rule_id,{}); new=new_api.get(rule_id,{})
        if old.get("occurrences",0)!=new.get("occurrences",0):
            api.append({"rule_id":rule_id,"message":new.get("message") or old.get("message"),
                        "occurrences_before":old.get("occurrences",0),"occurrences_after":new.get("occurrences",0),
                        "delta":new.get("occurrences",0)-old.get("occurrences",0),
                        "locations_after":new.get("locations",[])})
    return {"comparison_mode":"current-workspace-vs-baseline","baseline_label":Path(baseline).name,
            "current_label":Path(current).name,"packages":{"added":added,"removed":removed,"changed":changed},
            "api_usage_changes":api,
            "summary":{"packages_added":len(added),"packages_removed":len(removed),"packages_changed":len(changed),
                       "api_patterns_changed":len(api)}}

QOS_ENUMS={
 "reliability":{"reliable","best_effort"},
 "durability":{"volatile","transient_local"},
 "history":{"keep_last","keep_all"},
 "liveliness":{"automatic","manual_by_topic"}
}
def validate_qos_profile(path):
    """Validate DAEMON ACE's explicit JSON QoS profile contract and endpoint compatibility."""
    try: data=json.loads(Path(path).read_text())
    except (OSError,ValueError) as exc:
        return {"valid":False,"errors":[{"code":"QOS-JSON-001","message":f"Cannot read QoS JSON profile: {exc}"}],"warnings":[],"profiles":[],"pair_checks":[]}
    errors=[]; warnings=[]
    if data.get("schema")!="daemon-ace.ros2-qos-profile.v1":
        errors.append({"code":"QOS-SCHEMA-001","message":"schema must be daemon-ace.ros2-qos-profile.v1"})
    profiles=data.get("profiles")
    if not isinstance(profiles,list) or not profiles:
        errors.append({"code":"QOS-PROFILES-001","message":"profiles must be a non-empty array"})
        profiles=[]
    seen=set()
    for i,p in enumerate(profiles):
        label=f"profiles[{i}]"
        if not isinstance(p,dict):
            errors.append({"code":"QOS-PROFILE-001","message":f"{label} must be an object"}); continue
        for field in ("topic","endpoint","reliability","durability","history"):
            if not isinstance(p.get(field),str) or not p[field].strip():
                errors.append({"code":"QOS-FIELD-001","message":f"{label}.{field} is required"})
        if p.get("endpoint") not in {"publisher","subscriber"}:
            errors.append({"code":"QOS-ENDPOINT-001","message":f"{label}.endpoint must be publisher or subscriber"})
        for field,allowed in QOS_ENUMS.items():
            if field in p and p[field] not in allowed:
                errors.append({"code":"QOS-ENUM-001","message":f"{label}.{field} must be one of {sorted(allowed)}"})
        if p.get("history")=="keep_last":
            depth=p.get("depth")
            if not isinstance(depth,int) or isinstance(depth,bool) or depth<1:
                errors.append({"code":"QOS-DEPTH-001","message":f"{label}.depth must be a positive integer for keep_last"})
        elif p.get("history")=="keep_all" and "depth" in p:
            warnings.append({"code":"QOS-DEPTH-002","message":f"{label}.depth is ignored with keep_all history"})
        for field in ("deadline_ms","lifespan_ms","lease_duration_ms"):
            if field in p and (not isinstance(p[field],(int,float)) or isinstance(p[field],bool) or p[field]<0):
                errors.append({"code":"QOS-DURATION-001","message":f"{label}.{field} must be a non-negative number"})
        key=(p.get("topic"),p.get("endpoint"))
        if key in seen: errors.append({"code":"QOS-DUPLICATE-001","message":f"Duplicate {key[1]} profile for topic {key[0]}"})
        seen.add(key)
    by_topic={}
    for p in profiles:
        if isinstance(p,dict) and isinstance(p.get("topic"),str):
            by_topic.setdefault(p["topic"],{})[p.get("endpoint")]=p
    pair_checks=[]
    for topic,endpoints in sorted(by_topic.items()):
        pub=endpoints.get("publisher"); sub=endpoints.get("subscriber")
        if not pub or not sub: continue
        compatible=True; reasons=[]
        # ROS 2 request-vs-offered compatibility: subscriber requests no more than publisher offers.
        if pub.get("reliability")=="best_effort" and sub.get("reliability")=="reliable":
            compatible=False; reasons.append("Reliable subscriber requests more than best-effort publisher offers.")
        if pub.get("durability")=="volatile" and sub.get("durability")=="transient_local":
            compatible=False; reasons.append("Transient-local subscriber requests durability not offered by volatile publisher.")
        if compatible and not reasons: reasons.append("Reliability and durability request/offered policies are compatible.")
        pair_checks.append({"topic":topic,"compatible":compatible,"reasons":reasons})
        if not compatible: errors.append({"code":"QOS-COMPAT-001","message":f"{topic}: "+" ".join(reasons)})
    return {"valid":not errors,"errors":errors,"warnings":warnings,"profiles":profiles,"pair_checks":pair_checks}
