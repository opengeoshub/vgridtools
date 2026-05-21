"""QGIS-native helpers for raster-to-DGGS (binning / nearest_neighbour), aligned with vgrid."""

from __future__ import annotations

import math

import geopandas as gpd
from qgis.core import (
    QgsFeature,
    QgsFields,
    QgsField,
    QgsGeometry,
    QgsPointXY,
    QgsVectorLayer,
)
from qgis.PyQt.QtCore import QVariant
from shapely.geometry import Point
from shapely.wkt import loads as load_wkt

from vgrid.utils.geometry import _metric_crs
from vgrid.utils.io import (
    finalize_dggs_band_values,
    init_dggs_band_accumulator,
    normalize_raster2dggs_method,
    update_dggs_band_accumulator,
    validate_raster_stats_option,
)


def normalize_method(method: str) -> str:
    return normalize_raster2dggs_method(method)


def footprint_vector_layer(raster_layer) -> QgsVectorLayer:
    """Single-polygon footprint of the raster extent (for bbox-scoped grid generation)."""
    ext = raster_layer.extent()
    crs_auth = raster_layer.crs().authid()
    layer = QgsVectorLayer(f"Polygon?crs={crs_auth}", "footprint", "memory")
    provider = layer.dataProvider()
    feat = QgsFeature()
    feat.setGeometry(QgsGeometry.fromRect(ext))
    provider.addFeatures([feat])
    layer.updateExtents()
    return layer


def qgs_vector_layer_to_gdf(layer: QgsVectorLayer) -> gpd.GeoDataFrame:
    rows = []
    for feat in layer.getFeatures():
        row = {f.name(): feat[f.name()] for f in layer.fields()}
        row["geometry"] = load_wkt(feat.geometry().asWkt())
        rows.append(row)
    crs = layer.crs().authid() if layer.crs().isValid() else "EPSG:4326"
    return gpd.GeoDataFrame(rows, geometry="geometry", crs=crs)


def gdf_to_qgs_vector_layer(
    gdf: gpd.GeoDataFrame, layer_name: str = "Raster2DGGS"
) -> QgsVectorLayer:
    if gdf is None or gdf.empty:
        raise ValueError("No DGGS cells were produced from the raster.")

    crs_auth = gdf.crs.to_string() if gdf.crs is not None else "EPSG:4326"
    fields = QgsFields()
    attr_cols = [c for c in gdf.columns if c != "geometry"]
    for col in attr_cols:
        series = gdf[col].dropna()
        if len(series) and isinstance(series.iloc[0], str):
            fields.append(QgsField(col, QVariant.String))
        elif len(series) and isinstance(series.iloc[0], int):
            fields.append(QgsField(col, QVariant.Int))
        else:
            fields.append(QgsField(col, QVariant.Double))

    layer = QgsVectorLayer(f"Polygon?crs={crs_auth}", layer_name, "memory")
    provider = layer.dataProvider()
    provider.addAttributes(fields)
    layer.updateFields()

    features = []
    for _, row in gdf.iterrows():
        geom = row.geometry
        if geom is None or geom.is_empty:
            continue
        feat = QgsFeature(fields)
        feat.setGeometry(QgsGeometry.fromWkt(geom.wkt))
        feat.setAttributes([row[c] for c in attr_cols])
        features.append(feat)
    provider.addFeatures(features)
    layer.updateExtents()
    return layer


