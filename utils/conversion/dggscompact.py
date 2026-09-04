from collections import defaultdict

from qgis.PyQt.QtCore import QVariant
from qgis.core import (
    QgsVectorLayer,
    QgsFeature,
    QgsGeometry,
    QgsField,
    QgsFields,
    QgsProcessingException,
)
from vgrid.dggs import s2
import h3
import a5

from vgrid.dggs.rhealpixdggs.dggs import RHEALPixDGGS
from vgrid.dggs.rhealpixdggs.ellipsoids import WGS84_ELLIPSOID
from vgrid.utils.constants import DGGAL_TYPES
from dggal import *
import platform

if platform.system() == "Windows":
    from vgrid.dggs.eaggr.eaggr import Eaggr
    from vgrid.dggs.eaggr.enums.model import Model
    from vgrid.conversion.dggscompact.isea4tcompact import isea4t_compact
    from vgrid.conversion.dggscompact.isea4tcompact import get_isea4t_resolution
    from vgrid.conversion.dggscompact.isea3hcompact import isea3h_compact
    from vgrid.conversion.dggscompact.isea3hcompact import get_isea3h_resolution
    from vgrid.conversion.dggs2geo.isea4t2geo import isea4t2geo
    from vgrid.conversion.dggs2geo.isea3h2geo import isea3h2geo

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
from vgrid.conversion.dggscompact.h3compact import h3_compact
from vgrid.conversion.dggscompact.s2compact import s2_compact
from vgrid.conversion.dggscompact.a5compact import a5_compact
from vgrid.conversion.dggscompact.rhealpixcompact import rhealpix_compact
from vgrid.conversion.dggscompact.dggalcompact import dggal_compact
from vgrid.utils.io import agg_column_name, aggregate_values, validate_agg
from vgrid.conversion.dggs2geo.qtm2geo import qtm2geo
from vgrid.conversion.dggscompact.qtmcompact import qtm_compact, get_qtm_resolution
from vgrid.conversion.dggs2geo.olc2geo import olc2geo
from vgrid.conversion.dggscompact.olccompact import olc_compact, get_olc_resolution
from vgrid.conversion.dggs2geo.geohash2geo import geohash2geo
from vgrid.conversion.dggscompact.geohashcompact import (
    geohash_compact,
    get_geohash_resolution,
)
from vgrid.conversion.dggscompact.tilecodecompact import tilecode_compact
from vgrid.conversion.dggs2geo.tilecode2geo import tilecode2geo
from vgrid.conversion.dggscompact.quadkeycompact import quadkey_compact
from vgrid.conversion.dggs2geo.quadkey2geo import quadkey2geo
from vgrid.dggs.tilecode import tilecode_resolution, quadkey_resolution
from vgrid.conversion.dggs2geo.dggal2geo import dggal2geo
from vgrid.conversion.dggs2geo.digipin2geo import digipin2geo
from vgrid.conversion.dggscompact.digipincompact import digipin_compact
from vgrid.conversion.dggscompact import *
from pyproj import Geod

from ..antimeridian_helper import (
    geo_with_fix as _geo_with_fix,
    use_split_antimeridian as _use_split_antimeridian,
)
from ..binning.bin_helper import agg_field_type, qgs_attribute_value

geod = Geod(ellps="WGS84")
E = WGS84_ELLIPSOID


def prepare_qgis_compact_bags(layer, id_field, agg=None, numeric_col=None):
    """Build per-cell value bags from a QGIS layer (same rules as vgrid compact).

    When ``agg`` is None, unique cell IDs are collected without aggregating values.
    """
    if agg is not None:
        if not validate_agg(agg):
            raise QgsProcessingException(f"Invalid aggregation '{agg}'")
        if agg != "count" and not numeric_col:
            raise QgsProcessingException(
                "A numeric field is required for aggregate functions other than 'count'."
            )

    bags = defaultdict(list)
    for feat in layer.getFeatures():
        cell = qgs_attribute_value(feat[id_field])
        if cell is None or cell == "":
            continue
        cell = str(cell)
        if agg is None:
            bags.setdefault(cell, [])
        elif agg == "count":
            bags[cell].append(1)
        else:
            bags[cell].append(qgs_attribute_value(feat[numeric_col]))

    agg_col = None
    if agg is not None:
        agg_col = agg_column_name(
            agg, numeric_col=None if agg == "count" else numeric_col
        )
    if not bags:
        return None, agg_col
    return bags, agg_col


def append_compact_agg_field(fields, agg_col, agg):
    if not agg or not agg_col:
        return
    fields.append(QgsField(agg_col, agg_field_type(agg)))


def compact_agg_value(bags, cell_id, agg):
    if not agg:
        return None
    return aggregate_values(bags.get(cell_id, []), agg)


