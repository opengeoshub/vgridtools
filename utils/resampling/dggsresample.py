from vgrid.dggs import s2, olc, mercantile
from ...utils.resampling import dggsgrid

import h3
import a5
import re
import dggal
from vgrid.stats.s2stats import s2_metrics
from vgrid.stats.dggalstats import dggal_metrics
from vgrid.utils.constants import DGGAL_TYPES
from vgrid.utils.io import validate_dggal_type
from vgrid.stats.a5stats import a5_metrics
from vgrid.stats.rhealpixstats import rhealpix_metrics
from vgrid.stats.isea4tstats import isea4t_metrics
from vgrid.stats.qtmstats import qtm_metrics
from vgrid.stats.olcstats import olc_metrics
from vgrid.stats.geohashstats import geohash_metrics
from vgrid.stats.tilecodestats import tilecode_metrics
from vgrid.stats.quadkeystats import quadkey_metrics
from shapely.wkt import loads as load_wkt

from numbers import Number
from vgrid.dggs.rhealpixdggs.dggs import RHEALPixDGGS
from vgrid.dggs.rhealpixdggs.ellipsoids import WGS84_ELLIPSOID
from pyproj import Geod
import platform

if platform.system() == "Windows":
    from vgrid.dggs.eaggr.eaggr import Eaggr
    from vgrid.dggs.eaggr.enums.model import Model

    isea4t_dggs = Eaggr(Model.ISEA4T)
    isea3h_dggs = Eaggr(Model.ISEA3H)

from qgis.core import (
    QgsFeature,
    QgsField,
    QgsFields,
    QgsGeometry,
    QgsSpatialIndex,
    QgsVectorLayer,
)
from qgis.PyQt.QtCore import QVariant


geod = Geod(ellps="WGS84")
E = WGS84_ELLIPSOID


def _dggal_short_type(dggs_key):
    """Map ``dggal_gnosis`` / bare ``gnosis`` to keys in ``DGGAL_TYPES``."""
    k = dggs_key.strip().lower()
    if k.startswith("dggal_"):
        short = k[len("dggal_") :]
        return short if short in DGGAL_TYPES else None
    if k in DGGAL_TYPES and k != "rhealpix":
        return k
    return None


