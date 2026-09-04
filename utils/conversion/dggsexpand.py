from qgis.PyQt.QtCore import QVariant
from qgis.core import (
    QgsVectorLayer,
    QgsFeature,
    QgsGeometry,
    QgsField,
    QgsFields,
    QgsProcessingException,
)
import platform
from vgrid.dggs import s2, olc
import h3
import a5

if platform.system() == "Windows":
    from vgrid.dggs.eaggr.eaggr import Eaggr
    from vgrid.dggs.eaggr.enums.model import Model
    from vgrid.conversion.dggs2geo.isea4t2geo import isea4t2geo
    from vgrid.conversion.dggs2geo.isea3h2geo import isea3h2geo
    from vgrid.conversion.dggscompact.isea3hcompact import get_isea3h_resolution

    isea3h_dggs = Eaggr(Model.ISEA3H)
    isea4t_dggs = Eaggr(Model.ISEA4T)

from vgrid.utils.geometry import (
    graticule_dggs_metrics,
    geodesic_dggs_metrics,
)

from vgrid.conversion.dggs2geo.h32geo import h32geo
from vgrid.conversion.dggs2geo.s22geo import s22geo
from vgrid.conversion.dggs2geo.a52geo import a52geo
from vgrid.conversion.dggs2geo.rhealpix2geo import rhealpix2geo
from vgrid.conversion.dggscompact.h3compact import h3_expand
from vgrid.conversion.dggscompact.s2compact import s2_expand
from vgrid.conversion.dggscompact.a5compact import a5_expand
from vgrid.conversion.dggscompact.rhealpixcompact import (
    get_rhealpix_resolution,
    rhealpix_expand,
)
from vgrid.conversion.dggscompact.isea4tcompact import (
    get_isea4t_resolution,
    isea4t_expand,
)
from vgrid.conversion.dggscompact.isea3hcompact import isea3h_expand
from vgrid.conversion.dggscompact.qtmcompact import get_qtm_resolution, qtm_expand
from vgrid.conversion.dggs2geo.qtm2geo import qtm2geo
from vgrid.conversion.dggscompact.olccompact import get_olc_resolution, olc_expand
from vgrid.conversion.dggs2geo.olc2geo import olc2geo
from vgrid.conversion.dggscompact.geohashcompact import (
    get_geohash_resolution,
    geohash_expand,
)
from vgrid.conversion.dggs2geo.geohash2geo import geohash2geo
from vgrid.conversion.dggscompact.tilecodecompact import tilecode_expand
from vgrid.conversion.dggs2geo.tilecode2geo import tilecode2geo
from vgrid.conversion.dggscompact.quadkeycompact import quadkey_expand
from vgrid.conversion.dggs2geo.quadkey2geo import quadkey2geo
from vgrid.conversion.dggscompact.dggalcompact import dggal_expand
from vgrid.conversion.dggs2geo.dggal2geo import dggal2geo
from vgrid.conversion.dggscompact.digipincompact import digipin_expand
from vgrid.conversion.dggs2geo.digipin2geo import digipin2geo
from vgrid.utils.constants import DGGAL_TYPES
from vgrid.dggs.tilecode import quadkey_resolution, tilecode_resolution
from vgrid.dggs.digipin import digipin_resolution
from dggal import *

from pyproj import Geod

from ..antimeridian_helper import (
    geo_with_fix as _geo_with_fix,
    use_split_antimeridian as _use_split_antimeridian,
)

geod = Geod(ellps="WGS84")


def _expand_resolution_depth(resolution, depth):
    """Map QGIS sentinels to vgrid expand kwargs (resolution wins when set)."""
    res = None if resolution is None or int(resolution) < 0 else int(resolution)
    d = None if depth is None or int(depth) < 1 else int(depth)
    if res is None and d is None:
        raise QgsProcessingException(
            "Specify Resolution (>= 0) or Expand depth (>= 1). "
            "When Resolution is set, depth is ignored."
        )
    return res, d


def _report_expand_res_too_coarse(feedback, resolution, max_res):
    if feedback:
        feedback.reportError(
            f"Target expand resolution ({resolution}) must >= {max_res}."
        )
    return None


##########################
# H3
#########################
def h3expand(
    h3_layer: QgsVectorLayer,
    resolution: int,
    H3ID_field=None,
    feedback=None,
    shift_antimeridian=False,
    split_antimeridian=False,
    depth=None,
) -> QgsVectorLayer:
    if not H3ID_field:
        H3ID_field = "h3"

    fields = QgsFields()
    fields.append(QgsField("h3", QVariant.String))
    fields.append(QgsField("resolution", QVariant.Int))
    fields.append(QgsField("center_lat", QVariant.Double))
    fields.append(QgsField("center_lon", QVariant.Double))
    fields.append(QgsField("avg_edge_len", QVariant.Double))
    fields.append(QgsField("cell_area", QVariant.Double))
    fields.append(QgsField("cell_perimeter", QVariant.Double))

    mem_layer = QgsVectorLayer("Polygon?crs=EPSG:4326", "h3_expanded", "memory")
    mem_provider = mem_layer.dataProvider()
    mem_provider.addAttributes(fields)
    mem_layer.updateFields()

    h3_ids = [
        feature[H3ID_field] for feature in h3_layer.getFeatures() if feature[H3ID_field]
    ]
    h3_ids = list(set(h3_ids))

    if h3_ids:
        try:
            res, d = _expand_resolution_depth(resolution, depth)
            if res is not None:
                max_res = max(h3.get_resolution(h3_id) for h3_id in h3_ids)
                if res < max_res:
                    return _report_expand_res_too_coarse(feedback, res, max_res)
            h3_ids_expand = h3_expand(
                h3_ids, resolution=res, depth=d, verbose=False
            )
        except QgsProcessingException:
            raise
        except BaseException:
            raise QgsProcessingException(
                "Expand cells failed. Please check your H3 cell Ids."
            )

        total_cells = len(h3_ids_expand)

        for i, h3_id_expand in enumerate(h3_ids_expand):
            if feedback:
                feedback.setProgress(int((i / total_cells) * 100))
                if feedback.isCanceled():
                    return None

            cell_polygon = _geo_with_fix(
                h32geo,
                h3_id_expand,
                "h3",
                shift_antimeridian,
                split_antimeridian,
            )

            if not cell_polygon.is_valid:
                continue

            num_edges = 5 if h3.is_pentagon(h3_id_expand) else 6
            center_lat, center_lon, avg_edge_len, cell_area, cell_perimeter = (
                geodesic_dggs_metrics(cell_polygon, num_edges)
            )

            cell_geom = QgsGeometry.fromWkt(cell_polygon.wkt)
            h3_feature = QgsFeature(fields)
            h3_feature.setGeometry(cell_geom)

            attributes = {
                "h3": h3_id_expand,
                "resolution": h3.get_resolution(h3_id_expand),
                "center_lat": center_lat,
                "center_lon": center_lon,
                "avg_edge_len": avg_edge_len,
                "cell_area": cell_area,
                "cell_perimeter": cell_perimeter,
            }
            h3_feature.setAttributes([attributes[field.name()] for field in fields])
            mem_provider.addFeatures([h3_feature])

        if feedback:
            feedback.setProgress(100)
            feedback.pushInfo("H3 DGGS expansion completed.")

    return mem_layer