##########################
# H3
# ########################
def h3compact(
    h3_layer: QgsVectorLayer,
    H3ID_field=None,
    feedback=None,
    depth=-1,
    agg=None,
    numeric_col=None,
    shift_antimeridian=False,
    split_antimeridian=False,
) -> QgsVectorLayer:
    if not H3ID_field:
        H3ID_field = "h3"
    bags, agg_col = prepare_qgis_compact_bags(
        h3_layer, H3ID_field, agg=agg, numeric_col=numeric_col
    )

    fields = QgsFields()
    fields.append(QgsField("h3", QVariant.String))
    fields.append(QgsField("resolution", QVariant.Int))
    fields.append(QgsField("center_lat", QVariant.Double))
    fields.append(QgsField("center_lon", QVariant.Double))
    fields.append(QgsField("avg_edge_len", QVariant.Double))
    fields.append(QgsField("cell_area", QVariant.Double))
    fields.append(QgsField("cell_perimeter", QVariant.Double))
    append_compact_agg_field(fields, agg_col, agg)

    mem_layer = QgsVectorLayer("Polygon?crs=EPSG:4326", "h3_compacted", "memory")
    mem_provider = mem_layer.dataProvider()
    mem_provider.addAttributes(fields)
    mem_layer.updateFields()

    if bags:
        try:
            h3_ids_compact = h3_compact(
                list(bags.keys()), depth=depth, bags=bags, verbose=False
            )
        except BaseException:
            raise QgsProcessingException(
                "Compact cells failed. Please check your H3 ID field."
            )

        total_cells = len(h3_ids_compact)

        for i, h3_id_compact in enumerate(h3_ids_compact):
            if feedback:
                feedback.setProgress(int((i / total_cells) * 100))
                if feedback.isCanceled():
                    return None

            cell_polygon = _geo_with_fix(
                h32geo,
                h3_id_compact,
                "h3",
                shift_antimeridian,
                split_antimeridian,
            )

            if not cell_polygon.is_valid:
                continue

            resolution = h3.get_resolution(h3_id_compact)
            num_edges = 5 if h3.is_pentagon(h3_id_compact) else 6
            center_lat, center_lon, avg_edge_len, cell_area, cell_perimeter = (
                geodesic_dggs_metrics(cell_polygon, num_edges)
            )

            cell_geom = QgsGeometry.fromWkt(cell_polygon.wkt)
            h3_feature = QgsFeature(fields)
            h3_feature.setGeometry(cell_geom)

            attributes = {
                "h3": h3_id_compact,
                "resolution": resolution,
                "center_lat": center_lat,
                "center_lon": center_lon,
                "avg_edge_len": avg_edge_len,
                "cell_area": cell_area,
                "cell_perimeter": cell_perimeter,
                agg_col: compact_agg_value(bags, h3_id_compact, agg),
            }
            h3_feature.setAttributes([attributes[field.name()] for field in fields])
            mem_provider.addFeatures([h3_feature])

        if feedback:
            feedback.setProgress(100)
            feedback.pushInfo("H3 Compact completed.")

        return mem_layer


##########################
# S2
# ########################
def s2compact(
    s2_layer: QgsVectorLayer,
    S2ID_field=None,
    feedback=None,
    depth=-1,
    agg=None,
    numeric_col=None,
    shift_antimeridian=False,
    split_antimeridian=False,
) -> QgsVectorLayer:
    if not S2ID_field:
        S2ID_field = "s2"
    bags, agg_col = prepare_qgis_compact_bags(
        s2_layer, S2ID_field, agg=agg, numeric_col=numeric_col
    )

    fields = QgsFields()
    fields.append(QgsField("s2", QVariant.String))
    fields.append(QgsField("resolution", QVariant.Int))
    fields.append(QgsField("center_lat", QVariant.Double))
    fields.append(QgsField("center_lon", QVariant.Double))
    fields.append(QgsField("avg_edge_len", QVariant.Double))
    fields.append(QgsField("cell_area", QVariant.Double))
    fields.append(QgsField("cell_perimeter", QVariant.Double))
    append_compact_agg_field(fields, agg_col, agg)
    mem_layer = QgsVectorLayer("Polygon?crs=EPSG:4326", "s2_compacted", "memory")
    mem_provider = mem_layer.dataProvider()
    mem_provider.addAttributes(fields)
    mem_layer.updateFields()

    if bags:
        try:
            s2_tokens_compact = s2_compact(
                list(bags.keys()), depth=depth, bags=bags, verbose=False
            )
        except BaseException:
            raise QgsProcessingException(
                "Compact cells failed. Please check your S2 ID field."
            )

        total_cells = len(s2_tokens_compact)

        for i, s2_token_compact in enumerate(s2_tokens_compact):
            if feedback:
                feedback.setProgress(int((i / total_cells) * 100))
                if feedback.isCanceled():
                    return None

            cell_polygon = _geo_with_fix(
                s22geo,
                s2_token_compact,
                "s2",
                shift_antimeridian,
                split_antimeridian,
            )

            if not cell_polygon.is_valid:
                continue

            resolution = s2.CellId.from_token(s2_token_compact).level()
            num_edges = 4
            center_lat, center_lon, avg_edge_len, cell_area, cell_perimeter = (
                geodesic_dggs_metrics(cell_polygon, num_edges)
            )

            cell_geom = QgsGeometry.fromWkt(cell_polygon.wkt)
            s2_feature = QgsFeature(fields)
            s2_feature.setGeometry(cell_geom)

            attributes = {
                "s2": s2_token_compact,
                "resolution": resolution,
                "center_lat": center_lat,
                "center_lon": center_lon,
                "avg_edge_len": avg_edge_len,
                "cell_area": cell_area,
                "cell_perimeter": cell_perimeter,
                agg_col: compact_agg_value(bags, s2_token_compact, agg),
            }
            s2_feature.setAttributes([attributes[field.name()] for field in fields])
            mem_provider.addFeatures([s2_feature])

        if feedback:
            feedback.setProgress(100)
            feedback.pushInfo("S2 Compact completed.")

        return mem_layer


