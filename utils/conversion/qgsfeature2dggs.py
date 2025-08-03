from shapely.geometry import Polygon, box, mapping, LineString
from shapely.wkt import loads as load_wkt
import numpy as np

from shapely.wkt import loads as wkt_loads
import platform,re
from qgis.core import QgsFeature, QgsGeometry, QgsField, QgsFields,QgsWkbTypes

from PyQt5.QtCore import QVariant

import h3 
import a5
from vgrid.dggs import s2

from vgrid.conversion.latlon2dggs import (
    latlon2h3,latlon2s2,latlon2a5,latlon2isea4t,
    latlon2isea3h,latlon2rhealpix,latlon2qtm,latlon2olc,latlon2geohash,latlon2georef,latlon2tilecode,latlon2quadkey,latlon2maidenhead,latlon2gars
)
from vgrid.dggs.rhealpixdggs.dggs import RHEALPixDGGS
from vgrid.dggs.rhealpixdggs.ellipsoids import WGS84_ELLIPSOID

from vgrid.utils.geometry import s2_cell_to_polygon

from vgrid.utils.geometry import geodesic_buffer
from vgrid.conversion.dggs2geo.h32geo import h32geo
from vgrid.conversion.dggs2geo.s22geo import s22geo
from vgrid.conversion.dggs2geo.rhealpix2geo import rhealpix2geo
from vgrid.conversion.dggs2geo.isea4t2geo import isea4t2geo
from vgrid.conversion.dggs2geo.isea3h2geo import isea3h2geo
from vgrid.conversion.dggs2geo.ease2geo import ease2geo
from vgrid.conversion.dggs2geo.qtm2geo import qtm2geo
from vgrid.conversion.dggs2geo.olc2geo import olc2geo
from vgrid.conversion.dggs2geo.geohash2geo import geohash2geo
from vgrid.conversion.dggs2geo.georef2geo import georef2geo
from vgrid.conversion.dggs2geo.a52geo import a52geo
from vgrid.conversion.dggs2geo.isea4t2geo import isea4t2geo
from vgrid.conversion.dggs2geo.geohash2geo import geohash2geo
from vgrid.utils.geometry import  graticule_dggs_metrics, geodesic_dggs_metrics,check_predicate

from vgrid.dggs.easedggs.constants import levels_specs
from vgrid.dggs.easedggs.dggs.grid_addressing import grid_ids_to_geos,geos_to_grid_ids

if (platform.system() == 'Windows'):
    from vgrid.dggs.eaggr.eaggr import Eaggr
    from vgrid.dggs.eaggr.shapes.dggs_cell import DggsCell
    from vgrid.dggs.eaggr.enums.model import Model
    from vgrid.dggs.eaggr.enums.shape_string_format import ShapeStringFormat
    from vgrid.dggs.eaggr.shapes.lat_long_point import LatLongPoint
    from vgrid.generator.isea4tgrid import get_isea4t_children_cells_within_bbox
    from vgrid.utils.geometry import isea4t_cell_to_polygon, isea3h_cell_to_polygon, fix_isea4t_antimeridian_cells
    from vgrid.conversion.dggscompact.isea4tcompact import isea4t_compact
    from vgrid.conversion.dggscompact.isea3hcompact import isea3h_compact
    from vgrid.generator.isea3hgrid import get_isea3h_children_cells_within_bbox                                   
    from vgrid.generator.settings import ISEA3H_RES_ACCURACY_DICT,ISEA3H_ACCURACY_RES_DICT
    isea4t_dggs = Eaggr(Model.ISEA4T)
    isea3h_dggs = Eaggr(Model.ISEA3H)

from vgrid.conversion.dggscompact.qtmcompact import qtm_compact
from vgrid.conversion.dggscompact.olccompact import olc_compact
from vgrid.conversion.dggscompact.geohashcompact import geohash_compact
from vgrid.conversion.dggscompact.tilecodecompact import tilecode_compact
from vgrid.conversion.dggscompact.quadkeycompact import quadkey_compact
from vgrid.conversion.dggscompact.a5compact import a5_compact

from vgrid.generator.geohashgrid import expand_geohash_bbox
from vgrid.generator.settings import INITIAL_GEOHASHES, ISEA4T_RES_ACCURACY_DICT,ISEA3H_ACCURACY_RES_DICT

from vgrid.conversion import latlon2dggs

from pyproj import Geod
geod = Geod(ellps="WGS84")
p90_n180, p90_n90, p90_p0, p90_p90, p90_p180 = (90.0, -180.0), (90.0, -90.0), (90.0, 0.0), (90.0, 90.0), (90.0, 180.0)
p0_n180, p0_n90, p0_p0, p0_p90, p0_p180 = (0.0, -180.0), (0.0, -90.0), (0.0, 0.0), (0.0, 90.0), (0.0, 180.0)
n90_n180, n90_n90, n90_p0, n90_p90, n90_p180 = (-90.0, -180.0), (-90.0, -90.0), (-90.0, 0.0), (-90.0, 90.0), (-90.0, 180.0)


#######################
# QgsFeatures to H3
#######################
def qgsfeature2h3(feature, resolution, predicate = None, compact=None,feedback=None):
    gfeature_geom = feature.geometry()
    if gfeature_geom.wkbType() == QgsWkbTypes.Point:
        return point2h3(feature,resolution,feedback)
    elif gfeature_geom.wkbType() == QgsWkbTypes.LineString:
        return polyline2h3(feature,resolution,None,None,feedback)
    elif gfeature_geom.wkbType() == QgsWkbTypes.Polygon:
        return polygon2h3(feature, resolution,predicate,compact,feedback)

def point2h3(feature, resolution, feedback): 
    if feedback and feedback.isCanceled():
        return []

    feature_geometry = feature.geometry()
    point = feature_geometry.asPoint()
    h3_id = latlon2h3(point.y(), point.x(), resolution)
    cell_polygon = h32geo(h3_id)
      
    num_edges = 6
    if h3.is_pentagon(h3_id):
        num_edges = 5
    
    center_lat, center_lon, avg_edge_len, cell_area = geodesic_dggs_metrics(cell_polygon, num_edges)
    
    cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)    
    h3_feature = QgsFeature()
    h3_feature.setGeometry(cell_geometry)
    
    original_attributes = feature.attributes()
    original_fields = feature.fields()
    
    new_fields = QgsFields()
    new_fields.append(QgsField("h3", QVariant.String))
    new_fields.append(QgsField("resolution", QVariant.Int))
    new_fields.append(QgsField("center_lat", QVariant.Double))
    new_fields.append(QgsField("center_lon", QVariant.Double))
    new_fields.append(QgsField("avg_edge_len", QVariant.Double))
    new_fields.append(QgsField("cell_area", QVariant.Double))
    
    # Combine original fields and new fields
    all_fields = QgsFields()
    for field in original_fields:
        all_fields.append(field)
    for field in new_fields:
        all_fields.append(field)
    
    h3_feature.setFields(all_fields)
    
    # Combine original attributes with new attributes
    new_attributes = [str(h3_id), resolution, center_lat, center_lon, avg_edge_len, cell_area]
    all_attributes = original_attributes + new_attributes
    
    h3_feature.setAttributes(all_attributes)
    
    return [h3_feature]


def polyline2h3(feature, resolution, predicate = None, compact=None, feedback=None):  
    h3_features = []  
    feature_geometry = feature.geometry()
    feature_rect = feature_geometry.boundingBox()
    min_x = feature_rect.xMinimum()
    min_y = feature_rect.yMinimum()
    max_x = feature_rect.xMaximum()
    max_y = feature_rect.yMaximum()
    # Create a Shapely box
    bbox = box(min_x, min_y, max_x, max_y)    
    
    buufer_distance = h3.average_hexagon_edge_length(resolution, unit='m') * 2
    bbox_buffer = geodesic_buffer(bbox, buufer_distance)
    bbox_buffer_cells = h3.geo_to_cells(bbox_buffer, resolution)
        
    if feedback:
        feedback.pushInfo(f"Processing feature {feature.id()}")   
        feedback.setProgress(0)
    total_cells = len(bbox_buffer_cells)
    for i, bbox_buffer_cell in enumerate(bbox_buffer_cells):
        if feedback and feedback.isCanceled():
            return []    
        cell_polygon = h32geo(bbox_buffer_cell)                
        num_edges = 6
        if h3.is_pentagon(bbox_buffer_cell):
            num_edges = 5
        
        h3_id = str(bbox_buffer_cell)
        center_lat, center_lon, avg_edge_len, cell_area = geodesic_dggs_metrics(cell_polygon, num_edges)
        cell_resolution = h3.get_resolution(h3_id) 
        cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)    
        
        if not check_predicate(cell_geometry, feature_geometry, "intersects"):
            continue

        h3_feature = QgsFeature()
        h3_feature.setGeometry(cell_geometry)
        
        # Get all attributes from the input feature
        original_attributes = feature.attributes()
        original_fields = feature.fields()
        
        # Define new H3-related attributes
        new_fields = QgsFields()
        new_fields.append(QgsField("h3", QVariant.String))
        new_fields.append(QgsField("resolution", QVariant.Int))
        new_fields.append(QgsField("center_lat", QVariant.Double))
        new_fields.append(QgsField("center_lon", QVariant.Double))
        new_fields.append(QgsField("avg_edge_len", QVariant.Double))
        new_fields.append(QgsField("cell_area", QVariant.Double))
        
        # Combine original fields and new fields
        all_fields = QgsFields()
        for field in original_fields:
            all_fields.append(field)
        for field in new_fields:
            all_fields.append(field)
        
        h3_feature.setFields(all_fields)
        
        # Combine original attributes with new attributes
        new_attributes = [h3_id,cell_resolution, center_lat, center_lon,  avg_edge_len, cell_area]
        all_attributes = original_attributes + new_attributes
        
        h3_feature.setAttributes(all_attributes)    

        h3_features.append(h3_feature)
        
        if feedback and i % 100 == 0:
            feedback.setProgress(int(100 * i / total_cells))

    if feedback:
        feedback.setProgress(100)
            
    return h3_features

def polygon2h3(feature, resolution, predicate = None, compact=None, feedback=None):  
    h3_features = []  
    feature_geometry = feature.geometry()
    shapely_geom = load_wkt(feature_geometry.asWkt())
    feature_rect = feature_geometry.boundingBox()
    min_x = feature_rect.xMinimum()
    min_y = feature_rect.yMinimum()
    max_x = feature_rect.xMaximum()
    max_y = feature_rect.yMaximum()
    # Create a Shapely box
    bbox = box(min_x, min_y, max_x, max_y)    
    
    buufer_distance = h3.average_hexagon_edge_length(resolution, unit='m') * 2
    bbox_buffer = geodesic_buffer(bbox, buufer_distance)
    bbox_buffer_cells = h3.geo_to_cells(bbox_buffer, resolution)
        
    if compact:
        bbox_buffer_cells = h3.compact_cells(bbox_buffer_cells)

    total_cells = len(bbox_buffer_cells)

    if feedback:
        feedback.pushInfo(f"Processing feature {feature.id()}")   
        feedback.setProgress(0)

    for i, bbox_buffer_cell  in enumerate(bbox_buffer_cells):
        if feedback and feedback.isCanceled():
            return []

        cell_polygon = h32geo(bbox_buffer_cell)
        if not check_predicate(cell_polygon, shapely_geom, predicate):
            continue

        num_edges = 6
        if h3.is_pentagon(bbox_buffer_cell):
            num_edges = 5
        
        h3_id = str(bbox_buffer_cell)
        center_lat, center_lon, avg_edge_len, cell_area = geodesic_dggs_metrics(cell_polygon, num_edges)
        cell_resolution = h3.get_resolution(h3_id) 
        cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)    

        h3_feature = QgsFeature()
        h3_feature.setGeometry(cell_geometry)
        
        # Get all attributes from the input feature
        original_attributes = feature.attributes()
        original_fields = feature.fields()
        
        # Define new H3-related attributes
        new_fields = QgsFields()
        new_fields.append(QgsField("h3", QVariant.String))
        new_fields.append(QgsField("resolution", QVariant.Int))
        new_fields.append(QgsField("center_lat", QVariant.Double))
        new_fields.append(QgsField("center_lon", QVariant.Double))
        new_fields.append(QgsField("avg_edge_len", QVariant.Double))
        new_fields.append(QgsField("cell_area", QVariant.Double))
        
        # Combine original fields and new fields
        all_fields = QgsFields()
        for field in original_fields:
            all_fields.append(field)
        for field in new_fields:
            all_fields.append(field)
        
        h3_feature.setFields(all_fields)
        
        # Combine original attributes with new attributes
        new_attributes = [h3_id,cell_resolution, center_lat, center_lon,  avg_edge_len, cell_area]
        all_attributes = original_attributes + new_attributes
        
        h3_feature.setAttributes(all_attributes)    

        h3_features.append(h3_feature)
        
        if feedback and i % 100 == 0:
            feedback.setProgress(int(100 * i / total_cells))

    if feedback:
        feedback.setProgress(100)
            
    return h3_features
  
  
#######################
# QgsFeatures to S2
#######################
def qgsfeature2s2(feature, resolution, predicate = None, compact=None, feedback=None):
    gfeature_geom = feature.geometry()
    if gfeature_geom.wkbType() == QgsWkbTypes.Point:
        return point2s2(feature, resolution,feedback)
    elif gfeature_geom.wkbType() == QgsWkbTypes.LineString: 
        return polyline2s2(feature, resolution,None,None,feedback)
    elif gfeature_geom.wkbType() == QgsWkbTypes.Polygon:
        return polygon2s2(feature, resolution,predicate,compact,feedback)
  
def point2s2(feature,resolution,feedback): 
    if feedback and feedback.isCanceled():
        return []
    # Convert point to the seed cell
    feature_geometry = feature.geometry()
    point = feature_geometry.asPoint()
    s2_token = latlon2s2(point.y(), point.x(), resolution)
    cell_polygon = s22geo(s2_token)         
    num_edges = 4
    center_lat, center_lon, avg_edge_len, cell_area = geodesic_dggs_metrics(cell_polygon, num_edges)
    
    cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)        
    # Create a single QGIS feature
    s2_feature = QgsFeature()
    s2_feature.setGeometry(cell_geometry)
    
    # Get all attributes from the input feature
    original_attributes = feature.attributes()
    original_fields = feature.fields()
    
    # Define new s2-related attributes
    new_fields = QgsFields()
    new_fields.append(QgsField("s2", QVariant.String))
    new_fields.append(QgsField("resolution", QVariant.Int))
    new_fields.append(QgsField("center_lat", QVariant.Double))
    new_fields.append(QgsField("center_lon", QVariant.Double))
    new_fields.append(QgsField("avg_edge_len", QVariant.Double))
    new_fields.append(QgsField("cell_area", QVariant.Double))
    
    # Combine original fields and new fields
    all_fields = QgsFields()
    for field in original_fields:
        all_fields.append(field)
    for field in new_fields:
        all_fields.append(field)
    
    s2_feature.setFields(all_fields)
    
    # Combine original attributes with new attributes
    new_attributes = [s2_token, resolution, center_lat, center_lon, avg_edge_len, cell_area]
    all_attributes = original_attributes + new_attributes
    
    s2_feature.setAttributes(all_attributes)
    
    return [s2_feature]

