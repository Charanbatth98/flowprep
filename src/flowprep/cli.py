"""Command line: run workflows headlessly, list tools, serve the canvas."""
from __future__ import annotations
import argparse
import json
import os
import sys
import pandas as pd
from .engine import CATALOG, run_workflow, sinks


def main(argv=None):
    p = argparse.ArgumentParser(prog="flowprep", description="FlowPrep - visual data prep, spatial & predictive analytics")
    sub = p.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run", help="Run a workflow JSON file")
    run.add_argument("workflow")
    run.add_argument("--output", help="Write the final node's result to this CSV")
    run.add_argument("--base-dir", default=None, help="Base folder for relative input paths (default: workflow folder)")
    sub.add_parser("tools", help="List every tool")
    serve = sub.add_parser("serve", help="Start the visual canvas")
    serve.add_argument("--port", type=int, default=8765)
    args = p.parse_args(argv)

    if args.cmd == "tools":
        for name, s in sorted(CATALOG.items()):
            print(f"{s['category']:12} {name:20} {s['label']}")
        return 0
    if args.cmd == "serve":
        from .server import main as serve_main
        serve_main(args.port)
        return 0
    if args.cmd == "run":
        with open(args.workflow) as f:
            wf = json.load(f)
        base = args.base_dir or os.path.dirname(os.path.abspath(args.workflow))
        result = run_workflow(wf, base_dir=base, return_frames=True)
        for nid, r in result["nodes"].items():
            print(f"{nid}: {r['row_count']} rows x {len(r['columns'])} cols {r['info'] if r['info'] else ''}")
        if args.output:
            finals = sinks(wf)
            if not finals:
                print("No sink node to write", file=sys.stderr)
                return 1
            last = finals[-1]
            result["_frames"][last].to_csv(args.output, index=False)
            print(f"Wrote {last} -> {args.output}")
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
