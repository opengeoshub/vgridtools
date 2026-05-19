"""QGIS processing helpers for vgrid-style grid binning (bbox grid + spatial join)."""

from __future__ import annotations

import io
import os
import sys
from contextlib import contextmanager

from qgis.core import (
    QgsFeature,
    QgsFeatureSink,
    QgsField,
    QgsFields,
    QgsGeometry,
    QgsWkbTypes,
)
from qgis.PyQt.QtCore import QVariant

from .bin_helper import (
    append_geodesic_metric_fields,
    append_graticule_metric_fields,
    dggrid_num_edges,
    geodesic_cell_props,
    graticule_cell_props,
)

_GEODESIC_METRIC_COLS = (
    "resolution",
    "center_lat",
    "center_lon",
    "avg_edge_len",
    "cell_area",
    "cell_perimeter",
)
_GRATICULE_METRIC_COLS = (
    "resolution",
    "center_lat",
    "center_lon",
    "cell_width",
    "cell_height",
    "cell_area",
    "cell_perimeter",
)

_BIN_STEP_LABELS = (
    "Generating DGGS",
    "Binning points into DGGS",
)


class TwoStepBinProgress:
    """Map processing feedback to two visible binning steps (0–50% and 50–100%)."""

    def __init__(self, feedback):
        self.feedback = feedback

    def begin(self, step_index):
        if not self.feedback:
            return
        label = _BIN_STEP_LABELS[step_index]
        message = f"Step {step_index + 1}/2: {label}..."
        if hasattr(self.feedback, "setProgressText"):
            self.feedback.setProgressText(message)
        self.feedback.pushInfo(message)
        self.set(step_index, 0)

    def set(self, step_index, inner_percent):
        """*inner_percent* is 0–100 within the current step."""
        if not self.feedback:
            return
        inner = max(0.0, min(100.0, float(inner_percent)))
        overall = step_index * 50.0 + inner * 0.5
        self.feedback.setProgress(int(overall))

    def complete(self, step_index):
        self.set(step_index, 100)


@contextmanager
def silence_tqdm_for_qgis():
    """
    Disable vgrid/tqdm progress bars inside QGIS processing.

    QGIS often sets sys.stderr/stdout to None; tqdm then raises AttributeError.
    """
    saved_streams = {}
    for name in ("stderr", "stdout"):
        stream = getattr(sys, name, None)
        saved_streams[name] = stream
        if stream is None:
            setattr(sys, name, io.StringIO())

    env_prev = os.environ.get("TQDM_DISABLE")
    os.environ["TQDM_DISABLE"] = "1"

    tqdm_cls = None
    orig_init = None
    try:
        from tqdm.std import tqdm as tqdm_cls  # type: ignore[import-untyped]

        orig_init = tqdm_cls.__init__

        def _init(self, *args, **kwargs):
            kwargs["disable"] = True
            file_obj = kwargs.get("file")
            if file_obj is None:
                kwargs["file"] = sys.stderr
            return orig_init(self, *args, **kwargs)

        tqdm_cls.__init__ = _init  # type: ignore[method-assign]
        yield
    except ImportError:
        yield
    finally:
        if tqdm_cls is not None and orig_init is not None:
            tqdm_cls.__init__ = orig_init  # type: ignore[method-assign]
        if env_prev is None:
            os.environ.pop("TQDM_DISABLE", None)
        else:
            os.environ["TQDM_DISABLE"] = env_prev
        for name, stream in saved_streams.items():
            setattr(sys, name, stream)


def qgis_feature_source_to_gdf(source, feedback=None):
    """Build a GeoDataFrame from a QGIS feature source (point layer)."""
    import geopandas as gpd
    from shapely import wkt as shapely_wkt

    fields = source.fields()
    records = []
    geometries = []
    for feat in source.getFeatures():
        if feedback and feedback.isCanceled():
            break
        geom = feat.geometry()
        if not geom or geom.isEmpty():
            continue
        geometries.append(shapely_wkt.loads(geom.asWkt()))
        records.append({fields[i].name(): feat[i] for i in range(len(fields))})

    crs = "EPSG:4326"
    src_crs = source.sourceCrs()
    if src_crs.isValid():
        crs = src_crs.authid()

    if not geometries:
        return gpd.GeoDataFrame(crs=crs)

    return gpd.GeoDataFrame(records, geometry=geometries, crs=crs)


