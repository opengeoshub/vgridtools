from vgrid.dggs import s2, olc, mercantile
from ...utils.resampling import dggsgrid

import h3
import a5
import re
import dggal
import geopandas as gpd
from pyproj import CRS
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
    QgsGeometry,
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


def generate_grid(qgs_features, to_dggs, resolution, feedback=None):
    dggs_grid = {}
    if to_dggs == "h3":
        dggs_grid = dggsgrid.generate_h3_grid(resolution, qgs_features, feedback)
    elif to_dggs == "s2":
        dggs_grid = dggsgrid.generate_s2_grid(resolution, qgs_features, feedback)
    elif to_dggs == "a5":
        dggs_grid = dggsgrid.generate_a5_grid(resolution, qgs_features, feedback)
    elif to_dggs == "rhealpix":
        dggs_grid = dggsgrid.generate_rhealpix_grid(resolution, qgs_features, feedback)
    elif to_dggs == "isea4t":
        if platform.system() == "Windows":
            dggs_grid = dggsgrid.generate_isea4t_grid(
                resolution, qgs_features, feedback
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
        dggs_grid = dggsgrid.generate_dggal_grid(dt, resolution, qgs_features, feedback)
    else:
        raise ValueError(f"Unsupported DGGS type: {to_dggs}")

    return dggs_grid


def _metric_crs(gdf):
    """Lambert azimuthal equal-area CRS centered on the data extent (metres)."""
    if gdf.crs is None:
        return None
    if not gdf.crs.is_geographic:
        return gdf.crs

    minx, miny, maxx, maxy = gdf.total_bounds
    lon_0 = (minx + maxx) / 2.0
    lat_0 = max(-89.9, min(89.9, (miny + maxy) / 2.0))
    return CRS.from_proj4(
        f"+proj=laea +lat_0={lat_0} +lon_0={lon_0} +datum=WGS84 +units=m +no_defs"
    )


def _qgs_layer_to_gdf(layer, value_field=None):
    rows = []
    for idx, feature in enumerate(layer.getFeatures()):
        row = {"_idx": idx, "geometry": load_wkt(feature.geometry().asWkt())}
        if value_field is not None:
            row[value_field] = feature[value_field]
        rows.append(row)
    crs = layer.crs().authid() if layer.crs().isValid() else "EPSG:4326"
    return gpd.GeoDataFrame(rows, crs=crs)


def _resampling_area_weighted(layer1, layer2, resample_field, feedback=None):
    try:
        layer1_features = []
        for feature in layer1.getFeatures():
            if resample_field not in feature.fields().names():
                raise ValueError(
                    f"There is no <{resample_field}> field in the input layer1 features."
                )
            geom = load_wkt(feature.geometry().asWkt())
            value = feature[resample_field]
            layer1_features.append((geom, value))
    except ValueError as e:
        if feedback:
            feedback.reportError(str(e))
        else:
            print(e)
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

        layer2_geom = load_wkt(feature.geometry().asWkt())
        target_area = layer2_geom.area
        if target_area == 0:
            continue

        resampled_value = 0.0
        intersected = False

        for l1_geom, l1_value in layer1_features:
            if not layer2_geom.intersects(l1_geom):
                continue
            if not isinstance(l1_value, Number):
                msg = (
                    f"Non-numeric value found in <{resample_field}>. "
                    "Resampled field calculation failed."
                )
                if feedback:
                    feedback.reportError(msg)
                return output_layer

            intersection = layer2_geom.intersection(l1_geom)
            if intersection.is_empty:
                continue

            proportion = intersection.area / target_area
            resampled_value += float(l1_value) * proportion
            intersected = True

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

    target_features = list(layer2.getFeatures())
    source_gdf = _qgs_layer_to_gdf(layer1, resample_field)
    target_gdf = _qgs_layer_to_gdf(layer2)

    for val in source_gdf[resample_field]:
        if not isinstance(val, Number):
            msg = (
                f"Non-numeric value found in <{resample_field}>. "
                "Resampled field calculation failed."
            )
            if feedback:
                feedback.reportError(msg)
            return layer2

    hits = gpd.sjoin(
        target_gdf,
        source_gdf[["geometry"]],
        how="inner",
        predicate="intersects",
    )
    fields = layer2.fields()
    if resample_field not in fields.names():
        fields.append(QgsField(resample_field, QVariant.Double))

    output_layer = QgsVectorLayer(
        "Polygon?crs=" + layer2.crs().authid(), "resampled", "memory"
    )
    output_layer.startEditing()
    output_layer.dataProvider().addAttributes(fields)
    output_layer.updateFields()

    if hits.empty:
        output_layer.commitChanges()
        return output_layer

    target_hit = target_gdf.loc[hits.index.unique()].copy()
    metric_crs = _metric_crs(source_gdf)
    if metric_crs is not None and (
        source_gdf.crs is None or not source_gdf.crs.equals(metric_crs)
    ):
        source_metric = source_gdf.to_crs(metric_crs)
        target_metric = target_hit.to_crs(metric_crs)
    else:
        source_metric = source_gdf
        target_metric = target_hit

    source_pts = gpd.GeoDataFrame(
        {resample_field: source_metric[resample_field].values},
        geometry=source_metric.geometry.centroid,
        crs=source_metric.crs,
    )
    target_pts = gpd.GeoDataFrame(
        {"_idx": target_metric["_idx"].values},
        geometry=target_metric.geometry.centroid,
        crs=target_metric.crs,
    )

    nearest = gpd.sjoin_nearest(target_pts, source_pts, how="left")
    out = target_hit.copy()
    out[resample_field] = nearest[resample_field].astype(float).round(3)

    resample_idx = fields.indexOf(resample_field)
    total = len(out)
    for i, (_, row) in enumerate(out.iterrows()):
        if feedback and feedback.isCanceled():
            feedback.reportError("Operation cancelled.")
            return output_layer

        orig_feature = target_features[int(row["_idx"])]
        new_feat = QgsFeature(fields)
        new_feat.setGeometry(QgsGeometry.fromWkt(row.geometry.wkt))
        attrs = list(orig_feature.attributes())
        if len(attrs) < fields.count():
            attrs.append(float(row[resample_field]))
        else:
            attrs[resample_idx] = float(row[resample_field])
        new_feat.setAttributes(attrs)
        output_layer.addFeature(new_feat)

        if feedback:
            feedback.setProgress(int((i + 1) / total * 100))

    output_layer.commitChanges()
    output_layer.updateExtents()

    if feedback:
        feedback.setProgress(100)
        feedback.pushInfo(
            f"Nearest-neighbour resampling complete. "
            f"{output_layer.featureCount()} features updated."
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
):
    resampled_features = None
    if resolution == -1:
        resolution = get_nearest_resolution(
            dggs_layer, dggstype_from, dggstype_to, dggs_field
        )
        if feedback:
            feedback.pushInfo(f"Nearest resolution: {resolution}")
    if resolution:
        resampled_features = generate_grid(
            dggs_layer, dggstype_to, resolution, feedback
        )
        if resample_field:
            resampled_features = resampling(
                dggs_layer,
                resampled_features,
                resample_field,
                method=method,
                feedback=feedback,
            )
    return resampled_features