##########################
# A5
# ########################
def a5compact(
    a5_layer: QgsVectorLayer,
    A5ID_field=None,
    feedback=None,
    depth=-1,
    agg=None,
    numeric_col=None,
    shift_antimeridian=False,
    split_antimeridian=False,
) -> QgsVectorLayer:
    if not A5ID_field:
        A5ID_field = "a5"
    bags, agg_col = prepare_qgis_compact_bags(
        a5_layer, A5ID_field, agg=agg, numeric_col=numeric_col
    )

    fields = QgsFields()
    fields.append(QgsField("a5", QVariant.String))
    fields.append(QgsField("resolution", QVariant.Int))
    fields.append(QgsField("center_lat", QVariant.Double))
    fields.append(QgsField("center_lon", QVariant.Double))
    fields.append(QgsField("avg_edge_len", QVariant.Double))
    fields.append(QgsField("cell_area", QVariant.Double))
    fields.append(QgsField("cell_perimeter", QVariant.Double))
    append_compact_agg_field(fields, agg_col, agg)
    mem_layer = QgsVectorLayer("Polygon?crs=EPSG:4326", "a5_compacted", "memory")
    mem_provider = mem_layer.dataProvider()
    mem_provider.addAttributes(fields)
    mem_layer.updateFields()

    if bags:
        try:
            a5_hexes_compact = a5_compact(
                list(bags.keys()), depth=depth, bags=bags, verbose=False
            )
        except BaseException:
            raise QgsProcessingException(
                "Compact cells failed. Please check your A5 ID field."
            )

        total_cells = len(a5_hexes_compact)

        for i, a5_hex_compact in enumerate(a5_hexes_compact):
            if feedback:
                feedback.setProgress(int((i / total_cells) * 100))
                if feedback.isCanceled():
                    return None

            try:
                cell_polygon = a52geo(
                    a5_hex_compact,
                    split_antimeridian=_use_split_antimeridian(
                        shift_antimeridian, split_antimeridian
                    ),
                )
            except BaseException:
                raise QgsProcessingException(
                    "Compact cells failed. Please check your A5 ID field."
                )

            if not cell_polygon.is_valid:
                continue

            resolution = a5.get_resolution(a5.hex_to_u64(a5_hex_compact))
            num_edges = 5  # A5 cells are pentagons
            center_lat, center_lon, avg_edge_len, cell_area, cell_perimeter = (
                geodesic_dggs_metrics(cell_polygon, num_edges)
            )

            cell_geom = QgsGeometry.fromWkt(cell_polygon.wkt)
            a5_feature = QgsFeature(fields)
            a5_feature.setGeometry(cell_geom)

            attributes = {
                "a5": a5_hex_compact,
                "resolution": resolution,
                "center_lat": center_lat,
                "center_lon": center_lon,
                "avg_edge_len": avg_edge_len,
                "cell_area": cell_area,
                "cell_perimeter": cell_perimeter,
                agg_col: compact_agg_value(bags, a5_hex_compact, agg),
            }
            a5_feature.setAttributes([attributes[field.name()] for field in fields])
            mem_provider.addFeatures([a5_feature])

        if feedback:
            feedback.setProgress(100)
            feedback.pushInfo("A5 Compact completed.")

        return mem_layer


##########################
# rHEALPix
# ########################
def rhealpixcompact(
    rhealpix_layer: QgsVectorLayer,
    rHEALPixID_field=None,
    feedback=None,
    depth=-1,
    agg=None,
    numeric_col=None,
    shift_antimeridian=False,
    split_antimeridian=False,
) -> QgsVectorLayer:
    if not rHEALPixID_field:
        rHEALPixID_field = "rhealpix"
    bags, agg_col = prepare_qgis_compact_bags(
        rhealpix_layer, rHEALPixID_field, agg=agg, numeric_col=numeric_col
    )

    rhealpix_dggs = RHEALPixDGGS()

    fields = QgsFields()
    fields.append(QgsField("rhealpix", QVariant.String))
    fields.append(QgsField("resolution", QVariant.Int))
    fields.append(QgsField("center_lat", QVariant.Double))
    fields.append(QgsField("center_lon", QVariant.Double))
    fields.append(QgsField("avg_edge_len", QVariant.Double))
    fields.append(QgsField("cell_area", QVariant.Double))
    fields.append(QgsField("cell_perimeter", QVariant.Double))
    append_compact_agg_field(fields, agg_col, agg)
    mem_layer = QgsVectorLayer("Polygon?crs=EPSG:4326", "rhealpix_compacted", "memory")
    mem_provider = mem_layer.dataProvider()
    mem_provider.addAttributes(fields)
    mem_layer.updateFields()

    if bags:
        try:
            rhealpix_ids_compact = rhealpix_compact(
                list(bags.keys()), depth=depth, bags=bags, verbose=False
            )
        except BaseException:
            raise QgsProcessingException(
                "Compact cells failed. Please check your rHEALPix ID field."
            )

        total_cells = len(rhealpix_ids_compact)

        for i, rhealpix_id_compact in enumerate(rhealpix_ids_compact):
            if feedback:
                feedback.setProgress(int((i / total_cells) * 100))
                if feedback.isCanceled():
                    return None
            try:
                cell_polygon = _geo_with_fix(
                    rhealpix2geo,
                    rhealpix_id_compact,
                    "rhealpix",
                    shift_antimeridian,
                    split_antimeridian,
                )
                rhealpix_uids = (rhealpix_id_compact[0],) + tuple(
                    map(int, rhealpix_id_compact[1:])
                )
                rhealpix_cell = rhealpix_dggs.cell(rhealpix_uids)
            except BaseException:
                raise QgsProcessingException(
                    "Compact cells failed. Please check your rHEALPix ID field."
                )

            resolution = rhealpix_cell.resolution
            num_edges = 3 if rhealpix_cell.ellipsoidal_shape() == "dart" else 4

            center_lat, center_lon, avg_edge_len, cell_area, cell_perimeter = (
                geodesic_dggs_metrics(cell_polygon, num_edges)
            )

            cell_geom = QgsGeometry.fromWkt(cell_polygon.wkt)
            rhealpix_feature = QgsFeature(fields)
            rhealpix_feature.setGeometry(cell_geom)

            attributes = {
                "rhealpix": rhealpix_id_compact,
                "resolution": resolution,
                "center_lat": center_lat,
                "center_lon": center_lon,
                "avg_edge_len": avg_edge_len,
                "cell_area": cell_area,
                "cell_perimeter": cell_perimeter,
                agg_col: compact_agg_value(bags, rhealpix_id_compact, agg),
            }
            rhealpix_feature.setAttributes(
                [attributes[field.name()] for field in fields]
            )
            mem_provider.addFeatures([rhealpix_feature])

        if feedback:
            feedback.setProgress(100)
            feedback.pushInfo("rHEALPix Compact completed.")

        return mem_layer