def get_nearest_resolution(
    qgs_features, from_dggs, to_dggs, from_field=None, feedback=None
):
    if not from_field:
        from_field = from_dggs

    try:
        for feature in (
            qgs_features.getFeatures()
        ):  # Use getFeatures() to iterate through the features
            from_dggs_id = feature[from_field]
            break
        else:
            raise ValueError("No features provided.")
    except Exception:
        if feedback:
            feedback.reportError(f"No valid DGGS IDs found in <{from_field}> field.")
        return

    try:
        if from_dggs == "h3":
            from_resolution = h3.get_resolution(from_dggs_id)
            from_area = h3.average_hexagon_area(from_resolution, unit="m^2")

        elif from_dggs == "s2":
            s2_id = s2.CellId.from_token(from_dggs_id)
            from_resolution = s2_id.level()
            _, _, from_area, _ = s2_metrics(from_resolution)

        elif from_dggs == "a5":
            from_resolution = a5.get_resolution(a5.hex_to_u64(from_dggs_id))
            _, _, from_area, _ = a5_metrics(from_resolution)

        elif from_dggs == "rhealpix":
            rhealpix_uids = (from_dggs_id[0],) + tuple(map(int, from_dggs_id[1:]))
            rhealpix_dggs = RHEALPixDGGS(
                ellipsoid=E, north_square=1, south_square=3, N_side=3
            )
            rhealpix_cell = rhealpix_dggs.cell(rhealpix_uids)
            from_resolution = rhealpix_cell.resolution
            _, _, from_area, _ = rhealpix_metrics(from_resolution)

        elif from_dggs == "isea4t":
            if platform.system() == "Windows":
                from_resolution = len(from_dggs_id) - 2
                _, _, from_area, _ = isea4t_metrics(from_resolution)

        elif from_dggs == "qtm":
            from_resolution = len(from_dggs_id)
            _, _, from_area, _ = qtm_metrics(from_resolution)

        elif from_dggs == "olc":
            coord = olc.decode(from_dggs_id)
            from_resolution = coord.codeLength
            _, _, from_area, _ = olc_metrics(from_resolution)

        elif from_dggs == "geohash":
            from_resolution = len(from_dggs_id)
            _, _, from_area, _ = geohash_metrics(from_resolution)

        elif from_dggs == "tilecode":
            match = re.match(r"z(\d+)x(\d+)y(\d+)", from_dggs_id)
            from_resolution = int(match.group(1))
            _, _, from_area, _ = tilecode_metrics(from_resolution)

        elif from_dggs == "quadkey":
            tile = mercantile.quadkey_to_tile(from_dggs_id)
            from_resolution = tile.z
            _, _, from_area, _ = quadkey_metrics(from_resolution)

        elif (dt := _dggal_short_type(from_dggs)) is not None:
            dt = validate_dggal_type(dt)
            cls_name = DGGAL_TYPES[dt]["class_name"]
            dggrs = getattr(dggal, cls_name)()
            zone = dggrs.getZoneFromTextID(str(from_dggs_id))
            from_resolution = int(dggrs.getZoneLevel(zone))
            _, _, from_area, _ = dggal_metrics(dt, from_resolution)

    except Exception as e:
        if feedback:
            feedback.reportError(f"Failed to calculate area from {from_dggs}: {str(e)}")
        return

    nearest_resolution = None
    min_diff = float("inf")

    try:
        if to_dggs == "h3":
            for res in range(16):
                avg_area = h3.average_hexagon_area(res, unit="m^2")
                diff = abs(avg_area - from_area)
                if diff < min_diff:
                    min_diff = diff
                    nearest_resolution = res

        elif to_dggs == "s2":
            for res in range(31):
                _, _, avg_area, _ = s2_metrics(res)
                diff = abs(avg_area - from_area)
                if diff < min_diff:
                    min_diff = diff
                    nearest_resolution = res

        elif to_dggs == "a5":
            for res in range(30):
                _, _, avg_area, _ = a5_metrics(res)
                diff = abs(avg_area - from_area)
                if diff < min_diff:
                    min_diff = diff
                    nearest_resolution = res

        elif to_dggs == "rhealpix":
            for res in range(16):
                _, _, avg_area, _ = rhealpix_metrics(res)
                diff = abs(avg_area - from_area)
                if diff < min_diff:
                    min_diff = diff
                    nearest_resolution = res

        elif to_dggs == "isea4t":
            if platform.system() == "Windows":
                for res in range(26):
                    _, _, avg_area, _ = isea4t_metrics(res)
                    diff = abs(avg_area - from_area)
                    if diff < min_diff:
                        min_diff = diff
                        nearest_resolution = res

        elif to_dggs == "qtm":
            for res in range(1, 25):
                _, _, avg_area, _ = qtm_metrics(res)
                diff = abs(avg_area - from_area)
                if diff < min_diff:
                    min_diff = diff
                    nearest_resolution = res

        elif to_dggs == "olc":
            for res in [2, 4, 6, 8, 10, 11, 12, 13, 14, 15]:
                _, _, avg_area, _ = olc_metrics(res)
                diff = abs(avg_area - from_area)
                if diff < min_diff:
                    min_diff = diff
                    nearest_resolution = res

        elif to_dggs == "geohash":
            for res in range(1, 11):
                _, _, avg_area, _ = geohash_metrics(res)
                diff = abs(avg_area - from_area)
                if diff < min_diff:
                    min_diff = diff
                    nearest_resolution = res

        elif to_dggs == "tilecode":
            for res in range(30):
                _, _, avg_area, _ = tilecode_metrics(res)
                diff = abs(avg_area - from_area)
                if diff < min_diff:
                    min_diff = diff
                    nearest_resolution = res

        elif to_dggs == "quadkey":
            for res in range(30):
                _, _, avg_area, _ = quadkey_metrics(res)
                diff = abs(avg_area - from_area)
                if diff < min_diff:
                    min_diff = diff
                    nearest_resolution = res

        elif (dt := _dggal_short_type(to_dggs)) is not None:
            dt = validate_dggal_type(dt)
            lo = int(DGGAL_TYPES[dt]["min_res"])
            hi = int(DGGAL_TYPES[dt]["max_res"])
            for res in range(lo, hi + 1):
                _, _, avg_area, _ = dggal_metrics(dt, res)
                diff = abs(avg_area - from_area)
                if diff < min_diff:
                    min_diff = diff
                    nearest_resolution = res

    except Exception as e:
        if feedback:
            feedback.reportError(
                f"Failed to calculate nearest resolution for {to_dggs}: {str(e)}"
            )
        return

    if feedback:
        feedback.pushInfo(f"Nearest {to_dggs} resolution: {nearest_resolution}")
    return nearest_resolution


