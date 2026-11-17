#!/usr/bin/env python3
"""Compare ROS distribution catalog JSON files in a directory."""
import argparse, json
from pathlib import Path
from compatibility import compare_distro_catalogs

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--catalog-dir",required=True)
    ap.add_argument("--output",default="ros-distro-api-diff.json")
    args=ap.parse_args()
    root=Path(args.catalog_dir)
    catalogs=[json.loads(p.read_text()) for p in sorted(root.glob("ros-distro-catalog-*.json"))]
    if len(catalogs)<2: ap.error("at least two ROS distro catalog files are required")
    result=compare_distro_catalogs(catalogs)
    Path(args.output).write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps({"distributions":result["distributions"],"comparisons":len(result["comparisons"])},indent=2))
if __name__=="__main__": main()