##########################
# ISEA4T
# ########################
def isea4tcompact(
    isea4t_layer: QgsVectorLayer,
    ISEA4TID_field=None,
    feedback=None,
    depth=-1,
    agg=None,
    numeric_col=None,
    shift_antimeridian=False,
    split_antimeridian=False,
) -> QgsVectorLayer:
    if platform.system() == "Windows":
        if not ISEA4TID_field:
            ISEA4TID_field = "isea4t"
        bags, agg_col = prepare_qgis_compact_bags(
            isea4t_layer, ISEA4TID_field, agg=agg, numeric_col=numeric_col
        )

        fields = QgsFields()
        fields.append(QgsField("isea4t", QVariant.String))
        fields.append(QgsField("resolution", QVariant.Int))
        fields.append(QgsField("center_lat", QVariant.Double))
        fields.append(QgsField("center_lon", QVariant.Double))
        fields.append(QgsField("avg_edge_len", QVariant.Double))
        fields.append(QgsField("cell_area", QVariant.Double))
        fields.append(QgsField("cell_perimeter", QVariant.Double))
        append_compact_agg_field(fields, agg_col, agg)
        mem_layer = QgsVectorLayer("Polygon?crs=EPSG:4326", "isea4t_compacted", "memory")
        mem_provider = mem_layer.dataProvider()
        mem_provider.addAttributes(fields)
        mem_layer.updateFields()

        if bags:
            try:
                isea4t_ids_compact = isea4t_compact(
                    list(bags.keys()), depth=depth, bags=bags, verbose=False
                )
            except BaseException:
                raise QgsProcessingException(
                    "Compact cells failed. Please check your ISEA4T ID field."
                )

            total_cells = len(isea4t_ids_compact)

            for i, isea4t_id_compact in enumerate(isea4t_ids_compact):
                if feedback:
                    feedback.setProgress(int((i / total_cells) * 100))
                    if feedback.isCanceled():
                        return None

                cell_polygon = _geo_with_fix(
                    isea4t2geo,
                    isea4t_id_compact,
                    "isea4t",
                    shift_antimeridian,
                    split_antimeridian,
                )

                resolution = get_isea4t_resolution(isea4t_id_compact)
                num_edges = 3

                center_lat, center_lon, avg_edge_len, cell_area, cell_perimeter = (
                    geodesic_dggs_metrics(cell_polygon, num_edges)
                )

                cell_geom = QgsGeometry.fromWkt(cell_polygon.wkt)
                ISEA4T_feature = QgsFeature(fields)
                ISEA4T_feature.setGeometry(cell_geom)

                attributes = {
                    "isea4t": isea4t_id_compact,
                    "resolution": resolution,
                    "center_lat": center_lat,
                    "center_lon": center_lon,
                    "avg_edge_len": avg_edge_len,
                    "cell_area": cell_area,
                    "cell_perimeter": cell_perimeter,
                    agg_col: compact_agg_value(bags, isea4t_id_compact, agg),
                }
                ISEA4T_feature.setAttributes(
                    [attributes[field.name()] for field in fields]
                )
                mem_provider.addFeatures([ISEA4T_feature])

            if feedback:
                feedback.setProgress(100)
                feedback.pushInfo("ISEA4T Compact completed.")

            return mem_layer


