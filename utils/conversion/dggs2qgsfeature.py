from qgis.core import (
    QgsFeature,
    QgsGeometry,
    QgsField,
    QgsFields,
)
from qgis.PyQt.QtCore import QVariant
from pyproj import Geod
from vgrid.conversion.dggs2geo.digipin2geo import digipin2geo
from vgrid.conversion.dggs2geo.maidenhead2geo import maidenhead2geo
from vgrid.conversion.dggs2geo.geohash2geo import geohash2geo
from vgrid.conversion.dggs2geo.mgrs2geo import mgrs2geo
from vgrid.conversion.dggs2geo.olc2geo import olc2geo
from vgrid.conversion.dggs2geo.qtm2geo import qtm2geo
from vgrid.conversion.dggs2geo.ease2geo import ease2geo
from vgrid.conversion.dggs2geo.isea3h2geo import isea3h2geo
from vgrid.conversion.dggs2geo.isea4t2geo import isea4t2geo
from vgrid.conversion.dggs2geo.a52geo import a52geo
from vgrid.conversion.dggs2geo.rhealpix2geo import rhealpix2geo
from vgrid.conversion.dggs2geo.s22geo import s22geo
from vgrid.conversion.dggs2geo.h32geo import h32geo
from vgrid.utils.constants import ISEA3H_ACCURACY_RES_DICT
from vgrid.utils.geometry import (
    graticule_dggs_metrics,
    geodesic_dggs_metrics,
)
import a5
import h3
from vgrid.dggs import mercantile
import platform
from dggal import *
from vgrid.utils.constants import DGGAL_TYPES
from vgrid.utils.geometry import dggal_to_geo
from vgrid.utils.antimeridian import fix_polygon
import re
from shapely.geometry import Polygon

from vgrid.dggs import s2, olc, georef, mgrs
from gars_field.garsgrid import GARSGrid
from ..antimeridian_helper import geo_with_fix, use_split_antimeridian
from ..rhealpix_helper import resolve_rhealpix_n_side
from vgrid.utils.io import rhealpix_cell_from_id

app = Application(appGlobals=globals())
pydggal_setup(app)


if platform.system() == "Windows":
    from vgrid.dggs.eaggr.eaggr import Eaggr
    from vgrid.dggs.eaggr.shapes.dggs_cell import DggsCell
    from vgrid.dggs.eaggr.enums.model import Model

    isea3h_dggs = Eaggr(Model.ISEA3H)


geod = Geod(ellps="WGS84")

GEODESIC_METRIC_NAMES = (
    "center_lat",
    "center_lon",
    "avg_edge_len",
    "cell_area",
    "cell_perimeter",
)
GRATICULE_METRIC_NAMES = (
    "center_lat",
    "center_lon",
    "cell_width",
    "cell_height",
    "cell_area",
    "cell_perimeter",
)


def _cell_metrics_enabled(kwargs):
    return bool(kwargs.get("cell_metrics", False))


def _attach_dggs_attributes(
    qgs_feature,
    source_feature,
    id_field,
    cell_id,
    resolution,
    cell_metrics,
    metric_names,
    metric_values,
):
    """Set the cell id, resolution, and optional metric attributes."""
    all_fields = QgsFields()
    for field in source_feature.fields():
        all_fields.append(field)
    all_fields.append(QgsField(id_field, QVariant.String))
    all_fields.append(QgsField("resolution", QVariant.Int))
    attributes = list(source_feature.attributes()) + [cell_id, resolution]
    if cell_metrics:
        for name in metric_names:
            all_fields.append(QgsField(name, QVariant.Double))
        attributes.extend(metric_values)
    qgs_feature.setFields(all_fields)
    qgs_feature.setAttributes(attributes)
    return qgs_feature


