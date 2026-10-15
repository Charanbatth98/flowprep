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
    assert {"Preparation", "Spatial", "Predictive"} <= cats
    assert len(CATALOG) >= 25


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


def test_example_workflow_runs():
    with open(os.path.join(ROOT, "examples", "spatial_predictive_workflow.json")) as f:
        w = json.load(f)
    base = os.path.join(ROOT, "examples")
    res = run_workflow(w, base_dir=base)
    assert res["nodes"]["out"]["row_count"] == 8
    assert "predicted_revenue" in res["nodes"]["out"]["columns"]