##########################
# ISEA3H
# ########################
def isea3hcompact(
    isea3h_layer: QgsVectorLayer,
    ISEA3HID_field=None,
    feedback=None,
    depth=-1,
    agg=None,
    numeric_col=None,
    shift_antimeridian=False,
    split_antimeridian=False,
) -> QgsVectorLayer:
    if platform.system() == "Windows":
        if not ISEA3HID_field:
            ISEA3HID_field = "isea3h"
        bags, agg_col = prepare_qgis_compact_bags(
            isea3h_layer, ISEA3HID_field, agg=agg, numeric_col=numeric_col
        )

        fields = QgsFields()
        fields.append(QgsField("isea3h", QVariant.String))
        fields.append(QgsField("resolution", QVariant.Int))
        fields.append(QgsField("center_lat", QVariant.Double))
        fields.append(QgsField("center_lon", QVariant.Double))
        fields.append(QgsField("avg_edge_len", QVariant.Double))
        fields.append(QgsField("cell_area", QVariant.Double))
        fields.append(QgsField("cell_perimeter", QVariant.Double))
        append_compact_agg_field(fields, agg_col, agg)
        mem_layer = QgsVectorLayer("Polygon?crs=EPSG:4326", "isea3h_compacted", "memory")
        mem_provider = mem_layer.dataProvider()
        mem_provider.addAttributes(fields)
        mem_layer.updateFields()

        if bags:
            try:
                isea3h_ids_compact = isea3h_compact(
                    list(bags.keys()), depth=depth, bags=bags, verbose=False
                )
            except BaseException:
                raise QgsProcessingException(
                    "Compact cells failed. Please check your ISEA3H ID field."
                )

            total_cells = len(isea3h_ids_compact)

            for i, isea3h_id_compact in enumerate(isea3h_ids_compact):
                if feedback:
                    feedback.setProgress(int((i / total_cells) * 100))
                    if feedback.isCanceled():
                        return None

                cell_polygon = _geo_with_fix(
                    isea3h2geo,
                    isea3h_id_compact,
                    "isea3h",
                    shift_antimeridian,
                    split_antimeridian,
                )
                cell_resolution = get_isea3h_resolution(isea3h_id_compact)
                num_edges = 6

                center_lat, center_lon, avg_edge_len, cell_area, cell_perimeter = (
                    geodesic_dggs_metrics(cell_polygon, num_edges)
                )

                cell_geom = QgsGeometry.fromWkt(cell_polygon.wkt)
                isea3h_feature = QgsFeature(fields)
                isea3h_feature.setGeometry(cell_geom)

                attributes = {
                    "isea3h": isea3h_id_compact,
                    "resolution": cell_resolution,
                    "center_lat": center_lat,
                    "center_lon": center_lon,
                    "avg_edge_len": avg_edge_len,
                    "cell_area": cell_area,
                    "cell_perimeter": cell_perimeter,
                    agg_col: compact_agg_value(bags, isea3h_id_compact, agg),
                }

                isea3h_feature.setAttributes(
                    [attributes[field.name()] for field in fields]
                )
                mem_provider.addFeatures([isea3h_feature])

            if feedback:
                feedback.setProgress(100)
                feedback.pushInfo("ISEA3H Compact completed.")

            return mem_layer


##########################
# QTM
# ########################
def qtmcompact(
    qtm_layer: QgsVectorLayer,
    QTMID_field=None,
    feedback=None,
    depth=-1,
    agg=None,
    numeric_col=None,
    shift_antimeridian=False,
    split_antimeridian=False,
) -> QgsVectorLayer:
    if not QTMID_field:
        QTMID_field = "qtm"
    bags, agg_col = prepare_qgis_compact_bags(
        qtm_layer, QTMID_field, agg=agg, numeric_col=numeric_col
    )

    fields = QgsFields()
    fields.append(QgsField("qtm", QVariant.String))
    fields.append(QgsField("resolution", QVariant.Int))
    fields.append(QgsField("center_lat", QVariant.Double))
    fields.append(QgsField("center_lon", QVariant.Double))
    fields.append(QgsField("avg_edge_len", QVariant.Double))
    fields.append(QgsField("cell_area", QVariant.Double))
    fields.append(QgsField("cell_perimeter", QVariant.Double))
    append_compact_agg_field(fields, agg_col, agg)
    mem_layer = QgsVectorLayer("Polygon?crs=EPSG:4326", "qtm_compacted", "memory")
    mem_provider = mem_layer.dataProvider()
    mem_provider.addAttributes(fields)
    mem_layer.updateFields()

    if bags:
        try:
            qtm_ids_compact = qtm_compact(
                list(bags.keys()), depth=depth, bags=bags, verbose=False
            )
        except BaseException:
            raise QgsProcessingException(
                "Compact cells failed. Please check your QTM ID field."
            )

        total_cells = len(qtm_ids_compact)

        for i, qtm_id_compact in enumerate(qtm_ids_compact):
            if feedback:
                feedback.setProgress(int((i / total_cells) * 100))
                if feedback.isCanceled():
                    return None
            cell_polygon = qtm2geo(qtm_id_compact)
            resolution = get_qtm_resolution(qtm_id_compact)
            num_edges = 3
            center_lat, center_lon, avg_edge_len, cell_area, cell_perimeter = (
                geodesic_dggs_metrics(cell_polygon, num_edges)
            )

            cell_geom = QgsGeometry.fromWkt(cell_polygon.wkt)
            qtm_feature = QgsFeature(fields)
            qtm_feature.setGeometry(cell_geom)

            attributes = {
                "qtm": qtm_id_compact,
                "resolution": resolution,
                "center_lat": center_lat,
                "center_lon": center_lon,
                "avg_edge_len": avg_edge_len,
                "cell_area": cell_area,
                "cell_perimeter": cell_perimeter,
                agg_col: compact_agg_value(bags, qtm_id_compact, agg),
            }
            qtm_feature.setAttributes([attributes[field.name()] for field in fields])
            mem_provider.addFeatures([qtm_feature])

        if feedback:
            feedback.setProgress(100)
            feedback.pushInfo("QTM Compact completed.")

        return mem_layer