def h32qgsfeature(feature, h3_id, shift_antimeridian=False, split_antimeridian=False, **_kwargs):
    cell_polygon = geo_with_fix(
        h32geo, h3_id, "h3", shift_antimeridian, split_antimeridian
    )
    num_edges = 6
    if h3.is_pentagon(h3_id):
        num_edges = 5
    resolution = h3.get_resolution(h3_id)
    cell_metrics = _cell_metrics_enabled(_kwargs)
    metrics = geodesic_dggs_metrics(cell_polygon, num_edges) if cell_metrics else None

    h3_feature = QgsFeature()
    h3_feature.setGeometry(QgsGeometry.fromWkt(cell_polygon.wkt))
    return _attach_dggs_attributes(
        h3_feature,
        feature,
        "h3",
        h3_id,
        resolution,
        cell_metrics,
        GEODESIC_METRIC_NAMES,
        metrics,
    )


def s22qgsfeature(
    feature, s2_token, shift_antimeridian=False, split_antimeridian=False, **_kwargs
):
    cell_id = s2.CellId.from_token(s2_token)
    cell_polygon = geo_with_fix(
        s22geo, s2_token, "s2", shift_antimeridian, split_antimeridian
    )
    resolution = cell_id.level()
    num_edges = 4
    cell_metrics = _cell_metrics_enabled(_kwargs)
    metrics = geodesic_dggs_metrics(cell_polygon, num_edges) if cell_metrics else None

    s2_feature = QgsFeature()
    s2_feature.setGeometry(QgsGeometry.fromWkt(cell_polygon.wkt))
    return _attach_dggs_attributes(
        s2_feature,
        feature,
        "s2",
        s2_token,
        resolution,
        cell_metrics,
        GEODESIC_METRIC_NAMES,
        metrics,
    )


def a52qgsfeature(feature, a5_hex, shift_antimeridian=False, split_antimeridian=False, **_kwargs):
    cell_polygon = a52geo(
        a5_hex,
        split_antimeridian=use_split_antimeridian(
            shift_antimeridian, split_antimeridian
        ),
    )
    num_edges = 5
    cell_bigint = a5.hex_to_u64(a5_hex)
    resolution = a5.get_resolution(cell_bigint)
    cell_metrics = _cell_metrics_enabled(_kwargs)
    metrics = geodesic_dggs_metrics(cell_polygon, num_edges) if cell_metrics else None

    a5_feature = QgsFeature()
    a5_feature.setGeometry(QgsGeometry.fromWkt(cell_polygon.wkt))
    return _attach_dggs_attributes(
        a5_feature,
        feature,
        "a5",
        a5_hex,
        resolution,
        cell_metrics,
        GEODESIC_METRIC_NAMES,
        metrics,
    )


def rhealpix2qgsfeature(
    feature, rhealpix_id, shift_antimeridian=False, split_antimeridian=False, N_side=None, **_kwargs
):
    rhealpix_id = str(rhealpix_id)
    N_side = resolve_rhealpix_n_side(_kwargs.get("N_side", N_side))
    rhealpix_cell = rhealpix_cell_from_id(rhealpix_id, N_side=N_side)
    resolution = rhealpix_cell.resolution
    cell_polygon = geo_with_fix(
        rhealpix2geo, rhealpix_id, "rhealpix", shift_antimeridian, split_antimeridian, N_side=N_side
    )

    num_edges = 4
    if rhealpix_cell.ellipsoidal_shape == "dart":
        num_edges = 3

    cell_metrics = _cell_metrics_enabled(_kwargs)
    metrics = geodesic_dggs_metrics(cell_polygon, num_edges) if cell_metrics else None

    rhealpix_feature = QgsFeature()
    rhealpix_feature.setGeometry(QgsGeometry.fromWkt(cell_polygon.wkt))
    return _attach_dggs_attributes(
        rhealpix_feature,
        feature,
        "rhealpix",
        rhealpix_id,
        resolution,
        cell_metrics,
        GEODESIC_METRIC_NAMES,
        metrics,
    )