def generate_grid(
    qgs_features,
    to_dggs,
    resolution,
    feedback=None,
    shift_antimeridian=False,
    split_antimeridian=False,
):
    antimeridian_kw = {
        "shift_antimeridian": shift_antimeridian,
        "split_antimeridian": split_antimeridian,
    }
    dggs_grid = {}
    if to_dggs == "h3":
        dggs_grid = dggsgrid.generate_h3_grid(
            resolution, qgs_features, feedback, **antimeridian_kw
        )
    elif to_dggs == "s2":
        dggs_grid = dggsgrid.generate_s2_grid(
            resolution, qgs_features, feedback, **antimeridian_kw
        )
    elif to_dggs == "a5":
        dggs_grid = dggsgrid.generate_a5_grid(
            resolution, qgs_features, feedback, **antimeridian_kw
        )
    elif to_dggs == "rhealpix":
        dggs_grid = dggsgrid.generate_rhealpix_grid(
            resolution, qgs_features, feedback, **antimeridian_kw
        )
    elif to_dggs == "isea4t":
        if platform.system() == "Windows":
            dggs_grid = dggsgrid.generate_isea4t_grid(
                resolution, qgs_features, feedback, **antimeridian_kw
            )
    elif to_dggs == "qtm":
        dggs_grid = dggsgrid.generate_qtm_grid(resolution, qgs_features, feedback)
    elif to_dggs == "olc":
        dggs_grid = dggsgrid.generate_olc_grid(resolution, qgs_features, feedback)
    elif to_dggs == "geohash":
        dggs_grid = dggsgrid.generate_geohash_grid(resolution, qgs_features, feedback)
    elif to_dggs == "tilecode":
        dggs_grid = dggsgrid.generate_tilecode_grid(resolution, qgs_features, feedback)
    elif to_dggs == "quadkey":
        dggs_grid = dggsgrid.generate_quadkey_grid(resolution, qgs_features, feedback)
    elif (dt := _dggal_short_type(to_dggs)) is not None:
        dt = validate_dggal_type(dt)
        dggs_grid = dggsgrid.generate_dggal_grid(
            dt, resolution, qgs_features, feedback, **antimeridian_kw
        )
    else:
        raise ValueError(f"Unsupported DGGS type: {to_dggs}")

    return dggs_grid


def _build_source_spatial_index(layer1, resample_field):
    """Build QgsSpatialIndex and fid -> (feature, numeric value) for source layer."""
    index = QgsSpatialIndex()
    source_by_id = {}
    for feature in layer1.getFeatures():
        value = feature[resample_field]
        if not isinstance(value, Number):
            raise TypeError(
                f"Non-numeric value found in <{resample_field}>. "
                "Resampled field calculation failed."
            )
        fid = feature.id()
        if index.addFeature(feature):
            source_by_id[fid] = (feature, float(value))
    return index, source_by_id


def _target_intersects_source(geom, index, source_by_id):
    """True if geometry intersects at least one source feature."""
    if geom is None or geom.isEmpty():
        return False
    for fid in index.intersects(geom.boundingBox()):
        src_feature, _ = source_by_id.get(fid, (None, None))
        if src_feature is None:
            continue
        if geom.intersects(src_feature.geometry()):
            return True
    return False


def _resampling_area_weighted(layer1, layer2, resample_field, feedback=None):
    try:
        source_index, source_by_id = _build_source_spatial_index(layer1, resample_field)
    except TypeError as e:
        if feedback:
            feedback.reportError(str(e))
        return layer2

    fields = layer2.fields()
    if resample_field not in fields.names():
        fields.append(QgsField(resample_field, QVariant.Double))

    output_layer = QgsVectorLayer(
        "Polygon?crs=" + layer2.crs().authid(), "resampled", "memory"
    )
    output_layer.startEditing()
    output_layer.dataProvider().addAttributes(fields)
    output_layer.updateFields()

    total = layer2.featureCount()
    resampled_count = 0

    if feedback:
        feedback.pushInfo(f"Starting area-weighted resampling on {total} features...")

    for i, feature in enumerate(layer2.getFeatures()):
        if feedback and feedback.isCanceled():
            feedback.reportError("Operation cancelled.")
            return output_layer
        try:
            layer2_geom = dggsgrid._ensure_valid_geometry(
                load_wkt(feature.geometry().asWkt())
            )
            target_area = layer2_geom.area
            if target_area == 0:
                continue
        except Exception:
            continue

        resampled_value = 0.0
        intersected = False
        qgs_target = feature.geometry()

        for fid in source_index.intersects(qgs_target.boundingBox()):
            src_feature, l1_value = source_by_id.get(fid, (None, None))
            if src_feature is None:
                continue
            try:
                l1_geom = dggsgrid._ensure_valid_geometry(
                    load_wkt(src_feature.geometry().asWkt())
                )
                if not layer2_geom.intersects(l1_geom):
                    continue
                intersection = dggsgrid._safe_intersection(layer2_geom, l1_geom)
                if intersection.is_empty:
                    continue
                proportion = intersection.area / target_area
                resampled_value += l1_value * proportion
                intersected = True
            except Exception:
                continue

        if not intersected:
            continue

        new_feat = QgsFeature(fields)
        new_feat.setGeometry(QgsGeometry.fromWkt(layer2_geom.wkt))
        attrs = list(feature.attributes())
        if len(attrs) < fields.count():
            attrs.append(round(resampled_value, 3))
        else:
            idx = fields.indexOf(resample_field)
            attrs[idx] = round(resampled_value, 3)
        new_feat.setAttributes(attrs)

        output_layer.addFeature(new_feat)
        resampled_count += 1

        if feedback:
            feedback.setProgress(int((i + 1) / total * 100))

    output_layer.commitChanges()
    output_layer.updateExtents()

    if feedback:
        feedback.setProgress(100)
        feedback.pushInfo(f"Resampling complete. {resampled_count} features updated.")

    return output_layer


