"""
QGIS DGGS aggregate: roll cells up to a parent resolution and aggregate values.

Mirrors ``vgrid.conversion.dggsagg``. Incomplete child sets are included;
this is a group-by parent, not compaction. Parent grouping comes from vgrid's
``<dggs>_agg`` functions; geometry, edge counts, and antimeridian handling
follow the DGGS Compact tool.
"""

import importlib
import platform
from collections import defaultdict

import h3
from qgis.PyQt.QtCore import QVariant
from qgis.core import (
    QgsFeature,
    QgsField,
    QgsFields,
    QgsGeometry,
    QgsProcessingException,
    QgsVectorLayer,
)
from vgrid.utils.io import validate_h3_resolution

from ..antimeridian_helper import geo_with_fix, use_split_antimeridian
from ..rhealpix_helper import get_plugin_rhealpix_dggs, resolve_rhealpix_n_side
from .dggscompact import (
    append_compact_agg_field,
    append_compact_metric_fields,
    compact_agg_value,
    geodesic_metric_values,
    graticule_metric_values,
    prepare_qgis_compact_bags,
)

try:
    from vgrid.conversion.dggsagg.h3agg import h3_agg
except ImportError:
    # Older vgrid without dggsagg.

    def h3_agg(h3_ids, resolution, bags=None, verbose=False):
        resolution = validate_h3_resolution(resolution)
        parent_bags = defaultdict(list) if bags is not None else None
        parents = set()
        for h3_id in h3_ids:
            cell_res = h3.get_resolution(h3_id)
            if cell_res < resolution:
                raise ValueError(
                    f"H3 cell {h3_id} is resolution {cell_res}, coarser than "
                    f"parent resolution {resolution}."
                )
            parent = (
                h3_id if cell_res == resolution else h3.cell_to_parent(h3_id, resolution)
            )
            parents.add(parent)
            if parent_bags is not None:
                parent_bags[parent].extend(bags.get(h3_id, []))
        if bags is not None:
            bags.clear()
            bags.update(parent_bags)
        return sorted(parents)


def _vgrid_agg_module(name):
    """Import ``vgrid.conversion.dggsagg.<name>``; the package re-exports
    functions under the module names, so go through importlib."""
    try:
        return importlib.import_module(f"vgrid.conversion.dggsagg.{name}")
    except ImportError as exc:
        raise QgsProcessingException(
            f"This DGGS needs a newer vgrid with vgrid.conversion.dggsagg.{name} "
            f"({exc}). Please update vgrid."
        )


def _run_agg(
    layer,
    id_field,
    id_col,
    label,
    resolution,
    group_fn,
    geo_fn,
    num_edges_fn,
    feedback=None,
    agg="count",
    numeric_col=None,
    cell_metrics=False,
):
    """Group ``layer`` cells by parent and build the output polygon layer.

    ``group_fn(ids, bags)`` returns parent IDs and folds ``bags`` onto them.
    ``geo_fn(parent)`` returns a shapely polygon. ``num_edges_fn(parent)``
    gives the edge count for geodesic metrics; pass None for graticule DGGS.
    """
    if not id_field:
        id_field = id_col
    graticule = num_edges_fn is None
    bags, agg_col = prepare_qgis_compact_bags(
        layer, id_field, agg=agg, numeric_col=numeric_col
    )

    fields = QgsFields()
    fields.append(QgsField(id_col, QVariant.String))
    fields.append(QgsField("resolution", QVariant.Int))
    append_compact_metric_fields(fields, cell_metrics, graticule=graticule)
    append_compact_agg_field(fields, agg_col, agg)

    mem_layer = QgsVectorLayer("Polygon?crs=EPSG:4326", f"{id_col}_agg", "memory")
    mem_provider = mem_layer.dataProvider()
    mem_provider.addAttributes(fields)
    mem_layer.updateFields()

    if not bags:
        if feedback:
            feedback.pushInfo(f"No {label} IDs found in <{id_field}> field.")
        return mem_layer

    try:
        parent_ids = group_fn(list(bags.keys()), bags)
    except QgsProcessingException:
        raise
    except ValueError as exc:
        raise QgsProcessingException(str(exc))
    except Exception as exc:
        raise QgsProcessingException(
            f"Aggregate cells failed. Please check your {label} ID field. ({exc})"
        )

    total_cells = len(parent_ids)
    for i, parent_id in enumerate(parent_ids):
        if feedback:
            feedback.setProgress(int((i / total_cells) * 100))
            if feedback.isCanceled():
                return None
        try:
            cell_polygon = geo_fn(parent_id)
        except Exception as exc:
            if feedback:
                feedback.pushInfo(f"Warning: skipped {label} cell {parent_id}: {exc}")
            continue
        if not cell_polygon or not cell_polygon.is_valid:
            continue

        attributes = {
            id_col: parent_id,
            "resolution": resolution,
            agg_col: compact_agg_value(bags, parent_id, agg),
        }
        if graticule:
            (
                attributes["center_lat"],
                attributes["center_lon"],
                attributes["cell_width"],
                attributes["cell_height"],
                attributes["cell_area"],
                attributes["cell_perimeter"],
            ) = graticule_metric_values(cell_polygon, cell_metrics)
        else:
            num_edges = num_edges_fn(parent_id) if cell_metrics else None
            (
                attributes["center_lat"],
                attributes["center_lon"],
                attributes["avg_edge_len"],
                attributes["cell_area"],
                attributes["cell_perimeter"],
            ) = geodesic_metric_values(cell_polygon, num_edges, cell_metrics)

        feature = QgsFeature(fields)
        feature.setGeometry(QgsGeometry.fromWkt(cell_polygon.wkt))
        feature.setAttributes([attributes[field.name()] for field in fields])
        mem_provider.addFeatures([feature])

    if feedback:
        feedback.setProgress(100)
        feedback.pushInfo(f"{label} Aggregate completed.")
    return mem_layer


