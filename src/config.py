"""Shared configuration for the Field Data Quality & GIS Workflow pipeline.

Every threshold, rule and severity used by the pipeline is declared here so that
the validation logic is auditable in one place and the README can be kept in
sync with the code.

All data handled by this project are synthetic (see README - Confidentiality).
"""

from pathlib import Path

# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[1]

DATA_RAW_DIR = PROJECT_ROOT / "data" / "raw"
DATA_SYNTHETIC_DIR = PROJECT_ROOT / "data" / "synthetic"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
DASHBOARD_DIR = PROJECT_ROOT / "dashboard"
DASHBOARD_DATA_DIR = DASHBOARD_DIR / "data"
DOCS_DIR = PROJECT_ROOT / "docs"

RAW_CSV = DATA_RAW_DIR / "field_data_raw.csv"
RAW_GEOJSON = DATA_RAW_DIR / "field_data_raw.geojson"
INJECTED_ERRORS_CSV = DATA_RAW_DIR / "injected_errors.csv"

STUDY_AREA_GEOJSON = DATA_SYNTHETIC_DIR / "study_area.geojson"
SITES_GEOJSON = DATA_SYNTHETIC_DIR / "sites.geojson"

VALIDATED_CSV = OUTPUTS_DIR / "validated_data.csv"
VALIDATED_GEOJSON = OUTPUTS_DIR / "validated_data.geojson"
REVIEW_CSV = OUTPUTS_DIR / "records_to_review.csv"
REVIEW_GEOJSON = OUTPUTS_DIR / "records_to_review.geojson"
RECORD_STATUS_CSV = OUTPUTS_DIR / "record_status.csv"
QUALITY_REPORT_CSV = OUTPUTS_DIR / "quality_report.csv"
OVERLAPS_GEOJSON = OUTPUTS_DIR / "spatial_overlaps.geojson"
MAP_PNG = OUTPUTS_DIR / "map_overview.png"
DASHBOARD_PNG = DASHBOARD_DIR / "dashboard.png"
WORKFLOW_DIAGRAM_PNG = DOCS_DIR / "workflow_diagram.png"

PIPELINE_VERSION = "1.0"

# --------------------------------------------------------------------------
# Synthetic data generation
# --------------------------------------------------------------------------
RANDOM_SEED = 42
N_RECORDS = 100
CRS = "EPSG:4326"

# The study area is deliberately centred on 0 deg N / 0 deg E ("Null Island"),
# an open-ocean location that cannot correspond to any real field site. This is
# a confidentiality choice, not an oversight.
STUDY_AREA_BOUNDS = (-0.07, -0.07, 0.07, 0.07)  # minx, miny, maxx, maxy (~15.6 km)

# Fictitious collection sites: name -> (minx, miny, maxx, maxy)
SITES = {
    "Site Alpha": (-0.065, 0.010, -0.020, 0.065),
    "Site Beta": (-0.024, -0.065, 0.021, -0.010),
    "Site Gamma": (0.020, 0.010, 0.065, 0.065),
}

# Distance kept between a parcel centre and the border of its site box
SITE_INNER_MARGIN_DEG = 0.004

# Row blocks assigned to each site (start inclusive, end exclusive)
SITE_BLOCKS = {
    "Site Alpha": (0, 34),
    "Site Beta": (34, 67),
    "Site Gamma": (67, 100),
}

COLLECTOR_IDS = ["FT-01", "FT-02", "FT-03", "FT-04", "FT-05", "FT-06"]

SURVEY_DATE_MIN = "2025-01-06"
SURVEY_DATE_MAX = "2026-07-31"

PARCEL_AREA_MIN_HA = 1.0
PARCEL_AREA_MAX_HA = 16.0

# --------------------------------------------------------------------------
# Validation domains and thresholds
# --------------------------------------------------------------------------
ALLOWED_LAND_USE = ["Agriculture", "Forest", "Agroforestry", "Mixed", "Other"]
ALLOWED_COLLECTION_STATUS = ["Surveyed", "Pending Review", "Validated"]

REQUIRED_FIELDS = [
    "record_id",
    "site",
    "survey_date",
    "collector_id",
    "latitude",
    "longitude",
    "area_ha",
]

MAX_PLAUSIBLE_AREA_HA = 100.0        # above this, a parcel area is suspicious
AREA_MISMATCH_TOLERANCE = 0.20       # 20% gap between declared and computed area
POINT_GEOMETRY_MAX_DISTANCE_M = 250  # attribute point vs polygon location
OVERLAP_MIN_RATIO = 0.01             # min share of the smaller parcel to count
LATITUDE_RANGE = (-90.0, 90.0)
LONGITUDE_RANGE = (-180.0, 180.0)