def _prepare_points_gdf(points_gdf):
    """Keep point/multipoint geometries only (same as vgrid ``*_bin``)."""
    if points_gdf is None or points_gdf.empty:
        return points_gdf
    points_gdf = points_gdf[
        points_gdf.geometry.geom_type.isin(["Point", "MultiPoint"])
    ].copy()
    if "MultiPoint" in set(points_gdf.geometry.geom_type.unique()):
        points_gdf = points_gdf.explode(index_parts=False, ignore_index=True)
    return points_gdf


def aggregate_points_to_grid(
    points_gdf,
    grid_gdf,
    id_col,
    *,
    resolution,
    stats,
    category,
    numeric_field,
):
    """Spatial join points to grid cells and aggregate statistics."""
    import geopandas as gpd

    from vgrid.utils.io import aggregate_joined

    join_cols = []
    if category and category in points_gdf.columns:
        join_cols.append(category)
    if stats != "count" and numeric_field:
        if numeric_field not in points_gdf.columns:
            raise ValueError(
                f"numeric_field '{numeric_field}' not found in input layer"
            )
        join_cols.append(numeric_field)

    left = points_gdf[[c for c in ["geometry", *join_cols] if c]]
    joined = gpd.sjoin(
        left,
        grid_gdf[[id_col, "geometry"]],
        how="inner",
        predicate="within",
    )
    grouped = aggregate_joined(
        joined, id_col, stats=stats, category=category, numeric_field=numeric_field
    )
    grouped = grouped.reset_index()
    out = grid_gdf.merge(grouped, on=id_col, how="inner")
    if "resolution" not in out.columns:
        out["resolution"] = resolution
    return gpd.GeoDataFrame(out, geometry="geometry", crs=grid_gdf.crs or "EPSG:4326")


def _qvariant_type_for_series(series):
    import pandas as pd

    if pd.api.types.is_integer_dtype(series.dtype):
        return QVariant.Int
    if pd.api.types.is_float_dtype(series.dtype):
        return QVariant.Double
    return QVariant.String


def _python_value(val):
    if val is None:
        return None
    try:
        import pandas as pd

        if pd.isna(val):
            return None
    except Exception:
        pass
    return val


def _metrics_from_row(row, geom, resolution, metric_kind, num_edges_fn, cell_id):
    metric_cols = (
        _GRATICULE_METRIC_COLS if metric_kind == "graticule" else _GEODESIC_METRIC_COLS
    )

    if all(
        col in row.index
        and row[col] is not None
        and _python_value(row[col]) is not None
        for col in metric_cols
    ):
        return {col: _python_value(row[col]) for col in metric_cols}

    if metric_kind == "graticule":
        return graticule_cell_props(geom, resolution)

    num_edges = 4
    if num_edges_fn is not None:
        num_edges = num_edges_fn(cell_id, geom)
    elif hasattr(geom, "exterior"):
        num_edges = dggrid_num_edges(geom)
    return geodesic_cell_props(geom, resolution, num_edges)


def write_vgrid_bin_to_sink(
    result_gdf,
    *,
    algorithm,
    parameters,
    context,
    output_param,
    point_layer,
    id_field,
    resolution,
    metric_kind="geodesic",
    num_edges_fn=None,
    feedback=None,
    progress=None,
):
    """
    Write a vgrid ``*_bin`` GeoDataFrame result to a processing vector sink.

    Returns ``{output_key: dest_id}``.
    """
    metric_cols = (
        _GRATICULE_METRIC_COLS if metric_kind == "graticule" else _GEODESIC_METRIC_COLS
    )
    skip_cols = {"geometry", id_field, *metric_cols}
    stat_cols = [c for c in result_gdf.columns if c not in skip_cols]

    out_fields = QgsFields()
    out_fields.append(QgsField(id_field, QVariant.String))
    if metric_kind == "graticule":
        append_graticule_metric_fields(out_fields)
    else:
        append_geodesic_metric_fields(out_fields)
    for col in stat_cols:
        out_fields.append(QgsField(col, _qvariant_type_for_series(result_gdf[col])))

    sink, dest_id = algorithm.parameterAsSink(
        parameters,
        output_param,
        context,
        out_fields,
        QgsWkbTypes.Polygon,
        point_layer.sourceCrs(),
    )

    total = len(result_gdf)
    written = 0
    for i, (_, row) in enumerate(result_gdf.iterrows()):
        if feedback and feedback.isCanceled():
            break

        geom = row.geometry
        if geom is None or geom.is_empty:
            continue

        cell_id = _python_value(row.get(id_field))
        metrics = _metrics_from_row(
            row, geom, resolution, metric_kind, num_edges_fn, cell_id
        )

        attrs = [str(cell_id) if cell_id is not None else None]
        attrs.extend(_python_value(metrics[col]) for col in metric_cols)

        for col in stat_cols:
            val = _python_value(row.get(col))
            if isinstance(val, float) and val == int(val):
                if _qvariant_type_for_series(result_gdf[col]) == QVariant.Int:
                    val = int(val)
            attrs.append(val)

        out_feature = QgsFeature(out_fields)
        out_feature.setGeometry(QgsGeometry.fromWkt(geom.wkt))
        out_feature.setAttributes(attrs)
        sink.addFeature(out_feature, QgsFeatureSink.FastInsert)
        written += 1

        if progress and total:
            progress.set(1, 90 + int((i + 1) / total * 10))
        elif feedback and total:
            feedback.setProgress(int((i + 1) / total * 100))

    if progress:
        progress.complete(1)
    if feedback:
        feedback.pushInfo(f"Wrote {written} bin polygon(s).")

    return {output_param: dest_id}