##########################
# H3
##########################
def h3agg(
    h3_layer,
    H3ID_field=None,
    resolution=0,
    feedback=None,
    agg="count",
    numeric_col=None,
    shift_antimeridian=False,
    split_antimeridian=False,
    cell_metrics=False,
    **_kwargs,
) -> QgsVectorLayer:
    from vgrid.conversion.dggs2geo.h32geo import h32geo

    resolution = validate_h3_resolution(resolution)
    return _run_agg(
        h3_layer,
        H3ID_field,
        "h3",
        "H3",
        resolution,
        lambda ids, bags: h3_agg(ids, resolution, bags=bags, verbose=False),
        lambda pid: geo_with_fix(
            h32geo, pid, "h3", shift_antimeridian, split_antimeridian
        ),
        lambda pid: 5 if h3.is_pentagon(pid) else 6,
        feedback,
        agg,
        numeric_col,
        cell_metrics,
    )


##########################
# S2
##########################
def s2agg(
    s2_layer,
    S2ID_field=None,
    resolution=0,
    feedback=None,
    agg="count",
    numeric_col=None,
    shift_antimeridian=False,
    split_antimeridian=False,
    cell_metrics=False,
    **_kwargs,
) -> QgsVectorLayer:
    from vgrid.conversion.dggs2geo.s22geo import s22geo

    mod = _vgrid_agg_module("s2agg")
    return _run_agg(
        s2_layer,
        S2ID_field,
        "s2",
        "S2",
        resolution,
        lambda ids, bags: mod.s2_agg(ids, resolution, bags=bags, verbose=False),
        lambda pid: geo_with_fix(
            s22geo, pid, "s2", shift_antimeridian, split_antimeridian
        ),
        lambda pid: 4,
        feedback,
        agg,
        numeric_col,
        cell_metrics,
    )


##########################
# A5
##########################
def a5agg(
    a5_layer,
    A5ID_field=None,
    resolution=0,
    feedback=None,
    agg="count",
    numeric_col=None,
    shift_antimeridian=False,
    split_antimeridian=False,
    cell_metrics=False,
    **_kwargs,
) -> QgsVectorLayer:
    from vgrid.conversion.dggs2geo.a52geo import a52geo

    mod = _vgrid_agg_module("a5agg")
    split = use_split_antimeridian(shift_antimeridian, split_antimeridian)
    return _run_agg(
        a5_layer,
        A5ID_field,
        "a5",
        "A5",
        resolution,
        lambda ids, bags: mod.a5_agg(ids, resolution, bags=bags, verbose=False),
        lambda pid: a52geo(pid, split_antimeridian=split),
        lambda pid: 5,
        feedback,
        agg,
        numeric_col,
        cell_metrics,
    )


