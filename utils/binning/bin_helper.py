import math
import statistics
from collections import Counter, defaultdict

import pandas as pd
from qgis.PyQt.QtCore import QVariant
from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsFeature,
    QgsFeatureSink,
    QgsFields,
    QgsField,
    QgsGeometry,
    QgsPointXY,
    QgsProcessingException,
    QgsSpatialIndex,
    QgsVectorLayer,
    QgsWkbTypes,
)
from shapely import wkt as shapely_wkt
from shapely.geometry import box

from vgrid.utils.geometry import geodesic_dggs_metrics, graticule_dggs_metrics
from vgrid.utils.io import aggregate_joined, stat_column_name

from ..conversion.crs_helper import WGS84_REQUIRED_MSG, is_wgs84

_WGS84 = QgsCoordinateReferenceSystem("EPSG:4326")

BIN_STATISTICS = [
    "count",
    "sum",
    "min",
    "max",
    "mean",
    "median",
    "std",
    "var",
    "range",
    "minority",
    "majority",
    "variety",
]


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


def qgs_attribute_value(value):
    """Convert a Qgs feature attribute to a plain Python value (for pandas)."""
    if isinstance(value, QVariant):
        if not value.isValid() or value.isNull():
            return None
        return value.value()
    return value


def safe_float(value):
    """Convert QVariant or similar to float if possible."""
    value = qgs_attribute_value(value)
    if value is None:
        return None

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


def collect_bin_points(source, category, numeric_field, feedback):
    """Explode MultiPoint features to (lon, lat) records. Returns (records, bbox)."""
    fields = source.fields()
    names = [fields[i].name() for i in range(len(fields))]
    if category and category not in names:
        raise QgsProcessingException(
            f"Category field '{category}' not found in input layer."
        )
    if numeric_field and numeric_field not in names:
        raise QgsProcessingException(
            f"Numeric field '{numeric_field}' not found in input layer."
        )

    records = []
    minx = miny = float("inf")
    maxx = maxy = float("-inf")

    for feat in source.getFeatures():
        if feedback.isCanceled():
            break
        geom = feat.geometry()
        if geom is None or geom.isEmpty():
            continue
        if QgsWkbTypes.geometryType(geom.wkbType()) != QgsWkbTypes.PointGeometry:
            continue

        attrs = {}
        if category:
            val = qgs_attribute_value(feat[category])
            attrs[category] = None if val is None else str(val)
        if numeric_field:
            attrs[numeric_field] = safe_float(feat[numeric_field])

        if geom.isMultipart():
            points = geom.asMultiPoint()
        else:
            points = [geom.asPoint()]

        for pt in points:
            lon, lat = pt.x(), pt.y()
            minx, miny = min(minx, lon), min(miny, lat)
            maxx, maxy = max(maxx, lon), max(maxy, lat)
            records.append({**attrs, "lon": lon, "lat": lat})

    if not records:
        return [], None
    return records, (minx, miny, maxx, maxy)


def join_points_to_bin_grid(
    grid_layer, records, id_col, category, numeric_field, feedback
):
    """Point-in-polygon join using QgsSpatialIndex."""
    index = QgsSpatialIndex()
    cells = {}
    for feat in grid_layer.getFeatures():
        fid = feat.id()
        if index.addFeature(feat):
            cells[fid] = feat

    rows = []
    total = len(records)
    for i, rec in enumerate(records):
        if feedback.isCanceled():
            break
        pt_geom = QgsGeometry.fromPointXY(QgsPointXY(rec["lon"], rec["lat"]))
        for fid in index.intersects(pt_geom.boundingBox()):
            cell_feat = cells.get(fid)
            if cell_feat is None:
                continue
            if cell_feat.geometry().contains(pt_geom):
                row = {id_col: cell_feat[id_col]}
                if category:
                    row[category] = rec.get(category)
                if numeric_field:
                    row[numeric_field] = rec.get(numeric_field)
                rows.append(row)
                break
        if total and i % 500 == 0:
            feedback.setProgress(int(30 * i / total))

    return pd.DataFrame(rows)


def bbox_memory_layer(minx, miny, maxx, maxy, layer_name="bin_extent"):
    layer = QgsVectorLayer("Polygon?crs=EPSG:4326", layer_name, "memory")
    feat = QgsFeature()
    feat.setGeometry(QgsGeometry.fromWkt(box(minx, miny, maxx, maxy).wkt))
    layer.dataProvider().addFeatures([feat])
    return layer


def empty_bin_output_fields(id_col, metric_kind="geodesic"):
    out_fields = QgsFields()
    out_fields.append(QgsField(id_col, QVariant.String))
    if metric_kind == "graticule":
        append_graticule_metric_fields(out_fields)
    else:
        append_geodesic_metric_fields(out_fields)
    return out_fields


def build_bin_output_fields(grid_layer, grouped, stats, id_col):
    out_fields = QgsFields()
    for i in range(grid_layer.fields().count()):
        out_fields.append(grid_layer.fields()[i])
    stat_cols = [c for c in grouped.columns if c != id_col]
    for col in stat_cols:
        out_fields.append(QgsField(col, stat_field_type(stats)))
    return out_fields, stat_cols