def isea4t2qgsfeature(
    feature, isea4t_id, shift_antimeridian=False, split_antimeridian=False, **_kwargs
):
    if platform.system() == "Windows":
        resolution = len(isea4t_id) - 2
        cell_polygon = geo_with_fix(
            isea4t2geo, isea4t_id, "isea4t", shift_antimeridian, split_antimeridian
        )

        num_edges = 3
        cell_metrics = _cell_metrics_enabled(_kwargs)
        metrics = geodesic_dggs_metrics(cell_polygon, num_edges) if cell_metrics else None

        isea4t_feature = QgsFeature()
        isea4t_feature.setGeometry(QgsGeometry.fromWkt(cell_polygon.wkt))
        return _attach_dggs_attributes(
            isea4t_feature,
            feature,
            "isea4t",
            isea4t_id,
            resolution,
            cell_metrics,
            GEODESIC_METRIC_NAMES,
            metrics,
        )


def isea3h2qgsfeature(
    feature, isea3h_id, shift_antimeridian=False, split_antimeridian=False, **_kwargs
):
    if platform.system() == "Windows":
        DggsCell(isea3h_id)
        cell_polygon = geo_with_fix(
            isea3h2geo, isea3h_id, "isea3h", shift_antimeridian, split_antimeridian
        )
        cell_centroid = cell_polygon.centroid
        center_lat = round(cell_centroid.y, 7)
        center_lon = round(cell_centroid.x, 7)

        cell_area = abs(geod.geometry_area_perimeter(cell_polygon)[0])
        cell_perimeter = abs(geod.geometry_area_perimeter(cell_polygon)[1])
        isea3h2point = isea3h_dggs.convert_dggs_cell_to_point(DggsCell(isea3h_id))

        accuracy = isea3h2point._accuracy

        avg_edge_len = cell_perimeter / 6

        resolution = ISEA3H_ACCURACY_RES_DICT.get(accuracy)

        if resolution == 0:  # icosahedron faces at resolution = 0
            avg_edge_len = cell_perimeter / 3

        if accuracy == 0.0:
            if round(avg_edge_len, 2) == 0.06:
                resolution = 33
            elif round(avg_edge_len, 2) == 0.03:
                resolution = 34
            elif round(avg_edge_len, 2) == 0.02:
                resolution = 35
            elif round(avg_edge_len, 2) == 0.01:
                resolution = 36

            elif round(avg_edge_len, 3) == 0.007:
                resolution = 37
            elif round(avg_edge_len, 3) == 0.004:
                resolution = 38
            elif round(avg_edge_len, 3) == 0.002:
                resolution = 39
            elif round(avg_edge_len, 3) <= 0.001:
                resolution = 40

        cell_metrics = _cell_metrics_enabled(_kwargs)
        metrics = None
        if cell_metrics:
            metrics = (
                center_lat,
                center_lon,
                round(avg_edge_len, 3),
                round(cell_area, 3),
                round(cell_perimeter, 3),
            )

        isea3h_feature = QgsFeature()
        isea3h_feature.setGeometry(QgsGeometry.fromWkt(cell_polygon.wkt))
        return _attach_dggs_attributes(
            isea3h_feature,
            feature,
            "isea3h",
            isea3h_id,
            resolution,
            cell_metrics,
            GEODESIC_METRIC_NAMES,
            metrics,
        )


def ease2qgsfeature(feature, ease_id, **kwargs):
    resolution = int(ease_id[1])  # Get the level (e.g., 'L0' -> 0)
    cell_polygon = ease2geo(ease_id)

    num_edges = 4
    cell_metrics = _cell_metrics_enabled(kwargs)
    metrics = geodesic_dggs_metrics(cell_polygon, num_edges) if cell_metrics else None

    ease_feature = QgsFeature()
    ease_feature.setGeometry(QgsGeometry.fromWkt(cell_polygon.wkt))
    return _attach_dggs_attributes(
        ease_feature,
        feature,
        "ease",
        ease_id,
        resolution,
        cell_metrics,
        GEODESIC_METRIC_NAMES,
        metrics,
    )


