"""CRS checks and WGS84 reprojection helpers for DGGS tools.

DGGS processing expects geographic coordinates in EPSG:4326. Use these
helpers from conversion, binning, resampling, and other DGGS algorithms.
"""

import math

from qgis.core import (
    Qgis,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsFeature,
    QgsFeatureRequest,
    QgsGeometry,
    QgsProcessingException,
    QgsProject,
    QgsRasterLayer,
    QgsRectangle,
    QgsVectorLayer,
    QgsWkbTypes,
)

WGS84 = QgsCoordinateReferenceSystem("EPSG:4326")

WGS84_REQUIRED_MSG = (
    "Input must use WGS84 (EPSG:4326). "
    "Please reproject the layer to EPSG:4326 and run the tool again."
)


def is_wgs84(crs) -> bool:
    return crs is not None and crs.isValid() and crs.authid() == "EPSG:4326"


def _require_valid_crs(crs):
    if not crs or not crs.isValid():
        raise QgsProcessingException(
            "Input layer has no valid CRS. Define a CRS before running this tool."
        )


def wgs84_transform_if_needed(crs, transform_context=None, feedback=None):
    """
    Return a QgsCoordinateTransform to EPSG:4326, or None if *crs* is already WGS84.
    """
    _require_valid_crs(crs)
    if is_wgs84(crs):
        return None

    if feedback:
        feedback.pushInfo(f"Reprojecting input from {crs.authid()} to EPSG:4326...")

    if transform_context is None:
        transform_context = QgsProject.instance().transformContext()
    return QgsCoordinateTransform(crs, WGS84, transform_context)


def reproject_feature(feature, transform):
    """Return a copy of *feature* with geometry reprojected using *transform*."""
    new_feat = QgsFeature(feature)
    geom = feature.geometry()
    if geom is not None and not geom.isEmpty():
        geom = QgsGeometry(geom)
        geom.transform(transform)
        new_feat.setGeometry(geom)
    return new_feat


def flatten_feature_geometry(feature):
    """Return *feature* with Z/M stripped (DGGS tools expect 2D geometries)."""
    geom = feature.geometry()
    if geom is None or geom.isEmpty():
        return feature

    wkb = geom.wkbType()
    if not QgsWkbTypes.hasZ(wkb) and not QgsWkbTypes.hasM(wkb):
        return feature

    flat_wkb = QgsWkbTypes.flatType(wkb)
    coerced = geom.coerceToType(flat_wkb)
    if not coerced:
        return feature

    new_feat = QgsFeature(feature)
    new_feat.setGeometry(coerced[0])
    return new_feat


def _crs_of(source):
    if hasattr(source, "sourceCrs"):
        crs = source.sourceCrs()
        if crs is not None and crs.isValid():
            return crs
    if hasattr(source, "crs"):
        return source.crs()
    return None


def iter_features_skip_invalid_geometry(source, no_geometry=False):
    """Iterate features including those with invalid geometry.

    Matches Cell ID to DGGS: Processing normally drops invalid geometries,
    which is wrong for tools that only read a DGGS ID field.
    """
    request = QgsFeatureRequest()
    if no_geometry:
        request.setFlags(Qgis.FeatureRequestFlag.NoGeometry)
    try:
        return source.getFeatures(
            request, Qgis.ProcessingFeatureSourceFlag.SkipGeometryValidityChecks
        )
    except TypeError:
        return source.getFeatures(request)


def attributes_only_source(source, feedback=None, layer_name="dggs_ids"):
    """Memory layer of attributes only (no input geometry).

    Use for Compact/Expand/Cell-ID tools that rebuild geometry from DGGS IDs.
    """
    if source is None:
        raise QgsProcessingException("Could not load input layer.")

    fields = source.fields()
    layer = QgsVectorLayer("None", layer_name, "memory")
    if not layer.isValid():
        raise QgsProcessingException("Failed to create attribute-only input layer.")

    layer.dataProvider().addAttributes(fields.toList())
    layer.updateFields()

    out_features = []
    for feat in iter_features_skip_invalid_geometry(source, no_geometry=True):
        if feedback and feedback.isCanceled():
            break
        out_features.append(QgsFeature(feat))

    if out_features:
        layer.dataProvider().addFeatures(out_features)
    return layer


