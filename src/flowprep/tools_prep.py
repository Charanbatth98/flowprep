"""Preparation & transformation tools (the Alteryx 'Preparation' + 'Join' palettes)."""
from __future__ import annotations
import io
import pandas as pd
from ._util import as_list, num_float, num_int, opt_float, opt_int


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
    seed = num_int(cfg, "seed", 42)
    n = opt_int(cfg, "n")
    if n is not None:
        return df.sample(n=min(n, len(df)), random_state=seed)
    return df.sample(frac=opt_float(cfg, "frac") or 0.1, random_state=seed)


def crosstab(df, cfg, ctx):
    # Count mode (no value column) is the default crosstab - pandas rejects
    # an aggfunc without values, so only pass it when a value is set.
    if cfg.get("value"):
        out = pd.crosstab(df[cfg["row"]], df[cfg["column"]], values=df[cfg["value"]],
                          aggfunc=cfg.get("aggfunc") or "count")
    else:
        out = pd.crosstab(df[cfg["row"]], df[cfg["column"]])
    return out.reset_index()


def _levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if len(a) < len(b):
        a, b = b, a
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def _similarity(a, b) -> float:
    sa, sb = str(a).strip().lower(), str(b).strip().lower()
    if not sa or not sb:
        return 0.0
    return 1.0 - _levenshtein(sa, sb) / max(len(sa), len(sb))


def fuzzy_join(inputs, cfg, ctx):
    """Left join on near-matching text keys (typos, 'Jon' vs 'John').

    Each left row is matched to its single best-scoring right row at or
    above ``threshold`` (0-1, default 0.85); unmatched rows keep null
    right-hand values. Adds ``match_score`` so matches stay auditable -
    unlike a black-box fuzzy macro.
    """
    if len(inputs) < 2:
        raise ValueError("fuzzy_join needs two inputs (connect left + right)")
    left, right = inputs[0], inputs[1]
    lk, rk = cfg.get("left_on"), cfg.get("right_on") or cfg.get("left_on")
    if not lk or lk not in left.columns:
        raise ValueError("fuzzy_join needs 'left_on' - a text column in the left input")
    if not rk or rk not in right.columns:
        raise ValueError("fuzzy_join needs 'right_on' - a text column in the right input")
    threshold = num_float(cfg, "threshold", 0.85)
    right_vals = list(right[rk])
    best_idx, best_score = [], []
    for v in left[lk]:
        scores = [_similarity(v, rv) for rv in right_vals]
        k = int(max(range(len(scores)), key=lambda i: scores[i])) if scores else -1
        if k >= 0 and scores[k] >= threshold:
            best_idx.append(k)
            best_score.append(round(float(scores[k]), 4))
        else:
            best_idx.append(-1)
            best_score.append(None)
    out = left.reset_index(drop=True).copy()
    for c in right.columns:
        suffix = "_right" if c in out.columns else ""
        vals = [right.iloc[i][c] if i >= 0 else None for i in best_idx]
        out[f"{c}{suffix}"] = vals
    out["match_score"] = best_score
    matched = sum(1 for i in best_idx if i >= 0)
    ctx.info[ctx.node_id] = {"fuzzy_join": {"matched": int(matched), "unmatched": int(len(out) - matched),
                                            "threshold": threshold}}
    return out


def window(df, cfg, ctx):
    """Window / multi-row calculations per group: row_number, rank,
    dense_rank, lag, lead, cumsum, rolling_mean, rolling_sum.

    Rows are ordered within each group by ``order_by`` when given
    (the output follows that order); without it, the input order is used.
    """
    op = str(cfg.get("operation") or "lag").strip().lower()
    col = cfg.get("column")
    group_by = as_list(cfg.get("group_by"))
    order_by = cfg.get("order_by") or None
    new_col = cfg.get("new_column") or (f"{op}_{col}" if col else op)
    if op not in ("row_number", "rank", "dense_rank", "lag", "lead", "cumsum", "rolling_mean", "rolling_sum"):
        raise ValueError(f"window operation must be row_number, rank, dense_rank, lag, lead, cumsum, rolling_mean or rolling_sum (got '{op}')")
    if op != "row_number" and (not col or col not in df.columns):
        raise ValueError(f"window needs 'column' - the value column for {op}")
    out = df.copy()
    sort_keys = group_by + ([order_by] if order_by else [])
    if sort_keys:
        out = out.sort_values(by=sort_keys, kind="mergesort").reset_index(drop=True)
    grouped = out.groupby(group_by, sort=False) if group_by else None

    def whole(s):  # single-group fallback: treat the frame as one group
        return s

    if op == "row_number":
        vals = grouped[col or out.columns[0]].cumcount() + 1 if grouped is not None else pd.Series(range(1, len(out) + 1))
    elif op == "rank":
        vals = grouped[col].rank(method="min") if grouped is not None else out[col].rank(method="min")
    elif op == "dense_rank":
        vals = grouped[col].rank(method="dense") if grouped is not None else out[col].rank(method="dense")
    elif op == "lag":
        vals = grouped[col].shift(1) if grouped is not None else out[col].shift(1)
    elif op == "lead":
        vals = grouped[col].shift(-1) if grouped is not None else out[col].shift(-1)
    elif op == "cumsum":
        vals = grouped[col].cumsum() if grouped is not None else out[col].cumsum()
    else:
        w = max(1, num_int(cfg, "window_size", 3))
        fn = "mean" if op == "rolling_mean" else "sum"
        if grouped is not None:
            vals = grouped[col].transform(lambda s: s.rolling(w, min_periods=1).agg(fn))
        else:
            vals = out[col].rolling(w, min_periods=1).agg(fn)
    out[new_col] = vals
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
    "fuzzy_join": dict(fn=fuzzy_join, inputs=2, category="Join", label="Fuzzy Join", fields={"left_on": "text", "right_on": "text", "threshold": "number"}),
    "window":     dict(fn=lambda i, c, x: window(i[0], c, x), inputs=1, category="Transform", label="Window (Rank / Lag / Rolling)", fields={"group_by": "list", "order_by": "text", "column": "text", "operation": "text", "new_column": "text", "window_size": "number"}),
    "union":      dict(fn=union, inputs="many", category="Join", label="Union", fields={"distinct": "bool"}),
    "output":     dict(fn=lambda i, c, x: output_result(i[0], c, x), inputs=1, category="Output", label="Output / Browse", fields={}),
}
