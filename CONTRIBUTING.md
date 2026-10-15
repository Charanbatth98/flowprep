# Contributing to FlowPrep

Thanks for helping build an open alternative for visual analytics.

## Dev setup

```bash
git clone <your fork>
cd flowprep
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
flowprep serve   # http://127.0.0.1:8765
```

## Adding a tool (the most valuable kind of PR)

1. Add a function in `src/flowprep/tools_prep.py`, `tools_spatial.py` or
   `tools_predictive.py`. Signature: `fn(inputs, config, ctx) -> DataFrame`.
   `inputs` is a list of DataFrames in edge order. Record metrics/reports
   on `ctx.info[ctx.node_id]`.
2. Register it in that module's `TOOLS` dict with a label, category and
   UI field types (`text`, `number`, `bool`, `list`, `json`, `textarea`).
   The canvas builds its config form automatically from this.
3. Add a test in `tests/test_engine.py`.
4. Document it in `docs/tools.md`.

Ground rules: core tools must work with only pandas + numpy. Anything
heavier (scikit-learn, shapely, duckdb) goes behind an optional extra
with a clear install hint, exactly like the `random_forest` tool.

## Design principles

- Workflows are plain JSON - readable, diffable, version-controllable.
- Local-first. No telemetry, no account, no cloud lock-in.
- Spatial and predictive are core, free features - never an upsell.