def ensure_wgs84_source(source, feedback=None, layer_name="wgs84_reprojected"):
    """Return a QgsVectorLayer in EPSG:4326.

    Honors Processing Toolbox "Selected features only" when *source* comes
    from ``parameterAsSource``. An already-WGS84 ``QgsVectorLayer`` is
    returned unchanged; feature sources are copied into a memory layer.
    """
    if source is None:
        raise QgsProcessingException("Could not load input layer.")

    crs = _crs_of(source)
    transform = wgs84_transform_if_needed(crs, feedback=feedback)

    if transform is None and isinstance(source, QgsVectorLayer):
        return source

    fields = source.fields()
    wkb_name = QgsWkbTypes.displayString(source.wkbType())
    layer = QgsVectorLayer(f"{wkb_name}?crs=EPSG:4326", layer_name, "memory")
    if not layer.isValid():
        raise QgsProcessingException(
            f"Failed to create WGS84 layer for reprojection (geometry type: {wkb_name})."
        )

    layer.dataProvider().addAttributes(fields.toList())
    layer.updateFields()

    out_features = []
    for feat in source.getFeatures():
        if feedback and feedback.isCanceled():
            break
        if transform is not None:
            feat = reproject_feature(feat, transform)
        out_features.append(flatten_feature_geometry(feat))

    if out_features:
        layer.dataProvider().addFeatures(out_features)
    layer.updateExtents()
    return layer


def ensure_wgs84_raster_layer(raster_layer, context=None, feedback=None):
    """Return *raster_layer* unchanged if WGS84, else a temporary raster in EPSG:4326."""
    crs = raster_layer.crs()
    _require_valid_crs(crs)
    if is_wgs84(crs):
        return raster_layer

    if feedback:
        feedback.pushInfo(f"Reprojecting raster from {crs.authid()} to EPSG:4326...")

    from qgis import processing

    try:
        result = processing.run(
            "gdal:warpreproject",
            {
                "INPUT": raster_layer,
                "TARGET_CRS": WGS84,
                "RESAMPLING": 0,
                "OUTPUT": "TEMPORARY_OUTPUT",
            },
            context=context,
            feedback=feedback,
            is_child_algorithm=True,
        )
    except Exception as exc:
        raise QgsProcessingException(
            f"Failed to reproject raster to EPSG:4326: {exc}"
        ) from exc

    output = result.get("OUTPUT")
    if not output:
        raise QgsProcessingException(
            "Failed to reproject raster to EPSG:4326 (no output from gdal:warpreproject)."
        )

    reprojected = QgsRasterLayer(output, "raster_wgs84")
    if not reprojected.isValid():
        raise QgsProcessingException(
            "Failed to load reprojected raster in EPSG:4326."
        )
    return reprojected


# Web Mercator cannot represent ±90; this is the usual EPSG:3857 latitude limit.
_WORLD_GEO_FOR_PROJECTED = QgsRectangle(-180.0, -85.05112878, 180.0, 85.05112878)


def is_world_covering_wgs84(min_lon, min_lat, max_lon, max_lat) -> bool:
    """True when the WGS84 box is global or near-global (e.g. Web Mercator canvas)."""
    from vgrid.utils.io import is_full_world_bbox

    if not all(math.isfinite(v) for v in (min_lon, min_lat, max_lon, max_lat)):
        return True
    return is_full_world_bbox([min_lon, min_lat, max_lon, max_lat]) or (
        max_lon - min_lon
    ) >= 350