##########################
# rHEALPix
##########################
def rhealpixagg(
    rhealpix_layer,
    rHEALPixID_field=None,
    resolution=0,
    feedback=None,
    agg="count",
    numeric_col=None,
    shift_antimeridian=False,
    split_antimeridian=False,
    cell_metrics=False,
    N_side=None,
    **_kwargs,
) -> QgsVectorLayer:
    from vgrid.conversion.dggs2geo.rhealpix2geo import rhealpix2geo
    from vgrid.utils.io import rhealpix_cell_from_id

    mod = _vgrid_agg_module("rhealpixagg")
    N_side = resolve_rhealpix_n_side(N_side)
    rhealpix_dggs = get_plugin_rhealpix_dggs(N_side)

    def num_edges(pid):
        cell = rhealpix_cell_from_id(str(pid), dggs=rhealpix_dggs)
        return 3 if cell.ellipsoidal_shape == "dart" else 4

    return _run_agg(
        rhealpix_layer,
        rHEALPixID_field,
        "rhealpix",
        "rHEALPix",
        resolution,
        lambda ids, bags: mod.rhealpix_agg(
            ids, resolution, bags=bags, verbose=False, N_side=N_side
        ),
        lambda pid: geo_with_fix(
            rhealpix2geo,
            pid,
            "rhealpix",
            shift_antimeridian,
            split_antimeridian,
            N_side=N_side,
        ),
        num_edges,
        feedback,
        agg,
        numeric_col,
        cell_metrics,
    )


##########################
# ISEA4T / ISEA3H (Windows)
##########################
def isea4tagg(
    isea4t_layer,
    ISEA4TID_field=None,
    resolution=0,
    feedback=None,
    agg="count",
    numeric_col=None,
    shift_antimeridian=False,
    split_antimeridian=False,
    cell_metrics=False,
    **_kwargs,
) -> QgsVectorLayer:
    if platform.system() != "Windows":
        raise QgsProcessingException("ISEA4T is only supported on Windows.")
    from vgrid.conversion.dggs2geo.isea4t2geo import isea4t2geo

    mod = _vgrid_agg_module("isea4tagg")
    return _run_agg(
        isea4t_layer,
        ISEA4TID_field,
        "isea4t",
        "ISEA4T",
        resolution,
        lambda ids, bags: mod.isea4t_agg(ids, resolution, bags=bags, verbose=False),
        lambda pid: geo_with_fix(
            isea4t2geo, pid, "isea4t", shift_antimeridian, split_antimeridian
        ),
        lambda pid: 3,
        feedback,
        agg,
        numeric_col,
        cell_metrics,
    )


def isea3hagg(
    isea3h_layer,
    ISEA3HID_field=None,
    resolution=0,
    feedback=None,
    agg="count",
    numeric_col=None,
    shift_antimeridian=False,
    split_antimeridian=False,
    cell_metrics=False,
    **_kwargs,
) -> QgsVectorLayer:
    if platform.system() != "Windows":
        raise QgsProcessingException("ISEA3H is only supported on Windows.")
    from vgrid.conversion.dggs2geo.isea3h2geo import isea3h2geo

    mod = _vgrid_agg_module("isea3hagg")
    return _run_agg(
        isea3h_layer,
        ISEA3HID_field,
        "isea3h",
        "ISEA3H",
        resolution,
        lambda ids, bags: mod.isea3h_agg(ids, resolution, bags=bags, verbose=False),
        lambda pid: geo_with_fix(
            isea3h2geo, pid, "isea3h", shift_antimeridian, split_antimeridian
        ),
        lambda pid: 6,
        feedback,
        agg,
        numeric_col,
        cell_metrics,
    )


##########################
# EASE
##########################
def easeagg(
    ease_layer,
    EASEID_field=None,
    resolution=0,
    feedback=None,
    agg="count",
    numeric_col=None,
    cell_metrics=False,
    **_kwargs,
) -> QgsVectorLayer:
    from vgrid.conversion.dggs2geo.ease2geo import ease2geo

    mod = _vgrid_agg_module("easeagg")
    return _run_agg(
        ease_layer,
        EASEID_field,
        "ease",
        "EASE",
        resolution,
        lambda ids, bags: mod.ease_agg(ids, resolution, bags=bags, verbose=False),
        ease2geo,
        lambda pid: 4,
        feedback,
        agg,
        numeric_col,
        cell_metrics,
    )


