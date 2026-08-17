"""Step 1 - Generate the synthetic raw field dataset.

The script creates 100 fictitious parcel records for three fictitious sites,
then deliberately injects a controlled list of data-quality problems so that the
rest of the pipeline has something real to detect.

Every value produced here is artificial. No operational, organisational or
otherwise confidential data are used (see README - Confidentiality).

Outputs
-------
data/raw/field_data_raw.csv       raw attribute table, geometry stored as WKT
data/raw/field_data_raw.geojson   same records as a GeoJSON FeatureCollection
data/raw/injected_errors.csv      ground truth of the injected problems
data/synthetic/study_area.geojson fictitious study area boundary
data/synthetic/sites.geojson      fictitious site boundaries
"""

from __future__ import annotations

import json
import math
from datetime import date, timedelta

import numpy as np
import pandas as pd
from shapely.affinity import translate
from shapely.geometry import Polygon, mapping

import config as cfg
from geoutils import geodesic_area_ha, metres_to_degrees, site_polygons, study_area_polygon

# ---------------------------------------------------------------------------
# Parcel construction
# ---------------------------------------------------------------------------


def _make_parcel(rng: np.random.Generator, lon: float, lat: float, target_area_ha: float) -> Polygon:
    """Build a slightly irregular, rotated parcel centred on (lon, lat)."""
    side_m = math.sqrt(target_area_ha * 10_000.0)
    aspect = float(rng.uniform(0.75, 1.35))
    half_width = side_m * aspect / 2.0
    half_height = side_m / aspect / 2.0
    theta = float(rng.uniform(0.0, math.pi / 2.0))

    corners_m = []
    for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        jitter_x = float(rng.uniform(-0.07, 0.07)) * side_m
        jitter_y = float(rng.uniform(-0.07, 0.07)) * side_m
        x = sx * half_width + jitter_x
        y = sy * half_height + jitter_y
        corners_m.append((x * math.cos(theta) - y * math.sin(theta),
                          x * math.sin(theta) + y * math.cos(theta)))

    coords = []
    for x_m, y_m in corners_m:
        delta_lon, delta_lat = metres_to_degrees(1.0, lat)
        coords.append((lon + x_m * delta_lon, lat + y_m * delta_lat))
    return Polygon(coords)


def _bowtie(polygon: Polygon) -> Polygon:
    """Return a self-intersecting version of a parcel (invalid geometry)."""
    coords = list(polygon.exterior.coords)[:-1]
    coords[2], coords[3] = coords[3], coords[2]  # crosses two edges of the ring
    return Polygon(coords)


def _recentre(polygon: Polygon, lon: float, lat: float) -> Polygon:
    """Move a polygon so that its centroid sits on (lon, lat)."""
    centroid = polygon.centroid
    return translate(polygon, xoff=lon - centroid.x, yoff=lat - centroid.y)


# ---------------------------------------------------------------------------
# Clean dataset
# ---------------------------------------------------------------------------


def _site_cells(rng: np.random.Generator, bounds: tuple[float, float, float, float],
                count: int) -> list[tuple[float, float, float, float]]:
    """Split a site into shuffled cells, one per parcel.

    Field parcels are spread across a site rather than piled up at random, so a
    jittered grid keeps the synthetic landscape realistic and guarantees that the
    only overlaps in the dataset are the ones injected on purpose.
    """
    minx, miny, maxx, maxy = bounds
    columns = math.ceil(math.sqrt(count))
    rows = math.ceil(count / columns)
    cell_width = (maxx - minx) / columns
    cell_height = (maxy - miny) / rows
    cells = [(column, row) for row in range(rows) for column in range(columns)]
    rng.shuffle(cells)
    return [
        (minx + (column + 0.5) * cell_width, miny + (row + 0.5) * cell_height,
         cell_width, cell_height)
        for column, row in cells[:count]
    ]


