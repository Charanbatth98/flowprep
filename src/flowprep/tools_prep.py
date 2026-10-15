"""Preparation & transformation tools (the Alteryx 'Preparation' + 'Join' palettes)."""
from __future__ import annotations
import io
import pandas as pd


def input_csv(inputs, cfg, ctx):
    if cfg.get("data"):
        return pd.read_csv(io.StringIO(cfg["data"]))
    if cfg.get("path"):
        return pd.read_csv(ctx.resolve(cfg["path"]))
    raise ValueError("input_csv needs either 'path' or inline 'data'")


def input_data(inputs, cfg, ctx):
    return pd.DataFrame(cfg.get("rows", []))


def select_cols(df, cfg, ctx):
    cols = [c for c in cfg.get("columns", []) if c in df.columns]
    return df[cols] if cols else df


def rename_cols(df, cfg, ctx):
    return df.rename(columns=cfg.get("mapping", {}))


def filter_rows(df, cfg, ctx):
    expr = (cfg.get("expression") or "").strip()
    return df.query(expr) if expr else df


def formula(df, cfg, ctx):
    out = df.copy()
    out[cfg.get("new_column", "result")] = out.eval(cfg["expression"])
    return out


def sort_rows(df, cfg, ctx):
    by = cfg.get("by", [])
    if isinstance(by, str):
        by = [b.strip() for b in by.split(",") if b.strip()]
    return df.sort_values(by=by, ascending=bool(cfg.get("ascending", True))) if by else df


def summarize(df, cfg, ctx):
    group_by = cfg.get("group_by", [])
    aggs = cfg.get("aggregations", {})  # {"revenue": "sum"}
    if group_by:
        return df.groupby(group_by, as_index=False).agg(aggs)
    return df.agg(aggs).to_frame().T


def join(inputs, cfg, ctx):
    if len(inputs) < 2:
        raise ValueError("join needs two inputs (connect left + right)")
    left, right = inputs[0], inputs[1]
    return pd.merge(left, right, how=cfg.get("how", "inner"),
                    on=cfg.get("on") or None,
                    left_on=cfg.get("left_on") or None,
                    right_on=cfg.get("right_on") or None,
                    suffixes=("_left", "_right"))


def union(inputs, cfg, ctx):
    out = pd.concat(inputs, ignore_index=True)
    return out.drop_duplicates() if cfg.get("distinct") else out


def unique_rows(df, cfg, ctx):
    subset = cfg.get("columns") or None
    return df.drop_duplicates(subset=subset)


def sample_rows(df, cfg, ctx):
    if cfg.get("n"):
        return df.sample(n=min(int(cfg["n"]), len(df)), random_state=int(cfg.get("seed", 42)))
    return df.sample(frac=float(cfg.get("frac", 0.1)), random_state=int(cfg.get("seed", 42)))


def crosstab(df, cfg, ctx):
    out = pd.crosstab(df[cfg["row"]], df[cfg["column"]],
                        values=df[cfg["value"]] if cfg.get("value") else None,
                        aggfunc=cfg.get("aggfunc", "count")).reset_index()
    return out


def cast_types(df, cfg, ctx):
    out = df.copy()
    for col, dtype in cfg.get("types", {}).items():
        if col in out.columns:
            out[col] = out[col].astype(dtype) if dtype != "datetime" else pd.to_datetime(out[col])
    return out


def output_result(df, cfg, ctx):
    return df


TOOLS = {
    "input_csv":  dict(fn=input_csv, inputs=0, category="Input", label="Input CSV",
                       fields={"path": "text", "data": "textarea"}),
    "input_data": dict(fn=input_data, inputs=0, category="Input", label="Input Data (inline)",
                       fields={"rows": "json"}),
    "select":     dict(fn=lambda i, c, x: select_cols(i[0], c, x), inputs=1, category="Preparation", label="Select", fields={"columns": "list"}),
    "rename":     dict(fn=lambda i, c, x: rename_cols(i[0], c, x), inputs=1, category="Preparation", label="Rename", fields={"mapping": "json"}),
    "filter":     dict(fn=lambda i, c, x: filter_rows(i[0], c, x), inputs=1, category="Preparation", label="Filter", fields={"expression": "text"}),
    "formula":    dict(fn=lambda i, c, x: formula(i[0], c, x), inputs=1, category="Preparation", label="Formula", fields={"new_column": "text", "expression": "text"}),
    "sort":       dict(fn=lambda i, c, x: sort_rows(i[0], c, x), inputs=1, category="Preparation", label="Sort", fields={"by": "list", "ascending": "bool"}),
    "summarize":  dict(fn=lambda i, c, x: summarize(i[0], c, x), inputs=1, category="Preparation", label="Summarize (Group By)", fields={"group_by": "list", "aggregations": "json"}),
    "unique":     dict(fn=lambda i, c, x: unique_rows(i[0], c, x), inputs=1, category="Preparation", label="Unique", fields={"columns": "list"}),
    "sample":     dict(fn=lambda i, c, x: sample_rows(i[0], c, x), inputs=1, category="Preparation", label="Sample", fields={"n": "number", "frac": "number", "seed": "number"}),
    "crosstab":   dict(fn=lambda i, c, x: crosstab(i[0], c, x), inputs=1, category="Transform", label="Cross Tab", fields={"row": "text", "column": "text", "value": "text", "aggfunc": "text"}),
    "cast":       dict(fn=lambda i, c, x: cast_types(i[0], c, x), inputs=1, category="Preparation", label="Cast Types", fields={"types": "json"}),
    "join":       dict(fn=join, inputs=2, category="Join", label="Join", fields={"how": "text", "on": "text", "left_on": "text", "right_on": "text"}),
    "union":      dict(fn=union, inputs="many", category="Join", label="Union", fields={"distinct": "bool"}),
    "output":     dict(fn=lambda i, c, x: output_result(i[0], c, x), inputs=1, category="Output", label="Output / Browse", fields={}),
}