##########################
# QTM
##########################
def qtmagg(
    qtm_layer,
    QTMID_field=None,
    resolution=1,
    feedback=None,
    agg="count",
    numeric_col=None,
    cell_metrics=False,
    **_kwargs,
) -> QgsVectorLayer:
    from vgrid.conversion.dggs2geo.qtm2geo import qtm2geo

    mod = _vgrid_agg_module("qtmagg")
    return _run_agg(
        qtm_layer,
        QTMID_field,
        "qtm",
        "QTM",
        resolution,
        lambda ids, bags: mod.qtm_agg(ids, resolution, bags=bags, verbose=False),
        qtm2geo,
        lambda pid: 3,
        feedback,
        agg,
        numeric_col,
        cell_metrics,
    )


##########################
# DGGAL
##########################
def dggalagg(
    dggal_layer,
    DGGALID_field=None,
    resolution=0,
    feedback=None,
    dggal_type=None,
    agg="count",
    numeric_col=None,
    shift_antimeridian=False,
    split_antimeridian=False,
    cell_metrics=False,
    **_kwargs,
) -> QgsVectorLayer:
    from vgrid.conversion.dggs2geo.dggal2geo import dggal2geo

    mod = _vgrid_agg_module("dggalagg")
    dggrs = mod._dggal_dggrs(dggal_type)
    split = use_split_antimeridian(shift_antimeridian, split_antimeridian)
    return _run_agg(
        dggal_layer,
        DGGALID_field,
        f"dggal_{dggal_type}",
        f"DGGAL {dggal_type.upper()}",
        resolution,
        lambda ids, bags: mod.dggal_agg(
            dggal_type, ids, resolution, bags=bags, verbose=False
        ),
        lambda pid: dggal2geo(dggal_type, pid, split_antimeridian=split),
        lambda pid: dggrs.countZoneEdges(dggrs.getZoneFromTextID(pid)),
        feedback,
        agg,
        numeric_col,
        cell_metrics,
    )


##########################
# Graticule DGGS
##########################
def _graticule_agg(module, group_name, geo_import, id_col, label):
    def agg_fn(
        layer,
        id_field=None,
        resolution=0,
        feedback=None,
        agg="count",
        numeric_col=None,
        cell_metrics=False,
        **_kwargs,
    ) -> QgsVectorLayer:
        geo_module, geo_name = geo_import
        geo_fn = getattr(importlib.import_module(geo_module), geo_name)
        group = getattr(_vgrid_agg_module(module), group_name)
        return _run_agg(
            layer,
            id_field,
            id_col,
            label,
            resolution,
            lambda ids, bags: group(ids, resolution, bags=bags, verbose=False),
            geo_fn,
            None,
            feedback,
            agg,
            numeric_col,
            cell_metrics,
        )

    return agg_fn


olcagg = _graticule_agg(
    "olcagg", "olc_agg", ("vgrid.conversion.dggs2geo.olc2geo", "olc2geo"), "olc", "OLC"
)
geohashagg = _graticule_agg(
    "geohashagg",
    "geohash_agg",
    ("vgrid.conversion.dggs2geo.geohash2geo", "geohash2geo"),
    "geohash",
    "Geohash",
)
tilecodeagg = _graticule_agg(
    "tilecodeagg",
    "tilecode_agg",
    ("vgrid.conversion.dggs2geo.tilecode2geo", "tilecode2geo"),
    "tilecode",
    "Tilecode",
)
quadkeyagg = _graticule_agg(
    "quadkeyagg",
    "quadkey_agg",
    ("vgrid.conversion.dggs2geo.quadkey2geo", "quadkey2geo"),
    "quadkey",
    "Quadkey",
)
digipinagg = _graticule_agg(
    "digipinagg",
    "digipin_agg",
    ("vgrid.conversion.dggs2geo.digipin2geo", "digipin2geo"),
    "digipin",
    "DIGIPIN",
)