def accumulate_qgs_raster_pixels(raster_layer, cell_id_fn, stats, feedback=None):
    """
    Stream raster pixels and aggregate values per DGGS cell (vgrid ``accumulate_raster_pixels``).

    Expects a geographic CRS on ``raster_layer`` (EPSG:4326; enforced by processing).
    """
    if not raster_layer.isValid():
        raise ValueError("Invalid raster layer.")

    provider = raster_layer.dataProvider()
    extent = raster_layer.extent()
    width, height = raster_layer.width(), raster_layer.height()
    band_count = provider.bandCount()
    if width == 0 or height == 0:
        return {}, band_count

    pixel_size_x = extent.width() / width
    pixel_size_y = extent.height() / height
    acc = {}

    for row in range(height):
        if feedback and feedback.isCanceled():
            return None, band_count
        for col in range(width):
            lon = extent.xMinimum() + (col + 0.5) * pixel_size_x
            lat = extent.yMaximum() - (row + 0.5) * pixel_size_y
            point = QgsPointXY(lon, lat)

            values = []
            has_valid = False
            for b in range(band_count):
                val, ok = provider.sample(point, b + 1)
                if (
                    ok
                    and val is not None
                    and not (isinstance(val, float) and math.isnan(val))
                ):
                    values.append(float(val))
                    has_valid = True
                else:
                    values.append(None)
            if not has_valid:
                continue

            cell_id = cell_id_fn(lat, lon)
            if cell_id is None:
                continue
            if cell_id not in acc:
                acc[cell_id] = init_dggs_band_accumulator(band_count, stats)
            update_dggs_band_accumulator(acc[cell_id], values, stats)

        if feedback and height:
            feedback.setProgress(int(100 * row / height))

    return acc, band_count


def read_qgs_pixel_centroids(raster_layer, feedback=None):
    """Pixel centers with band values in EPSG:4326 (vgrid ``read_pixel_centroids``)."""
    provider = raster_layer.dataProvider()
    extent = raster_layer.extent()
    width, height = raster_layer.width(), raster_layer.height()
    band_count = provider.bandCount()
    pixel_size_x = extent.width() / width if width else 0
    pixel_size_y = extent.height() / height if height else 0
    records = []

    for row in range(height):
        if feedback and feedback.isCanceled():
            break
        for col in range(width):
            lon = extent.xMinimum() + (col + 0.5) * pixel_size_x
            lat = extent.yMaximum() - (row + 0.5) * pixel_size_y
            point = QgsPointXY(lon, lat)
            rec = {"geometry": Point(lon, lat)}
            valid = False
            for b in range(band_count):
                val, ok = provider.sample(point, b + 1)
                if (
                    ok
                    and val is not None
                    and not (isinstance(val, float) and math.isnan(val))
                ):
                    rec[f"band_{b + 1}"] = float(val)
                    valid = True
                else:
                    rec[f"band_{b + 1}"] = None
            if valid:
                records.append(rec)
        if feedback and height:
            feedback.setProgress(int(100 * row / height))

    return records, band_count


def nearest_neighbour_from_qgs_grid(raster_layer, grid_layer, feedback=None):
    """
    Assign each grid cell the band values of the nearest raster pixel center.

    Same logic as vgrid ``nearest_neighbour_from_grid``.
    """
    if grid_layer is None or grid_layer.featureCount() == 0:
        raise ValueError("No grid cells were generated for the raster extent.")

    pixel_records, band_count = read_qgs_pixel_centroids(raster_layer, feedback)
    if not pixel_records:
        raise ValueError("No valid raster pixels found.")

    pixel_gdf = gpd.GeoDataFrame(pixel_records, crs="EPSG:4326")
    grid_gdf = qgs_vector_layer_to_gdf(grid_layer)

    metric_crs = _metric_crs(grid_gdf)
    if (
        metric_crs is not None
        and grid_gdf.crs is not None
        and grid_gdf.crs.is_geographic
    ):
        grid_metric = grid_gdf.to_crs(metric_crs)
        pixel_metric = pixel_gdf.to_crs(metric_crs)
    else:
        grid_metric = grid_gdf
        pixel_metric = pixel_gdf

    grid_pts = gpd.GeoDataFrame(
        index=grid_metric.index,
        geometry=grid_metric.geometry.centroid,
        crs=grid_metric.crs,
    )

    out = grid_gdf.copy()
    for bi in range(band_count):
        field = f"band_{bi + 1}"
        source_pts = gpd.GeoDataFrame(
            {field: pixel_metric[field].values},
            geometry=pixel_metric.geometry,
            crs=pixel_metric.crs,
        )
        nearest = gpd.sjoin_nearest(grid_pts, source_pts, how="left")
        out[field] = nearest[field].astype(float).round(3)

    if band_count > 0:
        out = out[out["band_1"].notna()].copy()

    return gdf_to_qgs_vector_layer(out, grid_layer.name())