def normalize_wgs84_bbox(min_lon, min_lat, max_lon, max_lat, feedback=None):
    """Clamp WGS84 bounds; treat bigger-than-world / near-world as the globe.

    Returns ``(min_lon, min_lat, max_lon, max_lat, is_full_world)``.
    """
    from vgrid.utils.io import validate_coordinate

    world = (-180.0, -90.0, 180.0, 90.0)
    vals = (min_lon, min_lat, max_lon, max_lat)
    if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in vals):
        if feedback:
            feedback.pushInfo("Extent is not finite; using world bounds.")
        return (*world, True)

    bigger_than_world = (
        (max_lon - min_lon) > 360.0
        or (max_lat - min_lat) > 180.0
        or (min_lon < -180.0 and max_lon > 180.0)
        or (min_lat < -90.0 and max_lat > 90.0)
    )
    min_lon, min_lat, max_lon, max_lat = validate_coordinate(
        min_lon, min_lat, max_lon, max_lat
    )
    if (
        bigger_than_world
        or min_lon >= max_lon
        or min_lat >= max_lat
        or is_world_covering_wgs84(min_lon, min_lat, max_lon, max_lat)
    ):
        if feedback:
            feedback.pushInfo(
                "Extent in EPSG:4326 is larger than or covers the world; "
                "using world bounds."
            )
        return (*world, True)
    return min_lon, min_lat, max_lon, max_lat, False


def normalize_extent_to_india(min_lon, min_lat, max_lon, max_lat, feedback=None):
    """Clip WGS84 bounds into the DIGIPIN India box.

    If any of min/max lon/lat is outside India (even slightly), the extent is
    clamped to ``BOUNDS``. No overlap, or a world-covering box, uses the full
    India rectangle.
    """
    from vgrid.dggs.digipin import BOUNDS

    india_min_lon = BOUNDS["minLon"]
    india_min_lat = BOUNDS["minLat"]
    india_max_lon = BOUNDS["maxLon"]
    india_max_lat = BOUNDS["maxLat"]
    india = (india_min_lon, india_min_lat, india_max_lon, india_max_lat)

    if is_world_covering_wgs84(min_lon, min_lat, max_lon, max_lat):
        if feedback:
            feedback.pushInfo(
                "Extent covers the world; using India bounding box for DIGIPIN."
            )
        return india

    outside = (
        min_lon < india_min_lon
        or min_lat < india_min_lat
        or max_lon > india_max_lon
        or max_lat > india_max_lat
        or min_lon > india_max_lon
        or min_lat > india_max_lat
        or max_lon < india_min_lon
        or max_lat < india_min_lat
    )
    clipped_min_lon = max(min_lon, india_min_lon)
    clipped_min_lat = max(min_lat, india_min_lat)
    clipped_max_lon = min(max_lon, india_max_lon)
    clipped_max_lat = min(max_lat, india_max_lat)

    if clipped_min_lon >= clipped_max_lon or clipped_min_lat >= clipped_max_lat:
        if feedback:
            feedback.pushInfo(
                "Extent does not overlap India; using India bounding box."
            )
        return india

    if outside and feedback:
        feedback.pushInfo("Extent clipped to India bounding box.")
    return clipped_min_lon, clipped_min_lat, clipped_max_lon, clipped_max_lat


def _src_extent_covers_projected_world(extent, extent_crs) -> bool:
    """True when *extent* in a projected CRS is as large as (or larger than) the globe."""
    if extent is None or extent_crs is None or not extent_crs.isValid():
        return False
    if is_wgs84(extent_crs) or extent_crs.isGeographic():
        return False
    try:
        trans = QgsCoordinateTransform(
            WGS84, extent_crs, QgsProject.instance()
        )
        world_src = trans.transformBoundingBox(_WORLD_GEO_FOR_PROJECTED)
    except Exception:
        return False
    if world_src is None or world_src.isNull() or world_src.isEmpty():
        return False
    pad_x = max(1.0, world_src.width() * 0.001)
    pad_y = max(1.0, world_src.height() * 0.001)
    return (
        extent.xMinimum() <= world_src.xMinimum() + pad_x
        and extent.xMaximum() >= world_src.xMaximum() - pad_x
        and extent.yMinimum() <= world_src.yMinimum() + pad_y
        and extent.yMaximum() >= world_src.yMaximum() - pad_y
    )


