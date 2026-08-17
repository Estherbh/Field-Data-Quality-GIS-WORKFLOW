"""Step 2 - Attribute quality control.

The raw file is never modified. Every rule produces zero or more issues, one row
per (record, issue_code), which the pipeline later turns into a record status
and a quality report.

Rules applied here
------------------
uniqueness    duplicate_record_id
completeness  missing_<field> for every required field
validity      invalid_survey_date, non_numeric_coordinates, non_numeric_area,
              non_positive_area, suspicious_area, invalid_land_use,
              invalid_collection_status
geography     coordinates_out_of_study_area
"""

from __future__ import annotations

import pandas as pd

import config as cfg

ISSUE_COLUMNS = ["source_row", "record_id", "site", "issue_code", "severity",
                 "issue_description", "issue_detail"]

MISSING_FIELD_CODES = {
    "record_id": "missing_record_id",
    "site": "missing_site",
    "survey_date": "missing_survey_date",
    "collector_id": "missing_collector_id",
    "latitude": "missing_latitude",
    "longitude": "missing_longitude",
    "area_ha": "missing_area_ha",
}


# ---------------------------------------------------------------------------
# Loading and parsing
# ---------------------------------------------------------------------------


def load_raw(path=cfg.RAW_CSV) -> pd.DataFrame:
    """Load the raw CSV as text, so that "missing" and "not a number" stay distinct."""
    frame = pd.read_csv(path, dtype=str, keep_default_na=False, na_values=[""])
    frame.insert(0, "source_row", range(2, len(frame) + 2))  # CSV line number
    return frame


def parse_fields(frame: pd.DataFrame) -> pd.DataFrame:
    """Add typed columns (suffix _num / _dt) next to the raw text columns."""
    parsed = frame.copy()
    for column in ("latitude", "longitude", "area_ha"):
        parsed[f"{column}_num"] = pd.to_numeric(parsed[column], errors="coerce")
    parsed["survey_date_dt"] = pd.to_datetime(
        parsed["survey_date"], format="%Y-%m-%d", errors="coerce"
    )
    return parsed


# ---------------------------------------------------------------------------
# Issue helpers
# ---------------------------------------------------------------------------


def empty_issues() -> pd.DataFrame:
    return pd.DataFrame(columns=ISSUE_COLUMNS)


def collect(frame: pd.DataFrame, mask, issue_code: str, detail=None) -> pd.DataFrame:
    """Build the issue rows for the records selected by ``mask``."""
    subset = frame.loc[mask]
    if subset.empty:
        return empty_issues()
    if detail is None:
        detail_values = ""
    elif isinstance(detail, str):
        detail_values = detail
    else:  # a Series aligned on the frame index
        detail_values = detail.loc[subset.index]
    return pd.DataFrame(
        {
            "source_row": subset["source_row"].to_numpy(),
            "record_id": subset["record_id"].to_numpy(),
            "site": subset["site"].to_numpy(),
            "issue_code": issue_code,
            "severity": cfg.severity_of(issue_code),
            "issue_description": cfg.description_of(issue_code),
            "issue_detail": detail_values,
        }
    )


def concat_issues(parts) -> pd.DataFrame:
    """Concatenate issue frames and sort them by record and severity."""
    parts = [part for part in parts if part is not None and not part.empty]
    if not parts:
        return empty_issues()
    issues = pd.concat(parts, ignore_index=True)
    issues["severity_rank"] = issues["severity"].map(cfg.SEVERITY_RANK)
    issues = issues.sort_values(["source_row", "severity_rank", "issue_code"],
                                ascending=[True, False, True])
    return issues.drop(columns="severity_rank").reset_index(drop=True)


# ---------------------------------------------------------------------------
# Rules
# ---------------------------------------------------------------------------


def check_duplicates(frame: pd.DataFrame) -> pd.DataFrame:
    """Control 1 - record_id must identify exactly one record."""
    duplicated = frame["record_id"].notna() & frame["record_id"].duplicated(keep=False)
    counts = frame["record_id"].map(frame["record_id"].value_counts())
    detail = counts.map(
        lambda n: f"record_id used by {int(n)} records" if pd.notna(n) else ""
    )
    return collect(frame, duplicated, "duplicate_record_id", detail)