##########################
# S2
# ########################
def s2expand(
    s2_layer: QgsVectorLayer,
    resolution: int,
    S2Token_field=None,
    feedback=None,
    shift_antimeridian=False,
    split_antimeridian=False,
    depth=None,
) -> QgsVectorLayer:
    if not S2Token_field:
        S2Token_field = "s2"

    fields = QgsFields()
    fields.append(QgsField("s2", QVariant.String))
    fields.append(QgsField("resolution", QVariant.Int))
    fields.append(QgsField("center_lat", QVariant.Double))
    fields.append(QgsField("center_lon", QVariant.Double))
    fields.append(QgsField("avg_edge_len", QVariant.Double))
    fields.append(QgsField("cell_area", QVariant.Double))
    fields.append(QgsField("cell_perimeter", QVariant.Double))
    mem_layer = QgsVectorLayer("Polygon?crs=EPSG:4326", "s2_expanded", "memory")
    mem_provider = mem_layer.dataProvider()
    mem_provider.addAttributes(fields)
    mem_layer.updateFields()

    s2_tokens = [
        feature[S2Token_field]
        for feature in s2_layer.getFeatures()
        if feature[S2Token_field]
    ]
    s2_tokens = list(set(s2_tokens))
    s2_tokens_expand = []

    if s2_tokens:
        try:
            res, d = _expand_resolution_depth(resolution, depth)
            if res is not None:
                s2_ids = [s2.CellId.from_token(token) for token in s2_tokens]
                max_res = max(s2_id.level() for s2_id in s2_ids)
                if res < max_res:
                    return _report_expand_res_too_coarse(feedback, res, max_res)
            s2_tokens_expand = s2_expand(
                s2_tokens, resolution=res, depth=d, verbose=False
            )
        except QgsProcessingException:
            raise
        except BaseException:
            raise QgsProcessingException(
                "Expand cells failed. Please check your S2 Tokens."
            )

    total_cells = len(s2_tokens_expand)

    for i, s2_token_expand in enumerate(s2_tokens_expand):
        if feedback:
            feedback.setProgress(int((i / total_cells) * 100))
            if feedback.isCanceled():
                return None

        cell_polygon = _geo_with_fix(
            s22geo,
            s2_token_expand,
            "s2",
            shift_antimeridian,
            split_antimeridian,
        )

        if not cell_polygon.is_valid:
            continue

        num_edges = 4
        center_lat, center_lon, avg_edge_len, cell_area, cell_perimeter = (
            geodesic_dggs_metrics(cell_polygon, num_edges)
        )

        cell_geom = QgsGeometry.fromWkt(cell_polygon.wkt)
        s2_feature = QgsFeature(fields)
        s2_feature.setGeometry(cell_geom)

        attributes = {
            "s2": s2_token_expand,
            "resolution": s2.CellId.from_token(s2_token_expand).level(),
            "center_lat": center_lat,
            "center_lon": center_lon,
            "avg_edge_len": avg_edge_len,
            "cell_area": cell_area,
            "cell_perimeter": cell_perimeter,
        }
        s2_feature.setAttributes([attributes[field.name()] for field in fields])
        mem_provider.addFeatures([s2_feature])

    if feedback:
        feedback.setProgress(100)
        feedback.pushInfo("S2 DGGS expansion completed.")

    return mem_layer


##########################
# A5
#########################
def a5expand(
    a5_layer: QgsVectorLayer,
    resolution: int,
    A5ID_field=None,
    feedback=None,
    shift_antimeridian=False,
    split_antimeridian=False,
    depth=None,
) -> QgsVectorLayer:
    if not A5ID_field:
        A5ID_field = "a5"

    fields = QgsFields()
    fields.append(QgsField("a5", QVariant.String))
    fields.append(QgsField("resolution", QVariant.Int))
    fields.append(QgsField("center_lat", QVariant.Double))
    fields.append(QgsField("center_lon", QVariant.Double))
    fields.append(QgsField("avg_edge_len", QVariant.Double))
    fields.append(QgsField("cell_area", QVariant.Double))
    fields.append(QgsField("cell_perimeter", QVariant.Double))
    mem_layer = QgsVectorLayer("Polygon?crs=EPSG:4326", "a5_expanded", "memory")
    mem_provider = mem_layer.dataProvider()
    mem_provider.addAttributes(fields)
    mem_layer.updateFields()

    a5_hexes = [
        feature[A5ID_field] for feature in a5_layer.getFeatures() if feature[A5ID_field]
    ]
    a5_hexes = list(set(a5_hexes))

    if a5_hexes:
        try:
            res, d = _expand_resolution_depth(resolution, depth)
            if res is not None:
                max_res = max(
                    a5.get_resolution(a5.hex_to_u64(a5_hex)) for a5_hex in a5_hexes
                )
                if res < max_res:
                    return _report_expand_res_too_coarse(feedback, res, max_res)
            a5_hexes_expand = a5_expand(
                a5_hexes, resolution=res, depth=d, verbose=False
            )
        except QgsProcessingException:
            raise
        except BaseException:
            raise QgsProcessingException(
                "Expand cells failed. Please check your A5 cell Ids."
            )

        total_cells = len(a5_hexes_expand)

        for i, a5_hex_expand in enumerate(a5_hexes_expand):
            if feedback:
                feedback.setProgress(int((i / total_cells) * 100))
                if feedback.isCanceled():
                    return None

            cell_polygon = a52geo(
                a5_hex_expand,
                split_antimeridian=_use_split_antimeridian(
                    shift_antimeridian, split_antimeridian
                ),
            )

            if not cell_polygon.is_valid:
                continue

            num_edges = 5
            center_lat, center_lon, avg_edge_len, cell_area, cell_perimeter = (
                geodesic_dggs_metrics(cell_polygon, num_edges)
            )

            cell_geom = QgsGeometry.fromWkt(cell_polygon.wkt)
            a5_feature = QgsFeature(fields)
            a5_feature.setGeometry(cell_geom)

            attributes = {
                "a5": a5_hex_expand,
                "resolution": a5.get_resolution(a5.hex_to_u64(a5_hex_expand)),
                "center_lat": center_lat,
                "center_lon": center_lon,
                "avg_edge_len": avg_edge_len,
                "cell_area": cell_area,
                "cell_perimeter": cell_perimeter,
            }
            a5_feature.setAttributes([attributes[field.name()] for field in fields])
            mem_provider.addFeatures([a5_feature])

        if feedback:
            feedback.setProgress(100)
            feedback.pushInfo("A5 expansion completed.")

    return mem_layer


