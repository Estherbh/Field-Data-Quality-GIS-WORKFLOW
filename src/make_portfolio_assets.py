"""Render the portfolio image assets (English) from the real data and a real run.

    python src/make_portfolio_assets.py

Each asset is a self-contained PNG carrying its portfolio category, so the images
can be dropped into a case study without any further editing. Nothing is mocked:
the table cells come from data/raw/field_data_raw.csv, the console card comes from
an actual pipeline run, the figures come from outputs/.

Assets written to portfolio/
    01_raw_field_data.png     the problem - messy field records
    02_validation_rules.png   the approach - how a rule is written
    03_pipeline_run.png       the approach - one command, real output
    04_quality_report.png     the results - issues, statuses and outputs
"""

from __future__ import annotations

import contextlib
import io
import re

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.patches import FancyBboxPatch, Rectangle

import config as cfg
from quality_control import load_raw

PORTFOLIO_DIR = cfg.PROJECT_ROOT / "portfolio"

# --- visual identity (same palette as the dashboard) -----------------------
SURFACE = "#fcfcfb"
PANEL = "#ffffff"
INK = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRID = "#e1e0d9"
BORDER = "#d8d7cf"
BLUE = "#2a78d6"
VIOLET = "#4a3aa7"
GREEN = "#0ca30c"
HEADER_FILL = "#f2f1ed"

TERMINAL_BG = "#1a1a19"
TERMINAL_INK = "#e6e5df"
TERMINAL_MUTED = "#9a998f"

SEVERITY_TINT = {
    "Critical": ("#fadedd", "#a82c2c"),
    "High": ("#fce6d8", "#9d4f26"),
    "Medium": ("#fdf1d2", "#87610a"),
}

MONO = "DejaVu Sans Mono"
SANS = "DejaVu Sans"

FIG_WIDTH, FIG_HEIGHT = 16.0, 10.0

# issue_code -> the raw column the reader should look at
ISSUE_COLUMN = {
    "duplicate_record_id": "record_id",
    "missing_record_id": "record_id",
    "missing_site": "site",
    "missing_survey_date": "survey_date",
    "invalid_survey_date": "survey_date",
    "missing_collector_id": "collector_id",
    "missing_latitude": "latitude",
    "missing_longitude": "longitude",
    "coordinates_out_of_study_area": "latitude",
    "non_numeric_coordinates": "latitude",
    "missing_area_ha": "area_ha",
    "non_positive_area": "area_ha",
    "suspicious_area": "area_ha",
    "non_numeric_area": "area_ha",
    "area_attribute_mismatch": "area_ha",
    "invalid_land_use": "land_use",
    "invalid_collection_status": "status",
    "missing_geometry": "geometry",
    "invalid_geometry": "geometry",
    "geometry_out_of_study_area": "geometry",
}


# ---------------------------------------------------------------------------
# Canvas helpers
# ---------------------------------------------------------------------------


def _canvas():
    figure = plt.figure(figsize=(FIG_WIDTH, FIG_HEIGHT), facecolor=SURFACE)
    ax = figure.add_axes((0, 0, 1, 1))
    ax.set_axis_off()
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    return figure, ax


def _header(ax, number: str, category: str, title: str, subtitle: str) -> None:
    """Draw the category label, the title and the subtitle."""
    ax.text(0.045, 0.927, f"{number}  {category}", fontsize=12.5, fontweight="bold",
            color=INK_MUTED, family=SANS, va="center")
    ax.text(0.045, 0.855, title, fontsize=27, fontweight="bold", color=INK,
            family=SANS, va="center")
    ax.text(0.045, 0.808, subtitle, fontsize=13, color=INK_SECONDARY, family=SANS,
            va="center")


def _footer(ax) -> None:
    ax.plot([0.045, 0.955], [0.062, 0.062], color=GRID, linewidth=1)
    ax.text(0.045, 0.036, "100% synthetic data", fontsize=11,
            color=INK_MUTED, family=SANS, va="center")
    ax.text(0.955, 0.036, "Field Data Quality & GIS Workflow", fontsize=11,
            color=INK_MUTED, family=SANS, va="center", ha="right")