def normalize_extent_to_wgs84(extent, extent_crs, feedback=None):
    """Transform *extent* to EPSG:4326 and clamp to [-180, 180] x [-90, 90].

    Returns ``(min_lon, min_lat, max_lon, max_lat, is_full_world)``.
    Empty or null extent is treated as the full world.
    Projected extents larger than the globe (typical zoomed-out EPSG:3857
    canvas) are also treated as the full world, because transforming them
    to 4326 can invert or collapse the rectangle.
    """
    from vgrid.utils.io import validate_coordinate

    world = (-180.0, -90.0, 180.0, 90.0)
    empty = extent is None or (
        hasattr(extent, "isNull") and extent.isNull()
    ) or (hasattr(extent, "isEmpty") and extent.isEmpty())
    if empty:
        if feedback:
            feedback.pushInfo("Map extent is not set; using world bounds.")
        return (*world, True)

    if _src_extent_covers_projected_world(extent, extent_crs):
        if feedback:
            feedback.pushInfo(
                "Extent is larger than the world in the map CRS; using world bounds."
            )
        return (*world, True)

    try:
        min_lon = extent.xMinimum()
        min_lat = extent.yMinimum()
        max_lon = extent.xMaximum()
        max_lat = extent.yMaximum()
        if extent_crs is not None and extent_crs.isValid() and not is_wgs84(extent_crs):
            trans = QgsCoordinateTransform(
                extent_crs, WGS84, QgsProject.instance()
            )
            transformed = trans.transformBoundingBox(extent)
            min_lon = transformed.xMinimum()
            min_lat = transformed.yMinimum()
            max_lon = transformed.xMaximum()
            max_lat = transformed.yMaximum()
    except Exception:
        if feedback:
            feedback.pushInfo("Could not transform extent; using world bounds.")
        return (*world, True)

    if not all(math.isfinite(v) for v in (min_lon, min_lat, max_lon, max_lat)):
        if feedback:
            feedback.pushInfo("Extent transform was not finite; using world bounds.")
        return (*world, True)

    min_lon, min_lat, max_lon, max_lat = validate_coordinate(
        min_lon, min_lat, max_lon, max_lat
    )
    # 3857 (and similar) extents bigger than the globe often transform to an
    # inverted WGS84 rectangle such as lon 180..-180. That clips to nothing.
    projected = (
        extent_crs is not None
        and extent_crs.isValid()
        and not extent_crs.isGeographic()
    )
    if projected and (min_lon >= max_lon or min_lat >= max_lat):
        if feedback:
            feedback.pushInfo(
                "Extent inverted after converting from the map CRS to "
                "EPSG:4326; using world bounds."
            )
        return (*world, True)
    if is_world_covering_wgs84(min_lon, min_lat, max_lon, max_lat):
        if feedback:
            feedback.pushInfo(
                "Extent covers the world after normalizing to "
                "lon [-180, 180], lat [-90, 90]."
            )
        return (*world, True)
    return min_lon, min_lat, max_lon, max_lat, False


def processing_extent_wgs84(
    algorithm, parameters, param_name, context, feedback=None
):
    """Read a Processing extent parameter, reproject to EPSG:4326, and clamp."""
    extent = algorithm.parameterAsExtent(parameters, param_name, context)
    try:
        extent_crs = algorithm.parameterAsExtentCrs(parameters, param_name, context)
    except Exception:
        extent_crs = QgsProject.instance().crs()
    return normalize_extent_to_wgs84(extent, extent_crs, feedback)
