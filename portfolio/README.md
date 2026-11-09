# Portfolio assets

Seven images, ready to drop into the case study. Every figure comes from the real
pipeline run: no mock-ups, no hand-typed numbers.

Regenerate assets 01 to 04 at any time with:

    python src/make_portfolio_assets.py

Version francaise : [LISEZMOI.md](LISEZMOI.md)

## What goes into the portfolio

| # | Image | Portfolio section | Caption to use |
|---|---|---|---|
| 00 | `00_workflow_diagram.png` | **Overview** | From raw field data to decision-ready geospatial information. |
| 01 | `01_raw_field_data.png` | **The Challenge** | Field data arrives with duplicates, missing values, impossible dates and broken geometry. |
| 02 | `02_validation_rules.png` | **The Approach** | 22 explicit rules, 16 attribute checks and 6 spatial checks, each traceable to the record it flags. |
| 03 | `03_pipeline_run.png` | **The Approach** | One command runs the whole workflow and reproduces every output. |
| 04 | `04_quality_report.png` | **The Results** | 42 issues detected across 100 records, each linked to a rule and a severity. |
| 05 | `05_qgis_map.png` | **GIS Validation** | Validated parcels, records for review and spatial overlaps reviewed in QGIS. |
| 06 | `06_dashboard.png` | **Reporting** | Quality-control results summarised as indicators for rapid assessment. |

## Headline numbers

All values are produced by the pipeline and stored in `outputs/quality_report.csv`.

| Figure | Value |
|---|---:|
| Synthetic records processed | **100** |
| Records validated | **63** |
| Records requiring review | **31** |
| Invalid records | **6** |
| Issues detected | **42** |
| Required-field completeness | **98.7 %** |
| Spatial issues | **17** |
| Overlapping parcel pairs | **3** |
| Deliberately injected errors re-detected | **37 / 37** |

The last line is the strongest one: 37 errors were injected into the dataset on
purpose, and the pipeline found every single one. Lead with it.

## Case study text

**Title:** Field Data Quality & GIS Workflow
**Subtitle:** From raw field data to validated geospatial information

**The Challenge**

Field teams collect large volumes of geospatial data that cannot support analysis
or reporting until they have been validated. Duplicated identifiers, missing
coordinates, impossible dates, inconsistent areas, invalid geometries and
overlapping parcels are all common, and all invisible until something checks for
them.

**The Approach**

I designed a reproducible workflow that combines automated attribute checks,
spatial validation and GIS review. Twenty-two rules run on every record. Each rule
produces a traceable issue with a severity, and each record receives a status:
`VALID`, `REVIEW` or `INVALID`. The raw file is never modified. Only records that
pass every rule are exported as validated data.

**Automated Quality Control**

The workflow checks completeness, uniqueness, coordinate validity, attribute
consistency, geometry validity, study-area containment and spatial overlaps. To
verify the system itself, 37 errors were deliberately injected into the synthetic
dataset; the pipeline re-detected all 37.

**GIS Validation**

Validated records are exported as GIS-ready GeoJSON and reviewed spatially in
QGIS, alongside the records flagged for review and the detected overlap surfaces.

**Reporting**

Quality-control results are summarised as key indicators, including validation
rate, completeness, issues by type and issues by severity, so that data quality
can be assessed at a glance and the records needing attention can be sent back to
the field team.

**Technologies**

Python, Pandas, GeoPandas, Shapely, Matplotlib, GeoJSON, QGIS

## Code availability

> **Code availability.** The full source code, data and documentation of this
> project are public:
> https://github.com/Estherbh/Field-Data-Quality-GIS-WORKFLOW

## Data & confidentiality

> **Confidentiality Notice.** This portfolio project uses 100 % non-confidential
> data. The prototype is built entirely from synthetic data created specifically
> for demonstration purposes. No confidential, proprietary, operational or
> unpublished company data are used or disclosed anywhere in this project.