##########################
# rHEALPix
#########################
def rhealpixexpand(
    rhealpix_layer: QgsVectorLayer,
    resolution: int,
    rHealPixID_field=None,
    feedback=None,
    shift_antimeridian=False,
    split_antimeridian=False,
    depth=None,
) -> QgsVectorLayer:
    if not rHealPixID_field:
        rHealPixID_field = "rhealpix"

    fields = QgsFields()
    fields.append(QgsField("rhealpix", QVariant.String))
    fields.append(QgsField("resolution", QVariant.Int))
    fields.append(QgsField("center_lat", QVariant.Double))
    fields.append(QgsField("center_lon", QVariant.Double))
    fields.append(QgsField("avg_edge_len", QVariant.Double))
    fields.append(QgsField("cell_area", QVariant.Double))
    fields.append(QgsField("cell_perimeter", QVariant.Double))
    mem_layer = QgsVectorLayer("Polygon?crs=EPSG:4326", "rhealpix_expanded", "memory")
    mem_provider = mem_layer.dataProvider()
    mem_provider.addAttributes(fields)
    mem_layer.updateFields()

    rhealpix_ids = [
        feature[rHealPixID_field]
        for feature in rhealpix_layer.getFeatures()
        if feature[rHealPixID_field]
    ]

    rhealpix_ids = list(set(rhealpix_ids))

    if rhealpix_ids:
        try:
            res, d = _expand_resolution_depth(resolution, depth)
            if res is not None:
                max_res = max(
                    get_rhealpix_resolution(rhealpix_id) for rhealpix_id in rhealpix_ids
                )
                if res < max_res:
                    return _report_expand_res_too_coarse(feedback, res, max_res)
            rhealpix_cells_expand = rhealpix_expand(
                rhealpix_ids, resolution=res, depth=d, verbose=False
            )
        except QgsProcessingException:
            raise
        except Exception as e:
            raise QgsProcessingException(
                f"Expand cells failed. Please check your rHEALPix cell Ids: {e}"
            )

        total_cells = len(rhealpix_cells_expand)

        for i, rhealpix_cell_expand in enumerate(rhealpix_cells_expand):
            if feedback:
                feedback.setProgress(int((i / total_cells) * 100))
                if feedback.isCanceled():
                    return None

            rhealpix_id_expand = str(rhealpix_cell_expand)
            cell_polygon = _geo_with_fix(
                rhealpix2geo,
                rhealpix_id_expand,
                "rhealpix",
                shift_antimeridian,
                split_antimeridian,
            )

            if not cell_polygon.is_valid:
                continue
            num_edges = 3 if rhealpix_cell_expand.ellipsoidal_shape() == "dart" else 4
            center_lat, center_lon, avg_edge_len, cell_area, cell_perimeter = (
                geodesic_dggs_metrics(cell_polygon, num_edges)
            )

            cell_geom = QgsGeometry.fromWkt(cell_polygon.wkt)
            rhealpix_feature = QgsFeature(fields)
            rhealpix_feature.setGeometry(cell_geom)

            attributes = {
                "rhealpix": rhealpix_id_expand,
                "resolution": rhealpix_cell_expand.resolution,
                "center_lat": center_lat,
                "center_lon": center_lon,
                "avg_edge_len": avg_edge_len,
                "cell_area": cell_area,
                "cell_perimeter": cell_perimeter,
            }
            rhealpix_feature.setAttributes(
                [attributes[field.name()] for field in fields]
            )
            mem_provider.addFeatures([rhealpix_feature])

        if feedback:
            feedback.setProgress(100)
            feedback.pushInfo("rHEALPix DGGS expansion completed.")

    return mem_layer