def polyline2s2(feature, resolution, predicate=None, compact=None, feedback=None):  
    s2_features = []  

    feature_geometry = feature.geometry()
    shapely_geom = load_wkt(feature_geometry.asWkt())
    feature_rect = feature_geometry.boundingBox()
    min_x = feature_rect.xMinimum()
    min_y = feature_rect.yMinimum()
    max_x = feature_rect.xMaximum()
    max_y = feature_rect.yMaximum()
    level = resolution
    coverer = s2.RegionCoverer()
    coverer.min_level = level
    coverer.max_level = level
 
    region = s2.LatLngRect(
        s2.LatLng.from_degrees(min_y, min_x),
        s2.LatLng.from_degrees(max_y, max_x)
    )

    covering = coverer.get_covering(region)
    cell_ids = covering  
    if compact:
        covering = s2.CellUnion(covering)
        covering.normalize()
        cell_ids = covering.cell_ids()  
            
    total_cells = len(cell_ids)

    if feedback:
        feedback.pushInfo(f"Processing feature {feature.id()}")   
        feedback.setProgress(0)
        
    for i, cell_id in enumerate(cell_ids):     
        if feedback and feedback.isCanceled():
            return []
         
        cell_polygon = s2_cell_to_polygon(cell_id)
        if not check_predicate(cell_polygon, shapely_geom,"intersects"):
            continue

        cell_token = s2.CellId.to_token(cell_id)    
        cell_resolution = cell_id.level()
  
        num_edges = 4
        center_lat, center_lon, avg_edge_len, cell_area = geodesic_dggs_metrics(cell_polygon, num_edges)
        
        cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)    
              
        s2_feature = QgsFeature()
        s2_feature.setGeometry(cell_geometry)
        
        # Get all attributes from the input feature
        original_attributes = feature.attributes()
        original_fields = feature.fields()
        
        # Define new S2-related attributes
        new_fields = QgsFields()
        new_fields.append(QgsField("s2", QVariant.String))  # Dynamic cell ID field
        new_fields.append(QgsField("resolution", QVariant.Int))
        new_fields.append(QgsField("center_lat", QVariant.Double))
        new_fields.append(QgsField("center_lon", QVariant.Double))
        new_fields.append(QgsField("avg_edge_len", QVariant.Double))
        new_fields.append(QgsField("cell_area", QVariant.Double))

        # Combine original fields and new fields
        all_fields = QgsFields()
        for field in original_fields:
            all_fields.append(field)
        for field in new_fields:
            all_fields.append(field)
        
        s2_feature.setFields(all_fields)
        
        # Combine original attributes with new attributes
        new_attributes = [cell_token, cell_resolution, center_lat, center_lon, avg_edge_len, cell_area]
        all_attributes = original_attributes + new_attributes
        
        s2_feature.setAttributes(all_attributes)    

        s2_features.append(s2_feature)
        
        if feedback and i % 100 == 0:
            feedback.setProgress(int(100 * i / total_cells))

    if feedback:
        feedback.setProgress(100)
    
    return s2_features


def polygon2s2(feature, resolution, predicate=None, compact=None, feedback=None):  
    s2_features = []  

    feature_geometry = feature.geometry()
    shapely_geom = load_wkt(feature_geometry.asWkt())
    feature_rect = feature_geometry.boundingBox()
    min_x = feature_rect.xMinimum()
    min_y = feature_rect.yMinimum()
    max_x = feature_rect.xMaximum()
    max_y = feature_rect.yMaximum()
    level = resolution
    coverer = s2.RegionCoverer()
    coverer.min_level = level
    coverer.max_level = level
 
    region = s2.LatLngRect(
        s2.LatLng.from_degrees(min_y, min_x),
        s2.LatLng.from_degrees(max_y, max_x)
    )

    covering = coverer.get_covering(region)
    cell_ids = covering  
    if compact:
        covering = s2.CellUnion(covering)
        covering.normalize()
        cell_ids = covering.cell_ids()  
            
    total_cells = len(cell_ids)

    if feedback:
        feedback.pushInfo(f"Processing feature {feature.id()}")   
        feedback.setProgress(0)
        
    for i, cell_id in enumerate(cell_ids):     
        if feedback and feedback.isCanceled():
            return []
         
        cell_polygon = s2_cell_to_polygon(cell_id)
        if not check_predicate(cell_polygon, shapely_geom, predicate):
            continue

        cell_token = s2.CellId.to_token(cell_id)    
        cell_resolution = cell_id.level()
  
        num_edges = 4
        center_lat, center_lon, avg_edge_len, cell_area = geodesic_dggs_metrics(cell_polygon, num_edges)
        
        cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)    

              
        s2_feature = QgsFeature()
        s2_feature.setGeometry(cell_geometry)
        
        # Get all attributes from the input feature
        original_attributes = feature.attributes()
        original_fields = feature.fields()
        
        # Define new S2-related attributes
        new_fields = QgsFields()
        new_fields.append(QgsField("s2", QVariant.String))  # Dynamic cell ID field
        new_fields.append(QgsField("resolution", QVariant.Int))
        new_fields.append(QgsField("center_lat", QVariant.Double))
        new_fields.append(QgsField("center_lon", QVariant.Double))
        new_fields.append(QgsField("avg_edge_len", QVariant.Double))
        new_fields.append(QgsField("cell_area", QVariant.Double))

        # Combine original fields and new fields
        all_fields = QgsFields()
        for field in original_fields:
            all_fields.append(field)
        for field in new_fields:
            all_fields.append(field)
        
        s2_feature.setFields(all_fields)
        
        # Combine original attributes with new attributes
        new_attributes = [cell_token, cell_resolution, center_lat, center_lon, avg_edge_len, cell_area]
        all_attributes = original_attributes + new_attributes
        
        s2_feature.setAttributes(all_attributes)    

        s2_features.append(s2_feature)
        
        if feedback and i % 100 == 0:
            feedback.setProgress(int(100 * i / total_cells))

    if feedback:
        feedback.setProgress(100)
    
    return s2_features


#######################
# QgsFeatures to A5
#######################

def qgsfeature2a5(feature, resolution, predicate = None, compact=None, feedback=None):
    gfeature_geom = feature.geometry()
    if gfeature_geom.wkbType() == QgsWkbTypes.Point:
        return point2a5(feature, resolution,feedback)
    elif gfeature_geom.wkbType() == QgsWkbTypes.LineString: 
        return polyline2a5(feature, resolution,None,None,feedback)
    elif gfeature_geom.wkbType() == QgsWkbTypes.Polygon:
        return polygon2a5(feature, resolution,predicate,compact,feedback)
  
def point2a5(feature,resolution,feedback): 
    if feedback and feedback.isCanceled():
        return []
    # Convert point to the seed cell
    feature_geometry = feature.geometry()
    point = feature_geometry.asPoint()   
    a5_hex = latlon2a5(point.y(), point.x(), resolution)
    cell_polygon = a52geo(a5_hex)
    num_edges = 5
    center_lat, center_lon, avg_edge_len, cell_area = geodesic_dggs_metrics(cell_polygon, num_edges)
    
    cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)        
    # Create a single QGIS feature
    a5_feature = QgsFeature()
    a5_feature.setGeometry(cell_geometry)
    
    # Get all attributes from the input feature
    original_attributes = feature.attributes()
    original_fields = feature.fields()
    
    # Define new s2-related attributes
    new_fields = QgsFields()
    new_fields.append(QgsField("a5", QVariant.String))
    new_fields.append(QgsField("resolution", QVariant.Int))
    new_fields.append(QgsField("center_lat", QVariant.Double))
    new_fields.append(QgsField("center_lon", QVariant.Double))
    new_fields.append(QgsField("avg_edge_len", QVariant.Double))
    new_fields.append(QgsField("cell_area", QVariant.Double))
    
    # Combine original fields and new fields
    all_fields = QgsFields()
    for field in original_fields:
        all_fields.append(field)
    for field in new_fields:
        all_fields.append(field)
    
    a5_feature.setFields(all_fields)
    
    # Combine original attributes with new attributes
    new_attributes = [a5_hex, resolution, center_lat, center_lon, avg_edge_len, cell_area]
    all_attributes = original_attributes + new_attributes
    
    a5_feature.setAttributes(all_attributes)
    
    return [a5_feature]

def polyline2a5(feature, resolution, predicate=None, compact=None, feedback=None):  
    a5_features = []  

    feature_geometry = feature.geometry()
    shapely_geom = load_wkt(feature_geometry.asWkt())
    feature_rect = feature_geometry.boundingBox()
    min_lng = feature_rect.xMinimum()
    min_lat = feature_rect.yMinimum()
    max_lng = feature_rect.xMaximum()
    max_lat = feature_rect.yMaximum()
    # Calculate longitude and latitude width based on resolution
    if resolution == 0:
        lon_width = 40
        lat_width = 40
    elif resolution == 1:
        lon_width = 20
        lat_width = 20
    elif resolution == 2:
        lon_width = 10
        lat_width = 10
    elif resolution == 3:
        lon_width = 5
        lat_width = 5
    elif resolution > 3:
        base_width = 5  # at resolution 3
        factor = 0.5 ** (resolution - 3)
        lon_width = base_width * factor
        lat_width = base_width * factor
    
    # Generate longitude and latitude arrays
    longitudes = []
    latitudes = []
    
    lon = min_lng
    while lon < max_lng:
        longitudes.append(lon)
        lon += lon_width
    
    lat = min_lat
    while lat < max_lat:
        latitudes.append(lat)
        lat += lat_width
    
    seen_a5_hex = set()  # Track unique A5 hex codes
    
    if feedback:
        feedback.pushInfo(f"Processing feature {feature.id()}")   
        feedback.setProgress(0)
        
    total_cells = len(longitudes) * len(latitudes)
    
    # Generate and check each grid cell
    i = 0  # Counter for progress tracking
    for lon in longitudes:
        for lat in latitudes:
            i += 1  # Increment counter for each cell processed
            if feedback and feedback.isCanceled():
                return []
            min_lon = lon
            min_lat = lat
            max_lon = lon + lon_width
            max_lat = lat + lat_width
            
            # Calculate centroid
            centroid_lat = (min_lat + max_lat) / 2
            centroid_lon = (min_lon + max_lon) / 2            
            # Convert centroid to A5 cell ID using direct A5 functions
            a5_hex = latlon2a5(centroid_lat, centroid_lon, resolution)
            cell_polygon = a52geo(a5_hex)
            
            if cell_polygon is not None:
                if a5_hex not in seen_a5_hex:
                    seen_a5_hex.add(a5_hex)                        
                    if not check_predicate(cell_polygon, shapely_geom,"intersects"):
                        continue                                 
         
                    cell_resolution = a5.get_resolution(a5.hex_to_bigint(a5_hex))            
                    num_edges = 5
                    center_lat, center_lon, avg_edge_len, cell_area = geodesic_dggs_metrics(cell_polygon, num_edges)
                    
                    cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)    
                        
                    a5_feature = QgsFeature()
                    a5_feature.setGeometry(cell_geometry)
                    
                    # Get all attributes from the input feature
                    original_attributes = feature.attributes()
                    original_fields = feature.fields()
                    
                    # Define new S2-related attributes
                    new_fields = QgsFields()
                    new_fields.append(QgsField("a5", QVariant.String))  # Dynamic cell ID field
                    new_fields.append(QgsField("resolution", QVariant.Int))
                    new_fields.append(QgsField("center_lat", QVariant.Double))
                    new_fields.append(QgsField("center_lon", QVariant.Double))
                    new_fields.append(QgsField("avg_edge_len", QVariant.Double))
                    new_fields.append(QgsField("cell_area", QVariant.Double))

                    # Combine original fields and new fields
                    all_fields = QgsFields()
                    for field in original_fields:
                        all_fields.append(field)
                    for field in new_fields:
                        all_fields.append(field)
                    
                    a5_feature.setFields(all_fields)
                    
                    # Combine original attributes with new attributes
                    new_attributes = [a5_hex, cell_resolution, center_lat, center_lon, avg_edge_len, cell_area]
                    all_attributes = original_attributes + new_attributes
                    
                    a5_feature.setAttributes(all_attributes)    

                    a5_features.append(a5_feature)
                    
                    if feedback and i % 100 == 0:
                        feedback.setProgress(int(100 * i / total_cells))

    if feedback:
        feedback.setProgress(100)
    
    return a5_features


def polygon2a5(feature, resolution, predicate=None, compact=None, feedback=None):  
    a5_features = []  

    feature_geometry = feature.geometry()
    shapely_geom = load_wkt(feature_geometry.asWkt())
    feature_rect = feature_geometry.boundingBox()
    min_lng = feature_rect.xMinimum()
    min_lat = feature_rect.yMinimum()
    max_lng = feature_rect.xMaximum()
    max_lat = feature_rect.yMaximum()
    # Calculate longitude and latitude width based on resolution
    if resolution == 0:
        lon_width = 40
        lat_width = 40
    elif resolution == 1:
        lon_width = 20
        lat_width = 20
    elif resolution == 2:
        lon_width = 10
        lat_width = 10
    elif resolution == 3:
        lon_width = 5
        lat_width = 5
    elif resolution > 3:
        base_width = 5  # at resolution 3
        factor = 0.5 ** (resolution - 3)
        lon_width = base_width * factor
        lat_width = base_width * factor
    
    # Generate longitude and latitude arrays
    longitudes = []
    latitudes = []
    
    lon = min_lng
    while lon < max_lng:
        longitudes.append(lon)
        lon += lon_width
    
    lat = min_lat
    while lat < max_lat:
        latitudes.append(lat)
        lat += lat_width
    
    seen_a5_hex = set()  # Track unique A5 hex codes
    
    if feedback:
        feedback.pushInfo(f"Processing feature {feature.id()}")   
        feedback.setProgress(0)
        
    total_cells = len(longitudes) * len(latitudes)
    
    # Generate and check each grid cell
    i = 0  # Counter for progress tracking
    for lon in longitudes:
        for lat in latitudes:
            i += 1  # Increment counter for each cell processed
            if feedback and feedback.isCanceled():
                return []
            min_lon = lon
            min_lat = lat
            max_lon = lon + lon_width
            max_lat = lat + lat_width
            
            # Calculate centroid
            centroid_lat = (min_lat + max_lat) / 2
            centroid_lon = (min_lon + max_lon) / 2            
            # Convert centroid to A5 cell ID using direct A5 functions
            a5_hex = latlon2a5(centroid_lat, centroid_lon, resolution)
            cell_polygon = a52geo(a5_hex)
            
            if cell_polygon is not None:
                if a5_hex not in seen_a5_hex:
                    seen_a5_hex.add(a5_hex)                        
                    # Check if cell intersects with polygon
                    if not check_predicate(cell_polygon, shapely_geom,predicate):
                        continue                                 
         
                    cell_resolution = a5.get_resolution(a5.hex_to_bigint(a5_hex))            
                    num_edges = 5
                    center_lat, center_lon, avg_edge_len, cell_area = geodesic_dggs_metrics(cell_polygon, num_edges)
                    
                    cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)    
                        
                    a5_feature = QgsFeature()
                    a5_feature.setGeometry(cell_geometry)
                    
                    # Get all attributes from the input feature
                    original_attributes = feature.attributes()
                    original_fields = feature.fields()
                    
                    # Define new S2-related attributes
                    new_fields = QgsFields()
                    new_fields.append(QgsField("a5", QVariant.String))  # Dynamic cell ID field
                    new_fields.append(QgsField("resolution", QVariant.Int))
                    new_fields.append(QgsField("center_lat", QVariant.Double))
                    new_fields.append(QgsField("center_lon", QVariant.Double))
                    new_fields.append(QgsField("avg_edge_len", QVariant.Double))
                    new_fields.append(QgsField("cell_area", QVariant.Double))

                    # Combine original fields and new fields
                    all_fields = QgsFields()
                    for field in original_fields:
                        all_fields.append(field)
                    for field in new_fields:
                        all_fields.append(field)
                    
                    a5_feature.setFields(all_fields)
                    
                    # Combine original attributes with new attributes
                    new_attributes = [a5_hex, cell_resolution, center_lat, center_lon, avg_edge_len, cell_area]
                    all_attributes = original_attributes + new_attributes
                    
                    a5_feature.setAttributes(all_attributes)    

                    a5_features.append(a5_feature)
                    
                    if feedback and i % 100 == 0:
                        feedback.setProgress(int(100 * i / total_cells))

    if feedback:
        feedback.setProgress(100)
    
    # Apply compact mode if enabled
    if compact and a5_features:
        a5_features = a5compact_from_qgsfeatures(a5_features, feedback)
    
    return a5_features