def build_clean_records(rng: np.random.Generator) -> list[dict]:
    """Create the 100 error-free synthetic records."""
    date_min = date.fromisoformat(cfg.SURVEY_DATE_MIN)
    date_max = date.fromisoformat(cfg.SURVEY_DATE_MAX)
    span_days = (date_max - date_min).days

    records: list[dict] = []
    for site, (start, end) in cfg.SITE_BLOCKS.items():
        cells = _site_cells(rng, cfg.SITES[site], end - start)
        for index in range(start, end):
            centre_lon, centre_lat, cell_width, cell_height = cells[index - start]
            target_area = float(rng.uniform(cfg.PARCEL_AREA_MIN_HA, cfg.PARCEL_AREA_MAX_HA))

            # Jitter the parcel inside its own cell, never beyond it.
            extent_m = math.sqrt(target_area * 10_000.0) * 1.5
            extent_lon, extent_lat = metres_to_degrees(extent_m, centre_lat)
            jitter_lon = max((cell_width - extent_lon) / 2.0, 0.0)
            jitter_lat = max((cell_height - extent_lat) / 2.0, 0.0)
            lon = centre_lon + float(rng.uniform(-jitter_lon, jitter_lon))
            lat = centre_lat + float(rng.uniform(-jitter_lat, jitter_lat))
            polygon = _make_parcel(rng, lon, lat, target_area)
            survey_date = date_min + timedelta(days=int(rng.integers(0, span_days + 1)))

            records.append(
                {
                    "record_id": f"PL{index + 1:03d}",
                    "site": site,
                    "survey_date": survey_date.isoformat(),
                    "collector_id": str(rng.choice(cfg.COLLECTOR_IDS)),
                    "latitude": round(lat, 6),
                    "longitude": round(lon, 6),
                    # The declared area is derived from the polygon, so a clean
                    # record is consistent between its attributes and geometry.
                    "area_ha": round(geodesic_area_ha(polygon), 2),
                    "land_use": str(rng.choice(cfg.ALLOWED_LAND_USE)),
                    "status": str(rng.choice(cfg.ALLOWED_COLLECTION_STATUS)),
                    "geometry": polygon,
                }
            )
    return records


# ---------------------------------------------------------------------------
# Error injection
# ---------------------------------------------------------------------------


def inject_errors(records: list[dict], rng: np.random.Generator) -> pd.DataFrame:
    """Inject a controlled list of quality problems and return the ground truth."""
    log: list[dict] = []

    def note(row: int, injected: str, expected: list[str], comment: str = "") -> None:
        log.append(
            {
                "source_row": row + 2,  # 1-based line number in the CSV, header included
                "record_id": records[row]["record_id"],
                "injected_error": injected,
                "expected_issue_codes": ";".join(expected),
                "comment": comment,
            }
        )

    def overlap_pair(base_row: int, moved_row: int) -> None:
        """Move one parcel on top of a neighbouring parcel of the same site."""
        base = records[base_row]["geometry"]
        moved = records[moved_row]["geometry"]
        minx, miny, maxx, maxy = base.bounds
        offset_x = (maxx - minx) * 0.35
        offset_y = (maxy - miny) * 0.25
        shifted = _recentre(moved, base.centroid.x + offset_x, base.centroid.y + offset_y)
        records[moved_row]["geometry"] = shifted
        point = shifted.representative_point()
        records[moved_row]["latitude"] = round(point.y, 6)
        records[moved_row]["longitude"] = round(point.x, 6)
        note(moved_row, "parcel moved on top of a neighbouring parcel", ["spatial_overlap"],
             f"overlaps record {records[base_row]['record_id']}")

    # --- attribute problems ------------------------------------------------
    records[3]["status"] = "Complete"
    note(3, "collection status outside the allowed list", ["invalid_collection_status"])

    for row in (5, 88):
        records[row]["collector_id"] = None
        note(row, "collector_id removed", ["missing_collector_id"])

    for donor, row in ((6, 7), (60, 61)):
        records[row]["record_id"] = records[donor]["record_id"]
        note(row, "record_id duplicated", ["duplicate_record_id"],
             f"same id as source row {donor + 2}")

    for row, value in ((9, 640.5), (66, 1250.0)):
        records[row]["area_ha"] = value
        note(row, "abnormally large area", ["suspicious_area", "area_attribute_mismatch"])

    for row in (11, 74):
        records[row]["area_ha"] = round(records[row]["area_ha"] * 3.0, 2)
        note(row, "area inflated 3x (typing error)", ["area_attribute_mismatch"])

    for row in (12, 45):
        records[row]["latitude"] = None
        note(row, "latitude removed", ["missing_latitude"])

    records[23]["longitude"] = None
    note(23, "longitude removed", ["missing_longitude"])

    records[15]["latitude"] = 12.4083
    note(15, "latitude decimal shift", ["coordinates_out_of_study_area", "geometry_attribute_mismatch"])

    records[18]["area_ha"] = 0.0
    note(18, "area set to zero", ["non_positive_area"])

    records[52]["area_ha"] = -3.4
    note(52, "negative area", ["non_positive_area"])

    records[82]["area_ha"] = None
    note(82, "area removed", ["missing_area_ha"])

    for row, value in ((27, "Uknown"), (71, "forest land")):
        records[row]["land_use"] = value
        note(row, "land_use outside the allowed list", ["invalid_land_use"])

    for row in (31, 77):
        records[row]["survey_date"] = None
        note(row, "survey_date removed", ["missing_survey_date"])

    records[55]["survey_date"] = "2027-04-18"
    note(55, "survey date in the future", ["invalid_survey_date"])

    records[68]["survey_date"] = "2026-02-31"
    note(68, "impossible calendar date", ["invalid_survey_date"])

    records[49]["site"] = None
    note(49, "site removed", ["missing_site"])

    # --- spatial problems --------------------------------------------------
    for row in (29, 58):
        records[row]["geometry"] = _bowtie(records[row]["geometry"])
        note(row, "self-intersecting polygon", ["invalid_geometry"])

    records[36]["geometry"] = None
    note(36, "geometry removed", ["missing_geometry"])

    records[63]["geometry"] = Polygon()
    note(63, "empty geometry", ["missing_geometry"])

    for row, (dx, dy) in ((40, (0.115, 0.0)), (83, (0.0, -0.125))):
        records[row]["geometry"] = translate(records[row]["geometry"], xoff=dx, yoff=dy)
        records[row]["latitude"] = round(records[row]["latitude"] + dy, 6)
        records[row]["longitude"] = round(records[row]["longitude"] + dx, 6)
        note(row, "parcel located outside the study area",
             ["coordinates_out_of_study_area", "geometry_out_of_study_area"])

    for base_row, moved_row in ((21, 22), (47, 48), (91, 92)):
        overlap_pair(base_row, moved_row)

    return pd.DataFrame(log).sort_values("source_row").reset_index(drop=True)


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------