##########################
# ISEA4T
#########################
def isea4texpand(
    isea4t_layer: QgsVectorLayer,
    resolution: int,
    ISEA4TID_field=None,
    feedback=None,
    shift_antimeridian=False,
    split_antimeridian=False,
    depth=None,
) -> QgsVectorLayer:
    if platform.system() == "Windows":
        if not ISEA4TID_field:
            ISEA4TID_field = "isea4t"

        fields = QgsFields()
        fields.append(QgsField("isea4t", QVariant.String))
        fields.append(QgsField("resolution", QVariant.Int))
        fields.append(QgsField("center_lat", QVariant.Double))
        fields.append(QgsField("center_lon", QVariant.Double))
        fields.append(QgsField("avg_edge_len", QVariant.Double))
        fields.append(QgsField("cell_area", QVariant.Double))
        fields.append(QgsField("cell_perimeter", QVariant.Double))
        mem_layer = QgsVectorLayer("Polygon?crs=EPSG:4326", "isea4t_expanded", "memory")
        mem_provider = mem_layer.dataProvider()
        mem_provider.addAttributes(fields)
        mem_layer.updateFields()

        isea4t_ids = [
            feature[ISEA4TID_field]
            for feature in isea4t_layer.getFeatures()
            if feature[ISEA4TID_field]
        ]
        isea4t_ids = list(set(isea4t_ids))

        if isea4t_ids:
            try:
                res, d = _expand_resolution_depth(resolution, depth)
                if res is not None:
                    max_res = max(
                        get_isea4t_resolution(isea4t_id) for isea4t_id in isea4t_ids
                    )
                    if res < max_res:
                        return _report_expand_res_too_coarse(feedback, res, max_res)
                isea4t_cells_expand = isea4t_expand(
                    isea4t_ids, resolution=res, depth=d, verbose=False
                )
            except QgsProcessingException:
                raise
            except BaseException:
                raise QgsProcessingException(
                    "Expand cells failed. Please check your ISEA4T cell Ids."
                )

            isea4t_ids_expand = [c.get_cell_id() for c in isea4t_cells_expand]
            total_cells = len(isea4t_ids_expand)

            for i, isea4t_id_expand in enumerate(isea4t_ids_expand):
                if feedback:
                    feedback.setProgress(int((i / total_cells) * 100))
                    if feedback.isCanceled():
                        return None

                cell_polygon = _geo_with_fix(
                    isea4t2geo,
                    isea4t_id_expand,
                    "isea4t",
                    shift_antimeridian,
                    split_antimeridian,
                )
                if not cell_polygon.is_valid:
                    continue
                num_edges = 3
                center_lat, center_lon, avg_edge_len, cell_area, cell_perimeter = (
                    geodesic_dggs_metrics(cell_polygon, num_edges)
                )

                cell_geom = QgsGeometry.fromWkt(cell_polygon.wkt)
                isea4t_feature = QgsFeature(fields)
                isea4t_feature.setGeometry(cell_geom)

                attributes = {
                    "isea4t": isea4t_id_expand,
                    "resolution": get_isea4t_resolution(isea4t_id_expand),
                    "center_lat": center_lat,
                    "center_lon": center_lon,
                    "avg_edge_len": avg_edge_len,
                    "cell_area": cell_area,
                    "cell_perimeter": cell_perimeter,
                }
                isea4t_feature.setAttributes(
                    [attributes[field.name()] for field in fields]
                )
                mem_provider.addFeatures([isea4t_feature])

            if feedback:
                feedback.setProgress(100)
                feedback.pushInfo("ISEA4T DGGS expansion completed.")

        return mem_layer


##########################
# ISEA3H
#########################
def isea3hexpand(
    isea3h_layer: QgsVectorLayer,
    resolution: int,
    ISEA3HID_field=None,
    feedback=None,
    shift_antimeridian=False,
    split_antimeridian=False,
    depth=None,
) -> QgsVectorLayer:
    if not ISEA3HID_field:
        ISEA3HID_field = "isea3h"

    fields = QgsFields()
    fields.append(QgsField("isea3h", QVariant.String))
    fields.append(QgsField("resolution", QVariant.Int))
    fields.append(QgsField("center_lat", QVariant.Double))
    fields.append(QgsField("center_lon", QVariant.Double))
    fields.append(QgsField("avg_edge_len", QVariant.Double))
    fields.append(QgsField("cell_area", QVariant.Double))
    fields.append(QgsField("cell_perimeter", QVariant.Double))
    mem_layer = QgsVectorLayer("Polygon?crs=EPSG:4326", "isea3h_expanded", "memory")
    mem_provider = mem_layer.dataProvider()
    mem_provider.addAttributes(fields)
    mem_layer.updateFields()

    isea3h_ids = [
        feature[ISEA3HID_field]
        for feature in isea3h_layer.getFeatures()
        if feature[ISEA3HID_field]
    ]
    isea3h_ids = list(set(isea3h_ids))

    if isea3h_ids:
        try:
            res, d = _expand_resolution_depth(resolution, depth)
            if res is not None:
                max_res = max(
                    get_isea3h_resolution(isea3h_id) for isea3h_id in isea3h_ids
                )
                if res < max_res:
                    return _report_expand_res_too_coarse(feedback, res, max_res)
            isea3h_cells_expand = isea3h_expand(
                isea3h_ids, resolution=res, depth=d, verbose=False
            )
        except QgsProcessingException:
            raise
        except Exception as e:
            raise QgsProcessingException(
                f"Expand cells failed. Please check your ISEA3H cell Ids: {e}"
            )

        isea3h_ids_expand = [c.get_cell_id() for c in isea3h_cells_expand]
        total_cells = len(isea3h_ids_expand)

        for i, isea3h_id_expand in enumerate(isea3h_ids_expand):
            if feedback:
                feedback.setProgress(int((i / total_cells) * 100))
                if feedback.isCanceled():
                    return None

            cell_polygon = _geo_with_fix(
                isea3h2geo,
                isea3h_id_expand,
                "isea3h",
                shift_antimeridian,
                split_antimeridian,
            )
            if not cell_polygon.is_valid:
                continue

            num_edges = 6
            center_lat, center_lon, avg_edge_len, cell_area, cell_perimeter = (
                geodesic_dggs_metrics(cell_polygon, num_edges)
            )

            cell_geom = QgsGeometry.fromWkt(cell_polygon.wkt)
            isea3h_feature = QgsFeature(fields)
            isea3h_feature.setGeometry(cell_geom)

            attributes = {
                "isea3h": isea3h_id_expand,
                "resolution": get_isea3h_resolution(isea3h_id_expand),
                "center_lat": center_lat,
                "center_lon": center_lon,
                "avg_edge_len": round(avg_edge_len, 3),
                "cell_area": cell_area,
                "cell_perimeter": cell_perimeter,
            }
            isea3h_feature.setAttributes([attributes[field.name()] for field in fields])
            mem_provider.addFeatures([isea3h_feature])

        if feedback:
            feedback.setProgress(100)
            feedback.pushInfo("isea3h DGGS expansion completed.")

    return mem_layer