def a5compact_from_qgsfeatures(qgs_features, feedback):    
    original_fields = qgs_features[0].fields()
    # Get original attributes from the first feature (excluding A5-specific fields)
    original_attributes = qgs_features[0].attributes()
    
    # Find the indices of A5-specific fields to exclude from original attributes
    a5_field_names = ['a5', 'resolution', 'center_lat', 'center_lon', 'avg_edge_len', 'cell_area']
    a5_field_indices = []
    for field_name in a5_field_names:
        field_index = original_fields.indexOf(field_name)
        if field_index >= 0:
            a5_field_indices.append(field_index)
    
    # Create list of original attributes excluding A5-specific fields
    preserved_attributes = []
    for i, attr in enumerate(original_attributes):
        if i not in a5_field_indices:
            preserved_attributes.append(attr)

    a5_ids = [f["a5"] for f in qgs_features if f["a5"]]

    a5_ids_compact = a5_compact(a5_ids)
    a5_features = []
    total_cells = len(a5_ids_compact)
    if feedback:
        feedback.pushInfo(f"Compacting cells")   
        feedback.setProgress(0)
        
    for i, a5_id_compact in enumerate(a5_ids_compact):
        if feedback and feedback.isCanceled():
            return []
        cell_polygon = a52geo(a5_id_compact)
        cell_resolution = a5.get_resolution(a5.hex_to_bigint(a5_id_compact))
        num_edges = 5  # A5 cells are pentagons
        center_lat, center_lon, avg_edge_len, cell_area = geodesic_dggs_metrics(cell_polygon, num_edges)
        cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)

        a5_feature = QgsFeature()
        a5_feature.setFields(original_fields)
        a5_feature.setGeometry(cell_geometry)

        # Set preserved original attributes
        attr_index = 0
        for j, attr in enumerate(original_attributes):
            if j not in a5_field_indices:
                a5_feature[original_fields[j].name()] = preserved_attributes[attr_index]
                attr_index += 1

        # Overwrite A5-specific attributes
        a5_feature['a5'] = a5_id_compact
        a5_feature['resolution'] = cell_resolution
        a5_feature['center_lat'] = center_lat
        a5_feature['center_lon'] = center_lon
        a5_feature['avg_edge_len'] = avg_edge_len
        a5_feature['cell_area'] = cell_area

        a5_features.append(a5_feature)
        if feedback and i % 100 == 0:
            feedback.setProgress(int(100 * i / total_cells))

    if feedback:
        feedback.setProgress(100)        

    return a5_features


######################
# QgsFeatures to rHEALPix
#######################
rhealpix_dggs = RHEALPixDGGS()

def qgsfeature2rhealpix(feature, resolution, predicate = None, compact=None,feedback=None):
    gfeature_geom = feature.geometry()
    if gfeature_geom.wkbType() == QgsWkbTypes.Point:
        return point2rhealpix(feature, resolution,feedback)
    elif gfeature_geom.wkbType() == QgsWkbTypes.LineString: 
        return polyline2rhealpix(feature, resolution,None,None,feedback)
    elif gfeature_geom.wkbType() == QgsWkbTypes.Polygon:
        return polygon2rhealpix(feature, resolution,predicate,compact,feedback)
    
def point2rhealpix(feature, resolution,feedback):
    if feedback and feedback.isCanceled():
        return []

    feature_geometry = feature.geometry()
    point = feature_geometry.asPoint()
    longitude = point.x()
    latitude = point.y()
    
    # Convert point to the seed cell
    seed_cell = rhealpix_dggs.cell_from_point(resolution, (longitude, latitude), plane=False)
    seed_cell_id = str(seed_cell)  # Unique identifier for the current cell
    seed_cell_polygon = rhealpix_cell_to_polygon(seed_cell)
        
    num_edges = 4
    if seed_cell.ellipsoidal_shape() == 'dart':
        num_edges = 3 
    center_lat, center_lon, avg_edge_len, cell_area = geodesic_dggs_metrics(seed_cell_polygon, num_edges)
        
    cell_geometry = QgsGeometry.fromWkt(seed_cell_polygon.wkt)
    
    # Create a single QGIS feature
    rhealpix_feature = QgsFeature()
    rhealpix_feature.setGeometry(cell_geometry)
    
    # Get all attributes from the input feature
    original_attributes = feature.attributes()
    original_fields = feature.fields()
    
    # Define new s2-related attributes
    new_fields = QgsFields()
    new_fields.append(QgsField("rhealpix", QVariant.String))
    new_fields.append(QgsField("resolution", QVariant.Int))
    new_fields.append(QgsField("center_lat", QVariant.Double))
    new_fields.append(QgsField("center_lon", QVariant.Double))
    new_fields.append(QgsField("avg_edge_len", QVariant.Double))
    new_fields.append(QgsField("cell_area", QVariant.Double))
    
    # Combine original fields and new fields
    all_fields = QgsFields()
    for field in original_fields:
        all_fields.append(field)
    for field in new_fields:
        all_fields.append(field)
    
    rhealpix_feature.setFields(all_fields)
    
    # Combine original attributes with new attributes
    new_attributes = [seed_cell_id,resolution, center_lat, center_lon, avg_edge_len, cell_area]
    all_attributes = original_attributes + new_attributes
    
    rhealpix_feature.setAttributes(all_attributes)
    
    return [rhealpix_feature]
    
def polyline2rhealpix(feature, resolution, predicate=None, compact=None, feedback=None):
    rhealpix_features = []     
    
    feature_geometry = feature.geometry()
    shapely_geom = load_wkt(feature_geometry.asWkt())

    feature_rect = feature_geometry.boundingBox()
    min_x = feature_rect.xMinimum()
    min_y = feature_rect.yMinimum()
    max_x = feature_rect.xMaximum()
    max_y = feature_rect.yMaximum()
    
    # Create a bounding box polygon
    bbox_polygon = box(min_x, min_y, max_x, max_y)

    bbox_center_lon = bbox_polygon.centroid.x
    bbox_center_lat = bbox_polygon.centroid.y
    seed_point = (bbox_center_lon, bbox_center_lat)

    seed_cell = rhealpix_dggs.cell_from_point(resolution, seed_point, plane=False)
    seed_cell_id = str(seed_cell)  # Unique identifier for the current cell
    seed_cell_polygon = rhealpix_cell_to_polygon(seed_cell)

    if seed_cell_polygon.contains(bbox_polygon):
        num_edges = 4
        if seed_cell.ellipsoidal_shape() == 'dart':
            num_edges = 3 
        center_lat, center_lon, avg_edge_len, cell_area = geodesic_dggs_metrics(seed_cell_polygon, num_edges)
        cell_resolution = resolution
        cell_geometry = QgsGeometry.fromWkt(seed_cell_polygon.wkt)
          # Create a single QGIS feature
        rhealpix_feature = QgsFeature()
        rhealpix_feature.setGeometry(cell_geometry)
        
        # Get all attributes from the input feature
        original_attributes = feature.attributes()
        original_fields = feature.fields()
        
        # Define new S2-related attributes
        new_fields = QgsFields()
        new_fields.append(QgsField("rhealpix", QVariant.String))  
        new_fields.append(QgsField("resolution", QVariant.Int))
        new_fields.append(QgsField("center_lat", QVariant.Double))
        new_fields.append(QgsField("center_lon", QVariant.Double))
        new_fields.append(QgsField("avg_edge_len", QVariant.Double))
        new_fields.append(QgsField("cell_area", QVariant.Double))
        
        # Combine original fields and new fields
        all_fields = QgsFields()
        for field in original_fields:
            all_fields.append(field)
        for field in new_fields:
            all_fields.append(field)
        
        rhealpix_feature.setFields(all_fields)
        
        # Combine original attributes with new attributes
        new_attributes = [seed_cell_id, cell_resolution, center_lat, center_lon, avg_edge_len, cell_area]
        all_attributes = original_attributes + new_attributes
        
        rhealpix_feature.setAttributes(all_attributes)    

        rhealpix_features.append(rhealpix_feature)
    
    else:
        # Initialize sets and queue
        covered_cells = set()  # Cells that have been processed (by their unique ID)
        queue = [seed_cell]  # Queue for BFS exploration
        while queue:
            if feedback and feedback.isCanceled():
                return []
            current_cell = queue.pop()
            current_cell_id = str(current_cell)  # Unique identifier for the current cell

            if current_cell_id in covered_cells:
                continue

            # Add current cell to the covered set
            covered_cells.add(current_cell_id)

            # Convert current cell to polygon
            cell_polygon = rhealpix_cell_to_polygon(current_cell)
            if not cell_polygon.intersects(bbox_polygon):
                continue
            # Get neighbors and add to queue
            neighbors = current_cell.neighbors(plane=False)
            for _, neighbor in neighbors.items():
                neighbor_id = str(neighbor)  # Unique identifier for the neighbor
                if neighbor_id not in covered_cells:
                    queue.append(neighbor)
        
        total_cells = len(covered_cells)

        if feedback:
            feedback.pushInfo(f"Processing feature {feature.id()}")   
            feedback.setProgress(0)
        
        for i, cell_id in enumerate(covered_cells):
            if feedback and feedback.isCanceled():
                return []
            
            rhealpix_uids = (cell_id[0],) + tuple(map(int, cell_id[1:]))
            rhelpix_cell = rhealpix_dggs.cell(rhealpix_uids)   
            cell_polygon = rhealpix_cell_to_polygon(rhelpix_cell)           
           
            num_edges = 4
            if seed_cell.ellipsoidal_shape() == 'dart':
                num_edges = 3 
            center_lat, center_lon, avg_edge_len, cell_area = geodesic_dggs_metrics(cell_polygon, num_edges)
            cell_resolution = rhelpix_cell.resolution
            cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)
            if not check_predicate(cell_polygon, shapely_geom, "intersects"):
                continue   
            # Create a single QGIS feature
            rhealpix_feature = QgsFeature()
            rhealpix_feature.setGeometry(cell_geometry)
            
            # Get all attributes from the input feature
            original_attributes = feature.attributes()
            original_fields = feature.fields()
            
            # Define new S2-related attributes
            new_fields = QgsFields()
            new_fields.append(QgsField("rhealpix", QVariant.String))  
            new_fields.append(QgsField("resolution", QVariant.Int))
            new_fields.append(QgsField("center_lat", QVariant.Double))
            new_fields.append(QgsField("center_lon", QVariant.Double))
            new_fields.append(QgsField("avg_edge_len", QVariant.Double))
            new_fields.append(QgsField("cell_area", QVariant.Double))
            
            # Combine original fields and new fields
            all_fields = QgsFields()
            for field in original_fields:
                all_fields.append(field)
            for field in new_fields:
                all_fields.append(field)
            
            rhealpix_feature.setFields(all_fields)
            
            # Combine original attributes with new attributes
            new_attributes = [cell_id, cell_resolution, center_lat, center_lon, avg_edge_len, cell_area]
            all_attributes = original_attributes + new_attributes
            
            rhealpix_feature.setAttributes(all_attributes)    

            rhealpix_features.append(rhealpix_feature)
            
            if feedback and i % 100 == 0:
                feedback.setProgress(int(100 * i / total_cells))

    if feedback:
        feedback.setProgress(100)
        
    return rhealpix_features

def polygon2rhealpix(feature, resolution, predicate=None, compact=None, feedback=None):
    rhealpix_features = []     
    
    feature_geometry = feature.geometry()
    shapely_geom = load_wkt(feature_geometry.asWkt())

    feature_rect = feature_geometry.boundingBox()
    min_x = feature_rect.xMinimum()
    min_y = feature_rect.yMinimum()
    max_x = feature_rect.xMaximum()
    max_y = feature_rect.yMaximum()
    
    # Create a bounding box polygon
    bbox_polygon = box(min_x, min_y, max_x, max_y)

    bbox_center_lon = bbox_polygon.centroid.x
    bbox_center_lat = bbox_polygon.centroid.y
    seed_point = (bbox_center_lon, bbox_center_lat)

    seed_cell = rhealpix_dggs.cell_from_point(resolution, seed_point, plane=False)
    seed_cell_id = str(seed_cell)  # Unique identifier for the current cell
    seed_cell_polygon = rhealpix_cell_to_polygon(seed_cell)

    if seed_cell_polygon.contains(bbox_polygon):
        num_edges = 4
        if seed_cell.ellipsoidal_shape() == 'dart':
            num_edges = 3 
        center_lat, center_lon, avg_edge_len, cell_area = geodesic_dggs_metrics(seed_cell_polygon, num_edges)
        cell_resolution = resolution
        cell_geometry = QgsGeometry.fromWkt(seed_cell_polygon.wkt)
          # Create a single QGIS feature
        rhealpix_feature = QgsFeature()
        rhealpix_feature.setGeometry(cell_geometry)
        
        # Get all attributes from the input feature
        original_attributes = feature.attributes()
        original_fields = feature.fields()
        
        # Define new S2-related attributes
        new_fields = QgsFields()
        new_fields.append(QgsField("rhealpix", QVariant.String))  
        new_fields.append(QgsField("resolution", QVariant.Int))
        new_fields.append(QgsField("center_lat", QVariant.Double))
        new_fields.append(QgsField("center_lon", QVariant.Double))
        new_fields.append(QgsField("avg_edge_len", QVariant.Double))
        new_fields.append(QgsField("cell_area", QVariant.Double))
        
        # Combine original fields and new fields
        all_fields = QgsFields()
        for field in original_fields:
            all_fields.append(field)
        for field in new_fields:
            all_fields.append(field)
        
        rhealpix_feature.setFields(all_fields)
        
        # Combine original attributes with new attributes
        new_attributes = [seed_cell_id, cell_resolution, center_lat, center_lon, avg_edge_len, cell_area]
        all_attributes = original_attributes + new_attributes
        
        rhealpix_feature.setAttributes(all_attributes)    

        rhealpix_features.append(rhealpix_feature)
    
    else:
        # Initialize sets and queue
        covered_cells = set()  # Cells that have been processed (by their unique ID)
        queue = [seed_cell]  # Queue for BFS exploration
        while queue:
            if feedback and feedback.isCanceled():
                return []
            current_cell = queue.pop()
            current_cell_id = str(current_cell)  # Unique identifier for the current cell

            if current_cell_id in covered_cells:
                continue

            # Add current cell to the covered set
            covered_cells.add(current_cell_id)

            # Convert current cell to polygon
            cell_polygon = rhealpix_cell_to_polygon(current_cell)
            if not cell_polygon.intersects(bbox_polygon):
                continue
            # Get neighbors and add to queue
            neighbors = current_cell.neighbors(plane=False)
            for _, neighbor in neighbors.items():
                neighbor_id = str(neighbor)  # Unique identifier for the neighbor
                if neighbor_id not in covered_cells:
                    queue.append(neighbor)
        if compact:
            # need to recheck
            covered_cells = rhealpix_compact(covered_cells)
        
        total_cells = len(covered_cells)

        if feedback:
            feedback.pushInfo(f"Processing feature {feature.id()}")   
            feedback.setProgress(0)
        
        for i, cell_id in enumerate(covered_cells):
            if feedback and feedback.isCanceled():
                return []
            
            rhealpix_uids = (cell_id[0],) + tuple(map(int, cell_id[1:]))
            rhelpix_cell = rhealpix_dggs.cell(rhealpix_uids)   
            cell_polygon = rhealpix_cell_to_polygon(rhelpix_cell)           
            if not check_predicate(cell_polygon, shapely_geom, predicate):
                continue

            num_edges = 4
            if seed_cell.ellipsoidal_shape() == 'dart':
                num_edges = 3 
            center_lat, center_lon, avg_edge_len, cell_area = geodesic_dggs_metrics(cell_polygon, num_edges)
            cell_resolution = rhelpix_cell.resolution
            cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)
            # Create a single QGIS feature
            rhealpix_feature = QgsFeature()
            rhealpix_feature.setGeometry(cell_geometry)
            
            # Get all attributes from the input feature
            original_attributes = feature.attributes()
            original_fields = feature.fields()
            
            # Define new S2-related attributes
            new_fields = QgsFields()
            new_fields.append(QgsField("rhealpix", QVariant.String))  
            new_fields.append(QgsField("resolution", QVariant.Int))
            new_fields.append(QgsField("center_lat", QVariant.Double))
            new_fields.append(QgsField("center_lon", QVariant.Double))
            new_fields.append(QgsField("avg_edge_len", QVariant.Double))
            new_fields.append(QgsField("cell_area", QVariant.Double))
            
            # Combine original fields and new fields
            all_fields = QgsFields()
            for field in original_fields:
                all_fields.append(field)
            for field in new_fields:
                all_fields.append(field)
            
            rhealpix_feature.setFields(all_fields)
            
            # Combine original attributes with new attributes
            new_attributes = [cell_id, cell_resolution, center_lat, center_lon, avg_edge_len, cell_area]
            all_attributes = original_attributes + new_attributes
            
            rhealpix_feature.setAttributes(all_attributes)    

            rhealpix_features.append(rhealpix_feature)
            
            if feedback and i % 100 == 0:
                feedback.setProgress(int(100 * i / total_cells))

    if feedback:
        feedback.setProgress(100)
        
    return rhealpix_features


