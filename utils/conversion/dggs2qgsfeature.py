from vgrid.utils import s2, qtm, olc,geohash, georef, mgrs, maidenhead
from vgrid.utils.gars.garsgrid import GARSGrid  

import math, re, os
from vgrid.generator.h3grid import fix_h3_antimeridian_cells
from vgrid.conversion.cell2geojson import rhealpix_cell_to_polygon
from vgrid.utils.rhealpixdggs.dggs import RHEALPixDGGS
from vgrid.utils.rhealpixdggs.ellipsoids import WGS84_ELLIPSOID

from vgrid.utils import mercantile
import geopandas as gpd
from shapely.geometry import Polygon, Point
import json
import h3 
from vgrid.utils.antimeridian import fix_polygon

from qgis.core import QgsFeature, QgsGeometry, QgsPointXY, QgsField, QgsFields
from PyQt5.QtCore import QVariant

from pyproj import Geod
geod = Geod(ellps="WGS84")

from qgis.core import QgsMessageLog, Qgis
    
    
def h32qgsfeature(feature, h3_code):
      # Get the boundary coordinates of the H3 cell
    cell_boundary = h3.cell_to_boundary(h3_code)    
    if cell_boundary:
        filtered_boundary = fix_h3_antimeridian_cells(cell_boundary)
        # Reverse lat/lon to lon/lat for GeoJSON compatibility
        reversed_boundary = [(lon, lat) for lat, lon in filtered_boundary]
        cell_polygon = Polygon(reversed_boundary)
        
        center_lat, center_lon = h3.cell_to_latlng(h3_code)
        center_lat = round(center_lat,7)
        center_lon = round(center_lon,7)

        cell_area = round(abs(geod.geometry_area_perimeter(cell_polygon)[0]),3)  # Area in square meters     
        cell_perimeter = abs(geod.geometry_area_perimeter(cell_polygon)[1])  # Perimeter in meters  
        avg_edge_len = round(cell_perimeter/6,2)
        
        if (h3.is_pentagon(h3_code)):
            avg_edge_len = round(cell_perimeter/5,2)   
        resolution = h3.get_resolution(h3_code)        
            
        # Convert WKT to QgsGeometry
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
        new_attributes = [h3_code,resolution, center_lat, center_lon, avg_edge_len,cell_area]
        all_attributes = original_attributes + new_attributes
        
        h3_feature.setAttributes(all_attributes)    
        return h3_feature
   
def s22qgsfeature(feature, s2_token):
    # Create an S2 cell from the given cell ID
    cell_id = s2.CellId.from_token(s2_token)
    cell = s2.Cell(cell_id)
    
    if cell:
        # Get the vertices of the cell (4 vertices for a rectangular cell)
        vertices = [cell.get_vertex(i) for i in range(4)]
        
        # Convert vertices to QGIS coordinates format [longitude, latitude]
        shapely_vertices = []
        for vertex in vertices:
            lat_lng = s2.LatLng.from_point(vertex)
            longitude = lat_lng.lng().degrees
            latitude = lat_lng.lat().degrees
            shapely_vertices.append(QgsPointXY(longitude, latitude))
        
        # Close the polygon by adding the first vertex again
        shapely_vertices.append(shapely_vertices[0])  # Closing the polygon
        
        cell_polygon = fix_polygon(Polygon(shapely_vertices)) # Fix antimeridian
        lat_lng = cell_id.to_lat_lng()            
        # Extract latitude and longitude in degrees
        center_lat = round(lat_lng.lat().degrees,7)
        center_lon = round(lat_lng.lng().degrees,7)

        cell_area = round(abs(geod.geometry_area_perimeter(cell_polygon)[0]),2)  # Area in square meters     
        cell_perimeter = abs(geod.geometry_area_perimeter(cell_polygon)[1])  # Perimeter in meters  
        avg_edge_len = round(cell_perimeter/4,2)
        resolution = cell_id.level()
      
        cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt) 
       
        s2_feature = QgsFeature()
        s2_feature.setGeometry(cell_geometry)
        
        # Get all attributes from the input feature
        original_attributes = feature.attributes()
        original_fields = feature.fields()
        
        # Define new H3-related attributes
        new_fields = QgsFields()
        new_fields.append(QgsField("s2_token", QVariant.String))
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
        new_attributes = [s2_token, resolution, center_lat, center_lon, avg_edge_len,cell_area]
        all_attributes = original_attributes + new_attributes
        
        s2_feature.setAttributes(all_attributes)    
        return s2_feature