def dggrid_gdf_to_memory_layer(
    dggrid_gdf, id_col, resolution, dggs_type, feedback=None
):
    """Build a WGS84 memory polygon layer from a DGGRID GeoDataFrame (no GeoPandas sjoin)."""
    from vgrid.utils.geometry import dggrid_num_edges

    from ..dggrid_instance import normalize_dggrid_cell_id

    num_edges = dggrid_num_edges(dggs_type)

    fields = QgsFields()
    fields.append(QgsField(id_col, QVariant.String))
    fields.append(QgsField("resolution", QVariant.Int))
    fields.append(QgsField("center_lat", QVariant.Double))
    fields.append(QgsField("center_lon", QVariant.Double))
    fields.append(QgsField("avg_edge_len", QVariant.Double))
    fields.append(QgsField("cell_area", QVariant.Double))
    fields.append(QgsField("cell_perimeter", QVariant.Double))

    layer = QgsVectorLayer("Polygon?crs=EPSG:4326", "dggrid_bin_grid", "memory")
    provider = layer.dataProvider()
    provider.addAttributes(fields)
    layer.updateFields()

    id_source = "global_id" if "global_id" in dggrid_gdf.columns else None
    if id_source is None:
        for col in ("name", "seqnum"):
            if col in dggrid_gdf.columns:
                id_source = col
                break
    if id_source is None:
        raise QgsProcessingException(
            "DGGRID grid output has no cell ID column (global_id, name, seqnum)."
        )

    features = []
    total = len(dggrid_gdf)
    for idx, row in dggrid_gdf.iterrows():
        cell_polygon = row.geometry
        if cell_polygon is None or cell_polygon.is_empty:
            continue

        cell_id = normalize_dggrid_cell_id(row.get(id_source))
        if cell_id is None:
            continue

        center_lat, center_lon, avg_edge_len, cell_area, cell_perimeter = (
            geodesic_dggs_metrics(cell_polygon, num_edges)
        )

        feat = QgsFeature(fields)
        feat.setGeometry(QgsGeometry.fromWkt(cell_polygon.wkt))
        feat.setAttributes(
            [
                cell_id,
                resolution,
                center_lat,
                center_lon,
                avg_edge_len,
                cell_area,
                cell_perimeter,
            ]
        )
        features.append(feat)
        if feedback and total and idx % 500 == 0:
            feedback.setProgress(int(15 * idx / total))

    if features:
        provider.addFeatures(features)
    layer.updateExtents()
    if feedback:
        feedback.pushInfo(f"Generated {layer.featureCount()} DGGRID cells.")
    return layer


def generate_dggrid_grid_qgis(
    dggs_type,
    resolution,
    extent_layer,
    feedback=None,
    densification=None,
):
    """DGGRID grid over extent bbox for point binning."""
    from vgrid.utils.io import validate_dggrid_resolution, validate_dggrid_type

    from ...settings import settings
    from ..dggrid_instance import (
        _ensure_dggrid_global_id_column,
        build_dggrid_options,
        generate_grid_qgis,
        get_plugin_dggrid_instance,
    )

    dggs_type = validate_dggrid_type(dggs_type)
    resolution = validate_dggrid_resolution(dggs_type, resolution)
    id_col = f"dggrid_{dggs_type.lower()}"

    feat = next(extent_layer.getFeatures())
    bbox = feat.geometry().boundingBox()
    bbox_tuple = (
        bbox.xMinimum(),
        bbox.yMinimum(),
        bbox.xMaximum(),
        bbox.yMaximum(),
    )

    if feedback:
        feedback.pushInfo(
            f"Generating DGGRID {dggs_type} grid at resolution {resolution}..."
        )

    dens = (
        densification
        if densification is not None
        else settings.dggridDensificationSpinBox
    )
    options = build_dggrid_options(dens)
    dggrid_instance = get_plugin_dggrid_instance(feedback=feedback)
    dggrid_gdf = generate_grid_qgis(
        dggrid_instance,
        dggs_type,
        resolution,
        bbox_tuple,
        output_address_type="SEQNUM",
        split_antimeridian=False,
        aggregate=False,
        options=options,
    )

    if dggrid_gdf is None or dggrid_gdf.empty:
        if feedback:
            feedback.pushInfo("No DGGRID cells generated for the point extent.")
        layer = QgsVectorLayer("Polygon?crs=EPSG:4326", "dggrid_bin_grid", "memory")
        return layer

    dggrid_gdf, _ = _ensure_dggrid_global_id_column(dggrid_gdf)
    return dggrid_gdf_to_memory_layer(
        dggrid_gdf, id_col, resolution, dggs_type, feedback=feedback
    )