#######################
# QgsFeatures to OpenEAGGR ISEA4T
#######################

def qgsfeature2isea4t(feature, resolution, predicate = None, compact=None,feedback=None):
    if (platform.system() == 'Windows'):
        feature_geom = feature.geometry()
        if feature_geom.wkbType() == QgsWkbTypes.Point:
            return point2isea4t(feature, resolution,feedback)
        elif feature_geom.wkbType() == QgsWkbTypes.LineString:
            return polyline2isea4t(feature, resolution,None,None,feedback)
        elif feature_geom.wkbType() == QgsWkbTypes.Polygon:
            return polygon2isea4t(feature, resolution,predicate,compact,feedback)

def point2isea4t(feature, resolution, feedback):    
    if feedback and feedback.isCanceled():
        return []
    
    feature_geometry = feature.geometry()
    point = feature_geometry.asPoint()
    longitude = point.x()
    latitude = point.y()    
    accuracy = ISEA4T_RES_ACCURACY_DICT.get(resolution)
    lat_long_point = LatLongPoint(latitude, longitude,accuracy)

    isea4t_cell = isea4t_dggs.convert_point_to_dggs_cell(lat_long_point)

    isea4t_id = isea4t_cell.get_cell_id() # Unique identifier for the current cell
    cell_polygon = isea4t2geo(isea4t_id)
    
    num_edges = 3
    center_lat, center_lon, avg_edge_len, cell_area = geodesic_dggs_metrics(cell_polygon, num_edges)
   
    cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)
    
    # Create a single QGIS feature
    isea4t_feature = QgsFeature()
    isea4t_feature.setGeometry(cell_geometry)
    
    # Get all attributes from the input feature
    original_attributes = feature.attributes()
    original_fields = feature.fields()
    
    # Define new s2-related attributes
    new_fields = QgsFields()
    new_fields.append(QgsField("isea4t", QVariant.String))
    new_fields.append(QgsField("resolution", QVariant.Int))
    new_fields.append(QgsField("center_lat", QVariant.Double))
    new_fields.append(QgsField("center_lon", QVariant.Double))
    new_fields.append(QgsField("avg_edge_len", QVariant.Double))
    new_fields.append(QgsField("cell_area", QVariant.Double))
    
    # Combine original fields and new fields
    all_fields = QgsFields()
    for field in original_fields:
        all_fields.append(field)
    for field in new_fields:
        all_fields.append(field)
    
    isea4t_feature.setFields(all_fields)
    
    # Combine original attributes with new attributes
    new_attributes = [isea4t_id, resolution, center_lat, center_lon,  avg_edge_len, cell_area]
    all_attributes = original_attributes + new_attributes
    
    isea4t_feature.setAttributes(all_attributes)
        
    return [isea4t_feature]
        
def polyline2isea4t(feature, resolution, predicate=None, compact=None, feedback=None):
    isea4t_features = [] 
    feature_geometry = feature.geometry()
    shapely_geom = load_wkt(feature_geometry.asWkt())

    feature_rect = feature_geometry.boundingBox()
    min_x = feature_rect.xMinimum()
    min_y = feature_rect.yMinimum()
    max_x = feature_rect.xMaximum()
    max_y = feature_rect.yMaximum()

    # Create a bounding box polygon
    bounding_box = box(min_x, min_y, max_x, max_y)
    bounding_box_wkt = bounding_box.wkt  # Create a bounding box polygon
    accuracy = ISEA4T_RES_ACCURACY_DICT.get(resolution)
    shapes = isea4t_dggs.convert_shape_string_to_dggs_shapes(bounding_box_wkt, ShapeStringFormat.WKT, accuracy)
    shape = shapes[0]
    # for shape in shapes:
    bbox_cells = shape.get_shape().get_outer_ring().get_cells()
    bounding_cell = isea4t_dggs.get_bounding_dggs_cell(bbox_cells)
    bounding_child_cells = get_isea4t_children_cells_within_bbox(bounding_cell.get_cell_id(), bounding_box,resolution)
   
    if compact:
        bounding_child_cells = isea4t_compact(bounding_child_cells)
    
    total_cells = len(bounding_child_cells)

    if feedback:
        feedback.pushInfo(f"Processing feature {feature.id()}")   
        feedback.setProgress(0)

    for i, child in enumerate(bounding_child_cells):
        if feedback and feedback.isCanceled():
            return []
        isea4t_id = child
        cell_polygon = isea4t2geo(isea4t_id)
        if not check_predicate(cell_polygon, shapely_geom, "intersects"):
            continue

        num_edges = 3
        center_lat, center_lon, avg_edge_len, cell_area = geodesic_dggs_metrics(cell_polygon, num_edges)
        cell_resolution = len(isea4t_id)-2
        cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)        
            
        # Create a single QGIS feature
        isea4t_feature = QgsFeature()
        isea4t_feature.setGeometry(cell_geometry)
        
        # Get all attributes from the input feature
        original_attributes = feature.attributes()
        original_fields = feature.fields()
        
        # Define new S2-related attributes
        new_fields = QgsFields()
        new_fields.append(QgsField("isea4t", QVariant.String))  
        new_fields.append(QgsField("resolution", QVariant.Int))
        new_fields.append(QgsField("center_lat", QVariant.Double))
        new_fields.append(QgsField("center_lon", QVariant.Double))
        new_fields.append(QgsField("avg_edge_len", QVariant.Double))
        new_fields.append(QgsField("cell_area", QVariant.Double))
        
        # Combine original fields and new fields
        all_fields = QgsFields()
        for field in original_fields:
            all_fields.append(field)
        for field in new_fields:
            all_fields.append(field)
        
        isea4t_feature.setFields(all_fields)
        
        # Combine original attributes with new attributes
        new_attributes = [isea4t_id, cell_resolution, center_lat, center_lon, avg_edge_len, cell_area]
        all_attributes = original_attributes + new_attributes
        
        isea4t_feature.setAttributes(all_attributes)    

        isea4t_features.append(isea4t_feature)
        
        if feedback and i % 100 == 0:
            feedback.setProgress(int(100 * i / total_cells))

    if feedback:
        feedback.setProgress(100)
    
    return isea4t_features


def polygon2isea4t(feature, resolution, predicate=None, compact=None, feedback=None):
    isea4t_features = [] 
    feature_geometry = feature.geometry()
    shapely_geom = load_wkt(feature_geometry.asWkt())

    feature_rect = feature_geometry.boundingBox()
    min_x = feature_rect.xMinimum()
    min_y = feature_rect.yMinimum()
    max_x = feature_rect.xMaximum()
    max_y = feature_rect.yMaximum()

    # Create a bounding box polygon
    bounding_box = box(min_x, min_y, max_x, max_y)
    bounding_box_wkt = bounding_box.wkt  # Create a bounding box polygon
    accuracy = ISEA4T_RES_ACCURACY_DICT.get(resolution)
    shapes = isea4t_dggs.convert_shape_string_to_dggs_shapes(bounding_box_wkt, ShapeStringFormat.WKT, accuracy)
    shape = shapes[0]
    # for shape in shapes:
    bbox_cells = shape.get_shape().get_outer_ring().get_cells()
    bounding_cell = isea4t_dggs.get_bounding_dggs_cell(bbox_cells)
    bounding_child_cells = get_isea4t_children_cells_within_bbox(bounding_cell.get_cell_id(), bounding_box,resolution)
   
    if compact:
        bounding_child_cells = isea4t_compact(bounding_child_cells)
    
    total_cells = len(bounding_child_cells)

    if feedback:
        feedback.pushInfo(f"Processing feature {feature.id()}")   
        feedback.setProgress(0)

    for i, child in enumerate(bounding_child_cells):
        if feedback and feedback.isCanceled():
            return []
        isea4t_id = child
        cell_polygon = isea4t2geo(isea4t_id)
        if not check_predicate(cell_polygon, shapely_geom, predicate):
            continue

        num_edges = 3
        center_lat, center_lon, avg_edge_len, cell_area = geodesic_dggs_metrics(cell_polygon, num_edges)
        cell_resolution = len(isea4t_id)-2
        cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)        
            
        # Create a single QGIS feature
        isea4t_feature = QgsFeature()
        isea4t_feature.setGeometry(cell_geometry)
        
        # Get all attributes from the input feature
        original_attributes = feature.attributes()
        original_fields = feature.fields()
        
        # Define new S2-related attributes
        new_fields = QgsFields()
        new_fields.append(QgsField("isea4t", QVariant.String))  
        new_fields.append(QgsField("resolution", QVariant.Int))
        new_fields.append(QgsField("center_lat", QVariant.Double))
        new_fields.append(QgsField("center_lon", QVariant.Double))
        new_fields.append(QgsField("avg_edge_len", QVariant.Double))
        new_fields.append(QgsField("cell_area", QVariant.Double))
        
        # Combine original fields and new fields
        all_fields = QgsFields()
        for field in original_fields:
            all_fields.append(field)
        for field in new_fields:
            all_fields.append(field)
        
        isea4t_feature.setFields(all_fields)
        
        # Combine original attributes with new attributes
        new_attributes = [isea4t_id, cell_resolution, center_lat, center_lon, avg_edge_len, cell_area]
        all_attributes = original_attributes + new_attributes
        
        isea4t_feature.setAttributes(all_attributes)    

        isea4t_features.append(isea4t_feature)
        
        if feedback and i % 100 == 0:
            feedback.setProgress(int(100 * i / total_cells))

    if feedback:
        feedback.setProgress(100)
    
    return isea4t_features


#######################
# QgsFeatures to OpenEAGGR ISEA3H
#######################
def qgsfeature2isea3h(feature, resolution, predicate = None, compact=None,feedback=None):
    if (platform.system() == 'Windows'):
        feature_geometry = feature.geometry()
        if feature_geometry.wkbType() == QgsWkbTypes.Point:
            return point2isea3h(feature, resolution,feedback)
        elif feature_geometry.wkbType() == QgsWkbTypes.LineString:
            return polyline2isea3h(feature, resolution,None,None,feedback)
        elif feature_geometry.wkbType() == QgsWkbTypes.Polygon:
            return polygon2isea3h(feature, resolution,predicate,compact,feedback)

def point2isea3h(feature, resolution,feedback):  
    if feedback and feedback.isCanceled():
        return []  
    feature_geometry = feature.geometry()
    point = feature_geometry.asPoint()
    longitude = point.x()
    latitude = point.y()    
    accuracy = ISEA3H_RES_ACCURACY_DICT.get(resolution)
    lat_long_point = LatLongPoint(latitude, longitude, accuracy)

    isea3h_cell = isea3h_dggs.convert_point_to_dggs_cell(lat_long_point)

    isea3h_id = isea3h_cell.get_cell_id() # Unique identifier for the current cell
    cell_polygon = isea3h_cell_to_polygon(isea3h_cell)
    
    num_edges = 6  
    cell_resolution = resolution  
    if cell_resolution == 0:
        num_edges = 3 # icosahedron faces
    center_lat, center_lon, avg_edge_len, cell_area = geodesic_dggs_metrics(cell_polygon, num_edges)
    
    cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)
    
    # Create a single QGIS feature
    isea3h_feature = QgsFeature()
    isea3h_feature.setGeometry(cell_geometry)
    
    # Get all attributes from the input feature
    original_attributes = feature.attributes()
    original_fields = feature.fields()
    
    # Define new s2-related attributes
    new_fields = QgsFields()
    new_fields.append(QgsField("isea3h", QVariant.String))
    new_fields.append(QgsField("resolution", QVariant.Int))
    new_fields.append(QgsField("center_lat", QVariant.Double))
    new_fields.append(QgsField("center_lon", QVariant.Double))
    new_fields.append(QgsField("avg_edge_len", QVariant.Double))
    new_fields.append(QgsField("cell_area", QVariant.Double))
    
    # Combine original fields and new fields
    all_fields = QgsFields()
    for field in original_fields:
        all_fields.append(field)
    for field in new_fields:
        all_fields.append(field)
    
    isea3h_feature.setFields(all_fields)
    
    # Combine original attributes with new attributes
    new_attributes = [isea3h_id, cell_resolution, center_lat, center_lon,  avg_edge_len, cell_area]
    all_attributes = original_attributes + new_attributes
    
    isea3h_feature.setAttributes(all_attributes)
    
    return [isea3h_feature]

def polyline2isea3h(feature, resolution, predicate=None, compact=None, feedback=None):
    isea3h_features = [] 
    
    feature_geometry = feature.geometry()
    shapely_geom  = load_wkt(feature_geometry.asWkt())
    feature_rect = feature_geometry.boundingBox()
    min_x = feature_rect.xMinimum()
    min_y = feature_rect.yMinimum()
    max_x = feature_rect.xMaximum()
    max_y = feature_rect.yMaximum()

    # Create a bounding box polygon
    bounding_box = box(min_x, min_y, max_x, max_y)
    bounding_box_wkt = bounding_box.wkt  # Create a bounding box polygon
    accuracy = ISEA3H_RES_ACCURACY_DICT.get(resolution)
    shapes = isea3h_dggs.convert_shape_string_to_dggs_shapes(bounding_box_wkt, ShapeStringFormat.WKT, accuracy)
    shape = shapes[0]
    # for shape in shapes:
    bbox_cells = shape.get_shape().get_outer_ring().get_cells()
    bounding_cell = isea3h_dggs.get_bounding_dggs_cell(bbox_cells)
    bounding_child_cells = get_isea3h_children_cells_within_bbox(bounding_cell.get_cell_id(), bounding_box,resolution)
    
    total_cells = len(bounding_child_cells)

    if feedback:
        feedback.pushInfo(f"Processing feature {feature.id()}")   
        feedback.setProgress(0)

    for i, child in enumerate(bounding_child_cells):
        if feedback and feedback.isCanceled():
            return []
        isea3h_cell = DggsCell(child)
        cell_polygon = isea3h_cell_to_polygon(isea3h_cell)
        if not check_predicate(cell_polygon, shapely_geom, "intersects"):
            continue
        isea3h_id = isea3h_cell.get_cell_id()        
        isea3h2point = isea3h_dggs.convert_dggs_cell_to_point(isea3h_cell)      
        cell_accuracy = isea3h2point._accuracy        
        cell_resolution  = ISEA3H_ACCURACY_RES_DICT.get(cell_accuracy)
        num_edges = 3 if cell_resolution == 0 else 6  
        center_lat, center_lon, avg_edge_len, cell_area = geodesic_dggs_metrics(cell_polygon, num_edges)
                
        cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)
        # Create a single QGIS feature
        isea3h_feature = QgsFeature()
        isea3h_feature.setGeometry(cell_geometry)
        
        # Get all attributes from the input feature
        original_attributes = feature.attributes()
        original_fields = feature.fields()
        
        # Define new S2-related attributes
        new_fields = QgsFields()
        new_fields.append(QgsField("isea3h", QVariant.String))  
        new_fields.append(QgsField("resolution", QVariant.Int))
        new_fields.append(QgsField("center_lat", QVariant.Double))
        new_fields.append(QgsField("center_lon", QVariant.Double))
        new_fields.append(QgsField("avg_edge_len", QVariant.Double))
        new_fields.append(QgsField("cell_area", QVariant.Double))
        
        # Combine original fields and new fields
        all_fields = QgsFields()
        for field in original_fields:
            all_fields.append(field)
        for field in new_fields:
            all_fields.append(field)
        
        isea3h_feature.setFields(all_fields)
        
        # Combine original attributes with new attributes
        new_attributes = [isea3h_id, cell_resolution, center_lat, center_lon, avg_edge_len, cell_area]
        all_attributes = original_attributes + new_attributes
        
        isea3h_feature.setAttributes(all_attributes)    

        isea3h_features.append(isea3h_feature)
        if feedback and i % 100 == 0:
                feedback.setProgress(int(100 * i / total_cells))

    if feedback:
        feedback.setProgress(100)
        
    return isea3h_features


