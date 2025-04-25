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
    from vgrid.generator.isea3hgrid import isea3h_cell_to_polygon
    from vgrid.generator.settings import isea3h_accuracy_res_dict

if (platform.system() == 'Linux'):
    from vgrid.utils.dggrid4py import DGGRIDv7, dggs_types
    from vgrid.utils.dggrid4py.dggrid_runner import input_address_types


from vgrid.utils.easedggs.constants import levels_specs
from vgrid.utils.easedggs.dggs.grid_addressing import grid_ids_to_geos

from shapely.wkt import loads
from shapely.geometry import shape, Polygon,mapping

import json, re, os
from vgrid.generator.h3grid import fix_h3_antimeridian_cells

from vgrid.utils.antimeridian import fix_polygon
from vgrid.generator.settings import graticule_dggs_metrics, geodesic_dggs_metrics

from vgrid.conversion.dggs2geojson import rhealpix_cell_to_polygon
from vgrid.utils.easedggs.dggs.hierarchy import _parent_to_children
from vgrid.utils.easedggs.dggs.grid_addressing import grid_ids_to_geos
from vgrid.generator.geohashgrid import geohash_to_polygon
from vgrid.conversion.dggscompact import s2_expand,rhealpix_expand, isea4t_expand, isea3h_expand, qtm_expand

from pyproj import Geod
geod = Geod(ellps="WGS84")
E = WGS84_ELLIPSOID
from collections import defaultdict

from qgis.core import (
    QgsVectorLayer, QgsFeature, QgsGeometry, QgsField, QgsFields,
    QgsProcessingException,
    QgsWkbTypes, QgsVectorFileWriter, QgsProject, QgsCoordinateReferenceSystem
)
from PyQt5.QtCore import QVariant
from shapely.geometry import Polygon


########################## 
# H3
#########################
def h3expand(h3_layer: QgsVectorLayer, resolution: int, H3ID_field=None, feedback=None) -> QgsVectorLayer:
    if not H3ID_field:
        H3ID_field = 'h3'

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
        feature[H3ID_field]
        for feature in h3_layer.getFeatures()
        if feature[H3ID_field]
    ]
    
    if h3_ids:
        try:
            max_res = max(h3.get_resolution(h3_id) for h3_id in h3_ids)
            if resolution <= max_res:
                if feedback:
                    feedback.reportError(f"Target expand resolution ({resolution}) must > {max_res}.")
                    return None
            h3_ids_expand = h3.uncompact_cells(h3_ids, resolution)
        except:
            raise QgsProcessingException("Expand cells failed. Please check your H3 cell Ids.")
            
        total = len(h3_ids_expand)

        for i, h3_id_expand in enumerate(h3_ids_expand):
            if feedback:
                feedback.setProgress(int((i / total) * 100))
                if feedback.isCanceled():
                    return None

            cell_boundary = h3.cell_to_boundary(h3_id_expand)
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
            feedback.pushInfo("H3 DGGS expansion completed.")
                
    return mem_layer


