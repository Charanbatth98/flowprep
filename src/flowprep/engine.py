"""Workflow engine: executes a JSON workflow as a DAG of tools.

Workflow format (also what the visual canvas exports / imports)::

    {"name": "My workflow",
     "nodes": [{"id": "n1", "type": "input_csv", "config": {"path": "data.csv"}, "x": 40, "y": 40},
               {"id": "n2", "type": "filter", "config": {"expression": "revenue > 100"}}],
     "edges": [{"from": "n1", "to": "n2"}]}

Edges into a two-input tool are ordered: the first edge is the left /
primary input, the second is the right / secondary input.

The engine also computes *metadata propagation*: for every node it reports
the output columns + row count without the UI having to guess - the same
trick that makes Alteryx feel live while you build.
"""
from __future__ import annotations
import os
from dataclasses import dataclass, field
import pandas as pd
from . import tools_prep, tools_spatial, tools_predictive

CATALOG: dict = {}
for _mod in (tools_prep, tools_spatial, tools_predictive):
    for _name, _spec in _mod.TOOLS.items():
        CATALOG[_name] = {**_spec, "type": _name}


@dataclass
class Context:
    base_dir: str = "."
    info: dict = field(default_factory=dict)   # node_id -> model metrics etc.
    node_id: str = ""

    def resolve(self, path: str) -> str:
        return path if os.path.isabs(path) else os.path.join(self.base_dir, path)


def catalog_for_ui() -> list[dict]:
    return [{"type": s["type"], "label": s["label"], "category": s["category"],
             "inputs": str(s["inputs"]), "fields": s["fields"]} for s in CATALOG.values()]


def _topo_order(nodes: dict, edges: list) -> list[str]:
    incoming = {nid: 0 for nid in nodes}
    children: dict[str, list[str]] = {nid: [] for nid in nodes}
    for e in edges:
        incoming[e["to"]] += 1
        children[e["from"]].append(e["to"])
    queue = [nid for nid, d in incoming.items() if d == 0]
    order = []
    while queue:
        nid = queue.pop(0)
        order.append(nid)
        for ch in children[nid]:
            incoming[ch] -= 1
            if incoming[ch] == 0:
                queue.append(ch)
    if len(order) != len(nodes):
        raise ValueError("Workflow has a cycle - remove a looping connection")
    return order


def run_workflow(workflow: dict, base_dir: str = ".", return_frames: bool = False) -> dict:
    """Run every node. Returns per-node results with a data preview + info.

    With ``return_frames=True`` the result also carries ``_frames``
    (node_id -> DataFrame) for programmatic / CLI use - not JSON-safe.
    """
    nodes = {n["id"]: n for n in workflow.get("nodes", [])}
    edges = workflow.get("edges", [])
    ctx = Context(base_dir=base_dir)
    inputs_of: dict[str, list[str]] = {nid: [] for nid in nodes}
    for e in edges:  # preserve edge order = input order for join / spatial tools
        inputs_of[e["to"]].append(e["from"])
    outputs: dict[str, pd.DataFrame] = {}
    results: dict[str, dict] = {}
    for nid in _topo_order(nodes, edges):
        node = nodes[nid]
        spec = CATALOG.get(node["type"])
        if spec is None:
            raise ValueError(f"Unknown tool type: {node['type']}")
        ctx.node_id = nid
        ctx.info.pop(nid, None)
        ins = [outputs[src] for src in inputs_of[nid]]
        df = spec["fn"](ins, node.get("config", {}) or {}, ctx)
        if not isinstance(df, pd.DataFrame):
            df = pd.DataFrame(df)
        outputs[nid] = df
        results[nid] = {
            "columns": [str(c) for c in df.columns],
            "dtypes": {str(c): str(t) for c, t in df.dtypes.items()},
            "row_count": int(len(df)),
            "preview": df.head(100).where(pd.notnull(df), None).to_dict(orient="records"),
            "info": ctx.info.get(nid, {}),
        }
    out = {"workflow": workflow.get("name", "Untitled"), "nodes": results}
    if return_frames:
        out["_frames"] = outputs
    return out


def sinks(workflow: dict) -> list[str]:
    has_out = {e["from"] for e in workflow.get("edges", [])}
    return [n["id"] for n in workflow.get("nodes", []) if n["id"] not in has_out]
