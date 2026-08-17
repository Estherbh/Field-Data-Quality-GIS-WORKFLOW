"""Step 4 - Statuses, outputs, quality report and visual summaries.

Nothing in this module is hard-coded: every figure printed on the dashboard or
written to the report comes from the issues detected during the run.
"""

from __future__ import annotations

from datetime import datetime

import geopandas as gpd
import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import FancyBboxPatch, Patch, Rectangle

import config as cfg
from geoutils import site_polygons, study_area_polygon

# --------------------------------------------------------------------------
# Visual identity (light chart surface, status palette)
# --------------------------------------------------------------------------
SURFACE = "#fcfcfb"
PANEL = "#ffffff"
INK = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRID = "#e1e0d9"
BORDER = "#d8d7cf"
SERIES = "#2a78d6"
STATUS_COLORS = {"VALID": "#0ca30c", "REVIEW": "#fab219", "INVALID": "#d03b3b"}

plt.rcParams.update(
    {
        "font.family": "DejaVu Sans",
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE,
        "axes.edgecolor": BORDER,
        "text.color": INK,
        "axes.labelcolor": INK_SECONDARY,
        "xtick.color": INK_MUTED,
        "ytick.color": INK_MUTED,
    }
)

OUTPUT_COLUMNS = [
    "record_id", "site", "survey_date", "collector_id", "latitude", "longitude",
    "area_ha", "land_use", "status",
]


# --------------------------------------------------------------------------
# Statuses
# --------------------------------------------------------------------------


def build_record_status(frame: pd.DataFrame, issues: pd.DataFrame) -> pd.DataFrame:
    """Give every record a quality status from the severities it collected."""
    grouped = issues.groupby("source_row")
    severities = grouped["severity"].apply(list) if len(issues) else pd.Series(dtype=object)
    codes = grouped["issue_code"].apply(lambda values: "; ".join(sorted(set(values)))) \
        if len(issues) else pd.Series(dtype=object)

    status = frame[["source_row", "record_id", "site"]].copy()
    status["issue_count"] = status["source_row"].map(grouped.size()).fillna(0).astype(int)
    status["issue_codes"] = status["source_row"].map(codes).fillna("")
    status["qc_status"] = status["source_row"].map(
        lambda row: cfg.status_for_severities(severities.get(row, []))
    )
    status["max_severity"] = status["source_row"].map(
        lambda row: max(severities.get(row, []), key=lambda s: cfg.SEVERITY_RANK[s], default="")
    )
    return status[["source_row", "record_id", "site", "qc_status", "max_severity",
                   "issue_count", "issue_codes"]]


# --------------------------------------------------------------------------
# Tabular outputs
# --------------------------------------------------------------------------


def write_review_file(issues: pd.DataFrame, status: pd.DataFrame) -> pd.DataFrame:
    """One row per detected issue, with the status of the record it belongs to."""
    review = issues.merge(
        status[["source_row", "qc_status"]], on="source_row", how="left"
    )
    review = review[["record_id", "source_row", "site", "issue_code", "issue_description",
                     "issue_detail", "severity", "qc_status"]]
    review = review.rename(columns={"qc_status": "record_status"})
    review.to_csv(cfg.REVIEW_CSV, index=False, encoding="utf-8")
    return review


def write_validated_outputs(gdf: gpd.GeoDataFrame, status: pd.DataFrame) -> gpd.GeoDataFrame:
    """Export the records that passed every rule, as CSV and as GeoJSON for QGIS."""
    merged = gdf.merge(status[["source_row", "qc_status", "issue_count"]], on="source_row")
    validated = merged[merged["qc_status"] == "VALID"].copy()

    table = validated[OUTPUT_COLUMNS].copy()
    table["qc_status"] = "VALID"
    table.to_csv(cfg.VALIDATED_CSV, index=False, encoding="utf-8")

    layer = validated[OUTPUT_COLUMNS + ["qc_status", "geometry"]].copy()
    layer.to_file(cfg.VALIDATED_GEOJSON, driver="GeoJSON")
    return layer