def _resampling_nearest(layer1, layer2, resample_field, feedback=None):
    if layer1.featureCount() == 0:
        if feedback:
            feedback.reportError("No source cells for nearest-neighbour resampling.")
        return layer2

    if resample_field not in layer1.fields().names():
        msg = f"There is no <{resample_field}> field in the input layer1 features."
        if feedback:
            feedback.reportError(msg)
        return layer2

    try:
        source_index, source_by_id = _build_source_spatial_index(layer1, resample_field)
    except TypeError as e:
        if feedback:
            feedback.reportError(str(e))
        return layer2

    if not source_by_id:
        if feedback:
            feedback.reportError("No source cells for nearest-neighbour resampling.")
        return layer2

    fields = QgsFields(layer2.fields())
    if resample_field not in fields.names():
        fields.append(QgsField(resample_field, QVariant.Double))

    output_layer = QgsVectorLayer(
        "Polygon?crs=" + layer2.crs().authid(), "resampled", "memory"
    )
    output_layer.startEditing()
    output_layer.dataProvider().addAttributes(fields)
    output_layer.updateFields()

    resample_idx = fields.indexOf(resample_field)
    total = layer2.featureCount()
    resampled_count = 0

    if feedback:
        feedback.pushInfo(
            f"Starting nearest-neighbour resampling on {total} features..."
        )

    for i, target_feature in enumerate(layer2.getFeatures()):
        if feedback and feedback.isCanceled():
            feedback.reportError("Operation cancelled.")
            return output_layer

        geom = target_feature.geometry()
        if not _target_intersects_source(geom, source_index, source_by_id):
            continue

        centroid = geom.centroid()
        if centroid.isEmpty():
            continue

        nearest_ids = source_index.nearestNeighbor(centroid.asPoint(), 1)
        if not nearest_ids:
            continue

        _, source_value = source_by_id[nearest_ids[0]]
        resampled_value = round(source_value, 3)

        new_feat = QgsFeature(fields)
        new_feat.setGeometry(geom)
        attrs = list(target_feature.attributes())
        if len(attrs) < fields.count():
            attrs.append(resampled_value)
        else:
            attrs[resample_idx] = resampled_value
        new_feat.setAttributes(attrs)
        output_layer.addFeature(new_feat)
        resampled_count += 1

        if feedback:
            feedback.setProgress(int((i + 1) / total * 100))

    output_layer.commitChanges()
    output_layer.updateExtents()

    if feedback:
        feedback.setProgress(100)
        feedback.pushInfo(
            f"Nearest-neighbour resampling complete. "
            f"{resampled_count} features updated."
        )

    return output_layer


def resampling(layer1, layer2, resample_field, method="nearest", feedback=None):
    norm = method.strip().lower().replace("-", "_")
    if norm in ("area_weighted", "area"):
        return _resampling_area_weighted(layer1, layer2, resample_field, feedback)
    if norm in (
        "nearest",
        "nn",
        "nearest_neighbour",
        "nearest_neighbor",
    ):
        return _resampling_nearest(layer1, layer2, resample_field, feedback)

    msg = f"Unsupported resampling method {method!r}; use 'area_weighted' or 'nearest'."
    if feedback:
        feedback.reportError(msg)
    return layer2


def resample(
    dggs_layer,
    dggstype_from,
    dggstype_to,
    resolution,
    dggs_field=None,
    resample_field=None,
    method="nearest",
    feedback=None,
    shift_antimeridian=False,
    split_antimeridian=False,
):
    resampled_features = None
    if resolution == -1:
        resolution = get_nearest_resolution(
            dggs_layer, dggstype_from, dggstype_to, dggs_field
        )
        if feedback:
            feedback.pushInfo(f"Nearest resolution: {resolution}")

    if resolution is None:
        if feedback:
            feedback.reportError("Could not determine output resolution.")
        return None

    resampled_features = generate_grid(
        dggs_layer,
        dggstype_to,
        resolution,
        feedback,
        shift_antimeridian=shift_antimeridian,
        split_antimeridian=split_antimeridian,
    )
    if resample_field and resampled_features is not None:
        resampled_features = resampling(
            dggs_layer,
            resampled_features,
            resample_field,
            method=method,
            feedback=feedback,
        )
    return resampled_features
