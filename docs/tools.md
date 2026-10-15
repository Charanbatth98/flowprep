# Tool reference

Config keys are exactly what you type in the canvas Inspector or put in a
workflow JSON node's `config`.

## Input / Output
- **Input CSV** (`input_csv`) - `path` (relative to the workflow) or inline `data`.
- **Input Data** (`input_data`) - `rows`: JSON array of objects.
- **Output / Browse** (`output`) - passthrough; marks a result endpoint.

## Preparation
- **Select** (`select`) - `columns` list to keep, in order.
- **Rename** (`rename`) - `mapping` JSON, e.g. `{"old": "new"}`.
- **Filter** (`filter`) - `expression`, pandas query syntax: `revenue > 1000 and region == 'East'`.
- **Formula** (`formula`) - `new_column`, `expression` (pandas eval): `revenue * 1.13`.
- **Sort** (`sort`) - `by` list, `ascending` bool.
- **Unique** (`unique`) - dedupe, optionally on `columns`.
- **Sample** (`sample`) - `n` rows or `frac`, with `seed`.
- **Cast Types** (`cast`) - `types` JSON: `{"revenue": "float", "date": "datetime"}`.

## Transform / Join
- **Summarize** (`summarize`) - `group_by` list + `aggregations` JSON (`{"revenue": "sum"}`; also `mean`, `count`, `min`, `max`, ...).
- **Cross Tab** (`crosstab`) - `row`, `column`, optional `value` + `aggfunc` (leave `value` blank for a plain count cross tab).
- **Join** (`join`) - two inputs; `how` = inner/left/right/outer, key via `on` or `left_on`/`right_on`.
- **Fuzzy Join** (`fuzzy_join`) - two inputs; left join on near-matching text: `left_on` / `right_on` columns are compared with normalized Levenshtein similarity, each left row keeps its best right match at or above `threshold` (0-1, default 0.85), and a `match_score` column makes every match auditable. Unmatched left rows get null right-hand values.
- **Union** (`union`) - stack 2+ inputs; `distinct` to dedupe.
- **Window** (`window`) - per-group window / multi-row calculations: `group_by` list, `order_by` column, value `column`, `operation` = `row_number`, `rank`, `dense_rank`, `lag`, `lead`, `cumsum`, `rolling_mean` or `rolling_sum` (rolling uses `window_size`, default 3), output to `new_column`. Rows are ordered within each group by `order_by` when given.

## Quality & Privacy
- **Data Profile** (`profile`) - one output row per input column: `dtype`, `rows`, `nulls`, `null_pct`, `distinct`, `min`, `max`, `mean`, `top_value`, `top_count`. Optional `columns` list (blank = all columns). The node's info also reports total duplicate rows - point it at any stream before you trust it.
- **Anonymize (PII)** (`anonymize`) - protects the `columns` list in place. `method` = `hash` (SHA-256 hex), `mask` (emails keep first char + domain, other values keep only the last 4 characters), `redact` (`[REDACTED]`), or `shuffle` (permutes values within the column using `seed`, breaking the link to the row). Nulls stay null.
- **Data Diff (Compare)** (`data_diff`) - two inputs: connect the OLD data first, then the NEW data. Rows are matched on the `key` list; output is one row per key with `status` = `added`, `removed`, `changed` or `unchanged`, plus `changed_columns` naming the differing fields (optional `columns` list restricts what is compared; blank = all shared non-key columns). Built for regression-testing workflows and auditing refreshed datasets.

## Spatial (WGS84 lon/lat, geometry as WKT)
- **Create Points** (`create_points`) - builds `POINT (lon lat)` from `lat_column`/`lon_column`.
- **Distance** (`distance`) - haversine km to a fixed `to_lat`/`to_lon`, or between two column pairs (`to_lat_column`/`to_lon_column`).
- **Buffer** (`buffer`) - approximate circular buffer polygon, `radius_km` (32-gon WKT).
- **Point in Polygon** (`point_in_polygon`) - `polygon` as JSON `[[lon, lat], ...]`; adds a boolean column.
- **Centroid** (`centroid`) - mean coordinate of a WKT polygon column.
- **Spatial Join** (`spatial_join`) - points (1st input) get attributes of the polygon (2nd input, WKT `geometry` column) containing them.
- **Find Nearest** (`nearest`) - each row of input 1 gets the nearest row of input 2 (suffixed `_nearest`) + `nearest_distance_km`.

## Predictive
- **Train/Test Split** (`train_test_split`) - adds a `dataset` column (`train`/`test`), `train_fraction`, `seed`.
- **Linear Regression** (`linear_regression`) - `features` list, `target`; adds predictions; reports intercept, coefficients, R2, RMSE.
- **Logistic Regression** (`logistic_regression`) - binary `target`; adds `probability` + `prediction`; reports accuracy. Gradient descent on standardized features.
- **K-Means** (`kmeans`) - `features`, `k`; adds `cluster`; reports cluster sizes.
- **Random Forest** (`random_forest`) - needs `pip install "flowprep[ml]"`; auto classification vs regression; reports score + feature importance.
- **Correlation** (`correlation`) - correlation matrix of numeric (or listed) columns.
- **Evaluate** (`evaluate`) - `actual` vs `prediction` columns -> RMSE / MAE / R2.