def rhealpix2qgsfeature(feature, rhealpix_code):
    rhealpix_code = str(rhealpix_code)
    rhealpix_uids = (rhealpix_code[0],) + tuple(map(int, rhealpix_code[1:]))
    rhealpix_dggs = RHEALPixDGGS(ellipsoid= WGS84_ELLIPSOID, north_square=1, south_square=3, N_side=3) 
    rhealpix_cell = rhealpix_dggs.cell(rhealpix_uids)
    
    if rhealpix_cell:
        resolution = rhealpix_cell.resolution        
        cell_polygon = rhealpix_cell_to_polygon(rhealpix_cell)
        
        center_lat = round(cell_polygon.centroid.y,7)
        center_lon = round(cell_polygon.centroid.x,7)

        cell_area = round(abs(geod.geometry_area_perimeter(cell_polygon)[0]),2)  # Area in square meters                
        cell_perimeter = abs(geod.geometry_area_perimeter(cell_polygon)[1])  # Perimeter in meters  
        avg_edge_len = round(cell_perimeter/4,2)
        if rhealpix_cell.ellipsoidal_shape() == 'dart':
            avg_edge_len = round(cell_perimeter/3,2)

        cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt) 
       
        rhealpix_feature = QgsFeature()
        rhealpix_feature.setGeometry(cell_geometry)
        
        # Get all attributes from the input feature
        original_attributes = feature.attributes()
        original_fields = feature.fields()
        
        # Define new H3-related attributes
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
        new_attributes = [rhealpix_code, resolution, center_lat, center_lon, avg_edge_len,cell_area]
        all_attributes = original_attributes + new_attributes
        
        rhealpix_feature.setAttributes(all_attributes)    
        return rhealpix_feature
    
        
def qtm2qgsfeature(feature, qtm_code):
    facet = qtm.qtm_id_to_facet(qtm_code)
    if facet:
        resolution = len(qtm_code)
        cell_polygon = qtm.constructGeometry(facet)   
        
        cell_centroid = cell_polygon.centroid
        center_lat =  round(cell_centroid.y, 7)
        center_lon = round(cell_centroid.x, 7)
        
        cell_area = round(abs(geod.geometry_area_perimeter(cell_polygon)[0]),2)
        cell_perimeter = abs(geod.geometry_area_perimeter(cell_polygon)[1])
        avg_edge_len = round(cell_perimeter / 3,2)    
        cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)    
    
        if cell_geometry:            
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
            new_attributes = [qtm_code, resolution, center_lat, center_lon,  avg_edge_len, cell_area]
            all_attributes = original_attributes + new_attributes
            
            qtm_feature.setAttributes(all_attributes)
            
            return qtm_feature

def olc2qgsfeature(feature, olc_code):
    # Decode the Open Location Code into a CodeArea object
    coord = olc.decode(olc_code)   

    if coord:
        # Create the bounding box coordinates for the polygon
        min_lat, min_lon = coord.latitudeLo, coord.longitudeLo
        max_lat, max_lon = coord.latitudeHi, coord.longitudeHi
        
        center_lat = round(coord.latitudeCenter,7)
        center_lon = round(coord.longitudeCenter,7)
        resolution = coord.codeLength 
      
        cell_polygon = Polygon([
            [min_lon, min_lat],  # Bottom-left corner
            [max_lon, min_lat],  # Bottom-right corner
            [max_lon, max_lat],  # Top-right corner
            [min_lon, max_lat],  # Top-left corner
            [min_lon, min_lat]   # Closing the polygon (same as the first point)
        ])
          
        cell_area = round(abs(geod.geometry_area_perimeter(cell_polygon)[0]),2)  # Area in square meters     
        cell_perimeter = abs(geod.geometry_area_perimeter(cell_polygon)[1])  # Perimeter in meters  
        avg_edge_len = round(cell_perimeter/4,2)     
           
        # Get all attributes from the input feature
        original_attributes = feature.attributes()
        original_fields = feature.fields()
        
        # Define new H3-related attributes
        new_fields = QgsFields()
        new_fields.append(QgsField("olc", QVariant.String))
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
        
        cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt) 
        olc_feature = QgsFeature()
        olc_feature.setGeometry(cell_geometry)
        olc_feature.setFields(all_fields)
        
        # Combine original attributes with new attributes
        new_attributes = [olc_code, resolution, center_lat, center_lon, avg_edge_len,cell_area]
        all_attributes = original_attributes + new_attributes
        
        olc_feature.setAttributes(all_attributes)    
        
        return olc_feature

