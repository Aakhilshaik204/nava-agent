#!/usr/bin/env python3
"""
Planner Script for Typst PDF Maker Skill.
Parses content manifest and generates build plan JSON.
"""

import os
import sys
import argparse
import json

def plan_document(manifest_path, output_plan_path):
    if not os.path.exists(manifest_path):
        print(f"[ERROR] Manifest not found at {manifest_path}", file=sys.stderr)
        sys.exit(1)

    with open(manifest_path, "r") as f:
        manifest = json.load(f)

    plan = {
        "reused": False,
        "state": "ready",
        "channel": "typst-pdf-maker",
        "base": {
            "kind": "asset",
            "path": "assets/report-entry.typ",
            "title": "Native Professional Report"
        },
        "enhancements": [
            {
                "name": "report-theme",
                "kind": "local-asset",
                "path": "assets/report-theme.typ"
            }
        ],
        "content_features": manifest.get("content_features", {})
    }

    with open(output_plan_path, "w") as f:
        json.dump(plan, f, indent=2)

    print(f"[SUCCESS] Plan written to {output_plan_path}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('manifest_path', help='Path to content manifest JSON')
    parser.add_argument('--output', default='.typst-build-plan.json', help='Output plan path')
    args = parser.parse_args()

    plan_document(args.manifest_path, args.output)
