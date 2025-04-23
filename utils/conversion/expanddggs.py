from vgrid.utils import s2, olc, geohash,  mercantile, tilecode
from vgrid.utils import qtm
import h3

from vgrid.utils.rhealpixdggs.dggs import RHEALPixDGGS
from vgrid.utils.rhealpixdggs.ellipsoids import WGS84_ELLIPSOID
import platform

if (platform.system() == 'Windows'):   
    from vgrid.utils.eaggr.enums.shape_string_format import ShapeStringFormat
    from vgrid.utils.eaggr.eaggr import Eaggr
    from vgrid.utils.eaggr.shapes.dggs_cell import DggsCell
    from vgrid.utils.eaggr.enums.model import Model
    from vgrid.generator.isea4tgrid import fix_isea4t_wkt, fix_isea4t_antimeridian_cells


if (platform.system() == 'Linux'):
    from vgrid.utils.dggrid4py import DGGRIDv7, dggs_types
    from vgrid.utils.dggrid4py.dggrid_runner import input_address_types


from vgrid.utils.easedggs.constants import levels_specs
from vgrid.utils.easedggs.dggs.grid_addressing import grid_ids_to_geos

from shapely.wkt import loads
from shapely.geometry import shape, Polygon,mapping

import json, re,os,argparse
from vgrid.generator.h3grid import fix_h3_antimeridian_cells

from vgrid.utils.antimeridian import fix_polygon
from vgrid.generator.settings import graticule_dggs_metrics, geodesic_dggs_metrics

from vgrid.conversion.dggs2geojson import rhealpix_cell_to_polygon
from vgrid.utils.easedggs.dggs.hierarchy import _parent_to_children
from vgrid.utils.easedggs.dggs.grid_addressing import grid_ids_to_geos
from vgrid.generator.geohashgrid import geohash_to_polygon

from pyproj import Geod
geod = Geod(ellps="WGS84")
E = WGS84_ELLIPSOID
from collections import defaultdict

from qgis.core import (
    QgsVectorLayer, QgsFeature, QgsGeometry, QgsField, QgsFields,
    QgsWkbTypes, QgsVectorFileWriter, QgsProject, QgsCoordinateReferenceSystem
)
from PyQt5.QtCore import QVariant
from shapely.geometry import Polygon

def h3expand(h3_layer: QgsVectorLayer, resolution: int, feedback=None) -> QgsVectorLayer:
    fields = QgsFields()
    fields.append(QgsField("h3", QVariant.String))
    fields.append(QgsField("resolution", QVariant.Int))
    fields.append(QgsField("center_lat", QVariant.Double))
    fields.append(QgsField("center_lon", QVariant.Double))
    fields.append(QgsField("avg_edge_len", QVariant.Double))
    fields.append(QgsField("cell_area", QVariant.Double))

    crs = h3_layer.crs().toWkt()
    mem_layer = QgsVectorLayer("Polygon?crs=" + crs, "h3_expanded", "memory")
    mem_provider = mem_layer.dataProvider()
    mem_provider.addAttributes(fields)
    mem_layer.updateFields()

    h3_ids = [
        feature["h3"]
        for feature in h3_layer.getFeatures()
        if feature["h3"]
    ]

    h3_ids_expand = h3.uncompact_cells(h3_ids, resolution)
    total = len(h3_ids_expand)

    for i, h3_id_expand in enumerate(h3_ids_expand):
        if feedback:
            feedback.setProgress(int((i / total) * 100))
            if feedback.isCanceled():
                return None

        cell_boundary = h3.cell_to_boundary(h3_id_expand)
        if cell_boundary:
            filtered_boundary = fix_h3_antimeridian_cells(cell_boundary)
            reversed_boundary = [(lon, lat) for lat, lon in filtered_boundary]
            cell_polygon = Polygon(reversed_boundary)

            if not cell_polygon.is_valid:
                continue
            
            num_edges = 5 if h3.is_pentagon(h3_id_expand) else 6
            center_lat, center_lon, avg_edge_len, cell_area = geodesic_dggs_metrics(cell_polygon, num_edges)
            
            cell_geom = QgsGeometry.fromWkt(cell_polygon.wkt)
            h3_feature = QgsFeature(fields)
            h3_feature.setGeometry(cell_geom)
            
            attributes = {
            "h3": h3_id_expand,
            "resolution": resolution,
            "center_lat": center_lat,
            "center_lon": center_lon,
            "avg_edge_len": avg_edge_len,
            "cell_area": cell_area,
            }
            h3_feature.setAttributes([attributes[field.name()] for field in fields])
            mem_provider.addFeatures([h3_feature])

    if feedback:
        feedback.setProgress(100)
        feedback.pushInfo("H3 DGGS generation completed.")
            

    return mem_layer

