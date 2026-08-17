"""Field Data Quality & GIS Workflow - one command runs the whole pipeline.

    python src/run_pipeline.py [--regenerate] [--no-figures]

Steps
-----
1. generate the synthetic raw dataset (only if it is missing, or with --regenerate)
2. load the raw data as text and parse the typed fields
3. run the attribute quality checks
4. run the spatial quality checks
5. give every record a status (VALID / REVIEW / INVALID)
6. write the validated datasets, the review file and the quality report
7. write the dashboard tables and render the map, dashboard and workflow diagram
8. check the detected issues against the problems injected on purpose
"""

from __future__ import annotations

import argparse
import sys

import pandas as pd

import config as cfg
import reporting
from generate_synthetic_data import generate
from quality_control import concat_issues, load_raw, parse_fields, run_attribute_checks
from spatial_validation import build_geodataframe, run_spatial_checks

SEPARATOR = "-" * 66


def verify_against_injected(issues: pd.DataFrame) -> tuple[int, int, list[str]]:
    """Compare what the pipeline found with the problems injected on purpose."""
    if not cfg.INJECTED_ERRORS_CSV.exists():
        return 0, 0, []
    injected = pd.read_csv(cfg.INJECTED_ERRORS_CSV)
    detected = set(zip(issues["source_row"], issues["issue_code"]))
    expected_total, found_total, missed = 0, 0, []
    for _, row in injected.iterrows():
        for code in str(row["expected_issue_codes"]).split(";"):
            expected_total += 1
            if (row["source_row"], code) in detected:
                found_total += 1
            else:
                missed.append(f"row {row['source_row']} ({row['record_id']}): {code}")
    return found_total, expected_total, missed


def run(regenerate: bool = False, figures: bool = True) -> dict:
    cfg.ensure_directories()

    print(SEPARATOR)
    print("FIELD DATA QUALITY & GIS WORKFLOW - synthetic data")
    print(SEPARATOR)

    print("[1/7] Synthetic data")
    if regenerate or not cfg.RAW_CSV.exists():
        generate()
    else:
        print(f"  reusing existing {cfg.RAW_CSV.relative_to(cfg.PROJECT_ROOT)} "
              f"(use --regenerate to rebuild it)")

    print("[2/7] Loading raw data")
    raw = parse_fields(load_raw())
    print(f"  {len(raw)} records loaded from {cfg.RAW_CSV.name}")

    print("[3/7] Attribute quality control")
    attribute_issues = run_attribute_checks(raw)
    print(f"  {len(attribute_issues)} issues on "
          f"{attribute_issues['source_row'].nunique()} records")

    print("[4/7] Spatial validation")
    gdf = build_geodataframe(raw)
    spatial_issues, overlaps = run_spatial_checks(gdf)
    print(f"  {len(spatial_issues)} issues on {spatial_issues['source_row'].nunique()} records, "
          f"{len(overlaps)} overlapping pairs")

    print("[5/7] Status assignment")
    issues = concat_issues([attribute_issues, spatial_issues])
    status = reporting.build_record_status(raw, issues)
    counts = status["qc_status"].value_counts()
    print(f"  VALID {int(counts.get('VALID', 0))} | "
          f"REVIEW {int(counts.get('REVIEW', 0))} | "
          f"INVALID {int(counts.get('INVALID', 0))}")

    print("[6/7] Writing outputs")
    reporting.write_status_file(status)
    reporting.write_review_file(issues, status)
    validated = reporting.write_validated_outputs(gdf, status)
    review_layer = reporting.write_review_layer(gdf, status)
    reporting.write_overlaps(overlaps)
    report = reporting.build_quality_report(raw, issues, status, overlaps)
    tables = reporting.build_dashboard_tables(issues, status, report)
    for path in (cfg.RECORD_STATUS_CSV, cfg.REVIEW_CSV, cfg.VALIDATED_CSV,
                 cfg.VALIDATED_GEOJSON, cfg.REVIEW_GEOJSON, cfg.OVERLAPS_GEOJSON,
                 cfg.QUALITY_REPORT_CSV):
        print(f"  {path.relative_to(cfg.PROJECT_ROOT).as_posix()}")

    print("[7/7] Figures")
    if figures:
        reporting.make_map_figure(validated, review_layer, overlaps)
        reporting.make_dashboard_figure(report, tables, issues, validated, review_layer, overlaps)
        reporting.make_workflow_diagram()
        for path in (cfg.MAP_PNG, cfg.DASHBOARD_PNG, cfg.WORKFLOW_DIAGRAM_PNG):
            print(f"  {path.relative_to(cfg.PROJECT_ROOT).as_posix()}")
    else:
        print("  skipped (--no-figures)")

    print(SEPARATOR)
    print("DATA QUALITY REPORT")
    print(SEPARATOR)
    for _, row in report.iterrows():
        print(f"  {row['metric']:<38} {row['value']}")

    print(SEPARATOR)
    found, expected, missed = verify_against_injected(issues)
    if expected:
        print(f"Injected problems re-detected: {found}/{expected}")
        for item in missed:
            print(f"  NOT DETECTED: {item}")
    extra = len(issues) - found
    print(f"Additional issues detected beyond the injected list: {extra}")
    print("  (counterparts of a duplicated id or of an overlap, plus problems that")
    print("   appeared by chance when the random parcels were drawn)")
    print(SEPARATOR)

    return {
        "raw": raw, "issues": issues, "status": status, "report": report,
        "overlaps": overlaps, "validated": validated,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the field data quality pipeline.")
    parser.add_argument("--regenerate", action="store_true",
                        help="rebuild the synthetic raw dataset before running the checks")
    parser.add_argument("--no-figures", action="store_true",
                        help="skip the map, dashboard and diagram rendering")
    args = parser.parse_args()
    run(regenerate=args.regenerate, figures=not args.no_figures)
    return 0


if __name__ == "__main__":
    sys.exit(main())