def dggal2qgsfeature(
    feature, zone_id, dggs_type, shift_antimeridian=False, split_antimeridian=False, **_kwargs
):
    """
    Unified function to convert DGGSAL cell ID to QGIS feature for any DGGSAL type.

    Args:
        feature: Input QGIS feature
        zone_id: DGGSAL cell ID
        dggs_type: DGGSAL type (e.g., 'gnosis', 'isea3h', 'isea9r', etc.)

    Returns:
        QgsFeature: Feature with DGGSAL geometry and attributes
    """
    # Create the appropriate DGGS instance
    dggs_class_name = DGGAL_TYPES[dggs_type]["class_name"]
    dggrs = globals()[dggs_class_name]()

    zone = dggrs.getZoneFromTextID(zone_id)
    resolution = dggrs.getZoneLevel(zone)
    num_edges = dggrs.countZoneEdges(zone)
    cell_polygon = dggal_to_geo(dggs_type, zone_id)
    if use_split_antimeridian(shift_antimeridian, split_antimeridian):
        cell_polygon = fix_polygon(cell_polygon)
    cell_metrics = _cell_metrics_enabled(_kwargs)
    metrics = geodesic_dggs_metrics(cell_polygon, num_edges) if cell_metrics else None

    dggal_feature = QgsFeature()
    dggal_feature.setGeometry(QgsGeometry.fromWkt(cell_polygon.wkt))
    return _attach_dggs_attributes(
        dggal_feature,
        feature,
        f"dggal_{dggs_type}",
        zone_id,
        resolution,
        cell_metrics,
        GEODESIC_METRIC_NAMES,
        metrics,
    )


def qtm2qgsfeature(feature, qtm_id, **kwargs):
    cell_polygon = qtm2geo(qtm_id)
    resolution = len(qtm_id)
    num_edges = 3
    cell_metrics = _cell_metrics_enabled(kwargs)
    metrics = geodesic_dggs_metrics(cell_polygon, num_edges) if cell_metrics else None

    qtm_feature = QgsFeature()
    qtm_feature.setGeometry(QgsGeometry.fromWkt(cell_polygon.wkt))
    return _attach_dggs_attributes(
        qtm_feature,
        feature,
        "qtm",
        qtm_id,
        resolution,
        cell_metrics,
        GEODESIC_METRIC_NAMES,
        metrics,
    )


def olc2qgsfeature(feature, olc_id, **kwargs):
    cell_polygon = olc2geo(olc_id)
    coord = olc.decode(olc_id)
    resolution = coord.codeLength
    cell_metrics = _cell_metrics_enabled(kwargs)
    metrics = graticule_dggs_metrics(cell_polygon) if cell_metrics else None

    olc_feature = QgsFeature()
    olc_feature.setGeometry(QgsGeometry.fromWkt(cell_polygon.wkt))
    return _attach_dggs_attributes(
        olc_feature,
        feature,
        "olc",
        olc_id,
        resolution,
        cell_metrics,
        GRATICULE_METRIC_NAMES,
        metrics,
    )


def mgrs2qgsfeature(feature, mgrs_id, **kwargs):
    cell_polygon = mgrs2geo(mgrs_id)
    if not cell_polygon or isinstance(cell_polygon, list):
        return None

    resolution, _ = mgrs.get_mgrs_resolution_and_cell_size(mgrs_id)
    cell_metrics = _cell_metrics_enabled(kwargs)
    metrics = graticule_dggs_metrics(cell_polygon) if cell_metrics else None

    mgrs_feature = QgsFeature()
    mgrs_feature.setGeometry(QgsGeometry.fromWkt(cell_polygon.wkt))
    return _attach_dggs_attributes(
        mgrs_feature,
        feature,
        "mgrs",
        mgrs_id,
        resolution,
        cell_metrics,
        GRATICULE_METRIC_NAMES,
        metrics,
    )


def geohash2qgsfeature(feature, geohash_id, **kwargs):
    cell_polygon = geohash2geo(geohash_id)
    resolution = len(geohash_id)
    cell_metrics = _cell_metrics_enabled(kwargs)
    metrics = graticule_dggs_metrics(cell_polygon) if cell_metrics else None

    geohash_feature = QgsFeature()
    geohash_feature.setGeometry(QgsGeometry.fromWkt(cell_polygon.wkt))
    return _attach_dggs_attributes(
        geohash_feature,
        feature,
        "geohash",
        geohash_id,
        resolution,
        cell_metrics,
        GRATICULE_METRIC_NAMES,
        metrics,
    )


