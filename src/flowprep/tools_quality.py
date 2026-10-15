"""Quality & privacy tools - the palette Alteryx-style tools usually
leave to paid add-ons or hand-written macros.

- ``profile``: one-row-per-column data profile (nulls, distinct, ranges,
  top value) - point it at any stream to understand it before you trust it.
- ``anonymize``: hash / mask / redact / shuffle PII columns in place,
  using only hashlib + numpy, so de-identified data can be shared safely.
- ``data_diff``: compare two versions of a dataset by key and report,
  per key, whether the row was added, removed, changed or is unchanged -
  built-in regression testing for workflows.

Core deps only: pandas + numpy + the standard library.
"""
from __future__ import annotations
import hashlib
import numpy as np
import pandas as pd
from ._util import as_list, num_int


# ---------------------------------------------------------------- profile
def profile(df, cfg, ctx):
    cols = as_list(cfg.get("columns")) or list(df.columns)
    rows = []
    total = len(df)
    for col in cols:
        if col not in df.columns:
            continue
        s = df[col]
        non_null = s.dropna()
        is_num = pd.api.types.is_numeric_dtype(s)
        top_value, top_count = None, 0
        if len(non_null):
            vc = non_null.value_counts()
            top_value, top_count = vc.index[0], int(vc.iloc[0])
        rows.append({
            "column": str(col),
            "dtype": str(s.dtype),
            "rows": int(total),
            "nulls": int(s.isna().sum()),
            "null_pct": round(float(s.isna().mean() * 100), 2) if total else 0.0,
            "distinct": int(s.nunique(dropna=True)),
            "min": float(non_null.min()) if is_num and len(non_null) else (str(non_null.min()) if len(non_null) else None),
            "max": float(non_null.max()) if is_num and len(non_null) else (str(non_null.max()) if len(non_null) else None),
            "mean": round(float(non_null.mean()), 6) if is_num and len(non_null) else None,
            "top_value": str(top_value) if top_value is not None else None,
            "top_count": int(top_count),
        })
    ctx.info[ctx.node_id] = {"profiled_columns": len(rows), "rows": int(total),
                             "columns_with_nulls": sum(1 for r in rows if r["nulls"] > 0),
                             "duplicate_rows": int(df.duplicated().sum())}
    return pd.DataFrame(rows)


# ------------------------------------------------------------- anonymize
def _hash(v):
    if pd.isna(v):
        return None
    return hashlib.sha256(str(v).encode("utf-8")).hexdigest()


def _mask(v):
    if pd.isna(v):
        return None
    s = str(v)
    if "@" in s and "." in s.split("@")[-1]:  # email: keep first char + domain
        local, domain = s.split("@", 1)
        return (local[:1] + "***@" + domain) if local else "***@" + domain
    if len(s) > 4:
        return "*" * (len(s) - 4) + s[-4:]
    return "****"


def anonymize(df, cfg, ctx):
    cols = as_list(cfg.get("columns"))
    if not cols:
        raise ValueError("anonymize needs 'columns' - the PII columns to protect")
    method = str(cfg.get("method") or "hash").strip().lower()
    if method not in ("hash", "mask", "redact", "shuffle"):
        raise ValueError(f"anonymize method must be hash, mask, redact or shuffle (got '{method}')")
    out = df.copy()
    seed = num_int(cfg, "seed", 42)
    for col in cols:
        if col not in out.columns:
            continue
        if method == "hash":
            out[col] = out[col].map(_hash)
        elif method == "mask":
            out[col] = out[col].map(_mask)
        elif method == "redact":
            out[col] = out[col].map(lambda v: None if pd.isna(v) else "[REDACTED]")
        else:  # shuffle: permute values within the column (breaks the link to the row)
            vals = out[col].to_numpy(copy=True)
            np.random.default_rng(seed).shuffle(vals)
            out[col] = vals
    ctx.info[ctx.node_id] = {"anonymized_columns": [c for c in cols if c in df.columns], "method": method}
    return out


# ------------------------------------------------------------- data diff
def _same(a, b) -> bool:
    a_na, b_na = pd.isna(a), pd.isna(b)
    if a_na or b_na:
        return bool(a_na and b_na)
    try:
        return bool(a == b)
    except Exception:
        return str(a) == str(b)


def data_diff(inputs, cfg, ctx):
    if len(inputs) < 2:
        raise ValueError("data_diff needs two inputs (connect the OLD data first, then the NEW data)")
    old, new = inputs[0], inputs[1]
    keys = as_list(cfg.get("key") or cfg.get("keys"))
    if not keys:
        raise ValueError("data_diff needs 'key' - the column(s) that identify a row")
    for k in keys:
        if k not in old.columns or k not in new.columns:
            raise ValueError(f"data_diff key column '{k}' must exist in both inputs")
    compare = as_list(cfg.get("columns")) or [c for c in old.columns if c not in keys and c in new.columns]
    old_idx = old.drop_duplicates(subset=keys).set_index(keys)
    new_idx = new.drop_duplicates(subset=keys).set_index(keys)
    rows, counts = [], {"added": 0, "removed": 0, "changed": 0, "unchanged": 0}

    def key_dict(idx):
        return {k: (idx if len(keys) == 1 else idx[i]) for i, k in enumerate(keys)}

    for idx in new_idx.index:
        if idx not in old_idx.index:
            rows.append({**key_dict(idx), "status": "added", "changed_columns": ""})
            counts["added"] += 1
    for idx in old_idx.index:
        base = key_dict(idx)
        if idx not in new_idx.index:
            rows.append({**base, "status": "removed", "changed_columns": ""})
            counts["removed"] += 1
            continue
        changed = [c for c in compare if not _same(old_idx.loc[idx, c], new_idx.loc[idx, c])]
        status = "changed" if changed else "unchanged"
        counts[status] += 1
        rows.append({**base, "status": status, "changed_columns": ", ".join(changed)})
    ctx.info[ctx.node_id] = {"model": "data_diff", **counts}
    return pd.DataFrame(rows, columns=[*keys, "status", "changed_columns"])


TOOLS = {
    "profile": dict(fn=lambda i, c, x: profile(i[0], c, x), inputs=1, category="Quality",
                    label="Data Profile",
                    fields={"columns": "list"}),
    "anonymize": dict(fn=lambda i, c, x: anonymize(i[0], c, x), inputs=1, category="Quality",
                      label="Anonymize (PII)",
                      fields={"columns": "list", "method": "text", "seed": "number"}),
    "data_diff": dict(fn=data_diff, inputs=2, category="Quality",
                      label="Data Diff (Compare)",
                      fields={"key": "list", "columns": "list"}),
}