def check_required_fields(frame: pd.DataFrame) -> pd.DataFrame:
    """Control 2 - every required field must be filled in."""
    parts = []
    for field, issue_code in MISSING_FIELD_CODES.items():
        parts.append(collect(frame, frame[field].isna(), issue_code, f"{field} is empty"))
    return concat_issues(parts)


def check_survey_dates(frame: pd.DataFrame) -> pd.DataFrame:
    """Control 3 - dates must be real and inside the survey period."""
    today = pd.Timestamp.today().normalize()
    period_start = pd.Timestamp(cfg.SURVEY_DATE_MIN)
    provided = frame["survey_date"].notna()
    unparseable = provided & frame["survey_date_dt"].isna()
    out_of_period = provided & frame["survey_date_dt"].notna() & (
        (frame["survey_date_dt"] < period_start) | (frame["survey_date_dt"] > today)
    )
    detail = frame["survey_date"].map(
        lambda value: f"survey_date = {value!r} (expected {cfg.SURVEY_DATE_MIN} .. today)"
    )
    return collect(frame, unparseable | out_of_period, "invalid_survey_date", detail)


def check_area(frame: pd.DataFrame) -> pd.DataFrame:
    """Control 4 - area_ha must be a number strictly greater than zero and plausible."""
    provided = frame["area_ha"].notna()
    not_numeric = provided & frame["area_ha_num"].isna()
    non_positive = frame["area_ha_num"].notna() & (frame["area_ha_num"] <= 0)
    suspicious = frame["area_ha_num"].notna() & (frame["area_ha_num"] > cfg.MAX_PLAUSIBLE_AREA_HA)
    detail = frame["area_ha"].map(lambda value: f"area_ha = {value}")
    return concat_issues(
        [
            collect(frame, not_numeric, "non_numeric_area", detail),
            collect(frame, non_positive, "non_positive_area", detail),
            collect(frame, suspicious, "suspicious_area", detail),
        ]
    )


def check_categories(frame: pd.DataFrame) -> pd.DataFrame:
    """Control 5 - categorical fields must use the allowed values."""
    land_use = frame["land_use"].notna() & ~frame["land_use"].isin(cfg.ALLOWED_LAND_USE)
    collection_status = frame["status"].notna() & ~frame["status"].isin(cfg.ALLOWED_COLLECTION_STATUS)
    return concat_issues(
        [
            collect(frame, land_use, "invalid_land_use",
                    frame["land_use"].map(lambda v: f"land_use = {v!r}")),
            collect(frame, collection_status, "invalid_collection_status",
                    frame["status"].map(lambda v: f"status = {v!r}")),
        ]
    )


def check_coordinates(frame: pd.DataFrame) -> pd.DataFrame:
    """Control 6 - coordinates must be numeric and inside the study area."""
    minx, miny, maxx, maxy = cfg.STUDY_AREA_BOUNDS
    lat, lon = frame["latitude_num"], frame["longitude_num"]

    provided = frame["latitude"].notna() | frame["longitude"].notna()
    not_numeric = provided & (
        (frame["latitude"].notna() & lat.isna()) | (frame["longitude"].notna() & lon.isna())
    )
    both_numeric = lat.notna() & lon.notna()
    outside = both_numeric & ~(lat.between(miny, maxy) & lon.between(minx, maxx))
    detail = frame.apply(
        lambda row: f"latitude = {row['latitude']}, longitude = {row['longitude']}", axis=1
    )
    return concat_issues(
        [
            collect(frame, not_numeric, "non_numeric_coordinates", detail),
            collect(frame, outside, "coordinates_out_of_study_area", detail),
        ]
    )


def run_attribute_checks(frame: pd.DataFrame) -> pd.DataFrame:
    """Run every attribute rule and return one row per detected issue."""
    return concat_issues(
        [
            check_duplicates(frame),
            check_required_fields(frame),
            check_survey_dates(frame),
            check_area(frame),
            check_categories(frame),
            check_coordinates(frame),
        ]
    )


if __name__ == "__main__":
    data = parse_fields(load_raw())
    found = run_attribute_checks(data)
    print(f"{len(found)} attribute issues on {found['source_row'].nunique()} records")
    print(found["issue_code"].value_counts().to_string())