def georef2qgsfeature(feature, georef_id, **kwargs):
    center_lat, center_lon, min_lat, min_lon, max_lat, max_lon, resolution = (
        georef.georefcell(georef_id)
    )
    if center_lat:
        cell_polygon = Polygon(
            [
                [min_lon, min_lat],  # Bottom-left corner
                [max_lon, min_lat],  # Bottom-right corner
                [max_lon, max_lat],  # Top-right corner
                [min_lon, max_lat],  # Top-left corner
                [min_lon, min_lat],  # Closing the polygon (same as the first point)
            ]
        )

        cell_metrics = _cell_metrics_enabled(kwargs)
        metrics = graticule_dggs_metrics(cell_polygon) if cell_metrics else None

        georef_feature = QgsFeature()
        georef_feature.setGeometry(QgsGeometry.fromWkt(cell_polygon.wkt))
        return _attach_dggs_attributes(
            georef_feature,
            feature,
            "georef",
            georef_id,
            resolution,
            cell_metrics,
            GRATICULE_METRIC_NAMES,
            metrics,
        )


def tilecode2qgsfeature(feature, tilecode_id, **kwargs):
    # Extract z, x, y from the tilecode using regex
    match = re.match(r"z(\d+)x(\d+)y(\d+)", tilecode_id)
    if not match:
        raise ValueError("Invalid tilecode format. Expected format: 'zXxYyZ'")

    # Convert matched groups to integers
    z = int(match.group(1))
    x = int(match.group(2))
    y = int(match.group(3))

    # Get the bounds of the tile in (west, south, east, north)
    bounds = mercantile.bounds(x, y, z)

    if bounds:
        # Define bounding box coordinates
        min_lat, min_lon = bounds.south, bounds.west
        max_lat, max_lon = bounds.north, bounds.east
        cell_polygon = Polygon(
            [
                [min_lon, min_lat],  # Bottom-left corner
                [max_lon, min_lat],  # Bottom-right corner
                [max_lon, max_lat],  # Top-right corner
                [min_lon, max_lat],  # Top-left corner
                [min_lon, min_lat],  # Closing the polygon (same as the first point)
            ]
        )

        cell_metrics = _cell_metrics_enabled(kwargs)
        metrics = graticule_dggs_metrics(cell_polygon) if cell_metrics else None

        tilecode_feature = QgsFeature()
        tilecode_feature.setGeometry(QgsGeometry.fromWkt(cell_polygon.wkt))
        return _attach_dggs_attributes(
            tilecode_feature,
            feature,
            "tilecode",
            tilecode_id,
            z,
            cell_metrics,
            GRATICULE_METRIC_NAMES,
            metrics,
        )


def quadkey2qgsfeature(feature, quadkey_id, **kwargs):
    tile = mercantile.quadkey_to_tile(quadkey_id)
    z = tile.z
    x = tile.x
    y = tile.y
    # Get the bounds of the tile in (west, south, east, north)
    bounds = mercantile.bounds(x, y, z)
    if bounds:
        # Define bounding box coordinates
        min_lat, min_lon = bounds.south, bounds.west
        max_lat, max_lon = bounds.north, bounds.east
        cell_polygon = Polygon(
            [
                [min_lon, min_lat],  # Bottom-left corner
                [max_lon, min_lat],  # Bottom-right corner
                [max_lon, max_lat],  # Top-right corner
                [min_lon, max_lat],  # Top-left corner
                [min_lon, min_lat],  # Closing the polygon (same as the first point)
            ]
        )

        cell_metrics = _cell_metrics_enabled(kwargs)
        metrics = graticule_dggs_metrics(cell_polygon) if cell_metrics else None

        quadkey_feature = QgsFeature()
        quadkey_feature.setGeometry(QgsGeometry.fromWkt(cell_polygon.wkt))
        return _attach_dggs_attributes(
            quadkey_feature,
            feature,
            "quadkey",
            quadkey_id,
            z,
            cell_metrics,
            GRATICULE_METRIC_NAMES,
            metrics,
        )