def polygon2isea3h(feature, resolution, predicate=None, compact=None, feedback=None):
    isea3h_features = [] 
    
    feature_geometry = feature.geometry()
    shapely_geom  = load_wkt(feature_geometry.asWkt())
    feature_rect = feature_geometry.boundingBox()
    min_x = feature_rect.xMinimum()
    min_y = feature_rect.yMinimum()
    max_x = feature_rect.xMaximum()
    max_y = feature_rect.yMaximum()

    # Create a bounding box polygon
    bounding_box = box(min_x, min_y, max_x, max_y)
    bounding_box_wkt = bounding_box.wkt  # Create a bounding box polygon
    accuracy = ISEA3H_RES_ACCURACY_DICT.get(resolution)
    shapes = isea3h_dggs.convert_shape_string_to_dggs_shapes(bounding_box_wkt, ShapeStringFormat.WKT, accuracy)
    shape = shapes[0]
    # for shape in shapes:
    bbox_cells = shape.get_shape().get_outer_ring().get_cells()
    bounding_cell = isea3h_dggs.get_bounding_dggs_cell(bbox_cells)
    bounding_child_cells = get_isea3h_children_cells_within_bbox(bounding_cell.get_cell_id(), bounding_box,resolution)
    
    if compact:
        bounding_child_cells = isea3h_compact(bounding_child_cells)
    
    total_cells = len(bounding_child_cells)

    if feedback:
        feedback.pushInfo(f"Processing feature {feature.id()}")   
        feedback.setProgress(0)

    for i, child in enumerate(bounding_child_cells):
        if feedback and feedback.isCanceled():
            return []
        isea3h_cell = DggsCell(child)
        cell_polygon = isea3h_cell_to_polygon(isea3h_cell)
        if not check_predicate(cell_polygon, shapely_geom, predicate):
            continue

        isea3h_id = isea3h_cell.get_cell_id()        
        isea3h2point = isea3h_dggs.convert_dggs_cell_to_point(isea3h_cell)      
        cell_accuracy = isea3h2point._accuracy        
        cell_resolution  = ISEA3H_ACCURACY_RES_DICT.get(cell_accuracy)
       
        num_edges = 3 if cell_resolution == 0 else 6  
        center_lat, center_lon, avg_edge_len, cell_area = geodesic_dggs_metrics(cell_polygon, num_edges)
                
        cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)
        # Create a single QGIS feature
        isea3h_feature = QgsFeature()
        isea3h_feature.setGeometry(cell_geometry)
        
        # Get all attributes from the input feature
        original_attributes = feature.attributes()
        original_fields = feature.fields()
        
        # Define new S2-related attributes
        new_fields = QgsFields()
        new_fields.append(QgsField("isea3h", QVariant.String))  
        new_fields.append(QgsField("resolution", QVariant.Int))
        new_fields.append(QgsField("center_lat", QVariant.Double))
        new_fields.append(QgsField("center_lon", QVariant.Double))
        new_fields.append(QgsField("avg_edge_len", QVariant.Double))
        new_fields.append(QgsField("cell_area", QVariant.Double))
        
        # Combine original fields and new fields
        all_fields = QgsFields()
        for field in original_fields:
            all_fields.append(field)
        for field in new_fields:
            all_fields.append(field)
        
        isea3h_feature.setFields(all_fields)
        
        # Combine original attributes with new attributes
        new_attributes = [isea3h_id, cell_resolution, center_lat, center_lon, avg_edge_len, cell_area]
        all_attributes = original_attributes + new_attributes
        
        isea3h_feature.setAttributes(all_attributes)    

        isea3h_features.append(isea3h_feature)
        if feedback and i % 100 == 0:
                feedback.setProgress(int(100 * i / total_cells))

    if feedback:
        feedback.setProgress(100)
        
    return isea3h_features


#######################
# QgsFeatures to EASE-DGGS
#######################
def qgsfeature2ease(feature, resolution, predicate = None, compact=None,feedback=None):
    feature_geometry = feature.geometry()
    if feature_geometry.wkbType() == QgsWkbTypes.Point:
        return point2ease(feature, resolution,feedback)
    elif feature_geometry.wkbType() == QgsWkbTypes.LineString:
        return poly2ease(feature, resolution,None,None,feedback)
    elif feature_geometry.wkbType() == QgsWkbTypes.Polygon:
        return poly2ease(feature, resolution,predicate,compact,feedback)
        
def point2ease(feature, resolution,feedback):
    if feedback and feedback.isCanceled():
        return []  

    feature_geometry = feature.geometry()
    point = feature_geometry.asPoint()
    longitude = point.x()
    latitude = point.y()    
    ease_cell = geos_to_grid_ids([(longitude,latitude)],level = resolution)
    ease_id = ease_cell['result']['data'][0]

    level = int(ease_id[1])  # Get the level (e.g., 'L0' -> 0)
    # Get level specs
    level_spec = levels_specs[level]
    n_row = level_spec["n_row"]
    n_col = level_spec["n_col"]
        
    geo = grid_ids_to_geos([ease_id])
    center_lon, center_lat = geo['result']['data'][0] 

    cell_min_lat = center_lat - (180 / (2 * n_row))
    cell_max_lat = center_lat + (180 / (2 * n_row))
    cell_min_lon = center_lon - (360 / (2 * n_col))
    cell_max_lon = center_lon + (360 / (2 * n_col))

    cell_polygon = Polygon([
        [cell_min_lon, cell_min_lat],
        [cell_max_lon, cell_min_lat],
        [cell_max_lon, cell_max_lat],
        [cell_min_lon, cell_max_lat],
        [cell_min_lon, cell_min_lat]
     ])

    num_edges = 4
    center_lat, center_lon, avg_edge_len, cell_area = geodesic_dggs_metrics(cell_polygon,num_edges)  
  
    cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)
    
    # Create a single QGIS feature
    ease_feature = QgsFeature()
    ease_feature.setGeometry(cell_geometry)
    
    # Get all attributes from the input feature
    original_attributes = feature.attributes()
    original_fields = feature.fields()
    
    # Define new s2-related attributes
    new_fields = QgsFields()
    new_fields.append(QgsField("ease", QVariant.String))
    new_fields.append(QgsField("resolution", QVariant.Int))
    new_fields.append(QgsField("center_lat", QVariant.Double))
    new_fields.append(QgsField("center_lon", QVariant.Double))
    new_fields.append(QgsField("avg_edge_len", QVariant.Double))
    new_fields.append(QgsField("cell_area", QVariant.Double))
    
    # Combine original fields and new fields
    all_fields = QgsFields()
    for field in original_fields:
        all_fields.append(field)
    for field in new_fields:
        all_fields.append(field)
    
    ease_feature.setFields(all_fields)
    
    # Combine original attributes with new attributes
    new_attributes = [ease_id, resolution, center_lat, center_lon,  avg_edge_len, cell_area]
    all_attributes = original_attributes + new_attributes
    
    ease_feature.setAttributes(all_attributes)
    
    return [ease_feature]


def poly2ease(feature, resolution, predicate, compact,feedback):
    return []


#######################
# QgsFeatures to QTM
#######################

def qgsfeature2qtm(feature, resolution, predicate = None, compact=None,feedback=None):
    geometry = feature.geometry()
    if geometry.wkbType() == QgsWkbTypes.Point:
        return point2qtm(feature, resolution,feedback)
    elif geometry.wkbType() == QgsWkbTypes.LineString:
        return poly2qtm(feature, resolution,None,None,feedback)
    elif geometry.wkbType() == QgsWkbTypes.Polygon:
        return poly2qtm(feature, resolution,predicate,compact,feedback)
        
def point2qtm(feature, resolution,feedback):   
    if feedback and feedback.isCanceled():
        return []
    feature_geometry = feature.geometry()
    point = feature_geometry.asPoint()
    longitude = point.x()
    latitude = point.y()    
    
    qtm_id = qtm.latlon_to_qtm_id(latitude, longitude, resolution) 
    facet = qtm.qtm_id_to_facet(qtm_id)
    cell_polygon = qtm.constructGeometry(facet)   
    num_edges = 3
    center_lat, center_lon, avg_edge_len, cell_area = geodesic_dggs_metrics(cell_polygon, num_edges)    
    cell_resolution = resolution
    cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)    
   
    qtm_feature = QgsFeature()
    qtm_feature.setGeometry(cell_geometry)
    
    # Get all attributes from the input feature
    original_attributes = feature.attributes()
    original_fields = feature.fields()
    
    # Define new s2-related attributes
    new_fields = QgsFields()
    new_fields.append(QgsField("qtm", QVariant.String))
    new_fields.append(QgsField("resolution", QVariant.Int))
    new_fields.append(QgsField("center_lat", QVariant.Double))
    new_fields.append(QgsField("center_lon", QVariant.Double))
    new_fields.append(QgsField("avg_edge_len", QVariant.Double))
    new_fields.append(QgsField("cell_area", QVariant.Double))
    
    # Combine original fields and new fields
    all_fields = QgsFields()
    for field in original_fields:
        all_fields.append(field)
    for field in new_fields:
        all_fields.append(field)
    
    qtm_feature.setFields(all_fields)
    
    # Combine original attributes with new attributes
    new_attributes = [qtm_id, cell_resolution, center_lat, center_lon,  avg_edge_len, cell_area]
    all_attributes = original_attributes + new_attributes
    
    qtm_feature.setAttributes(all_attributes)
    
    return [qtm_feature]

def qtmcompact_from_qgsfeatures(qgs_features,feedback):    
    original_fields = qgs_features[0].fields()

    qtm_ids = [f["qtm"] for f in qgs_features if f["qtm"]]

    qtm_ids_compact = qtm_compact(qtm_ids)
    qtm_features = []
    total_cells = len(qtm_ids_compact)
    if feedback:
        feedback.pushInfo(f"Compacting cells")   
        feedback.setProgress(0)
        
    for i, qtm_id_compact in enumerate(qtm_ids_compact):
        if feedback and feedback.isCanceled():
            return []
        facet = qtm.qtm_id_to_facet(qtm_id_compact)
        cell_polygon = qtm.constructGeometry(facet)
        cell_resolution = len(qtm_id_compact)
        num_edges = 3
        center_lat, center_lon, avg_edge_len, cell_area = geodesic_dggs_metrics(cell_polygon, num_edges)
        cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)

        qtm_feature = QgsFeature()
        qtm_feature.setFields(original_fields)
        qtm_feature.setGeometry(cell_geometry)

        qtm_feature['qtm'] = qtm_id_compact
        qtm_feature['resolution'] = cell_resolution
        qtm_feature['center_lat'] = center_lat
        qtm_feature['center_lon'] = center_lon
        qtm_feature['avg_edge_len'] = avg_edge_len
        qtm_feature['cell_area'] = cell_area

        qtm_features.append(qtm_feature)
        if feedback and i % 100 == 0:
            feedback.setProgress(int(100 * i / total_cells))

    if feedback:
        feedback.setProgress(100)        

    return qtm_features

def poly2qtm(feature, resolution, predicate, compact,feedback):
    qtm_features = []
    
    feature_geometry = feature.geometry()    
    levelFacets = {}
    QTMID = {}
    
    if feedback:
        feedback.pushInfo(f"Processing feature {feature.id()}")   
        feedback.setProgress(0)

    for lvl in range(resolution):
        levelFacets[lvl] = []
        QTMID[lvl] = []

        if lvl == 0:
            initial_facets = [
                [p0_n180, p0_n90, p90_n90, p90_n180, p0_n180, True],
                [p0_n90, p0_p0, p90_p0, p90_n90, p0_n90, True],
                [p0_p0, p0_p90, p90_p90, p90_p0, p0_p0, True],
                [p0_p90, p0_p180, p90_p180, p90_p90, p0_p90, True],
                [n90_n180, n90_n90, p0_n90, p0_n180, n90_n180, False],
                [n90_n90, n90_p0, p0_p0, p0_n90, n90_n90, False],
                [n90_p0, n90_p90, p0_p90, p0_p0, n90_p0, False],
                [n90_p90, n90_p180, p0_p180, p0_p90, n90_p90, False],
            ]

            for i, facet in enumerate(initial_facets):
                QTMID[0].append(str(i + 1))
                facet_geom = qtm.constructGeometry(facet)
                num_edges = 3
                center_lat, center_lon, avg_edge_len, cell_area = geodesic_dggs_metrics(facet_geom, num_edges)    
                
                levelFacets[0].append(facet)
                cell_geometry = QgsGeometry.fromWkt(facet_geom.wkt)      
                
                keep = cell_geometry.intersects(feature_geometry)
                if predicate == 1:  # within
                    keep = cell_geometry.within(feature_geometry)
                elif predicate == 2:  # centroid_within
                    keep = cell_geometry.centroid().within(feature_geometry)
                elif predicate == 3:  # intersection >= 50% of cell area
                    if keep:  # Only check if they intersect
                        intersection_geom = cell_geometry.intersection(feature_geometry)
                        if intersection_geom and intersection_geom.area() > 0:
                            intersection_area = intersection_geom.area()
                            cell_area_qgis = cell_geometry.area()
                            keep = (intersection_area / cell_area_qgis) >= 0.5
                        else:
                            keep = False
                if keep and resolution == 1 :                                         
                    # Create a single QGIS feature
                    qtm_feature = QgsFeature()
                    qtm_feature.setGeometry(cell_geometry)
                    
                    # Get all attributes from the input feature
                    original_attributes = feature.attributes()
                    original_fields = feature.fields()
                    
                    # Define new S2-related attributes
                    new_fields = QgsFields()
                    new_fields.append(QgsField("qtm", QVariant.String))  
                    new_fields.append(QgsField("resolution", QVariant.Int))
                    new_fields.append(QgsField("center_lat", QVariant.Double))
                    new_fields.append(QgsField("center_lon", QVariant.Double))
                    new_fields.append(QgsField("avg_edge_len", QVariant.Double))
                    new_fields.append(QgsField("cell_area", QVariant.Double))
                    
                    # Combine original fields and new fields
                    all_fields = QgsFields()
                    for field in original_fields:
                        all_fields.append(field)
                    for field in new_fields:
                        all_fields.append(field)
                    
                    qtm_feature.setFields(all_fields)
                    
                    # Combine original attributes with new attributes
                    new_attributes = [QTMID[0][i], resolution, center_lat, center_lon, avg_edge_len, cell_area]
                    all_attributes = original_attributes + new_attributes
                    
                    qtm_feature.setAttributes(all_attributes)   
                    qtm_features.append(qtm_feature)                           
                    
                    if feedback:
                        feedback.setProgress(100)
                    return qtm_features            
        else:
            total_cells = len(levelFacets[lvl - 1])
            for i, pf in enumerate(levelFacets[lvl - 1]):
                if feedback and feedback.isCanceled():
                    return []
                subdivided_facets = qtm.divideFacet(pf)
                for j, subfacet in enumerate(subdivided_facets):
                    subfacet_geom = qtm.constructGeometry(subfacet)
                    cell_geometry = QgsGeometry.fromWkt(subfacet_geom.wkt) 
                    
                    keep = cell_geometry.intersects(feature_geometry)
                    if predicate == 1:  # within
                        keep = cell_geometry.within(feature_geometry)
                    elif predicate == 2:  # centroid_within
                        keep = cell_geometry.centroid().within(feature_geometry)
                    elif predicate == 3:  # intersection >= 50% of cell area
                        if keep:  # Only check if they intersect
                            intersection_geom = cell_geometry.intersection(feature_geometry)
                            if intersection_geom and intersection_geom.area() > 0:
                                intersection_area = intersection_geom.area()
                                cell_area_qgis = cell_geometry.area()
                                keep = (intersection_area / cell_area_qgis) >= 0.5
                    if keep:
                        new_id = QTMID[lvl - 1][i] + str(j)
                        QTMID[lvl].append(new_id)
                        levelFacets[lvl].append(subfacet)
                        if lvl == resolution - 1:  # Only store final resolution   
                            num_edges = 3
                            center_lat, center_lon, avg_edge_len, cell_area = geodesic_dggs_metrics(subfacet_geom, num_edges)    
                                         
                            # Create a single QGIS feature
                            qtm_feature = QgsFeature()
                            qtm_feature.setGeometry(cell_geometry)
                            
                            # Get all attributes from the input feature
                            original_attributes = feature.attributes()
                            original_fields = feature.fields()
                            
                            # Define new S2-related attributes
                            new_fields = QgsFields()
                            new_fields.append(QgsField("qtm", QVariant.String))  
                            new_fields.append(QgsField("resolution", QVariant.Int))
                            new_fields.append(QgsField("center_lat", QVariant.Double))
                            new_fields.append(QgsField("center_lon", QVariant.Double))
                            new_fields.append(QgsField("avg_edge_len", QVariant.Double))
                            new_fields.append(QgsField("cell_area", QVariant.Double))
                            
                            # Combine original fields and new fields
                            all_fields = QgsFields()
                            for field in original_fields:
                                all_fields.append(field)
                            for field in new_fields:
                                all_fields.append(field)
                            
                            qtm_feature.setFields(all_fields)
                            
                            # Combine original attributes with new attributes
                            new_attributes = [new_id, resolution, center_lat, center_lon, avg_edge_len, cell_area]
                            all_attributes = original_attributes + new_attributes
                            
                            qtm_feature.setAttributes(all_attributes)    

                            qtm_features.append(qtm_feature)   
                            if feedback and i % 100 == 0:
                                feedback.setProgress(int(100 * i / total_cells))

    if feedback:
        feedback.setProgress(100)
                                
    if compact: 
        qtm_features =  qtmcompact_from_qgsfeatures(qtm_features,feedback)                 
    
    return qtm_features
        