##########################
# QTM
#########################
def qtmexpand(
    qtm_layer: QgsVectorLayer,
    resolution: int,
    QTMID_field=None,
    feedback=None,
    shift_antimeridian=False,
    split_antimeridian=False,
    depth=None,
) -> QgsVectorLayer:
    if not QTMID_field:
        QTMID_field = "qtm"

    fields = QgsFields()
    fields.append(QgsField("qtm", QVariant.String))
    fields.append(QgsField("resolution", QVariant.Int))
    fields.append(QgsField("center_lat", QVariant.Double))
    fields.append(QgsField("center_lon", QVariant.Double))
    fields.append(QgsField("avg_edge_len", QVariant.Double))
    fields.append(QgsField("cell_area", QVariant.Double))
    fields.append(QgsField("cell_perimeter", QVariant.Double))
    mem_layer = QgsVectorLayer("Polygon?crs=EPSG:4326", "qtm_expanded", "memory")
    mem_provider = mem_layer.dataProvider()
    mem_provider.addAttributes(fields)
    mem_layer.updateFields()

    qtm_ids = [
        feature[QTMID_field]
        for feature in qtm_layer.getFeatures()
        if feature[QTMID_field]
    ]
    qtm_ids = list(set(qtm_ids))

    if qtm_ids:
        try:
            res, d = _expand_resolution_depth(resolution, depth)
            if res is not None:
                max_res = max(get_qtm_resolution(qtm_id) for qtm_id in qtm_ids)
                if res < max_res:
                    return _report_expand_res_too_coarse(feedback, res, max_res)
            qtm_ids_expand = qtm_expand(
                qtm_ids, resolution=res, depth=d, verbose=False
            )
        except QgsProcessingException:
            raise
        except BaseException:
            raise QgsProcessingException(
                "Expand cells failed. Please check your QTM cell Ids."
            )

        total_cells = len(qtm_ids_expand)

        for i, qtm_id_expand in enumerate(qtm_ids_expand):
            if feedback:
                feedback.setProgress(int((i / total_cells) * 100))
                if feedback.isCanceled():
                    return None

            cell_polygon = qtm2geo(qtm_id_expand)
            if not cell_polygon.is_valid:
                continue

            num_edges = 3
            center_lat, center_lon, avg_edge_len, cell_area, cell_perimeter = (
                geodesic_dggs_metrics(cell_polygon, num_edges)
            )

            cell_geom = QgsGeometry.fromWkt(cell_polygon.wkt)
            qtm_feature = QgsFeature(fields)
            qtm_feature.setGeometry(cell_geom)

            attributes = {
                "qtm": qtm_id_expand,
                "resolution": get_qtm_resolution(qtm_id_expand),
                "center_lat": center_lat,
                "center_lon": center_lon,
                "avg_edge_len": avg_edge_len,
                "cell_area": cell_area,
                "cell_perimeter": cell_perimeter,
            }
            qtm_feature.setAttributes([attributes[field.name()] for field in fields])
            mem_provider.addFeatures([qtm_feature])

        if feedback:
            feedback.setProgress(100)
            feedback.pushInfo("QTM expansion completed.")

    return mem_layer


##########################
# OLC
#########################
def olcexpand(
    olc_layer: QgsVectorLayer,
    resolution: int,
    OLCID_field=None,
    feedback=None,
    shift_antimeridian=False,
    split_antimeridian=False,
    depth=None,
) -> QgsVectorLayer:
    if not OLCID_field:
        OLCID_field = "olc"

    fields = QgsFields()
    fields.append(QgsField("olc", QVariant.String))
    fields.append(QgsField("resolution", QVariant.Int))
    fields.append(QgsField("center_lat", QVariant.Double))
    fields.append(QgsField("center_lon", QVariant.Double))
    fields.append(QgsField("cell_width", QVariant.Double))
    fields.append(QgsField("cell_height", QVariant.Double))
    fields.append(QgsField("cell_area", QVariant.Double))
    fields.append(QgsField("cell_perimeter", QVariant.Double))
    mem_layer = QgsVectorLayer("Polygon?crs=EPSG:4326", "olc_expanded", "memory")
    mem_provider = mem_layer.dataProvider()
    mem_provider.addAttributes(fields)
    mem_layer.updateFields()

    olc_ids = [
        feature[OLCID_field]
        for feature in olc_layer.getFeatures()
        if feature[OLCID_field]
    ]
    olc_ids = list(set(olc_ids))

    if olc_ids:
        try:
            res, d = _expand_resolution_depth(resolution, depth)
            if res is not None:
                max_res = max(get_olc_resolution(olc_id) for olc_id in olc_ids)
                if res < max_res:
                    return _report_expand_res_too_coarse(feedback, res, max_res)
            olc_ids_expand = olc_expand(
                olc_ids, resolution=res, depth=d, verbose=False
            )
        except QgsProcessingException:
            raise
        except BaseException:
            raise QgsProcessingException(
                "Expand cells failed. Please check your OLC cell Ids."
            )

        total_cells = len(olc_ids_expand)

        for i, olc_id_expand in enumerate(olc_ids_expand):
            if feedback:
                feedback.setProgress(int((i / total_cells) * 100))
                if feedback.isCanceled():
                    return None

            cell_polygon = olc2geo(olc_id_expand)
            if not cell_polygon.is_valid:
                continue

            (
                center_lat,
                center_lon,
                cell_width,
                cell_height,
                cell_area,
                cell_perimeter,
            ) = graticule_dggs_metrics(cell_polygon)

            cell_geom = QgsGeometry.fromWkt(cell_polygon.wkt)
            olc_feature = QgsFeature(fields)
            olc_feature.setGeometry(cell_geom)

            attributes = {
                "olc": olc_id_expand,
                "resolution": get_olc_resolution(olc_id_expand),
                "center_lat": center_lat,
                "center_lon": center_lon,
                "cell_width": cell_width,
                "cell_height": cell_height,
                "cell_area": cell_area,
                "cell_perimeter": cell_perimeter,
            }
            olc_feature.setAttributes([attributes[field.name()] for field in fields])
            mem_provider.addFeatures([olc_feature])

        if feedback:
            feedback.setProgress(100)
            feedback.pushInfo("OLC expansion completed.")

    return mem_layer


