"""Small geodesic helpers shared by the generation and validation steps."""

from __future__ import annotations

from pyproj import Geod
from shapely.geometry import Polygon, box

from config import SITES, STUDY_AREA_BOUNDS

_GEOD = Geod(ellps="WGS84")


def study_area_polygon() -> Polygon:
    """Return the polygon of the fictitious study area."""
    return box(*STUDY_AREA_BOUNDS)


def site_polygons() -> dict[str, Polygon]:
    """Return one polygon per fictitious collection site."""
    return {name: box(*bounds) for name, bounds in SITES.items()}


def geodesic_area_ha(geometry) -> float:
    """Return the area of a polygon in hectares, computed on the WGS84 ellipsoid."""
    if geometry is None or geometry.is_empty:
        return 0.0
    area_m2, _ = _GEOD.geometry_area_perimeter(geometry)
    return abs(area_m2) / 10_000.0


def geodesic_distance_m(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """Return the distance in metres between two WGS84 positions."""
    _, _, distance = _GEOD.inv(lon1, lat1, lon2, lat2)
    return abs(distance)


def metres_to_degrees(metres: float, latitude: float) -> tuple[float, float]:
    """Convert a distance in metres to (delta_longitude, delta_latitude) degrees."""
    import math

    delta_lat = metres / 111_320.0
    delta_lon = metres / (111_320.0 * max(math.cos(math.radians(latitude)), 1e-6))
    return delta_lon, delta_lat