#######################
# QgsFeatures to OLC
#######################
def qgsfeature2olc(feature, resolution, predicate = None, compact=None,feedback=None):
    geometry = feature.geometry()
    if geometry.wkbType() == QgsWkbTypes.Point:
        return point2olc(feature, resolution,feedback)
    elif geometry.wkbType() == QgsWkbTypes.LineString:
        return poly2olc(feature, resolution,None,None,feedback)
    elif geometry.wkbType() == QgsWkbTypes.Polygon:
        return poly2olc(feature, resolution,predicate,compact,feedback)

def point2olc(feature, resolution,feedback):
    if feedback and feedback.isCanceled():
        return []
       
    feature_geometry = feature.geometry()
    point = feature_geometry.asPoint()
    longitude = point.x()
    latitude = point.y()    
    olc_id = olc.encode(latitude, longitude, resolution) 
    coord = olc.decode(olc_id)   

    # Create the bounding box coordinates for the polygon
    min_lat, min_lon = coord.latitudeLo, coord.longitudeLo
    max_lat, max_lon = coord.latitudeHi, coord.longitudeHi    
    
    cell_polygon = Polygon([
        [min_lon, min_lat],  # Bottom-left corner
        [max_lon, min_lat],  # Bottom-right corner
        [max_lon, max_lat],  # Top-right corner
        [min_lon, max_lat],  # Top-left corner
        [min_lon, min_lat]   # Closing the polygon (same as the first point)
    ])
    cell_resolution = resolution
    center_lat, center_lon, cell_width, cell_height, cell_area = graticule_dggs_metrics(cell_polygon)    

    # Get all attributes from the input feature
    original_attributes = feature.attributes()
    original_fields = feature.fields()
    
    new_fields = QgsFields()
    new_fields.append(QgsField("olc", QVariant.String))
    new_fields.append(QgsField("resolution", QVariant.Int))
    new_fields.append(QgsField("center_lat", QVariant.Double))
    new_fields.append(QgsField("center_lon", QVariant.Double))
    new_fields.append(QgsField("cell_width", QVariant.Double))
    new_fields.append(QgsField("cell_height", QVariant.Double))
    new_fields.append(QgsField("cell_area", QVariant.Double))
    
    # Combine original fields and new fields
    all_fields = QgsFields()
    for field in original_fields:
        all_fields.append(field)
    for field in new_fields:
        all_fields.append(field)
    
    cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt) 
    olc_feature = QgsFeature()
    olc_feature.setGeometry(cell_geometry)
    olc_feature.setFields(all_fields)
    
    # Combine original attributes with new attributes
    new_attributes = [olc_id, cell_resolution, center_lat, center_lon, cell_width, cell_height,cell_area]
    all_attributes = original_attributes + new_attributes
    
    olc_feature.setAttributes(all_attributes)    
    
    return [olc_feature]
        
def olc_generate_grid(resolution):
    """
    Generate a global grid of Open Location Codes (Plus Codes) at the specified precision
    as a GeoJSON-like feature collection.
    """
    # Define the boundaries of the world
    sw_lat, sw_lng = -90, -180
    ne_lat, ne_lng = 90, 180

    # Get the precision step size
    area = olc.decode(olc.encode(sw_lat, sw_lng, resolution))
    lat_step = area.latitudeHi - area.latitudeLo
    lng_step = area.longitudeHi - area.longitudeLo

    olc_features = []

    lat = sw_lat
    while lat < ne_lat:
        lng = sw_lng
        while lng < ne_lng:
            # Generate the Plus Code for the center of the cell
            center_lat = lat + lat_step / 2
            center_lon = lng + lng_step / 2
            olc_id = olc.encode(center_lat, center_lon, resolution)
            resolution = olc.decode(olc_id).codeLength
            cell_polygon = Polygon([
                        [lng, lat],  # SW
                        [lng, lat + lat_step],  # NW
                        [lng + lng_step, lat + lat_step],  # NE
                        [lng + lng_step, lat],  # SE
                        [lng, lat]  # Close the polygon
                ])            
            # Create the feature
            olc_features.append({
                "type": "Feature",
                "geometry": mapping(cell_polygon),
                "properties": {
                    "olc": olc_id,
                    "resolution": resolution
                    }
            })

            lng += lng_step
        lat += lat_step

    # Return the feature collection
    return {
        "type": "FeatureCollection",
        "features": olc_features
    }


def olc_refine_cell(bounds, current_resolution, target_resolution, bbox_poly):
    """
    Refine a cell defined by bounds to the target resolution, recursively refining intersecting cells.
    """
    min_lon, min_lat, max_lon, max_lat = bounds
    if current_resolution < 10:
        valid_resolution = current_resolution + 2
    else: valid_resolution = current_resolution + 1

    area = olc.decode(olc.encode(min_lat, min_lon, valid_resolution))
    lat_step = area.latitudeHi - area.latitudeLo
    lng_step = area.longitudeHi - area.longitudeLo

    olc_features = []

    lat = min_lat
    while lat < max_lat:
        lng = min_lon
        while lng < max_lon:
            # Define the bounds of the finer cell
            finer_cell_bounds = (lng, lat, lng + lng_step, lat + lat_step)
            finer_cell_poly = box(*finer_cell_bounds)

            if bbox_poly.intersects(finer_cell_poly):
                # Generate the Plus Code for the center of the finer cell
                center_lat = lat + lat_step / 2
                center_lon = lng + lng_step / 2
                olc_id = olc.encode(center_lat, center_lon, valid_resolution)
                resolution = olc.decode(olc_id).codeLength
                
                cell_polygon = Polygon([
                        [lng, lat],  # SW
                        [lng, lat + lat_step],  # NW
                        [lng + lng_step, lat + lat_step],  # NE
                        [lng + lng_step, lat],  # SE
                        [lng, lat]  # Close the polygon
                ])           
                
                # Add the finer cell as a feature
                olc_features.append({
                "type": "Feature",
                "geometry": mapping(cell_polygon),
                "properties": {
                    "olc": olc_id,
                    "resolution": resolution
                    }
                })

                # Recursively refine the cell if not at target resolution
                if valid_resolution < target_resolution:
                    olc_features.extend(
                        olc_refine_cell(
                            finer_cell_bounds,
                            valid_resolution,
                            target_resolution,
                            bbox_poly
                        )
                    )

            lng += lng_step
        lat += lat_step

    return olc_features


def olccompact_from_qgsfeatures(qgs_features, feedback):
    original_fields = qgs_features[0].fields()
    olc_ids = [f["olc"] for f in qgs_features if f["olc"]]
    olc_ids_compact = olc_compact(olc_ids)
    olc_features = []
    
    total_cells = len(olc_ids_compact)
    if feedback:
        feedback.pushInfo(f"Compacting cells")   
        feedback.setProgress(0)
        
    for i, olc_id_compact in enumerate(olc_ids_compact): 
        if feedback and feedback.isCanceled():
            return []       
        coord = olc.decode(olc_id_compact)    
        min_lat, min_lon = coord.latitudeLo, coord.longitudeLo
        max_lat, max_lon = coord.latitudeHi, coord.longitudeHi        
        cell_resolution = coord.codeLength 

        # Define the polygon based on the bounding box
        cell_polygon = Polygon([
            [min_lon, min_lat],  # Bottom-left corner
            [max_lon, min_lat],  # Bottom-right corner
            [max_lon, max_lat],  # Top-right corner
            [min_lon, max_lat],  # Top-left corner
            [min_lon, min_lat]   # Closing the polygon (same as the first point)
        ])
        center_lat, center_lon, cell_width, cell_height, cell_area = graticule_dggs_metrics(cell_polygon) 
        
        cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)

        olc_feature = QgsFeature()
        olc_feature.setFields(original_fields)
        olc_feature.setGeometry(cell_geometry)

        olc_feature['olc'] = olc_id_compact
        olc_feature['resolution'] = cell_resolution
        olc_feature['center_lat'] = center_lat
        olc_feature['center_lon'] = center_lon
        olc_feature['cell_width'] = cell_width
        olc_feature['cell_height'] = cell_height
        olc_feature['cell_area'] = cell_area

        olc_features.append(olc_feature)
        if feedback and i % 100 == 0:
            feedback.setProgress(int(100 * i / total_cells))

    if feedback:
        feedback.setProgress(100)
   
    return olc_features

def poly2olc(feature, resolution, predicate, compact,feedback):
    olc_features = []
    
    feature_geometry = feature.geometry()
    feature_shapely = wkt_loads(feature_geometry.asWkt())
    fields = QgsFields()
    fields.append(QgsField("resolution", QVariant.Int))
    fields.append(QgsField("olc", QVariant.String))

    base_resolution = 2
    base_cells = olc_generate_grid(base_resolution)

    seed_cells = []
    for base_cell in base_cells["features"]:
        base_cell_poly = Polygon(base_cell["geometry"]["coordinates"][0])
        if base_cell_poly.intersects(feature_shapely):
            seed_cells.append(base_cell)

    refined_features = []
    for seed_cell in seed_cells:
        seed_cell_poly = Polygon(seed_cell["geometry"]["coordinates"][0])

        if seed_cell_poly.contains(feature_shapely) and resolution == base_resolution:
            refined_features.append(seed_cell)
        else:
            refined_features.extend(
                olc_refine_cell(seed_cell_poly.bounds, base_resolution, resolution, feature_shapely)
            )

    resolution_features = [
        refine_feature for refine_feature in refined_features if refine_feature["properties"]["resolution"] == resolution
    ]

    seen_olc_ids = set()
    total_cells = len (resolution_features)
    if feedback:
        feedback.pushInfo(f"Processing feature {feature.id()}")   
        feedback.setProgress(0)

    for i, resolution_feature in enumerate(resolution_features):
        if feedback and feedback.isCanceled():
            return []  
        olc_id = resolution_feature["properties"]["olc"]
        if olc_id not in seen_olc_ids:
            seen_olc_ids.add(olc_id)
            
            cell_polygon = Polygon(resolution_feature["geometry"]["coordinates"][0])
            olc_id = resolution_feature["properties"]["olc"]
            cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)

            # Predicate-based filtering
            keep = cell_geometry.intersects(feature_geometry)
            if predicate == 1:  # within
                keep = cell_geometry.within(feature_geometry)
            elif predicate == 2:  # centroid_within
                keep = cell_geometry.centroid().within(feature_geometry)
            elif predicate == 3:  # intersection >= 50% of cell area
                if keep:  # Only check if they intersect
                    intersection_geom = cell_geometry.intersection(feature_geometry)
                    if intersection_geom and intersection_geom.area() > 0:
                        intersection_area = intersection_geom.area()
                        cell_area_qgis = cell_geometry.area()
                        keep = (intersection_area / cell_area_qgis) >= 0.5
                    else:
                        keep = False
            
            if not keep:
                continue  # Skip non-matching cells

            # Compute additional attributes
            cell_resolution = resolution
            center_lat, center_lon, cell_width, cell_height, cell_area = graticule_dggs_metrics(cell_polygon)

            olc_feature = QgsFeature()
            olc_feature.setGeometry(cell_geometry)

            original_attributes = feature.attributes()
            original_fields = feature.fields()
            
            new_fields = QgsFields()
            new_fields.append(QgsField("olc", QVariant.String))
            new_fields.append(QgsField("resolution", QVariant.Int))
            new_fields.append(QgsField("center_lat", QVariant.Double))
            new_fields.append(QgsField("center_lon", QVariant.Double))
            new_fields.append(QgsField("cell_width", QVariant.Double))
            new_fields.append(QgsField("cell_height", QVariant.Double))
            new_fields.append(QgsField("cell_area", QVariant.Double))

            
            # Combine original fields and new fields
            all_fields = QgsFields()
            for field in original_fields:
                all_fields.append(field)
            for field in new_fields:
                all_fields.append(field)
            
            cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt) 
            olc_feature = QgsFeature()
            olc_feature.setGeometry(cell_geometry)
            olc_feature.setFields(all_fields)
            
            # Combine original attributes with new attributes
            new_attributes = [olc_id, cell_resolution, center_lat, center_lon, cell_width, cell_height, cell_area]
            all_attributes = original_attributes + new_attributes
            
            olc_feature.setAttributes(all_attributes)    
            
            # Create QgsFeature
            olc_features.append(olc_feature)
            if feedback and i % 100 == 0:
                feedback.setProgress(int(100 * i / total_cells))

    if feedback:
        feedback.setProgress(100) 
        
    if compact: 
        olc_features =  olccompact_from_qgsfeatures(olc_features, feedback)                 
    
    return olc_features


#######################
# QgsFeatures to Geohash
#######################
def qgsfeature2geohash(feature, resolution, predicate = None, compact=None,feedback=None):
    geometry = feature.geometry()
    if geometry.wkbType() == QgsWkbTypes.Point:
        return point2geohash(feature, resolution,feedback)
    elif geometry.wkbType() == QgsWkbTypes.LineString:
        return poly2geohash(feature, resolution,None,None,feedback)  
    elif geometry.wkbType() == QgsWkbTypes.Polygon:
        return poly2geohash(feature, resolution,predicate,compact,feedback)


def point2geohash(feature, resolution,feedback):
    if feedback and feedback.isCanceled():
        return []

    feature_geometry = feature.geometry()
    point = feature_geometry.asPoint()
    longitude = point.x()
    latitude = point.y()    
    geohash_id = geohash.encode(latitude, longitude, resolution)
    bbox =  geohash.bbox(geohash_id)
    min_lat, min_lon = bbox['s'], bbox['w']  # Southwest corner
    max_lat, max_lon = bbox['n'], bbox['e']  # Northeast corner    
    # Define the polygon based on the bounding box
    cell_polygon = Polygon([
        [min_lon, min_lat],  # Bottom-left corner
        [max_lon, min_lat],  # Bottom-right corner
        [max_lon, max_lat],  # Top-right corner
        [min_lon, max_lat],  # Top-left corner
        [min_lon, min_lat]   # Closing the polygon (same as the first point)
    ])        
    
    center_lat, center_lon, cell_width, cell_height, cell_area = graticule_dggs_metrics(cell_polygon)  
    cell_resolution = resolution
    cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)    
    # Create a single QGIS feature
    geohash_feature = QgsFeature()
    geohash_feature.setGeometry(cell_geometry)
    
    # Get all attributes from the input feature
    original_attributes = feature.attributes()
    original_fields = feature.fields()
    
    new_fields = QgsFields()
    new_fields.append(QgsField("geohash", QVariant.String))
    new_fields.append(QgsField("resolution", QVariant.Int))
    new_fields.append(QgsField("center_lat", QVariant.Double))
    new_fields.append(QgsField("center_lon", QVariant.Double))
    new_fields.append(QgsField("cell_width", QVariant.Double))
    new_fields.append(QgsField("cell_height", QVariant.Double))
    new_fields.append(QgsField("cell_area", QVariant.Double))
    
    # Combine original fields and new fields
    all_fields = QgsFields()
    for field in original_fields:
        all_fields.append(field)
    for field in new_fields:
        all_fields.append(field)
    
    geohash_feature.setFields(all_fields)
    
    # Combine original attributes with new attributes
    new_attributes = [geohash_id, cell_resolution, center_lat, center_lon,  cell_width, cell_height, cell_area]
    all_attributes = original_attributes + new_attributes
    
    geohash_feature.setAttributes(all_attributes)
    
    return [geohash_feature]