def _records_to_dataframe(records: list[dict]) -> pd.DataFrame:
    rows = []
    for record in records:
        row = dict(record)
        geometry = row.pop("geometry")
        row["geometry"] = "" if geometry is None else geometry.wkt
        rows.append(row)
    return pd.DataFrame(rows)


def _write_geojson(records: list[dict], path) -> None:
    """Write the raw records as GeoJSON, keeping invalid and null geometries as they are."""
    features = []
    for record in records:
        properties = {k: v for k, v in record.items() if k != "geometry"}
        properties = {k: (None if (isinstance(v, float) and math.isnan(v)) else v)
                      for k, v in properties.items()}
        geometry = record["geometry"]
        features.append(
            {
                "type": "Feature",
                "properties": properties,
                "geometry": None if geometry is None or geometry.is_empty else mapping(geometry),
            }
        )
    collection = {"type": "FeatureCollection", "features": features}
    path.write_text(json.dumps(collection, indent=1, allow_nan=False), encoding="utf-8")


def _write_reference_layers() -> None:
    """Write the fictitious study area and site boundaries."""
    study = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"name": "Conservation Landscape Data Project (synthetic)"},
                "geometry": mapping(study_area_polygon()),
            }
        ],
    }
    cfg.STUDY_AREA_GEOJSON.write_text(json.dumps(study, indent=1), encoding="utf-8")

    sites = {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature", "properties": {"site": name}, "geometry": mapping(polygon)}
            for name, polygon in site_polygons().items()
        ],
    }
    cfg.SITES_GEOJSON.write_text(json.dumps(sites, indent=1), encoding="utf-8")


def generate(verbose: bool = True) -> pd.DataFrame:
    """Generate the raw dataset and its ground-truth error log."""
    cfg.ensure_directories()
    rng = np.random.default_rng(cfg.RANDOM_SEED)

    records = build_clean_records(rng)
    injected = inject_errors(records, rng)

    frame = _records_to_dataframe(records)
    frame.to_csv(cfg.RAW_CSV, index=False, encoding="utf-8")
    _write_geojson(records, cfg.RAW_GEOJSON)
    injected.to_csv(cfg.INJECTED_ERRORS_CSV, index=False, encoding="utf-8")
    _write_reference_layers()

    if verbose:
        print(f"  {len(frame)} synthetic records written to {cfg.RAW_CSV.name}")
        print(f"  {len(injected)} problems injected on purpose "
              f"({injected['injected_error'].nunique()} distinct error types)")
    return injected


if __name__ == "__main__":
    generate()
