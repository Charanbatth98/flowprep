# Roadmap

## v0.2 - Inputs & outputs
- Input Excel, JSON, GeoJSON, Parquet; Output to Excel/Parquet/database
- Browse tool with full-grid view, column profiling (nulls, distinct, min/max)
- Map preview for geometry columns in the results panel

## v0.3 - Engine
- DuckDB execution push-down for prep tools (out-of-core, 100M+ rows)
- Polars fast path for filter/formula/summarize
- Caching of unchanged upstream nodes between runs

## v0.4 - More tools
- Prep: Multi-row formula, RegEx, Text to Columns, Fuzzy Match, Append Fields
- Spatial: Drive-time / trade-area (OSRM), Geocode (Nominatim), Spatial Match modes, Heat map
- Predictive: Decision Tree, GBM (LightGBM), Time-Series forecast, Model Comparison / AutoML-lite

## v0.5 - Sharing & automation
- Alteryx `.yxmd` importer (best-effort tool mapping)
- KNIME workflow importer (exploration)
- Scheduled runs + a tiny local gallery (share workflows on your own network)
- Docker image

## Principles that won't change
- MIT licensed, local-first, no telemetry
- Spatial + predictive stay in the free core
- Workflows stay plain, portable JSON