def mgrs2qgsfeature(mgrs_code, lat=None, lon=None):
    """
    Converts an MGRS code to a QgsFeature with a Polygon geometry representing the cell's bounds
    and includes the original MGRS code and other properties as attributes.

    Args:
        mgrs_code (str): The MGRS code.
        lat (float, optional): Latitude of a point to check within the intersection.
        lon (float, optional): Longitude of a point to check within the intersection.

    Returns:
        QgsFeature: A QgsFeature object representing the MGRS cell, with attributes.
    """
    # Assuming mgrs.mgrscell returns cell bounds and origin
    origin_lat, origin_lon, min_lat, min_lon, max_lat, max_lon, resolution = mgrs.mgrscell(mgrs_code)

    # Calculate bounding box dimensions
    lat_len = haversine(min_lat, min_lon, max_lat, min_lon)
    lon_len = haversine(min_lat, min_lon, min_lat, max_lon)
    
    bbox_width = f'{round(lon_len / 1000, 1)} km' if lon_len >= 10000 else f'{round(lon_len, 1)} m'
    bbox_height = f'{round(lat_len / 1000, 1)} km' if lat_len >= 10000 else f'{round(lat_len, 1)} m'

    # Define the polygon coordinates for the MGRS cell
    polygon_coords = [
        [min_lon, min_lat],  # Bottom-left corner
        [max_lon, min_lat],  # Bottom-right corner
        [max_lon, max_lat],  # Top-right corner
        [min_lon, max_lat],  # Top-left corner
        [min_lon, min_lat]   # Closing the polygon
    ]
    
    # Create the QgsFeature and set geometry as Polygon
    feature = QgsFeature()
    qgs_polygon = QgsGeometry.fromPolygonXY([[QgsPointXY(x, y) for x, y in polygon_coords]])
    feature.setGeometry(qgs_polygon)

    # Add MGRS-related attributes to the feature
    fields = QgsFields()
    fields.append(QgsField('mgrs', QVariant.String))
    fields.append(QgsField('resolution', QVariant.Int))
    fields.append(QgsField('origin_lat', QVariant.Double))
    fields.append(QgsField('origin_lon', QVariant.Double))
    fields.append(QgsField('bbox_height', QVariant.String))
    fields.append(QgsField('bbox_width', QVariant.String))
    feature.setFields(fields)


    feature.setAttribute("mgrs", mgrs_code)
    feature.setAttribute("origin_lat", origin_lat)
    feature.setAttribute("origin_lon", origin_lon)
    feature.setAttribute("bbox_height", bbox_height)
    feature.setAttribute("bbox_width", bbox_width)
    feature.setAttribute("resolution", resolution)
    
    # If lat and lon are provided, check for intersection with GZD polygons
    if lat is not None and lon is not None:
        # Load the GZD GeoJSON file
        gzd_json_path = os.path.join(os.path.dirname(__file__), 'gzd.geojson')
        with open(gzd_json_path) as f:
            gzd_json = json.load(f)
        
        # Convert GZD GeoJSON to a GeoDataFrame
        gzd_gdf = gpd.GeoDataFrame.from_features(gzd_json["features"], crs="EPSG:4326")
        
        # Create a GeoDataFrame for the MGRS cell polygon
        mgrs_polygon_gdf = gpd.GeoDataFrame(geometry=[Polygon(polygon_coords)], crs="EPSG:4326")
        
        # Perform intersection
        intersection_gdf = gpd.overlay(mgrs_polygon_gdf, gzd_gdf, how='intersection')

        # Check if the intersection is valid and if it contains the point
        if not intersection_gdf.empty:
            point = Point(lon, lat)
            for intersected_polygon in intersection_gdf.geometry:
                if intersected_polygon.contains(point):
                    # Update geometry to the intersection polygon if it contains the point
                    intersection_coords = [QgsPointXY(x, y) for x, y in intersected_polygon.exterior.coords]
                    qgs_intersection_polygon = QgsGeometry.fromPolygonXY([intersection_coords])
                    feature.setGeometry(qgs_intersection_polygon)
                    break  # Exit loop once a containing polygon is found

    return feature


