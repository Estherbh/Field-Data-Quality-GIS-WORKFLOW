"""Step 3 - Spatial quality control with GeoPandas and Shapely.

Presence, validity and location are tested separately so that "no geometry",
"broken geometry" and "geometry in the wrong place" never end up in the same
bucket.

Rules applied here
------------------
presence     missing_geometry
validity     invalid_geometry
geography    geometry_out_of_study_area
consistency  geometry_attribute_mismatch, area_attribute_mismatch
topology     spatial_overlap
"""

from __future__ import annotations

import geopandas as gpd
import pandas as pd
from shapely import wkt
from shapely.errors import GEOSException
from shapely.validation import explain_validity

import config as cfg
from geoutils import geodesic_area_ha, geodesic_distance_m, study_area_polygon
from quality_control import collect, concat_issues, empty_issues


def _parse_wkt(value):
    """Parse a WKT string, returning None when it is absent or unreadable."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    try:
        return wkt.loads(str(value))
    except (GEOSException, TypeError, ValueError):
        return None


def build_geodataframe(frame: pd.DataFrame) -> gpd.GeoDataFrame:
    """Attach the parsed geometries to the parsed attribute table."""
    geometries = [_parse_wkt(value) for value in frame["geometry"]]
    return gpd.GeoDataFrame(frame.drop(columns="geometry"), geometry=geometries, crs=cfg.CRS)


# ---------------------------------------------------------------------------
# Rules
# ---------------------------------------------------------------------------


def check_geometry_presence_and_validity(gdf: gpd.GeoDataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """Split geometries into missing / invalid / usable and report the first two."""
    missing = gdf.geometry.isna() | gdf.geometry.is_empty
    present = ~missing
    invalid = present & ~gdf.geometry.is_valid
    usable = present & ~invalid

    reason = gdf.geometry.map(
        lambda geom: "" if geom is None or geom.is_empty else explain_validity(geom)
    )
    issues = concat_issues(
        [
            collect(gdf, missing, "missing_geometry", "geometry is null or empty"),
            collect(gdf, invalid, "invalid_geometry", reason),
        ]
    )
    return issues, usable


def check_geometry_location(gdf: gpd.GeoDataFrame, usable: pd.Series) -> pd.DataFrame:
    """A usable polygon must lie entirely inside the study area."""
    study_area = study_area_polygon()
    outside = usable & ~gdf.geometry.within(study_area)
    detail = gdf.geometry.map(
        lambda geom: "" if geom is None or geom.is_empty
        else "polygon bounds: " + ", ".join(f"{value:.4f}" for value in geom.bounds)
    )
    return collect(gdf, outside, "geometry_out_of_study_area", detail)


def check_geometry_attribute_consistency(gdf: gpd.GeoDataFrame, usable: pd.Series) -> pd.DataFrame:
    """The polygon must sit where latitude/longitude say it does."""
    comparable = usable & gdf["latitude_num"].notna() & gdf["longitude_num"].notna()
    distances = pd.Series(0.0, index=gdf.index)
    for index in gdf.index[comparable]:
        point = gdf.geometry.loc[index].representative_point()
        distances.loc[index] = geodesic_distance_m(
            gdf["longitude_num"].loc[index], gdf["latitude_num"].loc[index], point.x, point.y
        )
    mismatch = comparable & (distances > cfg.POINT_GEOMETRY_MAX_DISTANCE_M)
    detail = distances.map(lambda d: f"{d:,.0f} m between the point and the polygon")
    return collect(gdf, mismatch, "geometry_attribute_mismatch", detail)


def check_area_consistency(gdf: gpd.GeoDataFrame, usable: pd.Series) -> pd.DataFrame:
    """The declared area must match the area computed from the polygon."""
    comparable = usable & gdf["area_ha_num"].notna() & (gdf["area_ha_num"] > 0)
    computed = pd.Series(float("nan"), index=gdf.index)
    for index in gdf.index[comparable]:
        computed.loc[index] = geodesic_area_ha(gdf.geometry.loc[index])
    gap = (gdf["area_ha_num"] - computed).abs() / computed
    mismatch = comparable & (gap > cfg.AREA_MISMATCH_TOLERANCE)
    detail = pd.Series(
        [
            f"declared {declared:.2f} ha vs computed {value:.2f} ha"
            if pd.notna(value) else ""
            for declared, value in zip(gdf["area_ha_num"], computed)
        ],
        index=gdf.index,
    )
    return collect(gdf, mismatch, "area_attribute_mismatch", detail)


def check_overlaps(gdf: gpd.GeoDataFrame, usable: pd.Series) -> tuple[pd.DataFrame, gpd.GeoDataFrame]:
    """Detect parcels that share more than a marginal part of their surface."""
    candidates = gdf.loc[usable, ["source_row", "record_id", "geometry"]].copy()
    empty_overlaps = gpd.GeoDataFrame(
        columns=["record_id_a", "record_id_b", "overlap_ha", "overlap_ratio", "geometry"],
        geometry="geometry",
        crs=cfg.CRS,
    )
    if len(candidates) < 2:
        return empty_issues(), empty_overlaps

    pairs = gpd.sjoin(candidates, candidates, how="inner", predicate="intersects")
    pairs = pairs[pairs["source_row_left"] < pairs["source_row_right"]]

    geometry_by_row = dict(zip(candidates["source_row"], candidates.geometry))
    id_by_row = dict(zip(candidates["source_row"], candidates["record_id"]))

    overlap_rows, flagged = [], {}
    for row_a, row_b in zip(pairs["source_row_left"], pairs["source_row_right"]):
        geom_a, geom_b = geometry_by_row[row_a], geometry_by_row[row_b]
        intersection = geom_a.intersection(geom_b)
        if intersection.is_empty:
            continue
        overlap_ha = geodesic_area_ha(intersection)
        smaller_ha = min(geodesic_area_ha(geom_a), geodesic_area_ha(geom_b))
        ratio = overlap_ha / smaller_ha if smaller_ha else 0.0
        if ratio < cfg.OVERLAP_MIN_RATIO:
            continue
        overlap_rows.append(
            {
                "record_id_a": id_by_row[row_a],
                "record_id_b": id_by_row[row_b],
                "overlap_ha": round(overlap_ha, 3),
                "overlap_ratio": round(ratio, 3),
                "geometry": intersection,
            }
        )
        flagged.setdefault(row_a, []).append((id_by_row[row_b], overlap_ha, ratio))
        flagged.setdefault(row_b, []).append((id_by_row[row_a], overlap_ha, ratio))

    if not overlap_rows:
        return empty_issues(), empty_overlaps

    detail = pd.Series("", index=gdf.index)
    for index, row in zip(gdf.index, gdf["source_row"]):
        if row in flagged:
            partners = ", ".join(
                f"{other} ({area:.2f} ha, {ratio:.0%} of the smaller parcel)"
                for other, area, ratio in flagged[row]
            )
            detail.loc[index] = f"overlaps {partners}"
    issues = collect(gdf, gdf["source_row"].isin(flagged), "spatial_overlap", detail)
    overlaps = gpd.GeoDataFrame(overlap_rows, geometry="geometry", crs=cfg.CRS)
    return issues, overlaps


def run_spatial_checks(gdf: gpd.GeoDataFrame) -> tuple[pd.DataFrame, gpd.GeoDataFrame]:
    """Run every spatial rule; return the issues and the overlap polygons."""
    presence_issues, usable = check_geometry_presence_and_validity(gdf)
    overlap_issues, overlaps = check_overlaps(gdf, usable)
    issues = concat_issues(
        [
            presence_issues,
            check_geometry_location(gdf, usable),
            check_geometry_attribute_consistency(gdf, usable),
            check_area_consistency(gdf, usable),
            overlap_issues,
        ]
    )
    return issues, overlaps


if __name__ == "__main__":
    from quality_control import load_raw, parse_fields

    data = build_geodataframe(parse_fields(load_raw()))
    found, overlapping = run_spatial_checks(data)
    print(f"{len(found)} spatial issues on {found['source_row'].nunique()} records")
    print(found["issue_code"].value_counts().to_string())
    print(f"{len(overlapping)} overlapping pairs")