##########################
# OLC
# ########################
def olccompact(
    olc_layer: QgsVectorLayer,
    OLCID_field=None,
    feedback=None,
    depth=-1,
    agg=None,
    numeric_col=None,
    shift_antimeridian=False,
    split_antimeridian=False,
) -> QgsVectorLayer:
    if not OLCID_field:
        OLCID_field = "olc"
    bags, agg_col = prepare_qgis_compact_bags(
        olc_layer, OLCID_field, agg=agg, numeric_col=numeric_col
    )

    fields = QgsFields()
    fields.append(QgsField("olc", QVariant.String))
    fields.append(QgsField("resolution", QVariant.Int))
    fields.append(QgsField("center_lat", QVariant.Double))
    fields.append(QgsField("center_lon", QVariant.Double))
    fields.append(QgsField("cell_width", QVariant.Double))
    fields.append(QgsField("cell_height", QVariant.Double))
    fields.append(QgsField("cell_area", QVariant.Double))
    fields.append(QgsField("cell_perimeter", QVariant.Double))
    append_compact_agg_field(fields, agg_col, agg)
    mem_layer = QgsVectorLayer("Polygon?crs=EPSG:4326", "olc_compacted", "memory")
    mem_provider = mem_layer.dataProvider()
    mem_provider.addAttributes(fields)
    mem_layer.updateFields()

    if bags:
        try:
            olc_ids_compact = olc_compact(
                list(bags.keys()), depth=depth, bags=bags, verbose=False
            )
        except BaseException:
            raise QgsProcessingException(
                "Compact cells failed. Please check your OLC ID field."
            )

        total_cells = len(olc_ids_compact)

        for i, olc_id_compact in enumerate(olc_ids_compact):
            if feedback:
                feedback.setProgress(int((i / total_cells) * 100))
                if feedback.isCanceled():
                    return None
            cell_polygon = olc2geo(olc_id_compact)
            cell_resolution = get_olc_resolution(olc_id_compact)
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
                "olc": olc_id_compact,
                "resolution": cell_resolution,
                "center_lat": center_lat,
                "center_lon": center_lon,
                "cell_width": cell_width,
                "cell_height": cell_height,
                "cell_area": cell_area,
                "cell_perimeter": cell_perimeter,
                agg_col: compact_agg_value(bags, olc_id_compact, agg),
            }
            olc_feature.setAttributes([attributes[field.name()] for field in fields])
            mem_provider.addFeatures([olc_feature])

        if feedback:
            feedback.setProgress(100)
            feedback.pushInfo("OLC Compact completed.")

        return mem_layer


##########################
# Geohash
# ########################
def geohashcompact(
    geohash_layer: QgsVectorLayer,
    GeohashID_field=None,
    feedback=None,
    depth=-1,
    agg=None,
    numeric_col=None,
    shift_antimeridian=False,
    split_antimeridian=False,
) -> QgsVectorLayer:
    if not GeohashID_field:
        GeohashID_field = "geohash"
    bags, agg_col = prepare_qgis_compact_bags(
        geohash_layer, GeohashID_field, agg=agg, numeric_col=numeric_col
    )

    fields = QgsFields()
    fields.append(QgsField("geohash", QVariant.String))
    fields.append(QgsField("resolution", QVariant.Int))
    fields.append(QgsField("center_lat", QVariant.Double))
    fields.append(QgsField("center_lon", QVariant.Double))
    fields.append(QgsField("cell_width", QVariant.Double))
    fields.append(QgsField("cell_height", QVariant.Double))
    fields.append(QgsField("cell_area", QVariant.Double))
    fields.append(QgsField("cell_perimeter", QVariant.Double))
    append_compact_agg_field(fields, agg_col, agg)
    mem_layer = QgsVectorLayer("Polygon?crs=EPSG:4326", "geohash_compacted", "memory")
    mem_provider = mem_layer.dataProvider()
    mem_provider.addAttributes(fields)
    mem_layer.updateFields()

    if bags:
        try:
            geohash_ids_compact = geohash_compact(
                list(bags.keys()), depth=depth, bags=bags, verbose=False
            )
        except BaseException:
            raise QgsProcessingException(
                "Compact cells failed. Please check your geohash ID field."
            )

        total_cells = len(geohash_ids_compact)

        for i, geohash_id_compact in enumerate(geohash_ids_compact):
            if feedback:
                feedback.setProgress(int((i / total_cells) * 100))
                if feedback.isCanceled():
                    return None
            cell_polygon = geohash2geo(geohash_id_compact)
            resolution = get_geohash_resolution(geohash_id_compact)
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
                "geohash": geohash_id_compact,
                "resolution": resolution,
                "center_lat": center_lat,
                "center_lon": center_lon,
                "cell_width": cell_width,
                "cell_height": cell_height,
                "cell_area": cell_area,
                "cell_perimeter": cell_perimeter,
                agg_col: compact_agg_value(bags, geohash_id_compact, agg),
            }
            geohash_feature.setAttributes(
                [attributes[field.name()] for field in fields]
            )
            mem_provider.addFeatures([geohash_feature])

        if feedback:
            feedback.setProgress(100)
            feedback.pushInfo("geohash Compact completed.")

        return mem_layer


