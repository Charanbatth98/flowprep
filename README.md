# FlowPrep

**Open-source visual data preparation, spatial and predictive analytics.**

FlowPrep is a modern, local-first alternative to Alteryx-style drag-and-drop
analytics tools - built in the open, with workflows stored as plain JSON.

- **Drag-and-drop canvas** - build workflows visually, no code required
- **Transformation & prep** - filter, formula, join, union, summarize, cross tab, and more
- **Spatial included, free** - distance, buffer, point-in-polygon, spatial join, nearest neighbour
- **Predictive included, free** - linear/logistic regression, k-means, random forest, evaluation
- **Light core** - the engine runs on just pandas + numpy. Heavier libraries are optional extras
- **Yours** - MIT licensed, no account, no telemetry, no cloud lock-in, no per-tool upsells

![Status](https://img.shields.io/badge/status-v0.2.0--alpha-orange) ![License](https://img.shields.io/badge/license-MIT-green) ![Python](https://img.shields.io/badge/python-3.10%2B-blue)

## Quick start

```bash
git clone https://github.com/Charanb23/flowprep.git
cd flowprep
pip install -e .

flowprep serve
# open http://127.0.0.1:8765 and press "Load sample workflow", then "Run workflow"
```

Run a workflow from the command line (great for scheduling / CI):

```bash
flowprep run examples/spatial_predictive_workflow.json --output result.csv
flowprep tools        # list all 29 tools
```

Use it as a Python library:

```python
import json
from flowprep.engine import run_workflow

with open("examples/spatial_join_workflow.json") as f:
    workflow = json.load(f)
result = run_workflow(workflow, base_dir="examples", return_frames=True)
print(result["_frames"]["sum"])
```

## Tools (29)

| Palette | Tools |
|---|---|
| Input / Output | Input CSV, Input Data (inline), Output / Browse |
| Preparation | Select, Rename, Filter, Formula, Sort, Unique, Sample, Cast Types |
| Transform / Join | Summarize (Group By), Cross Tab, Join, Union |
| Spatial | Create Points, Distance, Buffer, Point in Polygon, Centroid, Spatial Join, Find Nearest |
| Predictive | Train/Test Split, Linear Regression, Logistic Regression, K-Means, Random Forest*, Correlation, Evaluate |

\* Random Forest uses scikit-learn: `pip install "flowprep[ml]"`. Everything else
runs on the core install. Full reference: [docs/tools.md](docs/tools.md).

## Why another tool? (vs. KNIME / Alteryx)

KNIME is capable but heavy and Java-centric; Alteryx is polished but closed,
expensive, and charges extra for the spatial/predictive capabilities that
analysts actually need. FlowPrep bets on a different stack:

- **Python-native engine** on pandas / numpy (DuckDB + Polars are on the roadmap for the fast path)
- **Modern, lightweight canvas** in plain HTML/JS - no 2 GB install
- **JSON workflows** you can diff in git, generate with an LLM, and run headlessly anywhere
- **Spatial + predictive in the core**, free forever

## Examples

- [`examples/spatial_predictive_workflow.json`](examples/spatial_predictive_workflow.json) - distance from Toronto, revenue regression, customer segmentation
- [`examples/spatial_join_workflow.json`](examples/spatial_join_workflow.json) - assign customers to East/West region polygons, then total revenue by region
- Sample data lives in [`examples/data/`](examples/data/)

## Documentation

- [Getting started](docs/getting-started.md)
- [Tool reference](docs/tools.md)
- [Architecture](docs/architecture.md)
- [Roadmap](docs/roadmap.md)
- [Contributing](CONTRIBUTING.md) - adding a tool takes ~30 lines

## Roadmap (short version)

Excel / JSON / GeoJSON inputs, database connectors, DuckDB execution engine,
map preview in the canvas, workflow scheduling, Alteryx `.yxmd` importer.
See [docs/roadmap.md](docs/roadmap.md).

## Community

FlowPrep is public and open to everyone:

- **Star the repo** if it's useful, it genuinely helps others find it
- **Discussions** (tab at the top of the repo) - ask questions, share workflows
  in Show and Tell, react to posts
- **Issues** - bug reports and tool ideas, templates included
- **Pull requests** - adding a tool takes ~30 lines, see [CONTRIBUTING.md](CONTRIBUTING.md)

## License

MIT - see [LICENSE](LICENSE).