def geohashcompact_from_qgsfeatures(qgs_features, feedback):
    original_fields = qgs_features[0].fields()

    geohash_ids = [f["geohash"] for f in qgs_features if f["geohash"]]

    geohash_ids_compact = geohash_compact(geohash_ids)
    geohash_features = []
      
    total_cells = len(geohash_ids_compact)
    if feedback:
        feedback.pushInfo(f"Compacting cells")   
        feedback.setProgress(0)
        
    for i, geohash_id_compact in enumerate(geohash_ids_compact):  
        if feedback and feedback.isCanceled():
            return []      
        cell_polygon = geohash2geo(geohash_id_compact)
        cell_resolution =  len(geohash_id_compact)
        
        center_lat, center_lon, cell_width, cell_height, cell_area = graticule_dggs_metrics(cell_polygon) 
        
        cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)

        geohash_feature = QgsFeature()
        geohash_feature.setFields(original_fields)
        geohash_feature.setGeometry(cell_geometry)

        geohash_feature['geohash'] = geohash_id_compact
        geohash_feature['resolution'] = cell_resolution
        geohash_feature['center_lat'] = center_lat
        geohash_feature['center_lon'] = center_lon
        geohash_feature['cell_width'] = cell_width
        geohash_feature['cell_height'] = cell_height
        geohash_feature['cell_area'] = cell_area

        geohash_features.append(geohash_feature)
        if feedback and i % 100 == 0:
            feedback.setProgress(int(100 * i / total_cells))

    if feedback:
        feedback.setProgress(100)      

    return geohash_features


def poly2geohash(feature, resolution, predicate, compact, feedback):    
    geohash_features = []
    feature_geometry = feature.geometry()    
    feature_shapely = wkt_loads(feature_geometry.asWkt())

    intersected_geohashes = {gh for gh in INITIAL_GEOHASHES if geohash2geo(gh).intersects(feature_shapely)}
        # Expand geohash bounding box
   
    geohashes = set()
    for gh in intersected_geohashes:
        expand_geohash_bbox(gh, resolution, geohashes, feature_shapely)

    if feedback:
        feedback.pushInfo(f"Processing feature {feature.id()}")   
        feedback.setProgress(0)

    total_cells = len(geohashes)   
    
    # Step 4: Generate features for geohashes that intersect the bounding box
    for i, gh in enumerate(geohashes):
        if feedback and feedback.isCanceled():
            return []
        
        cell_polygon = geohash2geo(gh)
        # if cell_polygon.intersects(feature):
        cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)    
        # Predicate-based filtering
        keep = cell_geometry.intersects(feature_geometry)
        if predicate == 1:  # within
            keep = cell_geometry.within(feature_geometry)
        elif predicate == 2:  # centroid_within
            keep = cell_geometry.centroid().within(feature_geometry)
        elif predicate == 3:  # intersection >= 50% of cell area
            if keep:  # Only check if they intersect
                intersection_geom = cell_geometry.intersection(feature_geometry)
                if intersection_geom and intersection_geom.area() > 0:
                    intersection_area = intersection_geom.area()
                    cell_area_qgis = cell_geometry.area()
                    keep = (intersection_area / cell_area_qgis) >= 0.5
                else:
                    keep = False
        
        if not keep:
            continue  # Skip non-matching cells
        
        # Create a single QGIS feature
        geohash_feature = QgsFeature()
        geohash_feature.setGeometry(cell_geometry)
        
        center_lat, center_lon, cell_width, cell_height, cell_area = graticule_dggs_metrics(cell_polygon)  
        cell_resolution = resolution
            
        # Get all attributes from the input feature
        original_attributes = feature.attributes()
        original_fields = feature.fields()
        
        new_fields = QgsFields()
        new_fields.append(QgsField("geohash", QVariant.String))
        new_fields.append(QgsField("resolution", QVariant.Int))
        new_fields.append(QgsField("center_lat", QVariant.Double))
        new_fields.append(QgsField("center_lon", QVariant.Double))
        new_fields.append(QgsField("cell_width", QVariant.Double))
        new_fields.append(QgsField("cell_height", QVariant.Double))
        new_fields.append(QgsField("cell_area", QVariant.Double))
        
        # Combine original fields and new fields
        all_fields = QgsFields()
        for field in original_fields:
            all_fields.append(field)
        for field in new_fields:
            all_fields.append(field)
        
        geohash_feature.setFields(all_fields)
        
        # Combine original attributes with new attributes
        new_attributes = [gh,cell_resolution, center_lat, center_lon,  cell_width, cell_height, cell_area]
        all_attributes = original_attributes + new_attributes
        
        geohash_feature.setAttributes(all_attributes)    

        geohash_features.append(geohash_feature)
        
        if feedback and i % 100 == 0:
            feedback.setProgress(int(100 * i / total_cells))

    if feedback:
        feedback.setProgress(100)      

            
    if compact: 
        geohash_features =  geohashcompact_from_qgsfeatures(geohash_features,feedback)                 
    
    return geohash_features
    

#######################
# QgsFeatures to GEOREF
#######################
def qgsfeature2georef(feature, resolution, predicate = None, compact=None,feedback=None):
    geometry = feature.geometry()
    if geometry.wkbType() == QgsWkbTypes.Point:
        return point2georef(feature, resolution,feedback)
    elif geometry.wkbType() == QgsWkbTypes.LineString:
        return poly2georef(feature, resolution,None,None,feedback)
    elif geometry.wkbType() == QgsWkbTypes.Polygon:
        return poly2georef(feature, resolution,predicate,compact,feedback)

def georef_to_polygon(georef_id):
    center_lat, center_lon, min_lat, min_lon, max_lat, max_lon, resolution = georef.georefcell(georef_id)
    cell_polygon = Polygon([
        [min_lon, min_lat],  # Bottom-left corner
        [max_lon, min_lat],  # Bottom-right corner
        [max_lon, max_lat],  # Top-right corner
        [min_lon, max_lat],  # Top-left corner
        [min_lon, min_lat]   # Closing the polygon (same as the first point)
    ])
    return cell_polygon

def point2georef(feature, resolution,feedback):
    if feedback and feedback.isCanceled():
        return []
    feature_geometry = feature.geometry()
    point = feature_geometry.asPoint()
    longitude = point.x()
    latitude = point.y()  
    georef_id = latlon2dggs.latlon2georef(latitude, longitude, resolution)  
    center_lat, center_lon, min_lat, min_lon, max_lat, max_lon,resolution = georef.georefcell(georef_id)        
    cell_polygon = Polygon([
        [min_lon, min_lat],  # Bottom-left corner
        [max_lon, min_lat],  # Bottom-right corner
        [max_lon, max_lat],  # Top-right corner
        [min_lon, max_lat],  # Top-left corner
        [min_lon, min_lat]   # Closing the polygon (same as the first point)
    ])

    center_lat, center_lon, cell_width, cell_height, cell_area = graticule_dggs_metrics(cell_polygon)
    cell_resolution = resolution
    # Get all attributes from the input feature
    original_attributes = feature.attributes()
    original_fields = feature.fields()
    
    # Define new H3-related attributes
    new_fields = QgsFields()
    new_fields.append(QgsField("georef", QVariant.String))
    new_fields.append(QgsField("resolution", QVariant.Int))
    new_fields.append(QgsField("center_lat", QVariant.Double))
    new_fields.append(QgsField("center_lon", QVariant.Double))
    new_fields.append(QgsField("cell_width", QVariant.Double))
    new_fields.append(QgsField("cell_height", QVariant.Double))
    new_fields.append(QgsField("cell_area", QVariant.Double))
    
    # Combine original fields and new fields
    all_fields = QgsFields()
    for field in original_fields:
        all_fields.append(field)
    for field in new_fields:
        all_fields.append(field)
    
    cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt) 
    georef_feature = QgsFeature()
    georef_feature.setGeometry(cell_geometry)
    georef_feature.setFields(all_fields)
    
    # Combine original attributes with new attributes
    new_attributes = [georef_id, cell_resolution, center_lat, center_lon, cell_width, cell_height,cell_area]
    all_attributes = original_attributes + new_attributes
    
    georef_feature.setAttributes(all_attributes)     
    return [georef_feature]
    
   
def poly2georef(feature, resolution, predicate, compact, feedback):
    georef_features = []
    feature_geometry = feature.geometry()
    feature_rect = feature_geometry.boundingBox()
    min_x = feature_rect.xMinimum()
    min_y = feature_rect.yMinimum()
    max_x = feature_rect.xMaximum()
    max_y = feature_rect.yMaximum()

    bounding_box = box(min_x, min_y, max_x, max_y)
    minx, miny, maxx, maxy = bounding_box.bounds
    bbox_center = ((minx + maxx) / 2, (miny + maxy) / 2)
    center_georef = georef.encode(bbox_center[1], bbox_center[0], resolution)

    # Step 2: Find the ancestor georef that fully contains the bounding box
    def find_ancestor_georef(center_georef, bbox):
        for r in range(1, len(center_georef) + 1):
            ancestor = center_georef[:r]
            polygon = georef_to_polygon(ancestor)
            if polygon.contains(Polygon.from_bounds(*bbox)):
                return ancestor
        return None  # Fallback if no ancestor is found

    ancestor_georef = find_ancestor_georef(center_georef, bounding_box)

    if not ancestor_georef:
        raise ValueError("No ancestor georef fully contains the bounding box.")

    # Step 3: Expand georefs recursively from the ancestor
    bbox_polygon = Polygon.from_bounds(*bounding_box)

    def expand_georef(gr, target_length, georefs):
        """Expand georef only if it intersects the bounding box."""
        polygon = georef_to_polygon(gr)
        if not polygon.intersects(bbox_polygon):
            return  # Skip this branch if it doesn't intersect the bounding box

        if len(gr) == target_length:
            georefs.add(gr)  # Add to the set if it reaches the target resolution
            return

        for char in "0123456789bcdefghjkmnpqrstuvwxyz":
            expand_georef(gr + char, target_length, georefs)

    georefs = set()
    expand_georef(ancestor_georef, resolution, georefs)

    # Step 4: Generate features for georefs that intersect the bounding box
    total_cells = len(georefs)   
    
    if feedback:
        feedback.pushInfo(f"Processing feature {feature.id()}")   
        feedback.setProgress(0)
        
    # Step 4: Generate features for geohashes that intersect the bounding box        
    for i, gr in enumerate(georefs):
        if feedback and feedback.isCanceled():
            return []
        cell_polygon = georef_to_polygon(gr)
        # if cell_polygon.intersects(feature):
        cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)    
        # Predicate-based filtering
        keep = cell_geometry.intersects(feature_geometry)
        if predicate == 1:  # within
            keep = cell_geometry.within(feature_geometry)
        elif predicate == 2:  # centroid_within
            keep = cell_geometry.centroid().within(feature_geometry)
        elif predicate == 3:  # intersection >= 50% of cell area
            if keep:  # Only check if they intersect
                intersection_geom = cell_geometry.intersection(feature_geometry)
                if intersection_geom and intersection_geom.area() > 0:
                    intersection_area = intersection_geom.area()
                    cell_area_qgis = cell_geometry.area()
                    keep = (intersection_area / cell_area_qgis) >= 0.5
                else:
                    keep = False
        
        if not keep:
            continue  # Skip non-matching cells
        
        # Create a single QGIS feature
        georef_feature = QgsFeature()
        georef_feature.setGeometry(cell_geometry)
        
        center_lat, center_lon, cell_width, cell_height, cell_area = graticule_dggs_metrics(cell_polygon)  
        cell_resolution = resolution
        # Get all attributes from the input feature
        original_attributes = feature.attributes()
        original_fields = feature.fields()
        
        new_fields = QgsFields()
        new_fields.append(QgsField("georef", QVariant.String))
        new_fields.append(QgsField("resolution", QVariant.Int))
        new_fields.append(QgsField("center_lat", QVariant.Double))
        new_fields.append(QgsField("center_lon", QVariant.Double))
        new_fields.append(QgsField("cell_width", QVariant.Double))
        new_fields.append(QgsField("cell_height", QVariant.Double))
        new_fields.append(QgsField("cell_area", QVariant.Double))
        
        # Combine original fields and new fields
        all_fields = QgsFields()
        for field in original_fields:
            all_fields.append(field)
        for field in new_fields:
            all_fields.append(field)
        
        georef_feature.setFields(all_fields)
        
        # Combine original attributes with new attributes
        new_attributes = [str(gr),cell_resolution, center_lat, center_lon,  cell_width, cell_height, cell_area]
        all_attributes = original_attributes + new_attributes
        
        georef_feature.setAttributes(all_attributes)    
        georef_features.append(georef_feature)
        
        if feedback and i % 100 == 0:
            feedback.setProgress(int(100 * i / total_cells))

    if feedback:
        feedback.setProgress(100)      

    # if compact: 
    #     georef_features =  georefcompact_from_qgsfeatures(georef_features,feedback)    
            
    return georef_features
    

#######################
# QgsFeatures to Tilecode
#######################
def qgsfeature2tilecode(feature, resolution, predicate = None, compact=None,feedback=None):
    geometry = feature.geometry()
    if geometry.wkbType() == QgsWkbTypes.Point:
        return point2tilecode(feature, resolution,feedback)
    elif geometry.wkbType() == QgsWkbTypes.LineString:
        return poly2tilecode(feature, resolution,None,None,feedback)
    elif geometry.wkbType() == QgsWkbTypes.Polygon:
        return poly2tilecode(feature, resolution,predicate,compact,feedback)

def point2tilecode(feature, resolution,feedback):
    if feedback and feedback.isCanceled():
        return []

    feature_geometry = feature.geometry()
    point = feature_geometry.asPoint()
    longitude = point.x()
    latitude = point.y()    
    tilecode_id = tilecode.latlon2tilecode(latitude, longitude,resolution)
    tilecode_cell = mercantile.tile(longitude, latitude, resolution)
    bounds = mercantile.bounds(tilecode_cell)
    
    # Create the bounding box coordinates for the polygon
    min_lat, min_lon = bounds.south, bounds.west
    max_lat, max_lon = bounds.north, bounds.east        
    
    cell_polygon = Polygon([
        [min_lon, min_lat],  # Bottom-left corner
        [max_lon, min_lat],  # Bottom-right corner
        [max_lon, max_lat],  # Top-right corner
        [min_lon, max_lat],  # Top-left corner
        [min_lon, min_lat]   # Closing the polygon (same as the first point)
    ])
    
    center_lat, center_lon, cell_width, cell_height, cell_area = graticule_dggs_metrics(cell_polygon)  
    resolution = tilecode_cell.z 
    
    cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)

    # Create a single QGIS feature
    tilecode_feature = QgsFeature()
    tilecode_feature.setGeometry(cell_geometry)
    
    # Get all attributes from the input feature
    original_attributes = feature.attributes()
    original_fields = feature.fields()
    
    # Define new s2-related attributes
    new_fields = QgsFields()
    new_fields.append(QgsField("tilecode", QVariant.String))
    new_fields.append(QgsField("resolution", QVariant.Int))
    new_fields.append(QgsField("center_lat", QVariant.Double))
    new_fields.append(QgsField("center_lon", QVariant.Double))
    new_fields.append(QgsField("cell_width", QVariant.Double))
    new_fields.append(QgsField("cell_width", QVariant.Double))
    new_fields.append(QgsField("cell_height", QVariant.Double))
    
    # Combine original fields and new fields
    all_fields = QgsFields()
    for field in original_fields:
        all_fields.append(field)
    for field in new_fields:
        all_fields.append(field)
    
    tilecode_feature.setFields(all_fields)
    
    # Combine original attributes with new attributes
    new_attributes = [tilecode_id, resolution, center_lat, center_lon, cell_width, cell_height, cell_area]
    all_attributes = original_attributes + new_attributes
    
    tilecode_feature.setAttributes(all_attributes)
    
    return [tilecode_feature]