def run_vgrid_grid_bin(
    algorithm,
    parameters,
    context,
    feedback,
    *,
    point_layer,
    output_param,
    resolution,
    stats,
    category_field,
    numeric_field,
    grid_generator,
    id_field,
    metric_kind="geodesic",
    num_edges_fn=None,
    grid_kwargs=None,
):
    """
    Run two-phase vgrid-style binning on a QGIS point layer.

    *grid_generator* is called as ``grid_generator(resolution, bbox, **grid_kwargs)``
    and must return a GeoDataFrame of grid cells covering *bbox*.
    """
    progress = TwoStepBinProgress(feedback)
    points_gdf = qgis_feature_source_to_gdf(point_layer, feedback=feedback)
    points_gdf = _prepare_points_gdf(points_gdf)
    if points_gdf.empty:
        if feedback:
            feedback.pushInfo("No point features to bin.")
        empty_fields = QgsFields()
        empty_fields.append(QgsField(id_field, QVariant.String))
        if metric_kind == "graticule":
            append_graticule_metric_fields(empty_fields)
        else:
            append_geodesic_metric_fields(empty_fields)
        sink, dest_id = algorithm.parameterAsSink(
            parameters,
            output_param,
            context,
            empty_fields,
            QgsWkbTypes.Polygon,
            point_layer.sourceCrs(),
        )
        return {output_param: dest_id}

    minx, miny, maxx, maxy = points_gdf.total_bounds
    bbox = (minx, miny, maxx, maxy)
    gkw = dict(grid_kwargs or {})

    progress.begin(0)
    with silence_tqdm_for_qgis():
        grid_gdf = grid_generator(resolution, bbox, **gkw)
    progress.complete(0)

    if grid_gdf is None or grid_gdf.empty:
        if feedback:
            feedback.pushInfo("No grid cells were generated for the point extent.")
        empty_fields = QgsFields()
        empty_fields.append(QgsField(id_field, QVariant.String))
        if metric_kind == "graticule":
            append_graticule_metric_fields(empty_fields)
        else:
            append_geodesic_metric_fields(empty_fields)
        sink, dest_id = algorithm.parameterAsSink(
            parameters,
            output_param,
            context,
            empty_fields,
            QgsWkbTypes.Polygon,
            point_layer.sourceCrs(),
        )
        return {output_param: dest_id}

    progress.begin(1)
    progress.set(1, 10)
    result_gdf = aggregate_points_to_grid(
        points_gdf,
        grid_gdf,
        id_field,
        resolution=resolution,
        stats=stats,
        category=category_field or None,
        numeric_field=numeric_field or None,
    )
    progress.set(1, 85)

    if result_gdf is None or result_gdf.empty:
        if feedback:
            feedback.pushInfo("No grid cells with points were found.")
        empty_fields = QgsFields()
        empty_fields.append(QgsField(id_field, QVariant.String))
        if metric_kind == "graticule":
            append_graticule_metric_fields(empty_fields)
        else:
            append_geodesic_metric_fields(empty_fields)
        sink, dest_id = algorithm.parameterAsSink(
            parameters,
            output_param,
            context,
            empty_fields,
            QgsWkbTypes.Polygon,
            point_layer.sourceCrs(),
        )
        return {output_param: dest_id}

    return write_vgrid_bin_to_sink(
        result_gdf,
        algorithm=algorithm,
        parameters=parameters,
        context=context,
        output_param=output_param,
        point_layer=point_layer,
        id_field=id_field,
        resolution=resolution,
        metric_kind=metric_kind,
        num_edges_fn=num_edges_fn,
        feedback=feedback,
        progress=progress,
    )
