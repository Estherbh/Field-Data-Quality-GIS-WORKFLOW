# Field Data Quality & GIS Workflow

From raw field data to validated geospatial information.

## Overview

This portfolio project demonstrates a reproducible workflow for validating, cleaning and preparing field-based geospatial data for GIS analysis and reporting. The data are fully synthetic and deliberately include attribute and spatial quality issues.

## Workflow

Synthetic raw data → Attribute quality control → Spatial validation → Status assignment → Validated GIS-ready data → QGIS review and dashboard reporting.

## Technologies

Python · Pandas · NumPy · GeoPandas · Shapely · Matplotlib · GeoJSON · QGIS

## Installation

Install dependencies from the project root:

    python -m pip install -r requirements.txt

On Windows with Python 3.14:

    py -3.14 -m pip install -r requirements.txt

## Run the pipeline

    python src/run_pipeline.py --regenerate

On Windows:

    py -3.14 src/run_pipeline.py --regenerate

Use --no-figures to skip PNG output. The command regenerates raw data, runs quality checks and writes all outputs.

## Outputs

| File | Purpose |
|---|---|
| outputs/quality_report.csv | Quality-control metrics. |
| outputs/record_status.csv | Final status for each record. |
| outputs/records_to_review.csv | All detected issues and severity. |
| outputs/validated_data.geojson | GIS-ready validated records. |
| outputs/records_to_review.geojson | GIS layer of review and invalid records. |
| outputs/spatial_overlaps.geojson | Detected overlap pairs. |
| outputs/map_overview.png | Automated map overview. |
| dashboard/dashboard.png | Automated quality dashboard. |

## Current results

| Metric | Result |
|---|---:|
| Synthetic records processed | 100 |
| Valid records | 63 |
| Records requiring review | 31 |
| Invalid records | 6 |
| Total issues detected | 42 |
| Attribute issues | 25 |
| Spatial issues | 17 |
| Overlapping polygon pairs | 3 |
| Required-field completeness | 98.7% |

The pipeline produces these metrics in outputs/quality_report.csv. A single synthetic fault may create multiple issue records, for example both sides of a duplicate ID or an overlap.

## QGIS review

Open outputs/validated_data.geojson, outputs/records_to_review.geojson and outputs/spatial_overlaps.geojson in QGIS. Follow docs/QGIS_MAP_GUIDE_FR.md to create the final map.

## Data and confidentiality

Confidentiality Notice: This portfolio project uses entirely synthetic data created for demonstration purposes. No operational, organizational, producer, geographic or other confidential data from professional projects are included.