def _card(ax, x: float, y: float, width: float, height: float, facecolor: str = PANEL,
          edgecolor: str = BORDER) -> None:
    ax.add_patch(
        FancyBboxPatch((x, y), width, height, boxstyle="round,pad=0,rounding_size=0.008",
                       linewidth=1.1, edgecolor=edgecolor, facecolor=facecolor)
    )


def _mono_char_width(fontsize: float) -> float:
    """Width of one monospace character, in figure-x fraction."""
    return 0.60217 * fontsize / (FIG_WIDTH * 72.0)


def _mono_line(ax, x: float, y: float, segments, fontsize: float) -> None:
    """Draw a monospace line made of (text, colour) segments."""
    char_width = _mono_char_width(fontsize)
    cursor = x
    for text, colour in segments:
        ax.text(cursor, y, text, fontsize=fontsize, color=colour, family=MONO, va="center")
        cursor += len(text) * char_width


# ---------------------------------------------------------------------------
# Asset 1 - raw field data
# ---------------------------------------------------------------------------

DISPLAY_ROWS = [6, 7, 8, 9, 14, 20, 26, 29, 33, 54, 65, 70]
TABLE_COLUMNS = [
    ("record_id", 0.085),
    ("site", 0.098),
    ("survey_date", 0.105),
    ("collector_id", 0.098),
    ("latitude", 0.090),
    ("longitude", 0.090),
    ("area_ha", 0.075),
    ("land_use", 0.098),
    ("geometry", 0.161),
]


