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

from qgis.core import (
    QgsVectorLayer, QgsFeature, QgsGeometry, QgsField, QgsFields, QgsProcessingException,
    QgsWkbTypes, QgsVectorFileWriter, QgsProject, QgsCoordinateReferenceSystem
)
from PyQt5.QtCore import QVariant
from shapely.geometry import Polygon

def h3compact(h3_layer: QgsVectorLayer, H3ID_field,feedback=None) -> QgsVectorLayer:
    fields = QgsFields()
    fields.append(QgsField("h3", QVariant.String))
    fields.append(QgsField("resolution", QVariant.Int))
    fields.append(QgsField("center_lat", QVariant.Double))
    fields.append(QgsField("center_lon", QVariant.Double))
    fields.append(QgsField("avg_edge_len", QVariant.Double))
    fields.append(QgsField("cell_area", QVariant.Double))

    crs = h3_layer.crs().toWkt()
    mem_layer = QgsVectorLayer("Polygon?crs=" + crs, "h3_compacted", "memory")
    mem_provider = mem_layer.dataProvider()
    mem_provider.addAttributes(fields)
    mem_layer.updateFields()

    h3_ids = [
        feature[H3ID_field]
        for feature in h3_layer.getFeatures()
        if feature[H3ID_field]
    ]
    if h3_ids:
        try:
            h3_ids_compact = h3.compact_cells(h3_ids)
        except:
            raise QgsProcessingException("Compact cells failed. Please check your H3 cell Ids.")

        total = len(h3_ids_compact)

        for i, h3_id_compact in enumerate(h3_ids_compact):
            if feedback:
                feedback.setProgress(int((i / total) * 100))
                if feedback.isCanceled():
                    return None

            cell_boundary = h3.cell_to_boundary(h3_id_compact)
            filtered_boundary = fix_h3_antimeridian_cells(cell_boundary)
            reversed_boundary = [(lon, lat) for lat, lon in filtered_boundary]
            cell_polygon = Polygon(reversed_boundary)
            
            if not cell_polygon.is_valid:
                continue
            
            resolution = h3.get_resolution(h3_id_compact)
            num_edges = 5 if h3.is_pentagon(h3_id_compact) else 6
            center_lat, center_lon, avg_edge_len, cell_area = geodesic_dggs_metrics(cell_polygon, num_edges)
            
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
                }
            h3_feature.setAttributes([attributes[field.name()] for field in fields])
            mem_provider.addFeatures([h3_feature])

        if feedback:
            feedback.setProgress(100)
            feedback.pushInfo("H3 Compact completed.")
                
        return mem_layer


def s2compact(s2_layer: QgsVectorLayer, S2ID_field, feedback=None) -> QgsVectorLayer:
    fields = QgsFields()
    fields.append(QgsField("s2", QVariant.String))
    fields.append(QgsField("resolution", QVariant.Int))
    fields.append(QgsField("center_lat", QVariant.Double))
    fields.append(QgsField("center_lon", QVariant.Double))
    fields.append(QgsField("avg_edge_len", QVariant.Double))
    fields.append(QgsField("cell_area", QVariant.Double))

    crs = s2_layer.crs().toWkt()
    mem_layer = QgsVectorLayer("Polygon?crs=" + crs, "s2_compacted", "memory")
    mem_provider = mem_layer.dataProvider()
    mem_provider.addAttributes(fields)
    mem_layer.updateFields()

    s2_tokens = [
        feature[S2ID_field]
        for feature in s2_layer.getFeatures()
        if feature[S2ID_field]
    ]
    
    s2_ids = [s2.CellId.from_token(token) for token in s2_tokens]
    if s2_ids:
        try:
            covering = s2.CellUnion(s2_ids)
            covering.normalize()
            s2_tokens_compact = [cell_id.to_token() for cell_id in covering.cell_ids()]
        except:
            raise QgsProcessingException("Compact cells failed. Please check your S2 cell Ids.")

        total = len(s2_tokens_compact)

        for i, s2_token_compact in enumerate(s2_tokens_compact):
            if feedback:
                feedback.setProgress(int((i / total) * 100))
                if feedback.isCanceled():
                    return None

            s2_id_compact = s2.CellId.from_token(s2_token_compact)
            s2_cell = s2.Cell(s2_id_compact)    
            # Get the vertices of the cell (4 vertices for a rectangular cell)
            vertices = [s2_cell.get_vertex(i) for i in range(4)]
            # Prepare vertices in (longitude, latitude) format for Shapely
            shapely_vertices = []
            for vertex in vertices:
                lat_lng = s2.LatLng.from_point(vertex)  # Convert Point to LatLng
                longitude = lat_lng.lng().degrees  # Access longitude in degrees
                latitude = lat_lng.lat().degrees   # Access latitude in degrees
                shapely_vertices.append((longitude, latitude))

            # Close the polygon by adding the first vertex again
            shapely_vertices.append(shapely_vertices[0])  # Closing the polygon
            # Create a Shapely Polygon
            cell_polygon = fix_polygon(Polygon(shapely_vertices)) # Fix antimeridian
                
            if not cell_polygon.is_valid:
                continue
            
            resolution = s2_id_compact.level() 
            num_edges = 4
            center_lat, center_lon, avg_edge_len, cell_area = geodesic_dggs_metrics(cell_polygon, num_edges)
            
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
                }
            s2_feature.setAttributes([attributes[field.name()] for field in fields])
            mem_provider.addFeatures([s2_feature])

        if feedback:
            feedback.setProgress(100)
            feedback.pushInfo("S2 Compact completed.")
                
        return mem_layer
