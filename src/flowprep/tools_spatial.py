"""Spatial tools - pure Python (no GeoPandas required).

Geometries are carried as WKT strings in a column (default ``geometry``),
so they survive CSV export and play nicely with other tools.
Coordinates are WGS84 lon/lat. Optional: install shapely/geopandas for
heavier GIS work - the core tools below intentionally need neither.
"""
from __future__ import annotations
import math
import numpy as np
import pandas as pd
from ._util import num_float

EARTH_R_KM = 6371.0088


def haversine_km(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_R_KM * math.asin(math.sqrt(a))


def create_points(df, cfg, ctx):
    out = df.copy()
    lat, lon = cfg.get("lat_column", "latitude"), cfg.get("lon_column", "longitude")
    out[cfg.get("geometry_column", "geometry")] = [
        f"POINT ({x} {y})" for x, y in zip(out[lon], out[lat])]
    return out


def distance(df, cfg, ctx):
    out = df.copy()
    lat, lon = cfg["lat_column"], cfg["lon_column"]
    if cfg.get("to_lat_column"):  # distance between two columns on the same row
        vals = [haversine_km(a, b, c, d) for a, b, c, d in
                zip(out[lat], out[lon], out[cfg["to_lat_column"]], out[cfg["to_lon_column"]])]
    else:  # distance to one fixed point
        tlat, tlon = float(cfg["to_lat"]), float(cfg["to_lon"])
        vals = [haversine_km(a, b, tlat, tlon) for a, b in zip(out[lat], out[lon])]
    out[cfg.get("new_column", "distance_km")] = np.round(vals, 4)
    return out


def buffer_point(df, cfg, ctx):
    """Approximate a circular buffer as a 32-gon WKT polygon (good for mapping / overlap checks)."""
    out = df.copy()
    lat, lon, r = cfg["lat_column"], cfg["lon_column"], num_float(cfg, "radius_km", 5)
    geoms = []
    for la, lo in zip(out[lat], out[lon]):
        pts = []
        for k in range(33):
            ang = 2 * math.pi * k / 32
            dlat = (r / EARTH_R_KM) * (180 / math.pi) * math.cos(ang)
            dlon = (r / EARTH_R_KM) * (180 / math.pi) * math.sin(ang) / max(math.cos(math.radians(la)), 1e-9)
            pts.append(f"{lo + dlon:.6f} {la + dlat:.6f}")
        geoms.append("POLYGON ((" + ", ".join(pts) + "))")
    out[cfg.get("geometry_column", "geometry")] = geoms
    return out


def _parse_polygon(wkt: str):
    nums = wkt.replace("POLYGON", "").replace("(", " ").replace(")", " ").replace(",", " ").split()
    vals = [float(v) for v in nums]
    return list(zip(vals[0::2], vals[1::2]))  # [(lon, lat), ...]


def _point_in_poly(lon, lat, poly) -> bool:
    inside, j = False, len(poly) - 1
    for i, (xi, yi) in enumerate(poly):
        xj, yj = poly[j]
        if ((yi > lat) != (yj > lat)) and (lon < (xj - xi) * (lat - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def point_in_polygon(df, cfg, ctx):
    out = df.copy()
    poly = [tuple(p) for p in cfg["polygon"]]  # [[lon, lat], ...] from the config panel
    out[cfg.get("new_column", "inside")] = [
        _point_in_poly(float(lo), float(la), poly)
        for la, lo in zip(out[cfg["lat_column"]], out[cfg["lon_column"]])]
    return out


def centroid(df, cfg, ctx):
    out = df.copy()
    col = cfg.get("geometry_column", "geometry")
    lons, lats = [], []
    for wkt in out[col]:
        poly = _parse_polygon(str(wkt))
        lons.append(float(np.mean([p[0] for p in poly])))
        lats.append(float(np.mean([p[1] for p in poly])))
    out["centroid_lon"], out["centroid_lat"] = lons, lats
    return out


def spatial_join(inputs, cfg, ctx):
    """Points (input 1) x Polygons-as-WKT (input 2): attach polygon attributes to points inside them."""
    if len(inputs) < 2:
        raise ValueError("spatial_join needs points + polygons (two inputs)")
    points, polys = inputs[0].copy(), inputs[1]
    poly_geoms = [_parse_polygon(str(w)) for w in polys[cfg.get("polygon_geometry_column", "geometry")]]
    keep = [c for c in polys.columns if c != cfg.get("polygon_geometry_column", "geometry")]
    matched = []
    for _, row in points.iterrows():
        hit = None
        for idx, poly in enumerate(poly_geoms):
            if _point_in_poly(float(row[cfg["lon_column"]]), float(row[cfg["lat_column"]]), poly):
                hit = idx
                break
        matched.append({c: (polys.iloc[hit][c] if hit is not None else None) for c in keep})
    return pd.concat([points.reset_index(drop=True), pd.DataFrame(matched)], axis=1)


def nearest(inputs, cfg, ctx):
    """For each row in input 1, find the nearest row in input 2 (haversine) and attach its columns."""
    if len(inputs) < 2:
        raise ValueError("nearest needs two inputs")
    a, b = inputs[0].copy(), inputs[1]
    la, lo = cfg["lat_column"], cfg["lon_column"]
    best_idx, best_d = [], []
    b_coords = list(zip(b[la], b[lo]))
    for x, y in zip(a[la], a[lo]):
        dists = [haversine_km(x, y, p, q) for p, q in b_coords]
        k = int(np.argmin(dists))
        best_idx.append(k)
        best_d.append(round(dists[k], 4))
    near = b.iloc[best_idx].reset_index(drop=True).add_suffix("_nearest")
    a = a.reset_index(drop=True)
    a["nearest_distance_km"] = best_d
    return pd.concat([a, near], axis=1)


TOOLS = {
    "create_points": dict(fn=lambda i, c, x: create_points(i[0], c, x), inputs=1, category="Spatial", label="Create Points",
                          fields={"lat_column": "text", "lon_column": "text", "geometry_column": "text"}),
    "distance": dict(fn=lambda i, c, x: distance(i[0], c, x), inputs=1, category="Spatial", label="Distance (Haversine)",
                     fields={"lat_column": "text", "lon_column": "text", "to_lat": "number", "to_lon": "number",
                             "to_lat_column": "text", "to_lon_column": "text", "new_column": "text"}),
    "buffer": dict(fn=lambda i, c, x: buffer_point(i[0], c, x), inputs=1, category="Spatial", label="Buffer",
                   fields={"lat_column": "text", "lon_column": "text", "radius_km": "number", "geometry_column": "text"}),
    "point_in_polygon": dict(fn=lambda i, c, x: point_in_polygon(i[0], c, x), inputs=1, category="Spatial", label="Point in Polygon",
                             fields={"lat_column": "text", "lon_column": "text", "polygon": "json", "new_column": "text"}),
    "centroid": dict(fn=lambda i, c, x: centroid(i[0], c, x), inputs=1, category="Spatial", label="Centroid",
                     fields={"geometry_column": "text"}),
    "spatial_join": dict(fn=spatial_join, inputs=2, category="Spatial", label="Spatial Join (Points in Polygons)",
                         fields={"lat_column": "text", "lon_column": "text", "polygon_geometry_column": "text"}),
    "nearest": dict(fn=nearest, inputs=2, category="Spatial", label="Find Nearest",
                    fields={"lat_column": "text", "lon_column": "text"}),
}