def geohash2qgsfeature(feature, geohash_code):
    # Decode the Geohash to get bounding box coordinates
    bbox = geohash.bbox(geohash_code)        
    if bbox:
        # Define the bounding box corners
        min_lat, min_lon = bbox['s'], bbox['w']  # Southwest corner
        max_lat, max_lon = bbox['n'], bbox['e']  # Northeast corner
        resolution = len(geohash_code)
        
        cell_polygon = Polygon([
            [min_lon, min_lat],  # Bottom-left corner
            [max_lon, min_lat],  # Bottom-right corner
            [max_lon, max_lat],  # Top-right corner
            [min_lon, max_lat],  # Top-left corner
            [min_lon, min_lat]   # Closing the polygon (same as the first point)
        ])

        # Calculate the center point of the tile
        cell_centroid = cell_polygon.centroid
        center_lat =  round(cell_centroid.y, 7)
        center_lon = round(cell_centroid.x, 7)
        cell_area = round(abs(geod.geometry_area_perimeter(cell_polygon)[0]),2)  # Area in square meters     
        cell_perimeter = abs(geod.geometry_area_perimeter(cell_polygon)[1])  # Perimeter in meters  
        avg_edge_len = round(cell_perimeter/4,2)     
           
        # Get all attributes from the input feature
        original_attributes = feature.attributes()
        original_fields = feature.fields()
        
        # Define new H3-related attributes
        new_fields = QgsFields()
        new_fields.append(QgsField("geohash", QVariant.String))
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
        
        cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt) 
        geohash_feature = QgsFeature()
        geohash_feature.setGeometry(cell_geometry)
        geohash_feature.setFields(all_fields)
        
        # Combine original attributes with new attributes
        new_attributes = [geohash_code, resolution, center_lat, center_lon, avg_edge_len,cell_area]
        all_attributes = original_attributes + new_attributes
        
        geohash_feature.setAttributes(all_attributes)    
        
        return geohash_feature

     
def georef2qgsfeature(feature, georef_code):
    center_lat, center_lon, min_lat, min_lon, max_lat, max_lon,resolution = georef.georefcell(georef_code)        
    if center_lat:
        cell_polygon = Polygon([
            [min_lon, min_lat],  # Bottom-left corner
            [max_lon, min_lat],  # Bottom-right corner
            [max_lon, max_lat],  # Top-right corner
            [min_lon, max_lat],  # Top-left corner
            [min_lon, min_lat]   # Closing the polygon (same as the first point)
        ])

        # Calculate the center point of the tile
        cell_centroid = cell_polygon.centroid
        center_lat =  round(cell_centroid.y, 7)
        center_lon = round(cell_centroid.x, 7)
        cell_area = round(abs(geod.geometry_area_perimeter(cell_polygon)[0]),2)  # Area in square meters     
        cell_perimeter = abs(geod.geometry_area_perimeter(cell_polygon)[1])  # Perimeter in meters  
        avg_edge_len = round(cell_perimeter/4,2)     
           
        # Get all attributes from the input feature
        original_attributes = feature.attributes()
        original_fields = feature.fields()
        
        # Define new H3-related attributes
        new_fields = QgsFields()
        new_fields.append(QgsField("georef", QVariant.String))
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
        
        cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt) 
        georef_feature = QgsFeature()
        georef_feature.setGeometry(cell_geometry)
        georef_feature.setFields(all_fields)
        
        # Combine original attributes with new attributes
        new_attributes = [georef_code, resolution, center_lat, center_lon, avg_edge_len,cell_area]
        all_attributes = original_attributes + new_attributes
        
        georef_feature.setAttributes(all_attributes)    
        
        return georef_feature
        
def tilecode2qgsfeature(feature, tile_code):   
    # Extract z, x, y from the tilecode using regex
    match = re.match(r'z(\d+)x(\d+)y(\d+)', tile_code)
    if not match:
        raise ValueError("Invalid tilecode format. Expected format: 'zXxYyZ'")

    # Convert matched groups to integers
    z = int(match.group(1))
    x = int(match.group(2))
    y = int(match.group(3))

    # Get the bounds of the tile in (west, south, east, north)
    bounds = mercantile.bounds(x, y, z)
    
    if bounds:
        # Define bounding box coordinates
        min_lat, min_lon = bounds.south, bounds.west
        max_lat, max_lon = bounds.north, bounds.east
        cell_polygon = Polygon([
            [min_lon, min_lat],  # Bottom-left corner
            [max_lon, min_lat],  # Bottom-right corner
            [max_lon, max_lat],  # Top-right corner
            [min_lon, max_lat],  # Top-left corner
            [min_lon, min_lat]   # Closing the polygon (same as the first point)
        ])

        # Calculate the center point of the tile
        cell_centroid = cell_polygon.centroid
        center_lat =  round(cell_centroid.y, 7)
        center_lon = round(cell_centroid.x, 7)
        cell_area = round(abs(geod.geometry_area_perimeter(cell_polygon)[0]),2)  # Area in square meters     
        cell_perimeter = abs(geod.geometry_area_perimeter(cell_polygon)[1])  # Perimeter in meters  
        avg_edge_len = round(cell_perimeter/4,2)     
           
        # Get all attributes from the input feature
        original_attributes = feature.attributes()
        original_fields = feature.fields()
        
        # Define new H3-related attributes
        new_fields = QgsFields()
        new_fields.append(QgsField("tilecode", QVariant.String))
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
        
        cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt) 
        tilecode_feature = QgsFeature()
        tilecode_feature.setGeometry(cell_geometry)
        tilecode_feature.setFields(all_fields)
        
        # Combine original attributes with new attributes
        new_attributes = [tile_code, z, center_lat, center_lon, avg_edge_len,cell_area]
        all_attributes = original_attributes + new_attributes
        
        tilecode_feature.setAttributes(all_attributes)    
        
        return tilecode_feature
    
       