##########################
# Geohash
#########################
def geohashexpand(
    geohash_layer: QgsVectorLayer,
    resolution: int,
    GeohashID_field=None,
    feedback=None,
    shift_antimeridian=False,
    split_antimeridian=False,
    depth=None,
) -> QgsVectorLayer:
    if not GeohashID_field:
        GeohashID_field = "geohash"

    fields = QgsFields()
    fields.append(QgsField("geohash", QVariant.String))
    fields.append(QgsField("resolution", QVariant.Int))
    fields.append(QgsField("center_lat", QVariant.Double))
    fields.append(QgsField("center_lon", QVariant.Double))
    fields.append(QgsField("cell_width", QVariant.Double))
    fields.append(QgsField("cell_height", QVariant.Double))
    fields.append(QgsField("cell_area", QVariant.Double))
    fields.append(QgsField("cell_perimeter", QVariant.Double))
    mem_layer = QgsVectorLayer("Polygon?crs=EPSG:4326", "geohash_expanded", "memory")
    mem_provider = mem_layer.dataProvider()
    mem_provider.addAttributes(fields)
    mem_layer.updateFields()

    geohash_ids = [
        feature[GeohashID_field]
        for feature in geohash_layer.getFeatures()
        if feature[GeohashID_field]
    ]
    geohash_ids = list(set(geohash_ids))

    if geohash_ids:
        try:
            res, d = _expand_resolution_depth(resolution, depth)
            if res is not None:
                max_res = max(
                    get_geohash_resolution(geohash_id) for geohash_id in geohash_ids
                )
                if res < max_res:
                    return _report_expand_res_too_coarse(feedback, res, max_res)
            geohash_ids_expand = geohash_expand(
                geohash_ids, resolution=res, depth=d, verbose=False
            )
        except QgsProcessingException:
            raise
        except BaseException:
            raise QgsProcessingException(
                "Expand cells failed. Please check your Geohash cell Ids."
            )

        total_cells = len(geohash_ids_expand)

        for i, geohash_id_expand in enumerate(geohash_ids_expand):
            if feedback:
                feedback.setProgress(int((i / total_cells) * 100))
                if feedback.isCanceled():
                    return None

            cell_polygon = geohash2geo(geohash_id_expand)

            if not cell_polygon.is_valid:
                continue

            (
                center_lat,
                center_lon,
                cell_width,
                cell_height,
                cell_area,
                cell_perimeter,
            ) = graticule_dggs_metrics(cell_polygon)

            cell_geom = QgsGeometry.fromWkt(cell_polygon.wkt)
            geohash_feature = QgsFeature(fields)
            geohash_feature.setGeometry(cell_geom)

            attributes = {
                "geohash": geohash_id_expand,
                "resolution": get_geohash_resolution(geohash_id_expand),
                "center_lat": center_lat,
                "center_lon": center_lon,
                "cell_width": cell_width,
                "cell_height": cell_height,
                "cell_area": cell_area,
                "cell_perimeter": cell_perimeter,
            }
            geohash_feature.setAttributes(
                [attributes[field.name()] for field in fields]
            )
            mem_provider.addFeatures([geohash_feature])

        if feedback:
            feedback.setProgress(100)
            feedback.pushInfo("Geohash expansion completed.")

    return mem_layer


##########################
# Tilecode
#########################
def tilecodeexpand(
    tilecode_layer: QgsVectorLayer,
    resolution: int,
    TilecodeID_field=None,
    feedback=None,
    shift_antimeridian=False,
    split_antimeridian=False,
    depth=None,
) -> QgsVectorLayer:
    if not TilecodeID_field:
        TilecodeID_field = "tilecode"

    fields = QgsFields()
    fields.append(QgsField("tilecode", QVariant.String))
    fields.append(QgsField("resolution", QVariant.Int))
    fields.append(QgsField("center_lat", QVariant.Double))
    fields.append(QgsField("center_lon", QVariant.Double))
    fields.append(QgsField("cell_width", QVariant.Double))
    fields.append(QgsField("cell_height", QVariant.Double))
    fields.append(QgsField("cell_area", QVariant.Double))
    fields.append(QgsField("cell_perimeter", QVariant.Double))
    mem_layer = QgsVectorLayer("Polygon?crs=EPSG:4326", "tilecode_expanded", "memory")
    mem_provider = mem_layer.dataProvider()
    mem_provider.addAttributes(fields)
    mem_layer.updateFields()

    tilecode_ids = [
        feature[TilecodeID_field]
        for feature in tilecode_layer.getFeatures()
        if feature[TilecodeID_field]
    ]
    tilecode_ids = list(set(tilecode_ids))

    if tilecode_ids:
        try:
            res, d = _expand_resolution_depth(resolution, depth)
            if res is not None:
                max_res = max(
                    tilecode_resolution(tilecode_id) for tilecode_id in tilecode_ids
                )
                if res < max_res:
                    return _report_expand_res_too_coarse(feedback, res, max_res)
            tilecode_ids_expand = tilecode_expand(
                tilecode_ids, resolution=res, depth=d, verbose=False
            )
        except QgsProcessingException:
            raise
        except BaseException:
            raise QgsProcessingException(
                "Expand cells failed. Please check your tilecode cell Ids."
            )

        total_cells = len(tilecode_ids_expand)

        for i, tilecode_id_expand in enumerate(tilecode_ids_expand):
            if feedback:
                feedback.setProgress(int((i / total_cells) * 100))
                if feedback.isCanceled():
                    return None

            cell_polygon = tilecode2geo(tilecode_id_expand)

            if not cell_polygon.is_valid:
                continue

            (
                center_lat,
                center_lon,
                cell_width,
                cell_height,
                cell_area,
                cell_perimeter,
            ) = graticule_dggs_metrics(cell_polygon)

            cell_geom = QgsGeometry.fromWkt(cell_polygon.wkt)
            tilecode_feature = QgsFeature(fields)
            tilecode_feature.setGeometry(cell_geom)

            attributes = {
                "tilecode": tilecode_id_expand,
                "resolution": tilecode_resolution(tilecode_id_expand),
                "center_lat": center_lat,
                "center_lon": center_lon,
                "cell_width": cell_width,
                "cell_height": cell_height,
                "cell_area": cell_area,
                "cell_perimeter": cell_perimeter,
            }
            tilecode_feature.setAttributes(
                [attributes[field.name()] for field in fields]
            )
            mem_provider.addFeatures([tilecode_feature])

        if feedback:
            feedback.setProgress(100)
            feedback.pushInfo("Tilecode expansion completed.")

    return mem_layer


