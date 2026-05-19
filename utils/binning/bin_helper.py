import statistics
from collections import Counter, defaultdict

from qgis.PyQt.QtCore import QVariant
from qgis.core import QgsField
from shapely import wkt as shapely_wkt

from vgrid.utils.geometry import geodesic_dggs_metrics, graticule_dggs_metrics
from vgrid.utils.io import stat_column_name


def get_default_stats_structure():
    return {
        "count": 0,
        "sum": [],
        "mean": [],
        "min": [],
        "max": [],
        "median": [],
        "std": [],
        "var": [],
        "range": [],
        "values": [],
    }


def safe_float(value):
    """Convert QVariant or similar to float if possible."""
    if isinstance(value, QVariant):
        if not value.isValid() or value.isNull():
            return None
        value = value.value()

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def normalize_category(cat):
    """Normalize category strings to avoid duplicates due to case/spacing."""
    if not isinstance(cat, str):
        cat = str(cat)
    return cat.strip().lower()


def bin_stat_column_name(stats, numeric_field=None, category_field=None, category_value=None):
    """Match vgrid DGGS binning column names via :func:`stat_column_name`."""
    cat = category_value if category_field else None
    if stats == "count":
        return stat_column_name("count", category_value=cat)
    return stat_column_name(stats, numeric_field=numeric_field, category_value=cat)


def stat_field_type(stats):
    if stats in ("count", "variety"):
        return QVariant.Int
    if stats in ("minority", "majority"):
        return QVariant.String
    return QVariant.Double


def append_bin_stat_fields(
    out_fields,
    all_categories,
    stats,
    numeric_field=None,
    category_field=None,
):
    """Append statistic columns to ``out_fields`` using vgrid naming."""
    for cat in sorted(all_categories):
        col_name = bin_stat_column_name(
            stats,
            numeric_field=numeric_field,
            category_field=category_field,
            category_value=cat,
        )
        out_fields.append(QgsField(col_name, stat_field_type(stats)))


def append_geodesic_metric_fields(out_fields):
    out_fields.append(QgsField("resolution", QVariant.Int))
    out_fields.append(QgsField("center_lat", QVariant.Double))
    out_fields.append(QgsField("center_lon", QVariant.Double))
    out_fields.append(QgsField("avg_edge_len", QVariant.Double))
    out_fields.append(QgsField("cell_area", QVariant.Double))
    out_fields.append(QgsField("cell_perimeter", QVariant.Double))


def append_graticule_metric_fields(out_fields):
    out_fields.append(QgsField("resolution", QVariant.Int))
    out_fields.append(QgsField("center_lat", QVariant.Double))
    out_fields.append(QgsField("center_lon", QVariant.Double))
    out_fields.append(QgsField("cell_width", QVariant.Double))
    out_fields.append(QgsField("cell_height", QVariant.Double))
    out_fields.append(QgsField("cell_area", QVariant.Double))
    out_fields.append(QgsField("cell_perimeter", QVariant.Double))


def _shapely_polygon(geom):
    if hasattr(geom, "centroid") and hasattr(geom, "bounds"):
        return geom
    if hasattr(geom, "wkt"):
        return shapely_wkt.loads(geom.wkt)
    return geom


def geodesic_cell_props(geom, resolution, num_edges):
    poly = _shapely_polygon(geom)
    center_lat, center_lon, avg_edge_len, cell_area, cell_perimeter = (
        geodesic_dggs_metrics(poly, num_edges)
    )
    return {
        "resolution": resolution,
        "center_lat": center_lat,
        "center_lon": center_lon,
        "avg_edge_len": avg_edge_len,
        "cell_area": cell_area,
        "cell_perimeter": cell_perimeter,
    }


def graticule_cell_props(geom, resolution):
    poly = _shapely_polygon(geom)
    center_lat, center_lon, cell_width, cell_height, cell_area, cell_perimeter = (
        graticule_dggs_metrics(poly)
    )
    return {
        "resolution": resolution,
        "center_lat": center_lat,
        "center_lon": center_lon,
        "cell_width": cell_width,
        "cell_height": cell_height,
        "cell_area": cell_area,
        "cell_perimeter": cell_perimeter,
    }


def a5_num_edges(resolution):
    return 3 if resolution == 1 else 5


def h3_num_edges(h3_id):
    import h3

    return 5 if h3.is_pentagon(h3_id) else 6


def rhealpix_num_edges(rhealpix_id, rhealpix_dggs=None):
    if rhealpix_dggs is None:
        from vgrid.dggs.rhealpixdggs.dggs import RHEALPixDGGS
        from vgrid.dggs.rhealpixdggs.ellipsoids import WGS84_ELLIPSOID

        rhealpix_dggs = RHEALPixDGGS(
            ellipsoid=WGS84_ELLIPSOID, north_square=1, south_square=3, N_side=3
        )
    if ":" in rhealpix_id:
        parts = rhealpix_id.split(":")
        rhealpix_uids = (parts[0],) + tuple(int(p) for p in parts[1:])
    else:
        rhealpix_uids = (rhealpix_id[0],) + tuple(map(int, rhealpix_id[1:]))
    cell = rhealpix_dggs.cell(rhealpix_uids)
    return 3 if cell.ellipsoidal_shape() == "dart" else 4


