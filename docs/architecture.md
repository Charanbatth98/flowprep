# Architecture

```
flowprep/
  src/flowprep/
    engine.py          DAG executor + tool catalog + metadata propagation
    tools_prep.py      Input, Preparation, Transform, Join tools
    tools_spatial.py   Spatial tools (pure Python, WKT geometry column)
    tools_predictive.py Predictive tools (numpy-first, sklearn optional)
    server.py          Local canvas server (stdlib http.server only)
    cli.py             flowprep run | tools | serve
    web/index.html     The canvas: vanilla JS, zero build step, zero deps
  examples/            Runnable JSON workflows + sample CSV data
  tests/               Engine tests for every palette
```

## Core ideas

**Workflows are data.** A workflow is a JSON dict of `nodes`
(`id`, `type`, `config`, canvas `x/y`) and ordered `edges`. That makes
workflows diffable, generatable, testable and runnable anywhere -
canvas, CLI or library.

**Tools are functions.** `fn(inputs: list[DataFrame], config, ctx) -> DataFrame`.
Two-input tools receive inputs in edge order. A tool registers itself in
its module's `TOOLS` dict with a label, category and UI field schema;
the canvas generates its config form from that schema automatically.

**Metadata propagation.** After execution the engine reports every node's
columns, dtypes, row count, a 100-row preview and any model info
(`ctx.info`) - this is what lets the UI show live results per node,
the same trick that makes commercial tools feel responsive while building.

**Geometry without GIS lock-in.** Spatial tools carry geometry as WKT text
(`POINT (...)`, `POLYGON ((...))`) in a normal column, in WGS84 lon/lat.
It exports to CSV, imports anywhere, and needs no GeoPandas. Heavier GIS
can be layered on later behind the `geo` extra.

**Light core, optional muscle.** Core = pandas + numpy. scikit-learn,
shapely/geopandas and duckdb/polars are optional extras; a tool that
needs one must fail with a clear install hint (see `random_forest`).

## Execution

Nodes run in topological order (cycles are rejected with a readable
error). Runs are in-process and in-memory in v0.1; the DuckDB engine on
the roadmap will push prep operations down to SQL for out-of-core data
behind the same tool interface.