def tilecodecompact_from_qgsfeatures(qgs_features, feedback):
    original_fields = qgs_features[0].fields()

    tilecode_ids = [f["tilecode"] for f in qgs_features if f["tilecode"]]

    tilecode_ids_compact = tilecode_compact(tilecode_ids)
    tilecode_features = []
    total_cells = len (tilecode_ids_compact)
    
    if feedback:
        feedback.pushInfo(f"Compacting cells")   
        feedback.setProgress(0)
  
    for i, tilecode_id_compact in enumerate(tilecode_ids_compact):
        if feedback and feedback.isCanceled():
            return []       
      
        match = re.match(r'z(\d+)x(\d+)y(\d+)', tilecode_id_compact)
        if not match:
            raise ValueError("Invalid tilecode format. Expected format: 'zXxYyZ'")

        # Convert matched groups to integers
        z = int(match.group(1))
        x = int(match.group(2))
        y = int(match.group(3))

        # Get the bounds of the tile in (west, south, east, north)
        bounds = mercantile.bounds(x, y, z)    
        # Create the bounding box coordinates for the polygon
        min_lat, min_lon = bounds.south, bounds.west
        max_lat, max_lon = bounds.north, bounds.east
        cell_polygon = Polygon([
            [min_lon, min_lat],  # Bottom-left corner
            [max_lon, min_lat],  # Bottom-right corner
            [max_lon, max_lat],  # Top-right corner
            [min_lon, max_lat],  # Top-left corner
            [min_lon, min_lat]   # Closing the polygon (same as the first point)
        ])
        
        cell_resolution = z
    
        center_lat, center_lon, cell_width, cell_height, cell_area = graticule_dggs_metrics(cell_polygon) 
        
        cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)

        tilecode_feature = QgsFeature()
        tilecode_feature.setFields(original_fields)
        tilecode_feature.setGeometry(cell_geometry)

        tilecode_feature['tilecode'] = tilecode_id_compact
        tilecode_feature['resolution'] = cell_resolution
        tilecode_feature['center_lat'] = center_lat
        tilecode_feature['center_lon'] = center_lon
        tilecode_feature['cell_width'] = cell_width
        tilecode_feature['cell_height'] = cell_height
        tilecode_feature['cell_area'] = cell_area

        tilecode_features.append(tilecode_feature)
        
        if feedback and i % 100 == 0:
            feedback.setProgress(int(100 * i / total_cells))

    if feedback:
        feedback.setProgress(100)        

    return tilecode_features

def poly2tilecode(feature, resolution, predicate, compact,feedback):
    tilecode_features = []    
    feature_geometry = feature.geometry()
    feature_rect = feature_geometry.boundingBox()
    min_x = feature_rect.xMinimum()
    min_y = feature_rect.yMinimum()
    max_x = feature_rect.xMaximum()
    max_y = feature_rect.yMaximum()

    tiles = list(mercantile.tiles(min_x, min_y, max_x, max_y, resolution))
    total_cells = len(tiles)
    
    if feedback:
        feedback.pushInfo(f"Processing feature {feature.id()}")   
        feedback.setProgress(0)
        
    for i, tile in enumerate(tiles):
        if feedback and feedback.isCanceled():
            return []
        z, x, y = tile.z, tile.x, tile.y
        tilecode_id = f"z{tile.z}x{tile.x}y{tile.y}"
        bounds = mercantile.bounds(x, y, z)
        # Create the bounding box coordinates for the polygon
        min_lat, min_lon = bounds.south, bounds.west
        max_lat, max_lon = bounds.north, bounds.east            
                    
        cell_polygon = Polygon([
            [min_lon, min_lat],  # Bottom-left corner
            [max_lon, min_lat],  # Bottom-right corner
            [max_lon, max_lat],  # Top-right corner
            [min_lon, max_lat],  # Top-left corner
            [min_lon, min_lat]   # Closing the polygon (same as the first point)
        ])
                
        # if cell_polygon.intersects(feature):
        cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)    
            # **Check for intersection with the input feature**
        keep = cell_geometry.intersects(feature_geometry)
        if predicate == 1:  # within
            keep = cell_geometry.within(feature_geometry)
        elif predicate == 2:  # centroid_within
            keep = cell_geometry.centroid().within(feature_geometry)
        elif predicate == 3:  # intersection >= 50% of cell area
            if keep:  # Only check if they intersect
                intersection_geom = cell_geometry.intersection(feature_geometry)
                if intersection_geom and intersection_geom.area() > 0:
                    intersection_area = intersection_geom.area()
                    cell_area_qgis = cell_geometry.area()
                    keep = (intersection_area / cell_area_qgis) >= 0.5
                else:
                    keep = False
        
        if not keep:
            continue  # Skip non-matching cells
        
        # Create a single QGIS feature
        tilecode_feature = QgsFeature()
        tilecode_feature.setGeometry(cell_geometry)
        
        center_lat, center_lon, cell_width, cell_height, cell_area = graticule_dggs_metrics(cell_polygon)  
        resolution = tile.z 
    
        # Get all attributes from the input feature
        original_attributes = feature.attributes()
        original_fields = feature.fields()
        
        # Define new H3-related attributes
        new_fields = QgsFields()
        new_fields.append(QgsField("tilecode", QVariant.String))
        new_fields.append(QgsField("resolution", QVariant.Int))
        new_fields.append(QgsField("center_lat", QVariant.Double))
        new_fields.append(QgsField("center_lon", QVariant.Double))
        new_fields.append(QgsField("cell_width", QVariant.Double))
        new_fields.append(QgsField("cell_height", QVariant.Double))
        new_fields.append(QgsField("cell_area", QVariant.Double))
        
        # Combine original fields and new fields
        all_fields = QgsFields()
        for field in original_fields:
            all_fields.append(field)
        for field in new_fields:
            all_fields.append(field)
        
        tilecode_feature.setFields(all_fields)
        
        # Combine original attributes with new attributes
        new_attributes = [tilecode_id,resolution, center_lat, center_lon, cell_width, cell_height, cell_area]
        all_attributes = original_attributes + new_attributes
        
        tilecode_feature.setAttributes(all_attributes)    

        tilecode_features.append(tilecode_feature)
        if feedback and i % 100 == 0:
                feedback.setProgress(int(100 * i / total_cells))

    if feedback:
        feedback.setProgress(100)        

    if compact: 
        tilecode_features =  tilecodecompact_from_qgsfeatures(tilecode_features,feedback)                 
    
    return tilecode_features


#######################
# QgsFeatures to Quadkey
#######################
def qgsfeature2quadkey(feature, resolution, predicate = None, compact=None,feedback=None):
    geometry = feature.geometry()
    if geometry.wkbType() == QgsWkbTypes.Point:
        return point2quadkey(feature, resolution,feedback)
    elif geometry.wkbType() == QgsWkbTypes.LineString:
        return poly2quadkey(feature, resolution,None,None,feedback)
    elif geometry.wkbType() == QgsWkbTypes.Polygon:
        return poly2quadkey(feature, resolution,predicate,compact,feedback)

def point2quadkey(feature, resolution, feedback):
    if feedback and feedback.isCanceled():
        return []

    feature_geometry = feature.geometry()
    point = feature_geometry.asPoint()
    longitude = point.x()
    latitude = point.y()    
    quadkey_id = tilecode.latlon2quadkey(latitude, longitude,resolution)
    quadkey_cell = mercantile.tile(longitude, latitude, resolution)
    bounds = mercantile.bounds(quadkey_cell)
    # Create the bounding box coordinates for the polygon
    min_lat, min_lon = bounds.south, bounds.west
    max_lat, max_lon = bounds.north, bounds.east        
    
    cell_polygon = Polygon([
        [min_lon, min_lat],  # Bottom-left corner
        [max_lon, min_lat],  # Bottom-right corner
        [max_lon, max_lat],  # Top-right corner
        [min_lon, max_lat],  # Top-left corner
        [min_lon, min_lat]   # Closing the polygon (same as the first point)
    ])
    center_lat, center_lon, cell_width, cell_height, cell_area = graticule_dggs_metrics(cell_polygon)  
    cell_resolution = quadkey_cell.z 
    cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)

    # Create a single QGIS feature
    quadkey_feature = QgsFeature()
    quadkey_feature.setGeometry(cell_geometry)
    
    # Get all attributes from the input feature
    original_attributes = feature.attributes()
    original_fields = feature.fields()
    
    # Define new s2-related attributes
    new_fields = QgsFields()
    new_fields.append(QgsField("quadkey", QVariant.String))
    new_fields.append(QgsField("resolution", QVariant.Int))
    new_fields.append(QgsField("center_lat", QVariant.Double))
    new_fields.append(QgsField("center_lon", QVariant.Double))
    new_fields.append(QgsField("cell_width", QVariant.Double))
    new_fields.append(QgsField("cell_height", QVariant.Double))
    new_fields.append(QgsField("cell_area", QVariant.Double))
    
    # Combine original fields and new fields
    all_fields = QgsFields()
    for field in original_fields:
        all_fields.append(field)
    for field in new_fields:
        all_fields.append(field)
    
    quadkey_feature.setFields(all_fields)
    
    # Combine original attributes with new attributes
    new_attributes = [quadkey_id, cell_resolution, center_lat, center_lon, cell_width, cell_height, cell_area]
    all_attributes = original_attributes + new_attributes
    
    quadkey_feature.setAttributes(all_attributes)
    
    return [quadkey_feature]

def quadkeycompact_from_qgsfeatures(qgs_features, feedback):
    original_fields = qgs_features[0].fields()

    quadkey_ids = [f["quadkey"] for f in qgs_features if f["quadkey"]]

    quadkey_ids_compact = quadkey_compact(quadkey_ids)
    quadkey_features = []
   
    total_cells = len (quadkey_ids_compact)
    if feedback:
        feedback.pushInfo(f"Compacting cells")   
        feedback.setProgress(0)
        
    for i, quadkey_id_compact in enumerate(quadkey_ids_compact):   
        if feedback and feedback.isCanceled():
            return []       
        quadkey_id_compact_tile = mercantile.quadkey_to_tile(quadkey_id_compact)
        # Convert matched groups to integers
        z = quadkey_id_compact_tile.z
        x = quadkey_id_compact_tile.x
        y = quadkey_id_compact_tile.y

        # Get the bounds of the tile in (west, south, east, north)
        bounds = mercantile.bounds(x, y, z)    
        # Create the bounding box coordinates for the polygon
        min_lat, min_lon = bounds.south, bounds.west
        max_lat, max_lon = bounds.north, bounds.east
        cell_polygon = Polygon([
            [min_lon, min_lat],  # Bottom-left corner
            [max_lon, min_lat],  # Bottom-right corner
            [max_lon, max_lat],  # Top-right corner
            [min_lon, max_lat],  # Top-left corner
            [min_lon, min_lat]   # Closing the polygon (same as the first point)
        ])
        
        cell_resolution = z
    
        center_lat, center_lon, cell_width, cell_height, cell_area = graticule_dggs_metrics(cell_polygon) 
        
        cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)

        quadkey_feature = QgsFeature()
        quadkey_feature.setFields(original_fields)
        quadkey_feature.setGeometry(cell_geometry)

        quadkey_feature['quadkey'] = quadkey_id_compact
        quadkey_feature['resolution'] = cell_resolution
        quadkey_feature['center_lat'] = center_lat
        quadkey_feature['center_lon'] = center_lon
        quadkey_feature['cell_width'] = cell_width
        quadkey_feature['cell_height'] = cell_height
        quadkey_feature['cell_area'] = cell_area

        quadkey_features.append(quadkey_feature)
        if feedback and i % 100 == 0:
            feedback.setProgress(int(100 * i / total_cells))

    if feedback:
        feedback.setProgress(100)      

    return quadkey_features


def poly2quadkey(feature, resolution, predicate, compact, feedback):
    quadkey_features = []
    feature_geometry = feature.geometry()
    feature_rect = feature_geometry.boundingBox()
    min_x = feature_rect.xMinimum()
    min_y = feature_rect.yMinimum()
    max_x = feature_rect.xMaximum()
    max_y = feature_rect.yMaximum()

    tiles = list(mercantile.tiles(min_x, min_y, max_x, max_y, resolution))
    total_cells = len(tiles)
    
    if feedback:
        feedback.pushInfo(f"Processing feature {feature.id()}")   
        feedback.setProgress(0)
        
    for i, tile in enumerate(tiles):
        if feedback and feedback.isCanceled():
            return []
        z, x, y = tile.z, tile.x, tile.y
        quadkey_id = mercantile.quadkey(tile)
        bounds = mercantile.bounds(x, y, z)
        # Create the bounding box coordinates for the polygon
        min_lat, min_lon = bounds.south, bounds.west
        max_lat, max_lon = bounds.north, bounds.east            
        
        cell_polygon = Polygon([
            [min_lon, min_lat],  # Bottom-left corner
            [max_lon, min_lat],  # Bottom-right corner
            [max_lon, max_lat],  # Top-right corner
            [min_lon, max_lat],  # Top-left corner
            [min_lon, min_lat]   # Closing the polygon (same as the first point)
        ])  
                
        cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)    
        # Predicate-based filtering
        keep = cell_geometry.intersects(feature_geometry)
        if predicate == 1:  # within
            keep = cell_geometry.within(feature_geometry)
        elif predicate == 2:  # centroid_within
            keep = cell_geometry.centroid().within(feature_geometry)
        elif predicate == 3:  # intersection >= 50% of cell area
            if keep:  # Only check if they intersect
                intersection_geom = cell_geometry.intersection(feature_geometry)
                if intersection_geom and intersection_geom.area() > 0:
                    intersection_area = intersection_geom.area()
                    cell_area_qgis = cell_geometry.area()
                    keep = (intersection_area / cell_area_qgis) >= 0.5
                else:
                    keep = False
        
        if not keep:
            continue  # Skip non-matching cells
        
        quadkey_feature = QgsFeature()
        quadkey_feature.setGeometry(cell_geometry)
        
        center_lat, center_lon, cell_width, cell_height, cell_area = graticule_dggs_metrics(cell_polygon)  
        cell_resolution = tile.z 
    
        original_attributes = feature.attributes()
        original_fields = feature.fields()
        
        new_fields = QgsFields()
        new_fields.append(QgsField("quadkey", QVariant.String))
        new_fields.append(QgsField("resolution", QVariant.Int))
        new_fields.append(QgsField("center_lat", QVariant.Double))
        new_fields.append(QgsField("center_lon", QVariant.Double))
        new_fields.append(QgsField("cell_width", QVariant.Double))
        new_fields.append(QgsField("cell_height", QVariant.Double))
        new_fields.append(QgsField("cell_area", QVariant.Double))
        
        all_fields = QgsFields()
        for field in original_fields:
            all_fields.append(field)
        for field in new_fields:
            all_fields.append(field)
        
        quadkey_feature.setFields(all_fields)
        
        new_attributes = [quadkey_id,cell_resolution, center_lat, center_lon,cell_width, cell_height, cell_area]
        all_attributes = original_attributes + new_attributes
        
        quadkey_feature.setAttributes(all_attributes)    

        quadkey_features.append(quadkey_feature)
        
        if feedback and i % 100 == 0:
            feedback.setProgress(int(100 * i / total_cells))

    if feedback:
        feedback.setProgress(100)        
        
    if compact: 
        quadkey_features =  quadkeycompact_from_qgsfeatures(quadkey_features, feedback)                 
    
    return quadkey_features