def write_review_layer(gdf: gpd.GeoDataFrame, status: pd.DataFrame) -> gpd.GeoDataFrame:
    """Export the records needing attention that still have a usable geometry."""
    merged = gdf.merge(
        status[["source_row", "qc_status", "issue_count", "issue_codes", "max_severity"]],
        on="source_row",
    )
    flagged = merged[merged["qc_status"] != "VALID"].copy()
    drawable = flagged.geometry.map(lambda geom: geom is not None and not geom.is_empty)
    plottable = flagged[drawable].copy()
    columns = ["record_id", "site", "survey_date", "collector_id", "land_use",
               "qc_status", "max_severity", "issue_count", "issue_codes", "geometry"]
    layer = plottable[columns]
    layer.to_file(cfg.REVIEW_GEOJSON, driver="GeoJSON")
    return layer


def write_status_file(status: pd.DataFrame) -> None:
    status.to_csv(cfg.RECORD_STATUS_CSV, index=False, encoding="utf-8")


def write_overlaps(overlaps: gpd.GeoDataFrame) -> None:
    """Export the overlap surfaces themselves, so QGIS can show what is shared."""
    if overlaps.empty:
        overlaps.to_file(cfg.OVERLAPS_GEOJSON, driver="GeoJSON")
        return
    overlaps.to_file(cfg.OVERLAPS_GEOJSON, driver="GeoJSON")


# --------------------------------------------------------------------------
# Quality report
# --------------------------------------------------------------------------


def _records_with(issues: pd.DataFrame, *codes: str) -> int:
    subset = issues[issues["issue_code"].isin(codes)]
    return int(subset["source_row"].nunique())


def completeness_rate(frame: pd.DataFrame) -> float:
    """Share of required cells that are filled, in percent."""
    required = frame[cfg.REQUIRED_FIELDS]
    total_cells = required.size
    filled = int(required.notna().to_numpy().sum())
    return round(100.0 * filled / total_cells, 1) if total_cells else 0.0