##########################
# Quadkey
#########################
def quadkeyexpand(
    quadkey_layer: QgsVectorLayer,
    resolution: int,
    QuadkeyID_field=None,
    feedback=None,
    shift_antimeridian=False,
    split_antimeridian=False,
    depth=None,
) -> QgsVectorLayer:
    if not QuadkeyID_field:
        QuadkeyID_field = "quadkey"

    fields = QgsFields()
    fields.append(QgsField("quadkey", QVariant.String))
    fields.append(QgsField("resolution", QVariant.Int))
    fields.append(QgsField("center_lat", QVariant.Double))
    fields.append(QgsField("center_lon", QVariant.Double))
    fields.append(QgsField("cell_width", QVariant.Double))
    fields.append(QgsField("cell_height", QVariant.Double))
    fields.append(QgsField("cell_area", QVariant.Double))
    fields.append(QgsField("cell_perimeter", QVariant.Double))
    mem_layer = QgsVectorLayer("Polygon?crs=EPSG:4326", "quadkey_expanded", "memory")
    mem_provider = mem_layer.dataProvider()
    mem_provider.addAttributes(fields)
    mem_layer.updateFields()

    quadkey_ids = [
        feature[QuadkeyID_field]
        for feature in quadkey_layer.getFeatures()
        if feature[QuadkeyID_field]
    ]
    quadkey_ids = list(set(quadkey_ids))

    if quadkey_ids:
        try:
            res, d = _expand_resolution_depth(resolution, depth)
            if res is not None:
                max_res = max(
                    quadkey_resolution(quadkey_id) for quadkey_id in quadkey_ids
                )
                if res < max_res:
                    return _report_expand_res_too_coarse(feedback, res, max_res)
            quadkey_ids_expand = quadkey_expand(
                quadkey_ids, resolution=res, depth=d, verbose=False
            )
        except QgsProcessingException:
            raise
        except BaseException:
            raise QgsProcessingException(
                "Expand cells failed. Please check your quadkey cell Ids."
            )

        total_cells = len(quadkey_ids_expand)

        for i, quadkey_id_expand in enumerate(quadkey_ids_expand):
            if feedback:
                feedback.setProgress(int((i / total_cells) * 100))
                if feedback.isCanceled():
                    return None

            cell_polygon = quadkey2geo(quadkey_id_expand)

            if not cell_polygon.is_valid:
                continue

            (
                center_lat,
                center_lon,
                cell_width,
                cell_height,
                cell_area,
                cell_perimeter,
            ) = graticule_dggs_metrics(cell_polygon)

            cell_geom = QgsGeometry.fromWkt(cell_polygon.wkt)
            quadkey_feature = QgsFeature(fields)
            quadkey_feature.setGeometry(cell_geom)

            attributes = {
                "quadkey": quadkey_id_expand,
                "resolution": quadkey_resolution(quadkey_id_expand),
                "center_lat": center_lat,
                "center_lon": center_lon,
                "cell_width": cell_width,
                "cell_height": cell_height,
                "cell_area": cell_area,
                "cell_perimeter": cell_perimeter,
            }
            quadkey_feature.setAttributes(
                [attributes[field.name()] for field in fields]
            )
            mem_provider.addFeatures([quadkey_feature])

        if feedback:
            feedback.setProgress(100)
            feedback.pushInfo("Quadkey expansion completed.")

    return mem_layer