########################## 
# S2
# ########################
def s2expand(s2_layer: QgsVectorLayer, resolution: int, S2Token_field=None, feedback=None) -> QgsVectorLayer:
    if not S2Token_field:
        S2Token_field = 's2'

    fields = QgsFields()
    fields.append(QgsField("s2", QVariant.String))
    fields.append(QgsField("resolution", QVariant.Int))
    fields.append(QgsField("center_lat", QVariant.Double))
    fields.append(QgsField("center_lon", QVariant.Double))
    fields.append(QgsField("avg_edge_len", QVariant.Double))
    fields.append(QgsField("cell_area", QVariant.Double))

    crs = s2_layer.crs().toWkt()
    mem_layer = QgsVectorLayer("Polygon?crs=" + crs, "s2_expanded", "memory")
    mem_provider = mem_layer.dataProvider()
    mem_provider.addAttributes(fields)
    mem_layer.updateFields()

    s2_tokens = [
        feature[S2Token_field]
        for feature in s2_layer.getFeatures()
        if feature[S2Token_field]
    ]
             
    try:
        s2_ids = [s2.CellId.from_token(token) for token in s2_tokens]   
        if s2_ids:   
            max_res = max(s2_id.level() for s2_id in s2_ids)
            if resolution <= max_res:
                if feedback:
                    feedback.reportError(f"Target expand resolution ({resolution}) must > {max_res}.")
                    return None
            s2_ids_expand = s2_expand(s2_ids, resolution)
            s2_tokens_expand = [s2_id_expand.to_token() for s2_id_expand in s2_ids_expand]
    
    except:
        raise QgsProcessingException("Expand cells failed. Please check your S2 cell Ids.")
        
    total = len(s2_tokens_expand)

    for i, s2_token_expand in enumerate(s2_tokens_expand):
        if feedback:
            feedback.setProgress(int((i / total) * 100))
            if feedback.isCanceled():
                return None

        s2_id_expand = s2.CellId.from_token(s2_token_expand)
        s2_cell_expand = s2.Cell(s2_id_expand)    
        # Get the vertices of the cell (4 vertices for a rectangular cell)
        vertices = [s2_cell_expand.get_vertex(i) for i in range(4)]
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
        
        resolution = s2_id_expand.level()
        num_edges = 4
        center_lat, center_lon, avg_edge_len, cell_area = geodesic_dggs_metrics(cell_polygon, num_edges)
        
        cell_geom = QgsGeometry.fromWkt(cell_polygon.wkt)
        s2_feature = QgsFeature(fields)
        s2_feature.setGeometry(cell_geom)
        
        attributes = {
            "s2": s2_token_expand,
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
        feedback.pushInfo("s2 DGGS expansion completed.")
                
    return mem_layer


########################## 
# rHEALPix
#########################
def get_rhealpix_resolution(rhealpix_dggs, rhealpix_id):
    try:
        rhealpix_uids = (rhealpix_id[0],) + tuple(map(int, rhealpix_id[1:]))
        rhealpix_cell = rhealpix_dggs.cell(rhealpix_uids)
        return rhealpix_cell.resolution
    except Exception as e:
        raise ValueError(f"Invalid cell ID '{rhealpix_id}': {e}")

def rhealpixexpand(rhealpix_layer: QgsVectorLayer, resolution: int, rHealPixID_field=None, feedback=None) -> QgsVectorLayer:
    rhealpix_dggs = RHEALPixDGGS()
    
    if not rHealPixID_field:
        rHealPixID_field = 'rhealpix'

    fields = QgsFields()
    fields.append(QgsField("rhealpix", QVariant.String))
    fields.append(QgsField("resolution", QVariant.Int))
    fields.append(QgsField("center_lat", QVariant.Double))
    fields.append(QgsField("center_lon", QVariant.Double))
    fields.append(QgsField("avg_edge_len", QVariant.Double))
    fields.append(QgsField("cell_area", QVariant.Double))

    crs = rhealpix_layer.crs().toWkt()
    mem_layer = QgsVectorLayer("Polygon?crs=" + crs, "rhealpix_expanded", "memory")
    mem_provider = mem_layer.dataProvider()
    mem_provider.addAttributes(fields)
    mem_layer.updateFields()

    rhealpix_ids = [
        feature[rHealPixID_field]
        for feature in rhealpix_layer.getFeatures()
        if feature[rHealPixID_field]
    ]
    
    if rhealpix_ids:
        try:
            max_res = max(get_rhealpix_resolution(rhealpix_dggs,rhealpix_id) for rhealpix_id in rhealpix_ids)
        except Exception as e:
            raise QgsProcessingException(f"Error determining cell resolution from rHEALPix cell Ids: {e}")

        if resolution <= max_res:
            if feedback:
                feedback.reportError(f"Target expand resolution ({resolution}) must > {max_res}.")
            return None

        try:
            rhealpix_cells_expand = rhealpix_expand(rhealpix_dggs, rhealpix_ids, resolution)
        except:
            raise QgsProcessingException("Expand cells failed. Please check your rHEALPix cell Ids.")

        total = len(rhealpix_cells_expand)

        for i, rhealpix_cell_expand in enumerate(rhealpix_cells_expand):
            if feedback:
                feedback.setProgress(int((i / total) * 100))
                if feedback.isCanceled():
                    return None

            cell_polygon = rhealpix_cell_to_polygon(rhealpix_cell_expand)
            
            if not cell_polygon.is_valid:
                continue
            
            rhealpix_id_expand = str(rhealpix_cell_expand)               
            num_edges = 3 if rhealpix_cell_expand.ellipsoidal_shape() == 'dart' else 4
            center_lat, center_lon, avg_edge_len, cell_area = geodesic_dggs_metrics(cell_polygon, num_edges)
            
            cell_geom = QgsGeometry.fromWkt(cell_polygon.wkt)
            rhealpix_feature = QgsFeature(fields)
            rhealpix_feature.setGeometry(cell_geom)
            
            attributes = {
                "rhealpix": rhealpix_id_expand,
                "resolution": resolution,
                "center_lat": center_lat,
                "center_lon": center_lon,
                "avg_edge_len": avg_edge_len,
                "cell_area": cell_area,
            }
            rhealpix_feature.setAttributes([attributes[field.name()] for field in fields])
            mem_provider.addFeatures([rhealpix_feature])

        if feedback:
            feedback.setProgress(100)
            feedback.pushInfo("rHEALPix DGGS expansion completed.")
                
    return mem_layer


########################## 
# ISEA4T
#########################
def isea4texpand(isea4t_layer: QgsVectorLayer, resolution: int, ISEA4TID_field=None, feedback=None) -> QgsVectorLayer:
    if (platform.system() == 'Windows'):  
        isea4t_dggs = Eaggr(Model.ISEA4T)
        
        if not ISEA4TID_field:
            ISEA4TID_field = 'isea4t'

        fields = QgsFields()
        fields.append(QgsField("isea4t", QVariant.String))
        fields.append(QgsField("resolution", QVariant.Int))
        fields.append(QgsField("center_lat", QVariant.Double))
        fields.append(QgsField("center_lon", QVariant.Double))
        fields.append(QgsField("avg_edge_len", QVariant.Double))
        fields.append(QgsField("cell_area", QVariant.Double))

        crs = isea4t_layer.crs().toWkt()
        mem_layer = QgsVectorLayer("Polygon?crs=" + crs, "isea4t_expanded", "memory")
        mem_provider = mem_layer.dataProvider()
        mem_provider.addAttributes(fields)
        mem_layer.updateFields()

        isea4t_ids = [
            feature[ISEA4TID_field]
            for feature in isea4t_layer.getFeatures()
            if feature[ISEA4TID_field]
        ]
        
        if isea4t_ids:
            max_res = max(len(isea4t_id)-2 for isea4t_id in isea4t_ids)
            if resolution <= max_res:
                if feedback:
                    feedback.reportError(f"Target expand resolution ({resolution}) must > {max_res}.")
                return None

            try:
                isea4t_cells_expand = isea4t_expand(isea4t_dggs, isea4t_ids, resolution)
            except:
                raise QgsProcessingException("Expand cells failed. Please check your ISEA4T cell Ids.")

            total = len(isea4t_cells_expand)

            for i, isea4t_cell_expand in enumerate(isea4t_cells_expand):
                if feedback:
                    feedback.setProgress(int((i / total) * 100))
                    if feedback.isCanceled():
                        return None

                cell_to_shape = isea4t_dggs.convert_dggs_cell_outline_to_shape_string(isea4t_cell_expand,ShapeStringFormat.WKT)
                cell_to_shape_fixed = loads(fix_isea4t_wkt(cell_to_shape))
                isea4t_id_expand = isea4t_cell_expand.get_cell_id()
                if isea4t_id_expand.startswith('00') or isea4t_id_expand.startswith('09') or isea4t_id_expand.startswith('14')\
                    or isea4t_id_expand.startswith('04') or isea4t_id_expand.startswith('19'):
                    cell_to_shape_fixed = fix_isea4t_antimeridian_cells(cell_to_shape_fixed)
                    
                cell_polygon = Polygon(list(cell_to_shape_fixed.exterior.coords))
                
                if not cell_polygon.is_valid:
                    continue
                
                num_edges = 3
                center_lat, center_lon, avg_edge_len, cell_area = geodesic_dggs_metrics(cell_polygon, num_edges)
                
                cell_geom = QgsGeometry.fromWkt(cell_polygon.wkt)
                isea4t_feature = QgsFeature(fields)
                isea4t_feature.setGeometry(cell_geom)
                
                attributes = {
                    "isea4t": isea4t_id_expand,
                    "resolution": resolution,
                    "center_lat": center_lat,
                    "center_lon": center_lon,
                    "avg_edge_len": avg_edge_len,
                    "cell_area": cell_area,
                }
                isea4t_feature.setAttributes([attributes[field.name()] for field in fields])
                mem_provider.addFeatures([isea4t_feature])

            if feedback:
                feedback.setProgress(100)
                feedback.pushInfo("ISEA4T DGGS expansion completed.")
                    
        return mem_layer



########################## 
# ISEA3H
#########################
def get_isea3h_resolution(isea3h_dggs, isea3h_id):
    try:
        isea3h_cell = DggsCell(isea3h_id)
        cell_polygon = isea3h_cell_to_polygon(isea3h_dggs,isea3h_cell)    
        cell_perimeter = abs(geod.geometry_area_perimeter(cell_polygon)[1])
        
        isea3h2point = isea3h_dggs.convert_dggs_cell_to_point(isea3h_cell)      
        cell_accuracy = isea3h2point._accuracy
            
        avg_edge_len = cell_perimeter / 6
        cell_resolution  = isea3h_accuracy_res_dict.get(cell_accuracy)
        
        if (cell_resolution == 0): # icosahedron faces at resolution = 0
            avg_edge_len = cell_perimeter / 3
        
        if cell_accuracy == 0.0:
            if round(avg_edge_len,2) == 0.06:
                cell_resolution = 33
            elif round(avg_edge_len,2) == 0.03:
                cell_resolution = 34
            elif round(avg_edge_len,2) == 0.02:
                cell_resolution = 35
            elif round(avg_edge_len,2) == 0.01:
                cell_resolution = 36
            
            elif round(avg_edge_len,3) == 0.007:
                cell_resolution = 37
            elif round(avg_edge_len,3) == 0.004:
                cell_resolution = 38
            elif round(avg_edge_len,3) == 0.002:
                cell_resolution = 39
            elif round(avg_edge_len,3) <= 0.001:
                cell_resolution = 40
                
        return cell_resolution
    except Exception as e:
        raise ValueError(f"Invalid cell ID '{isea3h_id}': {e}")


def isea3hexpand(isea3h_layer: QgsVectorLayer, resolution: int, ISEA3HID_field=None, feedback=None) -> QgsVectorLayer:
    if (platform.system() == 'Windows'):  
        isea3h_dggs = Eaggr(Model.ISEA3H)
        
        if not ISEA3HID_field:
            ISEA3HID_field = 'isea3h'

        fields = QgsFields()
        fields.append(QgsField("isea3h", QVariant.String))
        fields.append(QgsField("resolution", QVariant.Int))
        fields.append(QgsField("center_lat", QVariant.Double))
        fields.append(QgsField("center_lon", QVariant.Double))
        fields.append(QgsField("avg_edge_len", QVariant.Double))
        fields.append(QgsField("cell_area", QVariant.Double))

        crs = isea3h_layer.crs().toWkt()
        mem_layer = QgsVectorLayer("Polygon?crs=" + crs, "isea3h_expanded", "memory")
        mem_provider = mem_layer.dataProvider()
        mem_provider.addAttributes(fields)
        mem_layer.updateFields()

        isea3h_ids = [
            feature[ISEA3HID_field]
            for feature in isea3h_layer.getFeatures()
            if feature[ISEA3HID_field]
        ]
        
        if isea3h_ids:
            try:
                max_res = max(get_isea3h_resolution(isea3h_dggs,rhealpix_id) for rhealpix_id in isea3h_ids)
            except Exception as e:
                raise QgsProcessingException(f"Error determining cell resolution from rHEALPix cell Ids: {e}")

            if resolution <= max_res:
                if feedback:
                    feedback.reportError(f"Target expand resolution ({resolution}) must > {max_res}.")
                return None
            
            try:
                isea3h_cells_expand = isea3h_expand(isea3h_dggs, isea3h_ids, resolution)
            except:
                raise QgsProcessingException("Expand cells failed. Please check your ISEA3H cell Ids.")

            total = len(isea3h_cells_expand)

            for i, isea3h_cell_expand in enumerate(isea3h_cells_expand):
                if feedback:
                    feedback.setProgress(int((i / total) * 100))
                    if feedback.isCanceled():
                        return None

                cell_polygon = isea3h_cell_to_polygon(isea3h_dggs,isea3h_cell_expand)                
                if not cell_polygon.is_valid:
                    continue
                
                isea3h_id = isea3h_cell_expand.get_cell_id()
                cell_centroid = cell_polygon.centroid
                center_lat =  round(cell_centroid.y, 7)
                center_lon = round(cell_centroid.x, 7)
                cell_area = round(abs(geod.geometry_area_perimeter(cell_polygon)[0]),3)
                cell_perimeter = abs(geod.geometry_area_perimeter(cell_polygon)[1])
                
                isea3h2point = isea3h_dggs.convert_dggs_cell_to_point(isea3h_cell_expand)      
                cell_accuracy = isea3h2point._accuracy
                    
                avg_edge_len = cell_perimeter / 6
                cell_resolution  = isea3h_accuracy_res_dict.get(cell_accuracy)
                
                if (cell_resolution == 0): # icosahedron faces at resolution = 0
                    avg_edge_len = cell_perimeter / 3
                
                if cell_accuracy == 0.0:
                    if round(avg_edge_len,2) == 0.06:
                        cell_resolution = 33
                    elif round(avg_edge_len,2) == 0.03:
                        cell_resolution = 34
                    elif round(avg_edge_len,2) == 0.02:
                        cell_resolution = 35
                    elif round(avg_edge_len,2) == 0.01:
                        cell_resolution = 36
                    
                    elif round(avg_edge_len,3) == 0.007:
                        cell_resolution = 37
                    elif round(avg_edge_len,3) == 0.004:
                        cell_resolution = 38
                    elif round(avg_edge_len,3) == 0.002:
                        cell_resolution = 39
                    elif round(avg_edge_len,3) <= 0.001:
                        cell_resolution = 40
            
                cell_geom = QgsGeometry.fromWkt(cell_polygon.wkt)
                isea3h_feature = QgsFeature(fields)
                isea3h_feature.setGeometry(cell_geom)
                
                attributes = {
                    "isea3h": isea3h_id,
                    "resolution": cell_resolution,
                    "center_lat": center_lat,
                    "center_lon": center_lon,
                    "avg_edge_len": round(avg_edge_len,3),
                    "cell_area": cell_area,
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
def qtmexpand(qtm_layer: QgsVectorLayer, resolution: int,QTMID_field=None, feedback=None) -> QgsVectorLayer:
    if not QTMID_field:
        QTMID_field = 'qtm'

    fields = QgsFields()
    fields.append(QgsField("qtm", QVariant.String))
    fields.append(QgsField("resolution", QVariant.Int))
    fields.append(QgsField("center_lat", QVariant.Double))
    fields.append(QgsField("center_lon", QVariant.Double))
    fields.append(QgsField("avg_edge_len", QVariant.Double))
    fields.append(QgsField("cell_area", QVariant.Double))

    crs = qtm_layer.crs().toWkt()
    mem_layer = QgsVectorLayer("Polygon?crs=" + crs, "qtm_expanded", "memory")
    mem_provider = mem_layer.dataProvider()
    mem_provider.addAttributes(fields)
    mem_layer.updateFields()

    qtm_ids = [
        feature[QTMID_field]
        for feature in qtm_layer.getFeatures()
        if feature[QTMID_field]
    ]
    
    if qtm_ids:
        try:
            max_res = max(len(qtm_id) for qtm_id in qtm_ids)
            if resolution <= max_res:
                if feedback:
                    feedback.reportError(f"Target expand resolution ({resolution}) must > {max_res}.")
                    return None
            qtm_ids_expand = qtm_expand(qtm_ids, resolution)
        except:
            raise QgsProcessingException("Expand cells failed. Please check your QTM cell Ids.")
            
        total = len(qtm_ids_expand)

        for i, qtm_id_expand in enumerate(qtm_ids_expand):
            if feedback:
                feedback.setProgress(int((i / total) * 100))
                if feedback.isCanceled():
                    return None

            facet = qtm.qtm_id_to_facet(qtm_id_expand)
            cell_polygon = qtm.constructGeometry(facet)    
            
            if not cell_polygon.is_valid:
                continue
            
            num_edges = 3
            center_lat, center_lon, avg_edge_len, cell_area = geodesic_dggs_metrics(cell_polygon, num_edges)
            
            cell_geom = QgsGeometry.fromWkt(cell_polygon.wkt)
            qtm_feature = QgsFeature(fields)
            qtm_feature.setGeometry(cell_geom)
            
            attributes = {
                "qtm": qtm_id_expand,
                "resolution": resolution,
                "center_lat": center_lat,
                "center_lon": center_lon,
                "avg_edge_len": avg_edge_len,
                "cell_area": cell_area,
            }
            qtm_feature.setAttributes([attributes[field.name()] for field in fields])
            mem_provider.addFeatures([qtm_feature])

        if feedback:
            feedback.setProgress(100)
            feedback.pushInfo("QTM expansion completed.")
                
    return mem_layer