def maidenhead2qgsfeature(feature, maidenhead_code):
    # Decode the Maidenhead code to get the bounding box and center coordinates
    center_lat, center_lon, min_lat, min_lon, max_lat, max_lon, _ = maidenhead.maidenGrid(maidenhead_code)
    if center_lat:
        cell_polygon = Polygon([
            [min_lon, min_lat],  # Bottom-left corner
            [max_lon, min_lat],  # Bottom-right corner
            [max_lon, max_lat],  # Top-right corner
            [min_lon, max_lat],  # Top-left corner
            [min_lon, min_lat]   # Closing the polygon (same as the first point)
        ])
        resolution = int(len(maidenhead_code) / 2)    
        # Calculate the center point of the cell
        cell_centroid = cell_polygon.centroid
        center_lat =  round(cell_centroid.y, 7)
        center_lon = round(cell_centroid.x, 7)
        cell_area = round(abs(geod.geometry_area_perimeter(cell_polygon)[0]),2)  # Area in square meters     
        cell_perimeter = abs(geod.geometry_area_perimeter(cell_polygon)[1])  # Perimeter in meters  
        avg_edge_len = round(cell_perimeter/4,2)     
           
        # Get all attributes from the input feature
        original_attributes = feature.attributes()
        original_fields = feature.fields()
        
        # Define new H3-related attributes
        new_fields = QgsFields()
        new_fields.append(QgsField("maidenhead", QVariant.String))
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
        
        cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt) 
        maidenhead_feature = QgsFeature()
        maidenhead_feature.setGeometry(cell_geometry)
        maidenhead_feature.setFields(all_fields)
        
        # Combine original attributes with new attributes
        new_attributes = [maidenhead_code, resolution, center_lat, center_lon, avg_edge_len,cell_area]
        all_attributes = original_attributes + new_attributes
        
        maidenhead_feature.setAttributes(all_attributes)    
        
        return maidenhead_feature    


def gars2qgsfeature(feature, gars_code):
    # Create a GARS grid object and retrieve the polygon
    gars_grid = GARSGrid(gars_code)
    wkt_polygon = gars_grid.polygon  

    if wkt_polygon:
        # Extract the bounding box coordinates for the polygon
        x, y = wkt_polygon.exterior.xy  # Assuming exterior.xy returns lists of x and y coordinates
        resolution_minute = gars_grid.resolution
        
        # Determine min/max latitudes and longitudes
        min_lon = min(x)
        max_lon = max(x)
        min_lat = min(y)
        max_lat = max(y)
       
        cell_polygon = Polygon([
            [min_lon, min_lat],  # Bottom-left corner
            [max_lon, min_lat],  # Bottom-right corner
            [max_lon, max_lat],  # Top-right corner
            [min_lon, max_lat],  # Top-left corner
            [min_lon, min_lat]   # Closing the polygon (same as the first point)
        ])

        cell_centroid = cell_polygon.centroid
        center_lat =  round(cell_centroid.y, 7)
        center_lon = round(cell_centroid.x, 7)
        cell_area = round(abs(geod.geometry_area_perimeter(cell_polygon)[0]),2)  # Area in square meters     
        cell_perimeter = abs(geod.geometry_area_perimeter(cell_polygon)[1])  # Perimeter in meters  
        avg_edge_len = round(cell_perimeter/4,2)     
           
        # Get all attributes from the input feature
        original_attributes = feature.attributes()
        original_fields = feature.fields()
        
        # Define new H3-related attributes
        new_fields = QgsFields()
        new_fields.append(QgsField("gars", QVariant.String))
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
        
        cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt) 
        gars_feature = QgsFeature()
        gars_feature.setGeometry(cell_geometry)
        gars_feature.setFields(all_fields)
        
        # Combine original attributes with new attributes
        new_attributes = [gars_code, resolution_minute, center_lat, center_lon, avg_edge_len,cell_area]
        all_attributes = original_attributes + new_attributes
        
        gars_feature.setAttributes(all_attributes)    
        
        return gars_feature   
              