def build_quality_report(
    frame: pd.DataFrame,
    issues: pd.DataFrame,
    status: pd.DataFrame,
    overlaps: gpd.GeoDataFrame,
) -> pd.DataFrame:
    """Build the metric,value quality report from the run itself."""
    counts = status["qc_status"].value_counts()
    total = len(frame)
    attribute_codes = [code for code, rule in cfg.RULES.items() if rule[0] == "attribute"]
    spatial_codes = [code for code, rule in cfg.RULES.items() if rule[0] == "spatial"]
    missing_codes = [code for code in cfg.RULES if code.startswith("missing_")
                     and code != "missing_geometry"]

    metrics = {
        "total_records": total,
        "valid_records": int(counts.get("VALID", 0)),
        "records_for_review": int(counts.get("REVIEW", 0)),
        "invalid_records": int(counts.get("INVALID", 0)),
        "valid_records_pct": round(100.0 * int(counts.get("VALID", 0)) / total, 1) if total else 0.0,
        "required_field_completeness_pct": completeness_rate(frame),
        "total_issues": len(issues),
        "attribute_issues": int(issues["issue_code"].isin(attribute_codes).sum()),
        "spatial_issues": int(issues["issue_code"].isin(spatial_codes).sum()),
        "duplicate_records": _records_with(issues, "duplicate_record_id"),
        "records_with_missing_required_fields": _records_with(issues, *missing_codes),
        "invalid_coordinates": _records_with(issues, "non_numeric_coordinates",
                                             "coordinates_out_of_study_area"),
        "invalid_survey_dates": _records_with(issues, "invalid_survey_date", "missing_survey_date"),
        "non_positive_area_values": _records_with(issues, "non_positive_area"),
        "suspicious_area_values": _records_with(issues, "suspicious_area"),
        "invalid_category_values": _records_with(issues, "invalid_land_use",
                                                 "invalid_collection_status"),
        "missing_geometries": _records_with(issues, "missing_geometry"),
        "invalid_geometries": _records_with(issues, "invalid_geometry"),
        "geometries_out_of_study_area": _records_with(issues, "geometry_out_of_study_area"),
        "attribute_geometry_mismatches": _records_with(issues, "geometry_attribute_mismatch",
                                                       "area_attribute_mismatch"),
        "overlapping_records": _records_with(issues, "spatial_overlap"),
        "overlapping_pairs": len(overlaps),
        "pipeline_version": cfg.PIPELINE_VERSION,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    report = pd.DataFrame({"metric": list(metrics), "value": list(metrics.values())})
    report.to_csv(cfg.QUALITY_REPORT_CSV, index=False, encoding="utf-8")
    return report


def build_dashboard_tables(issues: pd.DataFrame, status: pd.DataFrame,
                           report: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Write the tidy tables a BI tool (Power BI, Excel...) can consume directly."""
    issues_by_type = (
        issues.groupby("issue_code")
        .agg(issues=("issue_code", "size"), records=("source_row", "nunique"))
        .reset_index()
    )
    issues_by_type["severity"] = issues_by_type["issue_code"].map(cfg.severity_of)
    issues_by_type["check_family"] = issues_by_type["issue_code"].map(lambda c: cfg.RULES[c][0])
    issues_by_type["label"] = issues_by_type["issue_code"].map(cfg.label_of)
    issues_by_type = issues_by_type.sort_values("issues", ascending=False).reset_index(drop=True)

    by_site = (
        status.assign(site=status["site"].fillna("(missing site)"))
        .pivot_table(index="site", columns="qc_status", values="record_id",
                     aggfunc="count", fill_value=0)
        .reindex(columns=cfg.STATUS_ORDER, fill_value=0)
        .reset_index()
    )
    by_site["total_records"] = by_site[cfg.STATUS_ORDER].sum(axis=1)

    tables = {"kpi": report, "issues_by_type": issues_by_type, "records_by_site": by_site,
              "record_status": status}
    for name, table in tables.items():
        table.to_csv(cfg.DASHBOARD_DATA_DIR / f"{name}.csv", index=False, encoding="utf-8")
    return tables


# --------------------------------------------------------------------------
# Figures
# --------------------------------------------------------------------------


def _metric(report: pd.DataFrame, name: str):
    return report.loc[report["metric"] == name, "value"].iloc[0]


def _kpi_tiles(ax, tiles: list[tuple[str, str, str]]) -> None:
    """Draw a row of KPI tiles inside a blank axes."""
    ax.set_axis_off()
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    n = len(tiles)
    gap = 0.012
    width = (1 - gap * (n - 1)) / n
    for index, (value, label, color) in enumerate(tiles):
        x = index * (width + gap)
        ax.add_patch(
            FancyBboxPatch(
                (x, 0.06), width, 0.88,
                boxstyle="round,pad=0,rounding_size=0.012",
                linewidth=1, edgecolor=BORDER, facecolor=PANEL, transform=ax.transAxes,
            )
        )
        ax.add_patch(
            Rectangle((x, 0.06), 0.006, 0.88, linewidth=0, facecolor=color,
                      transform=ax.transAxes)
        )
        ax.text(x + width / 2, 0.60, value, ha="center", va="center", fontsize=30,
                fontweight="bold", color=INK)
        ax.text(x + width / 2, 0.24, label.upper(), ha="center", va="center", fontsize=9.5,
                color=INK_SECONDARY, fontweight="medium")


def _issues_chart(ax, issues_by_type: pd.DataFrame) -> None:
    data = issues_by_type.sort_values("issues")
    positions = range(len(data))
    ax.barh(list(positions), data["issues"], height=0.62, color=SERIES,
            edgecolor=SURFACE, linewidth=1.5)
    ax.set_yticks(list(positions))
    ax.set_yticklabels(data["label"], fontsize=9.5, color=INK_SECONDARY)
    ax.set_xlabel("issues detected", fontsize=9, color=INK_MUTED)
    ax.set_title("Issues by type", fontsize=13, fontweight="bold", color=INK, loc="left", pad=10)
    for spine in ("top", "right", "left"):
        ax.spines[spine].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(axis="x", labelsize=9)
    ax.xaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for position, value in zip(positions, data["issues"]):
        ax.text(value + max(data["issues"]) * 0.02, position, str(int(value)),
                va="center", fontsize=9.5, color=INK_SECONDARY)
    ax.set_xlim(0, max(data["issues"]) * 1.14)


def _sites_chart(ax, by_site: pd.DataFrame) -> None:
    sites = by_site["site"].tolist()
    positions = range(len(sites))
    left = [0.0] * len(sites)
    for status_name in cfg.STATUS_ORDER:
        values = by_site[status_name].tolist()
        ax.barh(list(positions), values, left=left, height=0.55,
                color=STATUS_COLORS[status_name], edgecolor=SURFACE, linewidth=2,
                label=status_name.capitalize())
        for index, (value, start) in enumerate(zip(values, left)):
            if value >= 3:
                ax.text(start + value / 2, index, str(int(value)), ha="center", va="center",
                        fontsize=9.5, color="#ffffff", fontweight="bold")
        left = [start + value for start, value in zip(left, values)]
    ax.set_yticks(list(positions))
    ax.set_yticklabels(sites, fontsize=9.5, color=INK_SECONDARY)
    ax.set_xlabel("records", fontsize=9, color=INK_MUTED)
    ax.set_title("Records by site", fontsize=13, fontweight="bold",
                 color=INK, loc="left", pad=10)
    for spine in ("top", "right", "left"):
        ax.spines[spine].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.xaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, fontsize=9.5, ncols=3, loc="lower right",
              bbox_to_anchor=(1.0, 1.0), labelcolor=INK_SECONDARY)


def _scale_bar(ax, x0: float, y0: float, length_deg: float, label: str) -> None:
    ax.plot([x0, x0 + length_deg], [y0, y0], color=INK_SECONDARY, linewidth=2.5,
            solid_capstyle="butt")
    for x in (x0, x0 + length_deg):
        ax.plot([x, x], [y0 - length_deg * 0.04, y0 + length_deg * 0.04],
                color=INK_SECONDARY, linewidth=2.5)
    ax.text(x0 + length_deg / 2, y0 + length_deg * 0.07, label, ha="center", va="bottom",
            fontsize=8.5, color=INK_SECONDARY)


def _fit_extent(ax, minx: float, miny: float, maxx: float, maxy: float) -> None:
    """Widen the data extent so that it fills the axes without distorting the map."""
    position = ax.get_position()
    figure = ax.figure
    width_in = position.width * figure.get_figwidth()
    height_in = position.height * figure.get_figheight()
    target_ratio = width_in / height_in
    width, height = maxx - minx, maxy - miny
    if width / height < target_ratio:
        extra = (height * target_ratio - width) / 2
        minx, maxx = minx - extra, maxx + extra
    else:
        extra = (width / target_ratio - height) / 2
        miny, maxy = miny - extra, maxy + extra
    ax.set_xlim(minx, maxx)
    ax.set_ylim(miny, maxy)


def _count_outside(frames, minx, miny, maxx, maxy) -> int:
    """Count features whose representative point falls outside the map extent."""
    outside = 0
    for frame in frames:
        if frame is None or frame.empty:
            continue
        points = frame.geometry.representative_point()
        outside += int((~(points.x.between(minx, maxx) & points.y.between(miny, maxy))).sum())
    return outside


def draw_map(ax, validated: gpd.GeoDataFrame, review: gpd.GeoDataFrame,
             overlaps: gpd.GeoDataFrame, title: str, subtitle: str | None = None) -> None:
    """Draw the quality-control map: study area, sites, parcels by status, overlaps."""
    study = study_area_polygon()
    gpd.GeoSeries([study], crs=cfg.CRS).plot(
        ax=ax, facecolor="#f4f4f0", edgecolor=INK_MUTED, linewidth=1.4, linestyle="--", zorder=1
    )
    sites = site_polygons()
    gpd.GeoSeries(list(sites.values()), crs=cfg.CRS).plot(
        ax=ax, facecolor="none", edgecolor=BORDER, linewidth=1.0, zorder=2
    )
    for name, polygon in sites.items():
        ax.text(polygon.centroid.x, polygon.bounds[3] + 0.008, name, ha="center",
                fontsize=9, color=INK_MUTED)

    if not validated.empty:
        validated.plot(ax=ax, facecolor=STATUS_COLORS["VALID"], edgecolor="#0a7d0a",
                       linewidth=0.6, alpha=0.75, zorder=3)
    for status_name in ("REVIEW", "INVALID"):
        subset = review[review["qc_status"] == status_name]
        if not subset.empty:
            subset.plot(ax=ax, facecolor=STATUS_COLORS[status_name], edgecolor="#7a4a00"
                        if status_name == "REVIEW" else "#8f1f1f",
                        linewidth=0.7, alpha=0.85, zorder=4)
    if not overlaps.empty:
        overlaps.plot(ax=ax, facecolor="none", edgecolor="#4a3aa7", hatch="///",
                      linewidth=1.2, zorder=5)

    # The map is framed on the study area: records located far outside it would
    # otherwise flatten the whole landscape into a few pixels.
    minx, miny, maxx, maxy = study.bounds
    margin = max(maxx - minx, maxy - miny) * 0.07
    minx, miny, maxx, maxy = minx - margin, miny - margin, maxx + margin, maxy + margin
    ax.set_aspect("equal", adjustable="box")
    _fit_extent(ax, minx, miny, maxx, maxy)
    (view_minx, view_maxx), (view_miny, view_maxy) = ax.get_xlim(), ax.get_ylim()
    off_extent = _count_outside((validated, review), view_minx, view_miny, view_maxx, view_maxy)

    ax.set_title(title, fontsize=14, fontweight="bold", color=INK, loc="left", pad=30)
    if subtitle:
        ax.text(0, 1.016, subtitle, transform=ax.transAxes, fontsize=9.5, color=INK_MUTED)
    ax.tick_params(labelsize=8)
    for spine in ax.spines.values():
        spine.set_color(BORDER)
    ax.grid(True, color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)

    # north arrow and scale bar
    ax.annotate("N", xy=(0.965, 0.955), xytext=(0.965, 0.86), xycoords="axes fraction",
                textcoords="axes fraction", ha="center", fontsize=11, color=INK_SECONDARY,
                arrowprops=dict(arrowstyle="-|>", color=INK_SECONDARY, linewidth=1.6))
    span = ax.get_xlim()[1] - ax.get_xlim()[0]
    target_km = max(round(span * 111.32 / 5), 1)
    length_deg = target_km / 111.32
    x0 = ax.get_xlim()[0] + span * 0.05
    y0 = ax.get_ylim()[0] + (ax.get_ylim()[1] - ax.get_ylim()[0]) * 0.06
    _scale_bar(ax, x0, y0, length_deg, f"{target_km} km")

    if off_extent:
        ax.text(0.985, 0.02,
                f"{off_extent} flagged record(s) located outside this extent",
                transform=ax.transAxes, ha="right", va="bottom", fontsize=8.5,
                color=INK_SECONDARY,
                bbox=dict(boxstyle="round,pad=0.35", facecolor=PANEL, edgecolor=BORDER))

    handles = [
        Patch(facecolor=STATUS_COLORS["VALID"], edgecolor="#0a7d0a", alpha=0.75,
              label="Validated parcels"),
        Patch(facecolor=STATUS_COLORS["REVIEW"], edgecolor="#7a4a00", alpha=0.85,
              label="Records for review"),
        Patch(facecolor=STATUS_COLORS["INVALID"], edgecolor="#8f1f1f", alpha=0.85,
              label="Invalid records"),
        Patch(facecolor="none", edgecolor="#4a3aa7", hatch="///", label="Overlapping surface"),
        Line2D([0], [0], color=INK_MUTED, linestyle="--", linewidth=1.4, label="Study area"),
    ]
    ax.legend(handles=handles, frameon=False, fontsize=9, loc="upper left",
              bbox_to_anchor=(0.0, -0.055), ncols=5, columnspacing=1.2,
              handlelength=1.6, labelcolor=INK_SECONDARY)


SEVERITY_COLORS = {"Critical": "#d03b3b", "High": "#ec835a", "Medium": "#fab219"}


def _severity_chart(ax, issues: pd.DataFrame) -> None:
    counts = issues["severity"].value_counts()
    order = ["Critical", "High", "Medium"]
    values = [int(counts.get(name, 0)) for name in order]
    positions = list(range(len(order)))[::-1]
    ax.barh(positions, values, height=0.6, color=[SEVERITY_COLORS[name] for name in order],
            edgecolor=SURFACE, linewidth=1.5)
    ax.set_yticks(positions)
    ax.set_yticklabels(order, fontsize=9.5, color=INK_SECONDARY)
    ax.set_title("Issues by severity", fontsize=13, fontweight="bold", color=INK,
                 loc="left", pad=10)
    ax.set_xlabel("issues detected", fontsize=9, color=INK_MUTED)
    for spine in ("top", "right", "left"):
        ax.spines[spine].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.xaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for position, value in zip(positions, values):
        ax.text(value + max(max(values), 1) * 0.02, position, str(value), va="center",
                fontsize=9.5, color=INK_SECONDARY)
    ax.set_xlim(0, max(max(values), 1) * 1.16)


def _rules_card(ax) -> None:
    """Show the rule that turns severities into a record status."""
    ax.set_axis_off()
    ax.add_patch(
        FancyBboxPatch((0, 0), 1, 1, boxstyle="round,pad=0,rounding_size=0.02",
                       linewidth=1, edgecolor=BORDER, facecolor=PANEL,
                       transform=ax.transAxes)
    )
    ax.text(0.04, 0.87, "How a record gets its status", fontsize=12, fontweight="bold",
            color=INK, transform=ax.transAxes)
    rows = [
        ("Critical issue", "INVALID", "cannot be used as it is", STATUS_COLORS["INVALID"]),
        ("High / Medium issue", "REVIEW", "must be checked by the field team",
         STATUS_COLORS["REVIEW"]),
        ("No issue", "VALID", "exported to validated_data", STATUS_COLORS["VALID"]),
    ]
    for index, (condition, status_name, comment, color) in enumerate(rows):
        y = 0.66 - index * 0.20
        ax.add_patch(Rectangle((0.04, y - 0.025), 0.008, 0.11, linewidth=0, facecolor=color,
                               transform=ax.transAxes))
        ax.text(0.075, y + 0.062, f"{condition}  ->  {status_name}", fontsize=10.5,
                fontweight="bold", color=INK, transform=ax.transAxes, va="center")
        ax.text(0.075, y - 0.012, comment, fontsize=9.5, color=INK_SECONDARY,
                transform=ax.transAxes, va="center")
    ax.text(0.04, 0.07,
            "The raw file is never modified. All data are synthetic.",
            fontsize=9, color=INK_MUTED, transform=ax.transAxes)


def make_map_figure(validated, review, overlaps) -> None:
    """Standalone map export (the reference layout reproduced in QGIS)."""
    fig = plt.figure(figsize=(10.5, 9.5))
    ax = fig.add_axes((0.07, 0.10, 0.88, 0.82))
    draw_map(
        ax, validated, review, overlaps,
        "Field Data Quality Control - Synthetic Dataset",
        "Portfolio demonstration using synthetic data - WGS 84 (EPSG:4326)",
    )
    fig.savefig(cfg.MAP_PNG, dpi=170)
    plt.close(fig)


def make_dashboard_figure(report: pd.DataFrame, tables: dict[str, pd.DataFrame],
                          issues: pd.DataFrame, validated, review, overlaps) -> None:
    """Render the KPI dashboard from the values produced by this run."""
    fig = plt.figure(figsize=(16, 12.5))

    fig.text(0.045, 0.955, "Field Data Quality Dashboard", fontsize=25, fontweight="bold",
             color=INK)
    fig.text(
        0.045, 0.928,
        f"Conservation Landscape Data Project (synthetic) - pipeline "
        f"v{_metric(report, 'pipeline_version')} - generated {_metric(report, 'generated_at')}",
        fontsize=11, color=INK_MUTED,
    )

    tiles = [
        (f"{_metric(report, 'total_records')}", "Total records", SERIES),
        (f"{_metric(report, 'valid_records')}", "Validated", STATUS_COLORS["VALID"]),
        (f"{_metric(report, 'records_for_review')}", "Requiring review", STATUS_COLORS["REVIEW"]),
        (f"{_metric(report, 'invalid_records')}", "Invalid", STATUS_COLORS["INVALID"]),
        (f"{_metric(report, 'required_field_completeness_pct')}%", "Field completeness", SERIES),
        (f"{_metric(report, 'spatial_issues')}", "Spatial issues", "#4a3aa7"),
    ]
    kpi_grid = fig.add_gridspec(1, 1, left=0.045, right=0.965, top=0.905, bottom=0.795)
    _kpi_tiles(fig.add_subplot(kpi_grid[0, 0]), tiles)

    charts = fig.add_gridspec(1, 2, left=0.115, right=0.965, top=0.735, bottom=0.545,
                              wspace=0.24)
    _issues_chart(fig.add_subplot(charts[0, 0]), tables["issues_by_type"])
    _sites_chart(fig.add_subplot(charts[0, 1]), tables["records_by_site"])

    bottom = fig.add_gridspec(1, 2, left=0.045, right=0.965, top=0.46, bottom=0.06,
                              width_ratios=[1.15, 1.0], wspace=0.14)
    map_ax = fig.add_subplot(bottom[0, 0])
    draw_map(map_ax, validated, review, overlaps,
             "Quality control map",
             "Validated records, records for review and spatial issues - WGS 84 (EPSG:4326)")

    right = bottom[0, 1].subgridspec(2, 1, height_ratios=[1.0, 1.0], hspace=0.38)
    _severity_chart(fig.add_subplot(right[0, 0]), issues)
    _rules_card(fig.add_subplot(right[1, 0]))

    fig.savefig(cfg.DASHBOARD_PNG, dpi=140)
    plt.close(fig)


def make_workflow_diagram() -> None:
    """Draw the workflow diagram used in the README and the portfolio case study."""
    steps = [
        ("Field data", "100 synthetic records", SERIES),
        ("Raw data", "CSV + GeoJSON, never modified", SERIES),
        ("Automated quality check", "attributes - completeness - consistency", "#4a3aa7"),
        ("Spatial validation", "geometry - study area - overlaps", "#4a3aa7"),
        ("Error report", "records_to_review.csv + quality_report.csv", STATUS_COLORS["REVIEW"]),
        ("Validated data", "validated_data.csv + .geojson", STATUS_COLORS["VALID"]),
        ("QGIS spatial review", "map, legend, scale, overlaps", STATUS_COLORS["VALID"]),
        ("Dashboard / reporting", "KPI, issues by type, map", STATUS_COLORS["VALID"]),
    ]
    fig, ax = plt.subplots(figsize=(7.5, 11))
    ax.set_axis_off()
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.text(0.5, 0.975, "From Raw Field Data to Decision-Ready", ha="center", fontsize=15.5,
            fontweight="bold", color=INK)
    ax.text(0.5, 0.945, "Geospatial Information", ha="center", fontsize=15.5,
            fontweight="bold", color=INK)

    top, box_height, gap = 0.895, 0.079, 0.031
    for index, (title, subtitle, color) in enumerate(steps):
        y = top - index * (box_height + gap) - box_height
        ax.add_patch(
            FancyBboxPatch((0.08, y), 0.84, box_height,
                           boxstyle="round,pad=0,rounding_size=0.012",
                           linewidth=1.2, edgecolor=BORDER, facecolor=PANEL)
        )
        ax.add_patch(Rectangle((0.08, y), 0.008, box_height, linewidth=0, facecolor=color))
        ax.text(0.5, y + box_height * 0.62, title, ha="center", fontsize=12.5,
                fontweight="bold", color=INK)
        ax.text(0.5, y + box_height * 0.26, subtitle, ha="center", fontsize=9.5,
                color=INK_SECONDARY)
        if index < len(steps) - 1:
            ax.annotate("", xy=(0.5, y - gap + 0.004), xytext=(0.5, y - 0.004),
                        arrowprops=dict(arrowstyle="-|>", color=INK_MUTED, linewidth=1.4))
    ax.text(0.5, 0.022, "Synthetic data - portfolio demonstration", ha="center", fontsize=9,
            color=INK_MUTED)
    fig.savefig(cfg.WORKFLOW_DIAGRAM_PNG, dpi=170, bbox_inches="tight")
    plt.close(fig)
