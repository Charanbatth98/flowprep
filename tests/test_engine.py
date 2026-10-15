import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from flowprep.engine import run_workflow, CATALOG  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")


def wf(nodes, edges):
    return {"name": "test", "nodes": nodes, "edges": edges}


def test_catalog_covers_all_three_areas():
    cats = {s["category"] for s in CATALOG.values()}
    assert {"Preparation", "Spatial", "Predictive", "Quality"} <= cats
    assert len(CATALOG) >= 34


def test_prep_pipeline():
    w = wf(
        [{"id": "a", "type": "input_data", "config": {"rows": [
            {"region": "East", "revenue": 100}, {"region": "East", "revenue": 50},
            {"region": "West", "revenue": 70}]}},
         {"id": "b", "type": "formula", "config": {"new_column": "taxed", "expression": "revenue * 1.1"}},
         {"id": "c", "type": "summarize", "config": {"group_by": ["region"], "aggregations": {"taxed": "sum"}}}],
        [{"from": "a", "to": "b"}, {"from": "b", "to": "c"}])
    out = run_workflow(w, return_frames=True)["_frames"]["c"].sort_values("region").reset_index(drop=True)
    assert round(out.loc[0, "taxed"], 2) == 165.0
    assert round(out.loc[1, "taxed"], 2) == 77.0


def test_spatial_distance_and_point_in_polygon():
    w = wf(
        [{"id": "a", "type": "input_data", "config": {"rows": [
            {"city": "Toronto", "latitude": 43.65, "longitude": -79.38},
            {"city": "Vancouver", "latitude": 49.28, "longitude": -123.12}]}},
         {"id": "d", "type": "distance", "config": {
             "lat_column": "latitude", "lon_column": "longitude", "to_lat": 43.65, "to_lon": -79.38, "new_column": "km"}},
         {"id": "p", "type": "point_in_polygon", "config": {
             "lat_column": "latitude", "lon_column": "longitude", "new_column": "in_ontario_box",
             "polygon": [[-80.5, 42.5], [-74, 42.5], [-74, 46.5], [-80.5, 46.5], [-80.5, 42.5]]}}],
        [{"from": "a", "to": "d"}, {"from": "d", "to": "p"}])
    df = run_workflow(w, return_frames=True)["_frames"]["p"]
    assert df.loc[0, "km"] == 0
    assert 3300 < df.loc[1, "km"] < 3400  # Toronto -> Vancouver, haversine
    assert bool(df.loc[0, "in_ontario_box"]) is True
    assert bool(df.loc[1, "in_ontario_box"]) is False


def test_spatial_join_example():
    with open(os.path.join(ROOT, "examples", "spatial_join_workflow.json")) as f:
        w = json.load(f)
    base = os.path.join(ROOT, "examples")
    frames = run_workflow(w, base_dir=base, return_frames=True)["_frames"]
    by_region = dict(zip(frames["sum"]["region_name"], frames["sum"]["revenue"]))
    assert by_region == {"East": 6480, "West": 3200}


def test_predictive_linear_regression_and_kmeans():
    rows = [{"x": i, "y": 2 * i + 1, "z": i % 3} for i in range(20)]
    w = wf(
        [{"id": "a", "type": "input_data", "config": {"rows": rows}},
         {"id": "m", "type": "linear_regression", "config": {"features": ["x"], "target": "y", "prediction_column": "pred"}},
         {"id": "k", "type": "kmeans", "config": {"features": ["x", "z"], "k": 2, "seed": 1, "new_column": "cluster"}}],
        [{"from": "a", "to": "m"}, {"from": "m", "to": "k"}])
    res = run_workflow(w, return_frames=True)
    info = res["nodes"]["m"]["info"]
    assert info["r2"] > 0.999 and abs(info["coefficients"]["x"] - 2) < 1e-4
    assert set(res["_frames"]["k"]["cluster"].unique()) == {0, 1}


def test_crosstab_count_mode_no_value():
    # Regression: count mode (no value column) used to crash with
    # "aggfunc cannot be used without values" - it is the canvas default.
    w = wf(
        [{"id": "a", "type": "input_data", "config": {"rows": [
            {"region": "East", "label": 0}, {"region": "East", "label": 1},
            {"region": "West", "label": 0}]}},
         {"id": "c", "type": "crosstab", "config": {"row": "region", "column": "label"}}],
        [{"from": "a", "to": "c"}])
    df = run_workflow(w, return_frames=True)["_frames"]["c"].set_index("region")
    assert df.loc["East", 0] == 1 and df.loc["East", 1] == 1 and df.loc["West", 1] == 0


def test_blank_numeric_config_uses_defaults():
    # Regression: the canvas sends untouched numeric fields as "" - tools
    # must fall back to their defaults instead of crashing on int('').
    rows = [{"x": i, "g": "a" if i < 3 else "b"} for i in range(20)]
    for tool, cfg in [
            ("sample", {"n": "", "frac": "", "seed": ""}),
            ("kmeans", {"features": ["x"], "k": "", "seed": ""}),
            ("train_test_split", {"train_fraction": "", "seed": ""})]:
        w = wf(
            [{"id": "a", "type": "input_data", "config": {"rows": rows}},
             {"id": "t", "type": tool, "config": cfg}],
            [{"from": "a", "to": "t"}])
        res = run_workflow(w, return_frames=True)
        assert res["nodes"]["t"]["row_count"] > 0, tool


