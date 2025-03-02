from . import olc,mgrs, maidenhead, geohash, georef, olc, s2
from .s2 import LatLng, CellId
from .gars import GARSGrid
import math, re, os
from ..utils import mercantile
import geopandas as gpd
from shapely.geometry import Polygon, box, mapping
import h3 
from ..utils.antimeridian import fix_polygon
import shapely

from qgis.core import QgsFeature, QgsGeometry, QgsPointXY, QgsField, QgsFields,QgsWkbTypes


from PyQt5.QtCore import QVariant

from pyproj import Geod
geod = Geod(ellps="WGS84")

def fix_h3_antimeridian_cells(hex_boundary, threshold=-128):
    if any(lon < threshold for _, lon in hex_boundary):
        # Adjust all longitudes accordingly
        return [(lat, lon - 360 if lon > 0 else lon) for lat, lon in hex_boundary]
    return hex_boundary

def qgsfeature2h3(feature, resolution):
     # Extract point geometry from feature
    geometry = feature.geometry()
    h3_features = []
    if geometry.wkbType() == QgsWkbTypes.Point:
        h3_features = point2h3(feature, resolution)
    elif geometry.wkbType() == QgsWkbTypes.LineString:
        h3_features = polyline2h3(feature, resolution)
    # elif geometry.wkbType() == QgsWkbTypes.Polygon:
    #     polygon2h3(feature, resolution)
    return h3_features

def point2h3(feature, resolution):
     # Extract point geometry from feature
    geometry = feature.geometry()
       
    point = geometry.asPoint()
    latitude = point.y()
    longitude = point.x()
    
    h3_cell = h3.latlng_to_cell(latitude, longitude, resolution)
    cell_boundary = h3.cell_to_boundary(h3_cell)
    
    # Ensure correct orientation for QGIS compatibility
    filtered_boundary = fix_h3_antimeridian_cells(cell_boundary)
    # Reverse lat/lon to lon/lat for GeoJSON compatibility
    reversed_boundary = [(lon, lat) for lat, lon in filtered_boundary]
    cell_polygon = Polygon(reversed_boundary)
    
    center_lat, center_lon = h3.cell_to_latlng(h3_cell)
    center_lat = round(center_lat, 7)
    center_lon = round(center_lon, 7)
    cell_area = round(abs(geod.geometry_area_perimeter(cell_polygon)[0]), 2)  # Area in square meters
    cell_perimeter = abs(geod.geometry_area_perimeter(cell_polygon)[1])  # Perimeter in meters
    avg_edge_len = round(cell_perimeter / 6, 2)
    if h3.is_pentagon(h3_cell):
        avg_edge_len = round(cell_perimeter / 5, 2)
    
    cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)
    
    # Create a single QGIS feature
    h3_feature = QgsFeature()
    h3_feature.setGeometry(cell_geometry)
    
    # Define attributes
    fields = QgsFields()
    fields.append(QgsField("h3", QVariant.String))
    fields.append(QgsField("center_lat", QVariant.Double))
    fields.append(QgsField("center_lon", QVariant.Double))
    fields.append(QgsField("cell_area", QVariant.Double))
    fields.append(QgsField("avg_edge_len", QVariant.Double))
    fields.append(QgsField("resolution", QVariant.Int))
    
    h3_feature.setFields(fields)
    h3_feature.setAttributes([h3_cell, center_lat, center_lon, cell_area, avg_edge_len, resolution])
    
    return h3_feature

def polyline2h3(feature, resolution):
     # Extract point geometry from feature
    # geometry = feature.geometry()
    # bbox = geometry.boundingBox()    
    # bbox_cells = h3.geo_to_cells(bbox, resolution)
    # h3_features = []
    # geometry = feature.geometry()
    # shapely_geom = shapely.wkt.loads(geometry.asWkt())
    # # Convert Shapely geometry to GeoJSON-like mapping
    # geo_interface = mapping(shapely_geom)
    # # Generate H3 hexagons covering the geometry
    # bbox_cells = h3.geo_to_cells(geo_interface, resolution)
    geometry = feature.geometry()
    # Assuming 'qgs_rect' is an instance of QgsRectangle
    qgs_rect = geometry.boundingBox()
    min_x = qgs_rect.xMinimum()
    min_y = qgs_rect.yMinimum()
    max_x = qgs_rect.xMaximum()
    max_y = qgs_rect.yMaximum()

            # Create a Shapely box
    bbox = box(min_x, min_y, max_x, max_y)    
    bbox_cells = h3.geo_to_cells(bbox, resolution)
    # h3_features = []
    
    for bbox_cell in bbox_cells:
        cell_boundary = h3.cell_to_boundary(bbox_cell)
        filtered_boundary = fix_h3_antimeridian_cells(cell_boundary)
        reversed_boundary = [(lon, lat) for lat, lon in filtered_boundary]
        cell_polygon = Polygon(reversed_boundary)

        center_lat, center_lon = h3.cell_to_latlng(bbox_cell)
        center_lat = round(center_lat, 7)
        center_lon = round(center_lon, 7)
        cell_area = round(abs(geod.geometry_area_perimeter(cell_polygon)[0]), 2)
        cell_perimeter = abs(geod.geometry_area_perimeter(cell_polygon)[1])
        avg_edge_len = round(cell_perimeter / 6, 2)

        if h3.is_pentagon(bbox_cell):
            avg_edge_len = round(cell_perimeter / 5, 2)

        # if cell_polygon.intersects(feature):
        cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)            
        # Create a single QGIS feature
        h3_feature = QgsFeature()
        h3_feature.setGeometry(cell_geometry)
        # h3_features.append(h3_feature)
        return h3_feature
    
    # return h3_features[0]