"""CRS checks and WGS84 reprojection helpers for DGGS tools."""

from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsFeature,
    QgsGeometry,
    QgsProcessingException,
    QgsProject,
    QgsRasterLayer,
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


def ensure_wgs84_source(source, feedback=None, layer_name="wgs84_reprojected"):
    """Return *source* unchanged if WGS84, else a memory layer reprojected to EPSG:4326."""
    crs = source.sourceCrs()
    transform = wgs84_transform_if_needed(crs, feedback=feedback)
    if transform is None:
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
        out_features.append(
            flatten_feature_geometry(reproject_feature(feat, transform))
        )

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
