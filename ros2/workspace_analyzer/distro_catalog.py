#!/usr/bin/env python3
"""Inventory installed ROS distribution packages and public-header API tokens."""
from __future__ import annotations
import argparse, hashlib, json, re, xml.etree.ElementTree as ET
from pathlib import Path

HEADER_SUFFIX={".h",".hh",".hpp",".hxx"}
SKIP={"detail","impl","implementation","internal","test","tests"}
DECLARATIONS=[
 re.compile(r"^\s*(?:class|struct|enum\s+class|enum)\s+([A-Za-z_][A-Za-z0-9_]*)",re.M),
 re.compile(r"^\s*(?:virtual\s+)?[A-Za-z_][A-Za-z0-9_:<> ,*&~]*\s+([A-Za-z_][A-Za-z0-9_]*)\s*\([^;{}]*\)\s*(?:const\s*)?(?:noexcept\s*)?;",re.M)
]
def inventory(root,distro):
 share=root/"share"; include=root/"include"
 packages={}
 if share.is_dir():
  for folder in sorted(x for x in share.iterdir() if x.is_dir()):
   manifests=list(folder.glob("package.xml"))
   if manifests:
    try:
     node=ET.parse(manifests[0]).getroot()
     name=(node.findtext("name") or folder.name).strip()
     packages[name]=(node.findtext("version") or "").strip()
    except (ET.ParseError,OSError): packages[folder.name]=""
   else: packages[folder.name]=""
 headers={}; symbols={}
 if include.is_dir():
  for path in sorted(x for x in include.rglob("*") if x.is_file() and x.suffix.lower() in HEADER_SUFFIX):
   relative=path.relative_to(include).as_posix()
   if any(part.lower() in SKIP for part in path.parts): continue
   try: body=path.read_text(errors="replace")
   except OSError: continue
   headers[relative]=hashlib.sha256(body.encode()).hexdigest()
   found=set()
   for pattern in DECLARATIONS: found.update(pattern.findall(body))
   if found: symbols[relative]=sorted(found)
 flat=sorted({symbol for names in symbols.values() for symbol in names})
 return {"schema":"daemon-ace.ros2-distro-api-catalog.v1","distro":distro,"ros_root":str(root),
         "packages":packages,"headers":headers,"api_symbols_by_header":symbols,"api_symbols":flat,
         "summary":{"package_count":len(packages),"header_count":len(headers),"api_symbol_count":len(flat)},
         "limitations":["Header declaration extraction is regex-based and may miss templates, macros, generated APIs or overload signatures.","Package presence and version inventory is not a binary ABI or runtime compatibility guarantee."]}
def main():
 ap=argparse.ArgumentParser(description=__doc__)
 ap.add_argument("--ros-root",required=True); ap.add_argument("--distro",required=True)
 ap.add_argument("--output",required=True); args=ap.parse_args()
 root=Path(args.ros_root)
 if not root.is_dir(): ap.error("ROS installation root does not exist")
 result=inventory(root,args.distro)
 Path(args.output).write_text(json.dumps(result,indent=2)+"\n")
 print(json.dumps(result["summary"],indent=2))
if __name__=="__main__": main()