def maidenhead2qgsfeature(feature, maidenhead_id, **kwargs):
    cell_polygon = maidenhead2geo(maidenhead_id)
    resolution = int(len(maidenhead_id) / 2)
    cell_metrics = _cell_metrics_enabled(kwargs)
    metrics = graticule_dggs_metrics(cell_polygon) if cell_metrics else None

    maidenhead_feature = QgsFeature()
    maidenhead_feature.setGeometry(QgsGeometry.fromWkt(cell_polygon.wkt))
    return _attach_dggs_attributes(
        maidenhead_feature,
        feature,
        "maidenhead",
        maidenhead_id,
        resolution,
        cell_metrics,
        GRATICULE_METRIC_NAMES,
        metrics,
    )


def gars2qgsfeature(feature, gars_id, **kwargs):
    # Create a GARS grid object and retrieve the polygon
    gars_grid = GARSGrid(gars_id)
    wkt_polygon = gars_grid.polygon

    if wkt_polygon:
        # Extract the bounding box coordinates for the polygon
        x, y = wkt_polygon.exterior.xy
        resolution_minute = gars_grid.resolution
        resolution = 1
        if resolution_minute == 30:
            resolution = 1
        elif resolution_minute == 15:
            resolution = 2
        elif resolution_minute == 5:
            resolution = 3
        elif resolution_minute == 1:
            resolution = 4

        # Determine min/max latitudes and longitudes
        min_lon = min(x)
        max_lon = max(x)
        min_lat = min(y)
        max_lat = max(y)

        cell_polygon = Polygon(
            [
                [min_lon, min_lat],  # Bottom-left corner
                [max_lon, min_lat],  # Bottom-right corner
                [max_lon, max_lat],  # Top-right corner
                [min_lon, max_lat],  # Top-left corner
                [min_lon, min_lat],  # Closing the polygon (same as the first point)
            ]
        )

        cell_metrics = _cell_metrics_enabled(kwargs)
        metrics = graticule_dggs_metrics(cell_polygon) if cell_metrics else None

        gars_feature = QgsFeature()
        gars_feature.setGeometry(QgsGeometry.fromWkt(cell_polygon.wkt))
        return _attach_dggs_attributes(
            gars_feature,
            feature,
            "gars",
            gars_id,
            resolution,
            cell_metrics,
            GRATICULE_METRIC_NAMES,
            metrics,
        )


def digipin2qgsfeature(feature, digipin_id, **kwargs):
    cell_polygon = digipin2geo(digipin_id)
    clean_id = digipin_id.replace("-", "")
    resolution = len(clean_id)
    cell_metrics = _cell_metrics_enabled(kwargs)
    metrics = graticule_dggs_metrics(cell_polygon) if cell_metrics else None

    digipin_feature = QgsFeature()
    digipin_feature.setGeometry(QgsGeometry.fromWkt(cell_polygon.wkt))
    return _attach_dggs_attributes(
        digipin_feature,
        feature,
        "digipin",
        digipin_id,
        resolution,
        cell_metrics,
        GRATICULE_METRIC_NAMES,
        metrics,
    )


def dggrid_join_qgsfeature(
    feature, cell_id, lookup, dggs_type, out_fields, cell_metrics=False
):
    """Join one input feature to a batch DGGRID lookup by cell ID."""
    from ..dggrid_instance import normalize_dggrid_cell_id
    from vgrid.utils.io import validate_dggrid_type

    dggs_type = validate_dggrid_type(dggs_type)
    cell_id_str = normalize_dggrid_cell_id(cell_id)
    if not cell_id_str:
        raise ValueError("empty DGGRID cell ID")
    cell_info = lookup.get(cell_id_str)
    if not cell_info:
        raise ValueError(f"DGGRID cell not found: {cell_id_str}")

    out_feature = QgsFeature(out_fields)
    out_feature.setGeometry(QgsGeometry.fromWkt(cell_info["geometry"].wkt))
    attributes = list(feature.attributes()) + [
        cell_info["cell_id"],
        cell_info["resolution"],
    ]
    if cell_metrics:
        attributes.extend(
            [
                cell_info["center_lat"],
                cell_info["center_lon"],
                cell_info["avg_edge_len"],
                cell_info["cell_area"],
                cell_info["cell_perimeter"],
            ]
        )
    out_feature.setAttributes(attributes)
    return out_feature


