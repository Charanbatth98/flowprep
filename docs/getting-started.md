# Getting started

## Install

```bash
pip install -e .            # core: pandas + numpy only
pip install -e ".[ml]"     # + scikit-learn (Random Forest)
pip install -e ".[dev]"    # + pytest, for contributors
```

## The canvas

1. `flowprep serve`, open http://127.0.0.1:8765
2. Click a tool in the left palette to add it to the canvas.
3. Drag nodes by their header. Connect them by clicking a node's
   **right dot**, then the next node's **left dot**.
4. Click a node to configure it in the Inspector (right panel).
   - `list` fields: comma-separated, e.g. `revenue, visits`
   - `json` fields: JSON, e.g. `{"revenue": "sum"}` for Summarize
   - Filter / Formula use pandas expressions, e.g. `revenue > 1000`,
     `revenue * 1.13`
5. Press **Run workflow**. Click any node afterwards to preview its
   output (first 50 rows) and, for models, its metrics.
6. **Export JSON** to save/share a workflow; **Import JSON** to reload it.

For two-input tools (Join, Union, Spatial Join, Find Nearest), edge order
matters: the first connection is the left/primary input, the second is
the right/secondary input.

## Headless runs

```bash
flowprep run examples/spatial_predictive_workflow.json --output result.csv
```

Exit code is non-zero on any tool error, so it drops cleanly into cron,
CI, or a scheduler.

## Your first spatial + predictive workflow

Open the sample in the canvas ("Load sample workflow"): inline customers
gain a tax formula, a haversine distance from Toronto, and a per-region
summary. The JSON examples in `examples/` add regression, k-means
segmentation and a point-in-polygon spatial join.