def test_profile_tool():
    w = wf(
        [{"id": "a", "type": "input_data", "config": {"rows": [
            {"name": "Ava", "revenue": 100}, {"name": "Ben", "revenue": None},
            {"name": "Ava", "revenue": 300}]}},
         {"id": "p", "type": "profile", "config": {"columns": []}}],
        [{"from": "a", "to": "p"}])
    res = run_workflow(w, return_frames=True)
    prof = res["_frames"]["p"].set_index("column")
    assert prof.loc["revenue", "nulls"] == 1
    assert abs(prof.loc["revenue", "null_pct"] - 33.33) < 0.01
    assert prof.loc["revenue", "mean"] == 200.0
    assert prof.loc["name", "top_value"] == "Ava" and prof.loc["name", "top_count"] == 2
    assert res["nodes"]["p"]["info"]["duplicate_rows"] == 0


def test_anonymize_hash_mask_redact():
    rows = [{"email": "ava@example.com", "name": "Ava"}, {"email": None, "name": "Ben"}]
    for method, check in [
            ("hash", lambda df: len(df.loc[0, "email"]) == 64 and df.loc[1, "email"] is None),
            ("mask", lambda df: df.loc[0, "email"] == "a***@example.com"),
            ("redact", lambda df: df.loc[0, "email"] == "[REDACTED]" and df.loc[1, "email"] is None)]:
        w = wf(
            [{"id": "a", "type": "input_data", "config": {"rows": rows}},
             {"id": "z", "type": "anonymize", "config": {"columns": ["email"], "method": method, "seed": 1}}],
            [{"from": "a", "to": "z"}])
        df = run_workflow(w, return_frames=True)["_frames"]["z"]
        assert check(df), method
        assert df.loc[0, "name"] == "Ava"  # untouched column


def test_fuzzy_join_matches_typos_and_rejects_far():
    w = wf(
        [{"id": "a", "type": "input_data", "config": {"rows": [
            {"customer": "Jon Smith", "amt": 10}, {"customer": "Zebra Corp", "amt": 20}]}},
         {"id": "b", "type": "input_data", "config": {"rows": [
            {"name": "John Smith", "tier": "gold"}]}},
         {"id": "f", "type": "fuzzy_join", "config": {"left_on": "customer", "right_on": "name", "threshold": 0.8}}],
        [{"from": "a", "to": "f"}, {"from": "b", "to": "f"}])
    res = run_workflow(w, return_frames=True)
    df = res["_frames"]["f"]
    assert df.loc[0, "tier"] == "gold" and df.loc[0, "match_score"] >= 0.8
    assert df.loc[1, "tier"] is None or (isinstance(df.loc[1, "tier"], float) and df.loc[1, "tier"] != df.loc[1, "tier"])
    assert res["nodes"]["f"]["info"]["fuzzy_join"]["matched"] == 1


def test_window_lag_rank_and_rolling():
    rows = [{"g": "East", "d": 1, "v": 10}, {"g": "East", "d": 2, "v": 30},
            {"g": "East", "d": 3, "v": 20}, {"g": "West", "d": 1, "v": 5}]
    def win(op, **extra):
        w = wf(
            [{"id": "a", "type": "input_data", "config": {"rows": rows}},
             {"id": "w", "type": "window", "config": {"group_by": ["g"], "order_by": "d", "column": "v",
                                                      "operation": op, "new_column": "out", **extra}}],
            [{"from": "a", "to": "w"}])
        return run_workflow(w, return_frames=True)["_frames"]["w"]
    lag = win("lag")
    assert lag[lag.g == "East"]["out"].tolist()[1] == 10
    assert str(lag[lag.g == "West"]["out"].tolist()[0]) in ("nan", "None")
    assert win("rank")[lambda d: d.g == "East"]["out"].tolist() == [1.0, 3.0, 2.0]
    roll = win("rolling_mean", window_size=2)
    assert roll[roll.g == "East"]["out"].tolist() == [10.0, 20.0, 25.0]
    assert win("row_number")[lambda d: d.g == "East"]["out"].tolist() == [1, 2, 3]


def test_data_diff_added_removed_changed_unchanged():
    old = [{"id": 1, "v": "a"}, {"id": 2, "v": "b"}, {"id": 3, "v": "c"}]
    new = [{"id": 1, "v": "a"}, {"id": 2, "v": "B"}, {"id": 4, "v": "d"}]
    w = wf(
        [{"id": "a", "type": "input_data", "config": {"rows": old}},
         {"id": "b", "type": "input_data", "config": {"rows": new}},
         {"id": "d", "type": "data_diff", "config": {"key": ["id"], "columns": []}}],
        [{"from": "a", "to": "d"}, {"from": "b", "to": "d"}])
    res = run_workflow(w, return_frames=True)
    by_id = {r["id"]: r for r in res["_frames"]["d"].to_dict("records")}
    assert by_id[1]["status"] == "unchanged"
    assert by_id[2]["status"] == "changed" and by_id[2]["changed_columns"] == "v"
    assert by_id[3]["status"] == "removed" and by_id[4]["status"] == "added"
    info = res["nodes"]["d"]["info"]
    assert info == {"model": "data_diff", "added": 1, "removed": 1, "changed": 1, "unchanged": 1}


def test_example_workflow_runs():
    with open(os.path.join(ROOT, "examples", "spatial_predictive_workflow.json")) as f:
        w = json.load(f)
    base = os.path.join(ROOT, "examples")
    res = run_workflow(w, base_dir=base)
    assert res["nodes"]["out"]["row_count"] == 8
    assert "predicted_revenue" in res["nodes"]["out"]["columns"]