def dggrid_batch2qgsfeatures(
    features,
    cell_ids,
    dggs_type,
    resolution,
    out_fields,
    feedback=None,
    split_antimeridian=False,
    aggregate=False,
    cell_metrics=False,
):
    """
    Convert many input features via one ``dggrid2geo`` call and join by cell ID.

    Returns ``(output_features, num_bad)``.
    """
    from ...settings import settings
    from ..dggrid_instance import (
        batch_dggrid_cells_qgis,
        build_dggrid_options,
        get_plugin_dggrid_instance,
    )
    from vgrid.utils.io import validate_dggrid_resolution, validate_dggrid_type

    dggs_type = validate_dggrid_type(dggs_type)
    resolution = validate_dggrid_resolution(dggs_type, resolution)

    lookup = batch_dggrid_cells_qgis(
        get_plugin_dggrid_instance(feedback=feedback),
        dggs_type,
        cell_ids,
        resolution,
        options=build_dggrid_options(settings.dggridDensificationSpinBox),
        feedback=feedback,
        split_antimeridian=split_antimeridian,
        aggregate=aggregate,
        cell_metrics=cell_metrics,
    )

    if not lookup:
        if feedback:
            feedback.reportError(
                "DGGRID returned no cells for the given cell IDs and resolution."
            )
        return [], len(features)

    if feedback:
        feedback.pushInfo(f"DGGRID lookup: {len(lookup)} cell polygon(s) loaded.")

    output_features = []
    num_bad = 0
    total = len(features)

    for i, (feat, cell_id) in enumerate(zip(features, cell_ids)):
        if feedback and feedback.isCanceled():
            break
        try:
            output_features.append(
                dggrid_join_qgsfeature(
                    feat, cell_id, lookup, dggs_type, out_fields, cell_metrics=cell_metrics
                )
            )
        except Exception as exc:
            num_bad += 1
            if feedback and num_bad <= 5:
                feedback.reportError(f"Feature {feat.id()}: {exc}")
        if feedback and total and i % 50 == 0:
            feedback.setProgress(int(50 + 50 * i / total))

    return output_features, num_bad


def dggrid2qgsfeature(feature, cell_id, dggs_type, resolution, cell_metrics=False):
    """Convert a single DGGRID cell ID (uses batch lookup for one ID)."""
    from ...settings import settings
    from ..dggrid_instance import (
        batch_dggrid_cells_qgis,
        build_dggrid_options,
        get_plugin_dggrid_instance,
    )
    from vgrid.utils.io import validate_dggrid_resolution, validate_dggrid_type

    dggs_type = validate_dggrid_type(dggs_type)
    resolution = validate_dggrid_resolution(dggs_type, resolution)
    from qgis.core import QgsField, QgsFields

    lookup = batch_dggrid_cells_qgis(
        get_plugin_dggrid_instance(),
        dggs_type,
        [cell_id],
        resolution,
        options=build_dggrid_options(settings.dggridDensificationSpinBox),
        cell_metrics=cell_metrics,
    )
    field_name = f"dggrid_{dggs_type.lower()}"
    out_fields = QgsFields()
    for fld in feature.fields():
        out_fields.append(fld)
    metric_fields = (
        (
            ("center_lat", QVariant.Double),
            ("center_lon", QVariant.Double),
            ("avg_edge_len", QVariant.Double),
            ("cell_area", QVariant.Double),
            ("cell_perimeter", QVariant.Double),
        )
        if cell_metrics
        else ()
    )
    for name, qtype in (
        (field_name, QVariant.String),
        ("resolution", QVariant.Int),
        *metric_fields,
    ):
        out_fields.append(QgsField(name, qtype))
    return dggrid_join_qgsfeature(
        feature, cell_id, lookup, dggs_type, out_fields, cell_metrics=cell_metrics
    )