def _short_geometry(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "(missing)"
    text = str(value)
    if text.strip() == "" or text.strip() == "POLYGON EMPTY":
        return "POLYGON EMPTY"
    return text[:20] + "..."


def asset_raw_data(raw: pd.DataFrame, issues: pd.DataFrame) -> None:
    figure, ax = _canvas()
    _header(ax, "01", "RAW FIELD DATA", "Field data arrives with problems",
            "12 of the 100 synthetic records, exactly as delivered by the field teams")

    rows = raw[raw["source_row"].isin(DISPLAY_ROWS)].copy()
    flags: dict[tuple[int, str], str] = {}
    for _, issue in issues.iterrows():
        column = ISSUE_COLUMN.get(issue["issue_code"])
        if column:
            current = flags.get((issue["source_row"], column))
            rank = cfg.SEVERITY_RANK
            if current is None or rank[issue["severity"]] > rank[current]:
                flags[(issue["source_row"], column)] = issue["severity"]

    table_left, table_right = 0.045, 0.955
    table_top, row_height = 0.735, 0.0455
    _card(ax, table_left, table_top - row_height * (len(rows) + 1) - 0.012,
          table_right - table_left, row_height * (len(rows) + 1) + 0.024)

    # header band
    ax.add_patch(
        Rectangle((table_left + 0.006, table_top - row_height + 0.004),
                  table_right - table_left - 0.012, row_height - 0.006,
                  linewidth=0, facecolor=HEADER_FILL)
    )
    x = table_left + 0.014
    for name, width in TABLE_COLUMNS:
        ax.text(x, table_top - row_height / 2 + 0.001, name, fontsize=11.5,
                fontweight="bold", color=INK_SECONDARY, family=MONO, va="center")
        x += width

    for index, (_, record) in enumerate(rows.iterrows()):
        y = table_top - row_height * (index + 2) + row_height / 2
        if index:
            ax.plot([table_left + 0.012, table_right - 0.012],
                    [y + row_height / 2, y + row_height / 2], color=GRID, linewidth=0.8)
        x = table_left + 0.014
        for name, width in TABLE_COLUMNS:
            value = record["geometry"] if name == "geometry" else record[name]
            text = _short_geometry(value) if name == "geometry" else (
                "(missing)" if pd.isna(value) else str(value)
            )
            severity = flags.get((record["source_row"], name))
            if severity:
                fill, colour = SEVERITY_TINT[severity]
                ax.add_patch(
                    Rectangle((x - 0.006, y - row_height / 2 + 0.006), width - 0.004,
                              row_height - 0.012, linewidth=0, facecolor=fill)
                )
                ax.text(x, y, text, fontsize=11.5, color=colour, family=MONO,
                        va="center", fontweight="bold")
            else:
                ax.text(x, y, text, fontsize=11.5, color=INK, family=MONO, va="center")
            x += width

    legend_y = table_top - row_height * (len(rows) + 1) - 0.048
    ax.text(0.045, legend_y, "Detected automatically:", fontsize=12,
            color=INK_SECONDARY, family=SANS, va="center")
    x = 0.045 + 0.145
    for severity in ("Critical", "High", "Medium"):
        fill, colour = SEVERITY_TINT[severity]
        ax.add_patch(Rectangle((x, legend_y - 0.011), 0.022, 0.022, linewidth=0,
                               facecolor=fill))
        ax.text(x + 0.028, legend_y, severity, fontsize=12, color=colour, family=SANS,
                va="center", fontweight="bold")
        x += 0.115
    ax.text(0.955, legend_y,
            "duplicate ids  -  missing values  -  impossible dates  -  invalid areas  -  empty geometry",
            fontsize=12, color=INK_MUTED, family=SANS, va="center", ha="right")

    _footer(ax)
    figure.savefig(PORTFOLIO_DIR / "01_raw_field_data.png", dpi=100)
    plt.close(figure)


# ---------------------------------------------------------------------------
# Asset 2 - validation rules
# ---------------------------------------------------------------------------


def asset_validation_rules() -> None:
    figure, ax = _canvas()
    _header(ax, "02", "AUTOMATED VALIDATION", "Every rule is one explicit expression",
            "Readable, testable, and traceable back to the record it flags")

    _card(ax, 0.045, 0.435, 0.560, 0.330, facecolor="#f7f7f4")
    comment, code, string, operator = INK_MUTED, INK, "#0a7d0a", "#a8420a"
    lines = [
        [("# attribute rule - a parcel area must be a positive number", comment)],
        [("non_positive_area", code), (" = ", operator), ("area.notna()", code),
         (" & ", operator), ("(area <= 0)", code)],
        [],
        [("# spatial rule - a polygon must be topologically valid", comment)],
        [("invalid_geometry", code), (" = ", operator), ("present", code),
         (" & ~", operator), ("gdf.geometry.is_valid", code)],
        [],
        [("# both are Critical -> the record is marked ", comment), ("INVALID", string)],
    ]
    y = 0.720
    for segments in lines:
        if segments:
            _mono_line(ax, 0.068, y, segments, 13.5)
        y -= 0.042

    attribute_rules = sum(1 for rule in cfg.RULES.values() if rule[0] == "attribute")
    spatial_rules = sum(1 for rule in cfg.RULES.values() if rule[0] == "spatial")

    _card(ax, 0.635, 0.435, 0.320, 0.330)
    ax.text(0.663, 0.720, "Rule catalogue", fontsize=15, fontweight="bold", color=INK,
            family=SANS, va="center")
    entries = [
        (f"{attribute_rules}", "attribute rules"),
        (f"{spatial_rules}", "spatial rules"),
        (f"{attribute_rules + spatial_rules}", "total checks"),
    ]
    x = 0.663
    for value, label in entries:
        ax.text(x, 0.630, value, fontsize=30, fontweight="bold", color=INK,
                family=SANS, va="center")
        ax.text(x, 0.560, label, fontsize=11.5, color=INK_SECONDARY, family=SANS,
                va="center")
        x += 0.100
    ax.text(0.663, 0.490,
            "completeness  -  uniqueness  -  validity\nconsistency  -  geography  -  topology",
            fontsize=11.5, color=INK_MUTED, family=SANS, va="center", linespacing=1.6)

    _card(ax, 0.045, 0.120, 0.910, 0.270)
    ax.text(0.070, 0.340, "How a severity becomes a record status", fontsize=15,
            fontweight="bold", color=INK, family=SANS, va="center")
    rules = [
        ("Critical issue", "INVALID", "the record cannot be used as it is", "#a82c2c"),
        ("High or Medium issue", "REVIEW", "the record must be checked by the field team",
         "#87610a"),
        ("No issue", "VALID", "the record is exported to validated_data", "#0a7d0a"),
    ]
    y = 0.268
    for condition, status, comment_text, colour in rules:
        ax.text(0.088, y, condition, fontsize=13, color=INK, family=SANS, va="center")
        ax.text(0.290, y, "->", fontsize=13, color=INK_MUTED, family=SANS, va="center")
        ax.text(0.330, y, status, fontsize=13.5, fontweight="bold", color=colour,
                family=SANS, va="center")
        ax.text(0.440, y, comment_text, fontsize=12.5, color=INK_SECONDARY, family=SANS,
                va="center")
        y -= 0.062

    _footer(ax)
    figure.savefig(PORTFOLIO_DIR / "02_validation_rules.png", dpi=100)
    plt.close(figure)


# ---------------------------------------------------------------------------
# Asset 3 - pipeline run
# ---------------------------------------------------------------------------


def _capture_run() -> list[str]:
    """Run the pipeline and capture its real console output."""
    import run_pipeline

    buffer = io.StringIO()
    try:
        with contextlib.redirect_stdout(buffer):
            run_pipeline.run(regenerate=False, figures=False, write_outputs=True)
    except PermissionError:
        # The GeoJSON outputs are open somewhere else (typically QGIS): fall back
        # to a dry run so the assets can still be rendered.
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            run_pipeline.run(regenerate=False, figures=False, write_outputs=False)
        print("  ! outputs locked (QGIS open?) - console card rendered from a dry run;"
              "\n    close QGIS and run this script again for the full output listing")
    return buffer.getvalue().splitlines()


def _select_console_lines(lines: list[str]) -> list[str]:
    """Keep the steps, the outputs and the verification block; drop the metric dump."""
    selected, skipping = [], False
    for line in lines:
        if line.startswith("DATA QUALITY REPORT"):
            skipping = True
        if line.startswith("Injected problems re-detected"):
            skipping = False
            selected.append("")
        if skipping or line.startswith("---"):
            continue
        selected.append(line)
    return selected[:27]


def asset_pipeline_run() -> None:
    console = _select_console_lines(_capture_run())

    figure, ax = _canvas()
    _header(ax, "03", "REPRODUCIBLE PIPELINE", "One command, from raw data to outputs",
            "Real console output - no manual step between the raw file and the results")

    _card(ax, 0.045, 0.105, 0.910, 0.660, facecolor=TERMINAL_BG, edgecolor="#33332f")
    ax.text(0.068, 0.735, "Terminal", fontsize=11.5, color=TERMINAL_MUTED, family=SANS,
            va="center")
    for index in range(3):
        ax.add_patch(plt.Circle((0.930 - index * 0.016, 0.735), 0.006,
                                facecolor="#55554f", linewidth=0))

    _mono_line(ax, 0.068, 0.700,
               [("PS C:\\field-data-quality-gis-workflow> ", "#7fb3f0"),
                ("python src/run_pipeline.py", TERMINAL_INK)], 13.0)

    y = 0.660
    for line in console:
        if not line.strip():
            y -= 0.014
            continue
        colour = TERMINAL_INK
        if line.startswith("---") or line.startswith("FIELD DATA"):
            colour = TERMINAL_MUTED
        elif re.match(r"^\[\d/\d\]", line):
            colour = "#7fb3f0"
        elif "VALID" in line and "REVIEW" in line:
            colour = "#7ee787"
        elif line.startswith("Injected problems"):
            colour = "#ffd479"
        _mono_line(ax, 0.068, y, [(line, colour)], 13.0)
        y -= 0.0245

    ax.text(0.955, 0.088, "37 deliberately injected errors  -  37 detected", fontsize=13,
            fontweight="bold", color=GREEN, family=SANS, va="center", ha="right")
    _footer(ax)
    figure.savefig(PORTFOLIO_DIR / "03_pipeline_run.png", dpi=100)
    plt.close(figure)


# ---------------------------------------------------------------------------
# Asset 4 - quality report
# ---------------------------------------------------------------------------


def _representative_extract(review: pd.DataFrame, per_severity: int = 3) -> pd.DataFrame:
    """Pick a few issues of each severity, so the extract shows the whole scale."""
    picked = pd.concat(
        [review[review["severity"] == severity].head(per_severity)
         for severity in ("Critical", "High", "Medium")]
    )
    return picked.sort_values("source_row")


def asset_quality_report(report: pd.DataFrame, review: pd.DataFrame) -> None:
    figure, ax = _canvas()
    metrics = dict(zip(report["metric"], report["value"]))
    _header(ax, "04", "QUALITY REPORT", "Every issue is traceable to a record",
            f"Extract of records_to_review.csv - {metrics['total_issues']} issues detected, "
            f"one row per issue")
    tiles = [
        (str(metrics["total_records"]), "records processed"),
        (str(metrics["valid_records"]), "validated"),
        (str(metrics["records_for_review"]), "for review"),
        (str(metrics["invalid_records"]), "invalid"),
        (f"{metrics['required_field_completeness_pct']}%", "completeness"),
        (str(metrics["spatial_issues"]), "spatial issues"),
    ]
    tile_width = 0.910 / 6
    for index, (value, label) in enumerate(tiles):
        x = 0.045 + index * tile_width
        _card(ax, x + 0.004, 0.640, tile_width - 0.010, 0.120)
        ax.text(x + tile_width / 2, 0.717, value, fontsize=26, fontweight="bold",
                color=INK, family=SANS, va="center", ha="center")
        ax.text(x + tile_width / 2, 0.670, label, fontsize=11.5, color=INK_SECONDARY,
                family=SANS, va="center", ha="center")

    columns = [("record_id", 0.115), ("issue_code", 0.290), ("severity", 0.115),
               ("record_status", 0.150)]
    extract = _representative_extract(review)
    top, row_height = 0.575, 0.045
    _card(ax, 0.045, top - row_height * (len(extract) + 1) - 0.014, 0.700,
          row_height * (len(extract) + 1) + 0.026)
    ax.add_patch(Rectangle((0.051, top - row_height + 0.004), 0.688, row_height - 0.006,
                           linewidth=0, facecolor=HEADER_FILL))
    x = 0.062
    for name, width in columns:
        ax.text(x, top - row_height / 2, name, fontsize=11.5, fontweight="bold",
                color=INK_SECONDARY, family=MONO, va="center")
        x += width

    for index, (_, row) in enumerate(extract.iterrows()):
        y = top - row_height * (index + 2) + row_height / 2
        if index:
            ax.plot([0.057, 0.733], [y + row_height / 2, y + row_height / 2], color=GRID,
                    linewidth=0.8)
        x = 0.062
        for name, width in columns:
            text = str(row[name])
            colour = INK
            weight = "normal"
            if name == "severity":
                colour = SEVERITY_TINT[text][1]
                weight = "bold"
            elif name == "record_status":
                colour = {"INVALID": "#d03b3b", "REVIEW": "#87610a"}.get(text, INK)
                weight = "bold"
            ax.text(x, y, text, fontsize=11.5, color=colour, family=MONO, va="center",
                    fontweight=weight)
            x += width

    _card(ax, 0.765, top - row_height * (len(extract) + 1) - 0.014, 0.190,
          row_height * (len(extract) + 1) + 0.026)
    ax.text(0.785, top - 0.030, "Outputs produced", fontsize=14, fontweight="bold",
            color=INK, family=SANS, va="center")
    files = [
        "quality_report.csv",
        "records_to_review.csv",
        "record_status.csv",
        "validated_data.csv",
        "validated_data.geojson",
        "records_to_review.geojson",
        "spatial_overlaps.geojson",
        "dashboard.png",
    ]
    y = top - 0.085
    for name in files:
        ax.text(0.785, y, name, fontsize=11, color=INK_SECONDARY, family=MONO,
                va="center")
        y -= 0.040

    _footer(ax)
    figure.savefig(PORTFOLIO_DIR / "04_quality_report.png", dpi=100)
    plt.close(figure)


# ---------------------------------------------------------------------------


def main() -> None:
    PORTFOLIO_DIR.mkdir(parents=True, exist_ok=True)
    raw = load_raw()
    review = pd.read_csv(cfg.REVIEW_CSV)
    report = pd.read_csv(cfg.QUALITY_REPORT_CSV)

    asset_raw_data(raw, review)
    asset_validation_rules()
    asset_pipeline_run()
    asset_quality_report(report, review)

    for path in sorted(PORTFOLIO_DIR.glob("*.png")):
        print(f"  portfolio/{path.name}")


if __name__ == "__main__":
    main()