def dggrid_num_edges(geom):
    poly = _shapely_polygon(geom)
    if hasattr(poly, "exterior"):
        return len(poly.exterior.coords) - 1
    return 4


def dggal_num_edges(dggs_type, zone_id):
    import vgrid.utils.geometry as vgrid_geometry
    from dggal import nullZone
    from vgrid.utils.constants import DGGAL_TYPES
    from vgrid.utils.io import validate_dggal_type

    dggs_type = validate_dggal_type(dggs_type)
    dggs_class_name = DGGAL_TYPES[dggs_type]["class_name"]
    dggrs = getattr(vgrid_geometry, dggs_class_name)()
    zone = dggrs.getZoneFromTextID(zone_id)
    if zone == nullZone:
        return 4
    return dggrs.countZoneEdges(zone)


def collect_stat_props(
    bins,
    cell_id,
    all_categories,
    stats,
    numeric_field=None,
    category_field=None,
):
    props = {}
    for cat in sorted(all_categories):
        values = bins[cell_id].get(cat, get_default_stats_structure())
        props.update(
            stat_props_for_category(
                values, stats, numeric_field, category_field, cat
            )
        )
    return props


def build_bin_feature_props(
    geom,
    resolution,
    id_field,
    cell_id,
    bins,
    all_categories,
    stats,
    numeric_field=None,
    category_field=None,
    metric_kind="geodesic",
    num_edges=None,
    rhealpix_dggs=None,
):
    if metric_kind == "geodesic":
        if num_edges is None and rhealpix_dggs is not None:
            num_edges = rhealpix_num_edges(cell_id, rhealpix_dggs)
        props = geodesic_cell_props(geom, resolution, num_edges)
    else:
        props = graticule_cell_props(geom, resolution)
    props.update(
        collect_stat_props(
            bins, cell_id, all_categories, stats, numeric_field, category_field
        )
    )
    props[id_field] = cell_id
    return props


def feature_attributes(out_fields, props):
    return [props.get(f.name()) for f in out_fields]


def compute_stat_value(values, stats):
    """Compute one statistic from the accumulated per-category structure."""
    if stats == "count":
        return values["count"]
    if stats == "sum":
        return sum(values["sum"]) if values["sum"] else None
    if stats == "min":
        return min(values["min"]) if values["min"] else None
    if stats == "max":
        return max(values["max"]) if values["max"] else None
    if stats == "mean":
        return statistics.mean(values["mean"]) if values["mean"] else None
    if stats == "median":
        return statistics.median(values["median"]) if values["median"] else None
    if stats == "std":
        return statistics.stdev(values["std"]) if len(values["std"]) > 1 else 0
    if stats == "var":
        return statistics.variance(values["var"]) if len(values["var"]) > 1 else 0
    if stats == "range":
        return (
            max(values["range"]) - min(values["range"]) if values["range"] else 0
        )
    if stats == "minority":
        freq = Counter(values["values"])
        return min(freq.items(), key=lambda x: x[1])[0] if freq else None
    if stats == "majority":
        freq = Counter(values["values"])
        return max(freq.items(), key=lambda x: x[1])[0] if freq else None
    if stats == "variety":
        return len(set(values["values"]))
    raise ValueError(f"Unsupported statistic: {stats}")


def stat_props_for_category(
    values,
    stats,
    numeric_field=None,
    category_field=None,
    category_value=None,
):
    """Return ``{column_name: value}`` for one category bucket."""
    col_name = bin_stat_column_name(
        stats,
        numeric_field=numeric_field,
        category_field=category_field,
        category_value=category_value,
    )
    return {col_name: compute_stat_value(values, stats)}


def append_stats_value(
    h3_bins, h3_id, props, stats, numeric_field=None, category_field=None
):
    category_value = props.get(category_field, "all") if category_field else "all"
    norm_category = normalize_category(category_value)

    if h3_id not in h3_bins:
        h3_bins[h3_id] = defaultdict(get_default_stats_structure)

    stats_struct = h3_bins[h3_id][norm_category]

    if stats == "count":
        stats_struct["count"] += 1

    elif stats in ["minority", "majority", "variety"]:
        value = props.get(numeric_field or category_field)
        if value is not None:
            stats_struct["values"].append(value)

    elif numeric_field:
        raw_value = props.get(numeric_field)
        val = safe_float(raw_value)
        if val is not None:
            stats_struct[stats].append(val)