##########################
# Tilecode
# ########################
def tilecodecompact(
    tilecode_layer: QgsVectorLayer,
    TilecodeID_field=None,
    feedback=None,
    depth=-1,
    agg=None,
    numeric_col=None,
    shift_antimeridian=False,
    split_antimeridian=False,
) -> QgsVectorLayer:
    if not TilecodeID_field:
        TilecodeID_field = "tilecode"
    bags, agg_col = prepare_qgis_compact_bags(
        tilecode_layer, TilecodeID_field, agg=agg, numeric_col=numeric_col
    )

    fields = QgsFields()
    fields.append(QgsField("tilecode", QVariant.String))
    fields.append(QgsField("resolution", QVariant.Int))
    fields.append(QgsField("center_lat", QVariant.Double))
    fields.append(QgsField("center_lon", QVariant.Double))
    fields.append(QgsField("cell_width", QVariant.Double))
    fields.append(QgsField("cell_height", QVariant.Double))
    fields.append(QgsField("cell_area", QVariant.Double))
    fields.append(QgsField("cell_perimeter", QVariant.Double))
    append_compact_agg_field(fields, agg_col, agg)
    mem_layer = QgsVectorLayer("Polygon?crs=EPSG:4326", "tilecode_compacted", "memory")
    mem_provider = mem_layer.dataProvider()
    mem_provider.addAttributes(fields)
    mem_layer.updateFields()

    if bags:
        try:
            tilecode_ids_compact = tilecode_compact(
                list(bags.keys()), depth=depth, bags=bags, verbose=False
            )
        except BaseException:
            raise QgsProcessingException(
                "Compact cells failed. Please check your tilecode ID field."
            )

        total_cells = len(tilecode_ids_compact)

        for i, tilecode_id_compact in enumerate(tilecode_ids_compact):
            if feedback:
                feedback.setProgress(int((i / total_cells) * 100))
                if feedback.isCanceled():
                    return None
            cell_polygon = tilecode2geo(tilecode_id_compact)
            resolution = tilecode_resolution(tilecode_id_compact)
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
                "tilecode": tilecode_id_compact,
                "resolution": resolution,
                "center_lat": center_lat,
                "center_lon": center_lon,
                "cell_width": cell_width,
                "cell_height": cell_height,
                "cell_area": cell_area,
                "cell_perimeter": cell_perimeter,
                agg_col: compact_agg_value(bags, tilecode_id_compact, agg),
            }
            tilecode_feature.setAttributes(
                [attributes[field.name()] for field in fields]
            )
            mem_provider.addFeatures([tilecode_feature])

        if feedback:
            feedback.setProgress(100)
            feedback.pushInfo("Tilecode Compact completed.")

        return mem_layer


##########################
# Quadkey
# ########################
def quadkeycompact(
    quadkey_layer: QgsVectorLayer,
    QuadkeyID_field=None,
    feedback=None,
    depth=-1,
    agg=None,
    numeric_col=None,
    shift_antimeridian=False,
    split_antimeridian=False,
) -> QgsVectorLayer:
    if not QuadkeyID_field:
        QuadkeyID_field = "quadkey"
    bags, agg_col = prepare_qgis_compact_bags(
        quadkey_layer, QuadkeyID_field, agg=agg, numeric_col=numeric_col
    )

    fields = QgsFields()
    fields.append(QgsField("quadkey", QVariant.String))
    fields.append(QgsField("resolution", QVariant.Int))
    fields.append(QgsField("center_lat", QVariant.Double))
    fields.append(QgsField("center_lon", QVariant.Double))
    fields.append(QgsField("cell_width", QVariant.Double))
    fields.append(QgsField("cell_height", QVariant.Double))
    fields.append(QgsField("cell_area", QVariant.Double))
    fields.append(QgsField("cell_perimeter", QVariant.Double))
    append_compact_agg_field(fields, agg_col, agg)
    mem_layer = QgsVectorLayer("Polygon?crs=EPSG:4326", "quadkey_compacted", "memory")
    mem_provider = mem_layer.dataProvider()
    mem_provider.addAttributes(fields)
    mem_layer.updateFields()

    if bags:
        try:
            quadkey_ids_compact = quadkey_compact(
                list(bags.keys()), depth=depth, bags=bags, verbose=False
            )
        except BaseException:
            raise QgsProcessingException(
                "Compact cells failed. Please check your Quadkey ID field."
            )

        total_cells = len(quadkey_ids_compact)

        for i, quadkey_id_compact in enumerate(quadkey_ids_compact):
            if feedback:
                feedback.setProgress(int((i / total_cells) * 100))
                if feedback.isCanceled():
                    return None
            cell_polygon = quadkey2geo(quadkey_id_compact)
            resolution = quadkey_resolution(quadkey_id_compact)
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
                "quadkey": quadkey_id_compact,
                "resolution": resolution,
                "center_lat": center_lat,
                "center_lon": center_lon,
                "cell_width": cell_width,
                "cell_height": cell_height,
                "cell_area": cell_area,
                "cell_perimeter": cell_perimeter,
                agg_col: compact_agg_value(bags, quadkey_id_compact, agg),
            }
            quadkey_feature.setAttributes(
                [attributes[field.name()] for field in fields]
            )
            mem_provider.addFeatures([quadkey_feature])

        if feedback:
            feedback.setProgress(100)
            feedback.pushInfo("Quadkey Compact completed.")

        return mem_layer


