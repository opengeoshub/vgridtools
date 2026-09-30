"""Shared "Compute cell metrics" support for the DGGS Generator tools."""

from qgis.core import QgsFields
from vgrid.utils.geometry import geodesic_dggs_metrics, graticule_dggs_metrics

from .binning.bin_helper import add_cell_metrics_parameter, read_cell_metrics

__all__ = [
    "add_cell_metrics_parameter",
    "read_cell_metrics",
    "generator_output_fields",
    "MetricFilteringSink",
    "geodesic_metric_values",
    "graticule_metric_values",
]

METRIC_FIELD_NAMES = frozenset(
    (
        "center_lat",
        "center_lon",
        "avg_edge_len",
        "cell_width",
        "cell_height",
        "cell_area",
        "cell_perimeter",
    )
)


def generator_output_fields(fields, cell_metrics):
    if cell_metrics:
        return fields
    out = QgsFields()
    for field in fields:
        if field.name() not in METRIC_FIELD_NAMES:
            out.append(field)
    return out


def geodesic_metric_values(cell_polygon, num_edges, cell_metrics):
    if not cell_metrics:
        return (None, None, None, None, None)
    return geodesic_dggs_metrics(cell_polygon, num_edges)


def graticule_metric_values(cell_polygon, cell_metrics):
    if not cell_metrics:
        return (None, None, None, None, None, None)
    return graticule_dggs_metrics(cell_polygon)


class MetricFilteringSink:
    """Drops metric attributes (by position in *full_fields*) before writing."""

    def __init__(self, sink, full_fields, cell_metrics):
        self._sink = sink
        self._keep = (
            None
            if cell_metrics
            else [
                i
                for i, field in enumerate(full_fields)
                if field.name() not in METRIC_FIELD_NAMES
            ]
        )

    def addFeature(self, feature, *args):
        if self._keep is not None:
            attrs = feature.attributes()
            feature.setAttributes([attrs[i] for i in self._keep if i < len(attrs)])
        return self._sink.addFeature(feature, *args)

    def __getattr__(self, name):
        return getattr(self._sink, name)