def build_standard_fields(band_count: int, digipin: bool = False) -> QgsFields:
    fields = QgsFields()
    fields.append(QgsField("resolution", QVariant.Int))
    fields.append(QgsField("center_lat", QVariant.Double))
    fields.append(QgsField("center_lon", QVariant.Double))
    if digipin:
        fields.append(QgsField("cell_width", QVariant.Double))
        fields.append(QgsField("cell_height", QVariant.Double))
    else:
        fields.append(QgsField("avg_edge_len", QVariant.Double))
    fields.append(QgsField("cell_area", QVariant.Double))
    fields.append(QgsField("cell_perimeter", QVariant.Double))
    for i in range(band_count):
        fields.append(QgsField(f"band_{i + 1}", QVariant.Double))
    return fields


def build_binning_qgs_layer(
    raster_layer,
    resolution,
    acc,
    band_count,
    stats,
    id_field,
    cell_builder,
    feedback=None,
    layer_name="DGGS",
    digipin_metrics_fn=False,
):
    """
    Build a memory layer from a binning accumulator.

    ``cell_builder(cell_id)`` returns ``(cell_polygon, id_value)`` or ``None`` to skip.
    """
    crs_auth = raster_layer.crs().authid()
    layer = QgsVectorLayer(f"Polygon?crs={crs_auth}", layer_name, "memory")
    provider = layer.dataProvider()

    fields = QgsFields()
    fields.append(QgsField(id_field, QVariant.String))
    for f in build_standard_fields(band_count, digipin=digipin_metrics_fn):
        fields.append(f)
    provider.addAttributes(fields)
    layer.updateFields()

    id_idx = fields.indexOf(id_field)
    res_idx = fields.indexOf("resolution")
    band_start = fields.indexOf("band_1")

    items = list(acc.items())
    total = len(items)
    for i, (cell_id, cell_acc) in enumerate(items):
        if feedback and feedback.isCanceled():
            return None
        built = cell_builder(cell_id, resolution)
        if built is None:
            continue
        cell_polygon, meta = built
        if cell_polygon is None or cell_polygon.is_empty:
            continue

        band_values = finalize_dggs_band_values(cell_acc, stats)
        attrs = [None] * fields.count()
        attrs[id_idx] = meta.get("id", cell_id)
        attrs[res_idx] = resolution
        for key, val in meta.items():
            idx = fields.indexOf(key)
            if idx >= 0:
                attrs[idx] = val
        for bi, bv in enumerate(band_values):
            attrs[band_start + bi] = bv

        feat = QgsFeature(fields)
        feat.setGeometry(QgsGeometry.fromWkt(cell_polygon.wkt))
        feat.setAttributes(attrs)
        provider.addFeature(feat)

        if feedback and total:
            feedback.setProgress(int(100 * i / total))

    layer.updateExtents()
    return layer


def run_raster2(
    raster_layer,
    resolution,
    method,
    stats,
    id_field,
    cell_id_fn,
    grid_generator,
    cell_builder,
    feedback=None,
    layer_name="DGGS",
    digipin_metrics_fn=False,
):
    """Dispatch binning vs nearest for one DGGS type."""
    method = normalize_method(method)
    if method == "binning":
        stats = validate_raster_stats_option(stats)
        if feedback:
            feedback.pushInfo(f"Method: binning ({stats})")
        acc, band_count = accumulate_qgs_raster_pixels(
            raster_layer, cell_id_fn, stats, feedback
        )
        if acc is None:
            return None
        if feedback:
            feedback.setProgress(0)
            feedback.pushInfo(f"Building {len(acc)} cells...")
        return build_binning_qgs_layer(
            raster_layer,
            resolution,
            acc,
            band_count,
            stats,
            id_field,
            cell_builder,
            feedback=feedback,
            layer_name=layer_name,
            digipin_metrics_fn=digipin_metrics_fn,
        )

    if feedback:
        feedback.pushInfo("Method: nearest_neighbour")
    footprint = footprint_vector_layer(raster_layer)
    if feedback:
        feedback.setProgress(0)
        feedback.pushInfo("Generating target DGGS grid...")
    grid_layer = grid_generator(resolution, footprint, feedback)
    if grid_layer is None:
        return None
    return nearest_neighbour_from_qgs_grid(raster_layer, grid_layer, feedback)