##########################
# DGGAL
# ########################
def dggalcompact(
    dggal_layer: QgsVectorLayer,
    DGGALID_field=None,
    feedback=None,
    dggal_type=None,
    depth=-1,
    agg=None,
    numeric_col=None,
    shift_antimeridian=False,
    split_antimeridian=False,
) -> QgsVectorLayer:
    if not DGGALID_field:
        DGGALID_field = f"dggal_{dggal_type}"
    bags, agg_col = prepare_qgis_compact_bags(
        dggal_layer, DGGALID_field, agg=agg, numeric_col=numeric_col
    )

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
    append_compact_agg_field(fields, agg_col, agg)
    layer_name = f"dggal_{dggal_type}_compacted" if dggal_type else "dggal_compacted"
    mem_layer = QgsVectorLayer("Polygon?crs=EPSG:4326", layer_name, "memory")
    mem_provider = mem_layer.dataProvider()
    mem_provider.addAttributes(fields)
    mem_layer.updateFields()

    if bags:
        try:
            dggal_ids_compact = dggal_compact(
                dggal_type, list(bags.keys()), depth=depth, bags=bags, verbose=False
            )
        except Exception as e:
            raise QgsProcessingException(
                f"Compact cells failed. Please check your DGGAL ID field. Error: {str(e)}"
            )

        total_cells = len(dggal_ids_compact)

        for i, dggal_id_compact in enumerate(dggal_ids_compact):
            if feedback:
                feedback.setProgress(int((i / total_cells) * 100))
                if feedback.isCanceled():
                    return None
            try:
                cell_polygon = dggal2geo(
                    dggal_type,
                    dggal_id_compact,
                    split_antimeridian=_use_split_antimeridian(
                        shift_antimeridian, split_antimeridian
                    ),
                )

                # Get resolution and edge count from DGGAL
                try:
                    dggs_class_name = DGGAL_TYPES[dggal_type]["class_name"]
                    dggrs = getattr(dggal, dggs_class_name)()
                    zone = dggrs.getZoneFromTextID(dggal_id_compact)
                    resolution = dggrs.getZoneLevel(zone)
                    num_edges = dggrs.countZoneEdges(zone)
                except BaseException:
                    # Fallback values if we can't get them from DGGAL
                    resolution = 0
                    num_edges = 6  # Default for hexagonal cells

                center_lat, center_lon, avg_edge_len, cell_area, cell_perimeter = (
                    geodesic_dggs_metrics(cell_polygon, num_edges)
                )
            except Exception as e:
                if feedback:
                    feedback.pushInfo(
                        f"Warning: Could not process DGGAL ID {dggal_id_compact}: {str(e)}"
                    )
                continue

            cell_geom = QgsGeometry.fromWkt(cell_polygon.wkt)
            dggal_feature = QgsFeature(fields)
            dggal_feature.setGeometry(cell_geom)

            attributes = {
                field_name: dggal_id_compact,
                "resolution": resolution,
                "center_lat": center_lat,
                "center_lon": center_lon,
                "avg_edge_len": avg_edge_len,
                "cell_area": cell_area,
                "cell_perimeter": cell_perimeter,
                agg_col: compact_agg_value(bags, dggal_id_compact, agg),
            }
            dggal_feature.setAttributes([attributes[field.name()] for field in fields])
            mem_provider.addFeatures([dggal_feature])

        if feedback:
            feedback.setProgress(100)
            feedback.pushInfo(f"DGGAL {dggal_type.upper()} Compact completed.")

        return mem_layer


##########################
# DIGIPIN
# ########################
def digipincompact(
    digipin_layer: QgsVectorLayer,
    DIGIPINID_field=None,
    feedback=None,
    depth=-1,
    agg=None,
    numeric_col=None,
    shift_antimeridian=False,
    split_antimeridian=False,
) -> QgsVectorLayer:
    if not DIGIPINID_field:
        DIGIPINID_field = "digipin"
    bags, agg_col = prepare_qgis_compact_bags(
        digipin_layer, DIGIPINID_field, agg=agg, numeric_col=numeric_col
    )

    fields = QgsFields()
    fields.append(QgsField("digipin", QVariant.String))
    fields.append(QgsField("resolution", QVariant.Int))
    fields.append(QgsField("center_lat", QVariant.Double))
    fields.append(QgsField("center_lon", QVariant.Double))
    fields.append(QgsField("cell_width", QVariant.Double))
    fields.append(QgsField("cell_height", QVariant.Double))
    fields.append(QgsField("cell_area", QVariant.Double))
    fields.append(QgsField("cell_perimeter", QVariant.Double))
    append_compact_agg_field(fields, agg_col, agg)
    mem_layer = QgsVectorLayer("Polygon?crs=EPSG:4326", "digipin_compacted", "memory")
    mem_provider = mem_layer.dataProvider()
    mem_provider.addAttributes(fields)
    mem_layer.updateFields()

    if bags:
        try:
            digipin_ids_compact = digipin_compact(
                list(bags.keys()), depth=depth, bags=bags, verbose=False
            )
        except BaseException:
            raise QgsProcessingException(
                "Compact cells failed. Please check your DIGIPIN ID field."
            )

        total_cells = len(digipin_ids_compact)

        for i, digipin_id_compact in enumerate(digipin_ids_compact):
            if feedback:
                feedback.setProgress(int((i / total_cells) * 100))
                if feedback.isCanceled():
                    return None
            try:
                cell_polygon = digipin2geo(digipin_id_compact)
                clean_id = digipin_id_compact.replace("-", "")
                resolution = len(clean_id)
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
                    "digipin": digipin_id_compact,
                    "resolution": resolution,
                    "center_lat": center_lat,
                    "center_lon": center_lon,
                    "cell_width": cell_width,
                    "cell_height": cell_height,
                    "cell_area": cell_area,
                    "cell_perimeter": cell_perimeter,
                    agg_col: compact_agg_value(bags, digipin_id_compact, agg),
                }
                digipin_feature.setAttributes(
                    [attributes[field.name()] for field in fields]
                )
                mem_provider.addFeatures([digipin_feature])
            except Exception as e:
                if feedback:
                    feedback.pushInfo(
                        f"Warning: Could not process DIGIPIN ID {digipin_id_compact}: {str(e)}"
                    )
                continue

        if feedback:
            feedback.setProgress(100)
            feedback.pushInfo("DIGIPIN Compact completed.")

        return mem_layer