# --------------------------------------------------------------------------
# Rule catalogue
# --------------------------------------------------------------------------
# severity -> record status. Written once, applied everywhere:
#   Critical -> INVALID   (the record cannot be used as it is)
#   High / Medium -> REVIEW (the record must be checked by a human)
#   no issue -> VALID
SEVERITY_RANK = {"Medium": 1, "High": 2, "Critical": 3}
STATUS_BY_SEVERITY = {"Critical": "INVALID", "High": "REVIEW", "Medium": "REVIEW"}
STATUS_ORDER = ["VALID", "REVIEW", "INVALID"]

# issue_code -> (check family, severity, human readable description)
RULES = {
    # --- attribute checks -------------------------------------------------
    "duplicate_record_id": ("attribute", "High", "record_id is used by more than one record"),
    "missing_record_id": ("attribute", "High", "record_id is empty"),
    "missing_site": ("attribute", "High", "site is empty"),
    "missing_survey_date": ("attribute", "High", "survey_date is empty"),
    "missing_collector_id": ("attribute", "High", "collector_id is empty"),
    "missing_latitude": ("attribute", "High", "latitude is empty"),
    "missing_longitude": ("attribute", "High", "longitude is empty"),
    "missing_area_ha": ("attribute", "High", "area_ha is empty"),
    "invalid_survey_date": ("attribute", "High", "survey_date is unparseable or out of the survey period"),
    "non_numeric_coordinates": ("attribute", "High", "latitude or longitude is not a number"),
    "non_numeric_area": ("attribute", "High", "area_ha is not a number"),
    "coordinates_out_of_study_area": ("attribute", "High", "point coordinates fall outside the study area"),
    "non_positive_area": ("attribute", "Critical", "area_ha is zero or negative"),
    "suspicious_area": ("attribute", "Medium", f"area_ha is above {MAX_PLAUSIBLE_AREA_HA:.0f} ha"),
    "invalid_land_use": ("attribute", "Medium", "land_use is outside the allowed value list"),
    "invalid_collection_status": ("attribute", "Medium", "status is outside the allowed value list"),
    # --- spatial checks ---------------------------------------------------
    "missing_geometry": ("spatial", "Critical", "geometry is null or empty"),
    "invalid_geometry": ("spatial", "Critical", "geometry is not valid (self-intersection or similar)"),
    "geometry_out_of_study_area": ("spatial", "High", "polygon is not fully inside the study area"),
    "geometry_attribute_mismatch": ("spatial", "Medium", "polygon location does not match latitude/longitude"),
    "area_attribute_mismatch": ("spatial", "Medium", "area_ha does not match the polygon area"),
    "spatial_overlap": ("spatial", "Medium", "polygon overlaps another parcel"),
}


# Short labels used on the dashboard and in the BI tables
ISSUE_LABELS = {
    "duplicate_record_id": "Duplicate id",
    "missing_record_id": "Missing id",
    "missing_site": "Missing site",
    "missing_survey_date": "Missing date",
    "missing_collector_id": "Missing collector",
    "missing_latitude": "Missing latitude",
    "missing_longitude": "Missing longitude",
    "missing_area_ha": "Missing area",
    "invalid_survey_date": "Invalid date",
    "non_numeric_coordinates": "Non-numeric coords",
    "non_numeric_area": "Non-numeric area",
    "coordinates_out_of_study_area": "Coords outside area",
    "non_positive_area": "Area zero or negative",
    "suspicious_area": "Suspicious area",
    "invalid_land_use": "Invalid land use",
    "invalid_collection_status": "Invalid status",
    "missing_geometry": "Missing geometry",
    "invalid_geometry": "Invalid geometry",
    "geometry_out_of_study_area": "Polygon outside area",
    "geometry_attribute_mismatch": "Point/polygon gap",
    "area_attribute_mismatch": "Area mismatch",
    "spatial_overlap": "Overlapping parcel",
}


def label_of(issue_code: str) -> str:
    """Return the short dashboard label of an issue code."""
    return ISSUE_LABELS.get(issue_code, issue_code.replace("_", " ").capitalize())


def severity_of(issue_code: str) -> str:
    """Return the severity declared for an issue code."""
    return RULES[issue_code][1]


def description_of(issue_code: str) -> str:
    """Return the human readable description declared for an issue code."""
    return RULES[issue_code][2]


def status_for_severities(severities) -> str:
    """Map the severities collected on one record to its quality status."""
    severities = list(severities)
    if not severities:
        return "VALID"
    worst = max(severities, key=lambda s: SEVERITY_RANK[s])
    return STATUS_BY_SEVERITY[worst]


def ensure_directories() -> None:
    """Create every output directory used by the pipeline."""
    for folder in (
        DATA_RAW_DIR,
        DATA_SYNTHETIC_DIR,
        OUTPUTS_DIR,
        DASHBOARD_DIR,
        DASHBOARD_DATA_DIR,
        DOCS_DIR,
    ):
        folder.mkdir(parents=True, exist_ok=True)