def generate_digipin_grid_qgis(resolution, extent_layer, feedback=None):
    """DIGIPIN grid over extent (vgrid digipin_grid → QgsVectorLayer)."""
    from vgrid.generator.digipingrid import digipin_grid
    from vgrid.utils.io import validate_digipin_resolution

    from ..conversion.raster2dggs_helper import gdf_to_qgs_vector_layer

    resolution = validate_digipin_resolution(resolution)
    feat = next(extent_layer.getFeatures())
    bbox = feat.geometry().boundingBox()
    bbox_tuple = (
        bbox.xMinimum(),
        bbox.yMinimum(),
        bbox.xMaximum(),
        bbox.yMaximum(),
    )
    if feedback:
        feedback.pushInfo(f"Generating DIGIPIN grid at resolution {resolution}...")
    gdf = digipin_grid(resolution, bbox_tuple)
    layer = gdf_to_qgs_vector_layer(gdf, f"digipin_grid_{resolution}")
    if feedback:
        feedback.pushInfo(f"Generated {layer.featureCount()} DIGIPIN cells.")
    return layer


def prepare_point_bin_algorithm(
    point_layer, stats, numeric_field, category_field
):
    """Shared prepareAlgorithm checks for point DGGS binning tools."""
    if stats != "count" and not numeric_field:
        raise QgsProcessingException(
            "A numeric field is required for statistics other than 'count'."
        )
    if not is_wgs84(point_layer.sourceCrs()):
        raise QgsProcessingException(WGS84_REQUIRED_MSG)


def process_point_dggs_bin(
    alg,
    parameters,
    context,
    feedback,
    point_layer,
    resolution,
    stats,
    category_field,
    numeric_field,
    id_col,
    dggs_label,
    validate_resolution_fn,
    generate_grid_fn,
    metric_kind="geodesic",
):
    """
    Grid over point extent → spatial join → aggregate → write binned cells.

    *generate_grid_fn* is ``(resolution, extent_layer, feedback) -> QgsVectorLayer``.
    """
    resolution = validate_resolution_fn(resolution)
    category = category_field or None
    numeric_field = numeric_field or None

    feedback.setProgress(0)
    feedback.pushInfo("Loading and exploding point geometries...")
    points, bbox = collect_bin_points(
        point_layer, category, numeric_field, feedback
    )

    if feedback.isCanceled():
        return {}

    def _create_sink(out_fields):
        return alg.parameterAsSink(
            parameters,
            alg.OUTPUT,
            context,
            out_fields,
            QgsWkbTypes.Polygon,
            _WGS84,
        )

    if not points:
        feedback.pushInfo("No point features to bin.")
        sink, dest_id = _create_sink(empty_bin_output_fields(id_col, metric_kind))
        return {alg.OUTPUT: dest_id}

    minx, miny, maxx, maxy = bbox
    extent_layer = bbox_memory_layer(
        minx, miny, maxx, maxy, layer_name=f"{id_col}_bin_extent"
    )

    feedback.pushInfo(
        f"Generating {dggs_label} grid (resolution {resolution}) "
        "for point layer extent..."
    )
    grid_layer = generate_grid_fn(resolution, extent_layer, feedback)
    if grid_layer is None or feedback.isCanceled():
        return {}

    feedback.pushInfo(f"Assigning points to {dggs_label} cells (spatial join)...")
    joined = join_points_to_bin_grid(
        grid_layer, points, id_col, category, numeric_field, feedback
    )

    if joined.empty:
        feedback.pushInfo(f"No points fell inside {dggs_label} cells.")
        sink, dest_id = _create_sink(empty_bin_output_fields(id_col, metric_kind))
        return {alg.OUTPUT: dest_id}

    feedback.pushInfo(
        f"Aggregating {len(joined)} point-in-cell match(es) ({stats})..."
    )
    grouped = aggregate_joined(
        joined,
        id_col,
        stats=stats,
        category=category,
        numeric_field=numeric_field,
    )
    grouped = grouped.reset_index()

    stats_by_id = {str(row[id_col]): row for _, row in grouped.iterrows()}
    out_fields, stat_cols = build_bin_output_fields(
        grid_layer, grouped, stats, id_col
    )

    sink, dest_id = _create_sink(out_fields)

    grid_count = grid_layer.featureCount()
    written = 0
    for i, feat in enumerate(grid_layer.getFeatures()):
        if feedback.isCanceled():
            break
        cell_id = str(feat[id_col])
        if cell_id not in stats_by_id:
            continue

        stat_row = stats_by_id[cell_id]
        attrs = list(feat.attributes())
        for col in stat_cols:
            val = stat_row[col]
            if val is None or (isinstance(val, float) and math.isnan(val)):
                attrs.append(None)
            else:
                attrs.append(val)

        out_feat = QgsFeature(out_fields)
        out_feat.setGeometry(QgsGeometry(feat.geometry()))
        out_feat.setAttributes(attrs)
        sink.addFeature(out_feat, QgsFeatureSink.FastInsert)
        written += 1
        if grid_count:
            feedback.setProgress(30 + int(70 * (i + 1) / grid_count))

    feedback.pushInfo(f"Wrote {written} binned {dggs_label} cell(s).")
    return {alg.OUTPUT: dest_id}