##########################
# DGGAL
#########################
def dggalexpand(
    dggal_layer: QgsVectorLayer,
    resolution: int,
    DGGALID_field=None,
    feedback=None,
    dggal_type=None,
    shift_antimeridian=False,
    split_antimeridian=False,
    depth=None,
) -> QgsVectorLayer:
    if not DGGALID_field:
        DGGALID_field = f"dggal_{dggal_type}"

    fields = QgsFields()
    # Use the specific DGGAL type for the field name
    field_name = f"dggal_{dggal_type}"
    fields.append(QgsField(field_name, QVariant.String))
    fields.append(QgsField("resolution", QVariant.Int))
    fields.append(QgsField("center_lat", QVariant.Double))
    fields.append(QgsField("center_lon", QVariant.Double))
    fields.append(QgsField("avg_edge_len", QVariant.Double))
    fields.append(QgsField("cell_area", QVariant.Double))
    fields.append(QgsField("cell_perimeter", QVariant.Double))
    layer_name = f"dggal_{dggal_type}_expanded" if dggal_type else "dggal_expanded"
    mem_layer = QgsVectorLayer("Polygon?crs=EPSG:4326", layer_name, "memory")
    mem_provider = mem_layer.dataProvider()
    mem_provider.addAttributes(fields)
    mem_layer.updateFields()

    dggal_ids = [
        feature[DGGALID_field]
        for feature in dggal_layer.getFeatures()
        if feature[DGGALID_field]
    ]
    dggal_ids = list(set(dggal_ids))

    if dggal_ids:
        try:
            res, d = _expand_resolution_depth(resolution, depth)
            app = Application(appGlobals=globals())
            pydggal_setup(app)
            dggs_class_name = DGGAL_TYPES[dggal_type]["class_name"]
            dggrs = getattr(dggal, dggs_class_name)()

            if res is not None:
                max_res = 0
                for dggal_id in dggal_ids:
                    try:
                        zone = dggrs.getZoneFromTextID(dggal_id)
                        zone_res = dggrs.getZoneLevel(zone)
                        max_res = max(max_res, zone_res)
                    except BaseException:
                        continue
                if res < max_res:
                    return _report_expand_res_too_coarse(feedback, res, max_res)

            dggal_ids_expand = dggal_expand(
                dggal_type, dggal_ids, resolution=res, depth=d, verbose=False
            )
        except QgsProcessingException:
            raise
        except Exception as e:
            raise QgsProcessingException(
                f"Expand cells failed. Please check your DGGAL ID field. Error: {str(e)}"
            )

        total_cells = len(dggal_ids_expand)

        for i, dggal_id_expand in enumerate(dggal_ids_expand):
            if feedback:
                feedback.setProgress(int((i / total_cells) * 100))
                if feedback.isCanceled():
                    return None
            try:
                cell_polygon = dggal2geo(
                    dggal_type,
                    dggal_id_expand,
                    split_antimeridian=_use_split_antimeridian(
                        shift_antimeridian, split_antimeridian
                    ),
                )

                # Get resolution and edge count from DGGAL
                try:
                    dggs_class_name = DGGAL_TYPES[dggal_type]["class_name"]
                    dggrs = getattr(dggal, dggs_class_name)()
                    zone = dggrs.getZoneFromTextID(dggal_id_expand)
                    zone_resolution = dggrs.getZoneLevel(zone)
                    num_edges = dggrs.countZoneEdges(zone)
                except BaseException:
                    # Fallback values if we can't get them from DGGAL
                    zone_resolution = resolution
                    num_edges = 6  # Default for hexagonal cells

                center_lat, center_lon, avg_edge_len, cell_area, cell_perimeter = (
                    geodesic_dggs_metrics(cell_polygon, num_edges)
                )
            except Exception as e:
                if feedback:
                    feedback.pushInfo(
                        f"Warning: Could not process DGGAL ID {dggal_id_expand}: {str(e)}"
                    )
                continue

            cell_geom = QgsGeometry.fromWkt(cell_polygon.wkt)
            dggal_feature = QgsFeature(fields)
            dggal_feature.setGeometry(cell_geom)

            attributes = {
                field_name: dggal_id_expand,
                "resolution": zone_resolution,
                "center_lat": center_lat,
                "center_lon": center_lon,
                "avg_edge_len": avg_edge_len,
                "cell_area": cell_area,
                "cell_perimeter": cell_perimeter,
            }
            dggal_feature.setAttributes([attributes[field.name()] for field in fields])
            mem_provider.addFeatures([dggal_feature])

        if feedback:
            feedback.setProgress(100)
            feedback.pushInfo(f"DGGAL {dggal_type.upper()} expansion completed.")

    return mem_layer


##########################
# DIGIPIN
#########################
def digipinexpand(
    digipin_layer: QgsVectorLayer,
    resolution: int,
    DIGIPINID_field=None,
    feedback=None,
    shift_antimeridian=False,
    split_antimeridian=False,
    depth=None,
) -> QgsVectorLayer:
    if not DIGIPINID_field:
        DIGIPINID_field = "digipin"

    fields = QgsFields()
    fields.append(QgsField("digipin", QVariant.String))
    fields.append(QgsField("resolution", QVariant.Int))
    fields.append(QgsField("center_lat", QVariant.Double))
    fields.append(QgsField("center_lon", QVariant.Double))
    fields.append(QgsField("cell_width", QVariant.Double))
    fields.append(QgsField("cell_height", QVariant.Double))
    fields.append(QgsField("cell_area", QVariant.Double))
    fields.append(QgsField("cell_perimeter", QVariant.Double))
    mem_layer = QgsVectorLayer("Polygon?crs=EPSG:4326", "digipin_expanded", "memory")
    mem_provider = mem_layer.dataProvider()
    mem_provider.addAttributes(fields)
    mem_layer.updateFields()

    digipin_ids = [
        feature[DIGIPINID_field]
        for feature in digipin_layer.getFeatures()
        if feature[DIGIPINID_field]
    ]
    digipin_ids = list(set(digipin_ids))

    if digipin_ids:
        try:
            res, d = _expand_resolution_depth(resolution, depth)
            if res is not None:
                max_res = max(digipin_resolution(digipin_id) for digipin_id in digipin_ids)
                if isinstance(max_res, str) or res < max_res:
                    return _report_expand_res_too_coarse(feedback, res, max_res)
            digipin_ids_expand = digipin_expand(
                digipin_ids, resolution=res, depth=d, verbose=False
            )
        except QgsProcessingException:
            raise
        except Exception as e:
            raise QgsProcessingException(
                f"Expand cells failed. Please check your DIGIPIN ID field. Error: {str(e)}"
            )

        total_cells = len(digipin_ids_expand)

        for i, digipin_id_expand in enumerate(digipin_ids_expand):
            if feedback:
                feedback.setProgress(int((i / total_cells) * 100))
                if feedback.isCanceled():
                    return None

            try:
                cell_polygon = digipin2geo(digipin_id_expand)

                if not cell_polygon.is_valid:
                    continue

                (
                    center_lat,
                    center_lon,
                    cell_width,
                    cell_height,
                    cell_area,
                    cell_perimeter,
                ) = graticule_dggs_metrics(cell_polygon)

                cell_geom = QgsGeometry.fromWkt(cell_polygon.wkt)
                digipin_feature = QgsFeature(fields)
                digipin_feature.setGeometry(cell_geom)

                attributes = {
                    "digipin": digipin_id_expand,
                    "resolution": digipin_resolution(digipin_id_expand),
                    "center_lat": center_lat,
                    "center_lon": center_lon,
                    "cell_width": cell_width,
                    "cell_height": cell_height,
                    "cell_area": cell_area,
                    "cell_perimeter": cell_perimeter,
                }
                digipin_feature.setAttributes(
                    [attributes[field.name()] for field in fields]
                )
                mem_provider.addFeatures([digipin_feature])

            except Exception as e:
                if feedback:
                    feedback.pushInfo(
                        f"Warning: Could not process DIGIPIN ID {digipin_id_expand}: {str(e)}"
                    )
                continue

        if feedback:
            feedback.setProgress(100)
            feedback.pushInfo("DIGIPIN expansion completed.")

    return mem_layer
