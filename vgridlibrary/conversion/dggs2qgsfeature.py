from vgrid.utils import olc,mgrs, maidenhead, geohash, georef, olc, s2, gars
import math, re, os
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

def fix_h3_antimeridian_cells(hex_boundary, threshold=-128):
    if any(lon < threshold for _, lon in hex_boundary):
        # Adjust all longitudes accordingly
        return [(lat, lon - 360 if lon > 0 else lon) for lat, lon in hex_boundary]
    return hex_boundary

def haversine(lat1, lon1, lat2, lon2):
    # Radius of the Earth in meters
    R = 6371000  

    # Convert latitude and longitude from degrees to radians
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    # Haversine formula
    a = math.sin(delta_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c  # Distance in meters

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
        avg_edge_len = round(cell_perimeter/6,3)
        
        if (h3.is_pentagon(h3_code)):
            avg_edge_len = round(cell_perimeter/5 ,3)   
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
        new_fields.append(QgsField("center_lat", QVariant.Double))
        new_fields.append(QgsField("center_lon", QVariant.Double))
        new_fields.append(QgsField("cell_area", QVariant.Double))
        new_fields.append(QgsField("avg_edge_len", QVariant.Double))
        new_fields.append(QgsField("resolution", QVariant.Int))
        
        # Combine original fields and new fields
        all_fields = QgsFields()
        for field in original_fields:
            all_fields.append(field)
        for field in new_fields:
            all_fields.append(field)
        
        h3_feature.setFields(all_fields)
        
        # Combine original attributes with new attributes
        new_attributes = [h3_code, center_lat, center_lon, cell_area, avg_edge_len, resolution]
        all_attributes = original_attributes + new_attributes
        
        h3_feature.setAttributes(all_attributes)    
        return h3_feature
    else:
        return None


def s22qgsfeature(feature, cell_id_token):
    # Create an S2 cell from the given cell ID
    cell_id = s2.CellId.from_token(cell_id_token)
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

        cell_area = round(abs(geod.geometry_area_perimeter(cell_polygon)[0]),3)  # Area in square meters     
        cell_perimeter = abs(geod.geometry_area_perimeter(cell_polygon)[1])  # Perimeter in meters  
        avg_edge_len = round(cell_perimeter/4,3)
        resolution = cell_id.level()
      
        cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)   
       
        h3_feature = QgsFeature()
        h3_feature.setGeometry(cell_geometry)
        
        # Get all attributes from the input feature
        original_attributes = feature.attributes()
        original_fields = feature.fields()
        
        # Define new H3-related attributes
        new_fields = QgsFields()
        new_fields.append(QgsField("h3", QVariant.String))
        new_fields.append(QgsField("center_lat", QVariant.Double))
        new_fields.append(QgsField("center_lon", QVariant.Double))
        new_fields.append(QgsField("cell_area", QVariant.Double))
        new_fields.append(QgsField("avg_edge_len", QVariant.Double))
        new_fields.append(QgsField("resolution", QVariant.Int))
        
        # Combine original fields and new fields
        all_fields = QgsFields()
        for field in original_fields:
            all_fields.append(field)
        for field in new_fields:
            all_fields.append(field)
        
        h3_feature.setFields(all_fields)
        
        # Combine original attributes with new attributes
        new_attributes = [cell_id_token, center_lat, center_lon, cell_area, avg_edge_len, resolution]
        all_attributes = original_attributes + new_attributes
        
        h3_feature.setAttributes(all_attributes)    
        return h3_feature
    else:
        return None

def olc2qgsfeature(olc_code):
    # Decode the Open Location Code into a CodeArea object
    coord = olc.decode(olc_code)
    if coord:
        # Create the bounding box coordinates for the polygon
        min_lat, min_lon = coord.latitudeLo, coord.longitudeLo
        max_lat, max_lon = coord.latitudeHi, coord.longitudeHi

        # Create a polygon geometry from the bounding box using QgsPointXY
        ring = [
            QgsPointXY(min_lon, min_lat),  # Bottom-left corner
            QgsPointXY(max_lon, min_lat),  # Bottom-right corner
            QgsPointXY(max_lon, max_lat),  # Top-right corner
            QgsPointXY(min_lon, max_lat),  # Top-left corner
            QgsPointXY(min_lon, min_lat)   # Closing the polygon (same as the first point)
        ]
        
        # Create QgsGeometry from the ring
        geometry = QgsGeometry.fromPolygonXY([ring])

        # Create the QgsFeature and set its geometry
        feature = QgsFeature()
        feature.setGeometry(geometry)

        # Create QgsFields and add fields to it
        fields = QgsFields()
        fields.append(QgsField('olc', QVariant.String))
        fields.append(QgsField('center_lat', QVariant.Double))
        fields.append(QgsField('center_lon', QVariant.Double))
        fields.append(QgsField('bbox_height', QVariant.String))
        fields.append(QgsField('bbox_width', QVariant.String))
        fields.append(QgsField('resolution', QVariant.Int))
        
        feature.setFields(fields)

        # Set the attribute values
        center_lat, center_lon = coord.latitudeCenter, coord.longitudeCenter
        resolution = coord.codeLength

        # Compute bounding box dimensions
        lat_len = haversine(min_lat, min_lon, max_lat, min_lon)
        lon_len = haversine(min_lat, min_lon, min_lat, max_lon)

        # Format bbox dimensions
        bbox_width = f'{round(lon_len, 1)} m' if lon_len < 10000 else f'{round(lon_len / 1000, 1)} km'
        bbox_height = f'{round(lat_len, 1)} m' if lat_len < 10000 else f'{round(lat_len / 1000, 1)} km'

        # Set the properties
        feature.setAttribute('olc', olc_code)
        feature.setAttribute('center_lat', center_lat)
        feature.setAttribute('center_lon', center_lon)
        feature.setAttribute('bbox_height', bbox_height)
        feature.setAttribute('bbox_width', bbox_width)
        feature.setAttribute('resolution', resolution)

        return feature

    return None  # Return None if OLC is invalid


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
    fields.append(QgsField('origin_lat', QVariant.Double))
    fields.append(QgsField('origin_lon', QVariant.Double))
    fields.append(QgsField('bbox_height', QVariant.String))
    fields.append(QgsField('bbox_width', QVariant.String))
    fields.append(QgsField('resolution', QVariant.Int))
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


def geohash2qgsfeature(geohash_code):
    # Decode the Geohash to get bounding box coordinates
    bbox = geohash.bbox(geohash_code)
    
    if bbox:
        # Define the bounding box corners
        min_lat, min_lon = bbox['s'], bbox['w']  # Southwest corner
        max_lat, max_lon = bbox['n'], bbox['e']  # Northeast corner

        # Calculate center and resolution
        center_lat = (min_lat + max_lat) / 2
        center_lon = (min_lon + max_lon) / 2
        resolution = len(geohash_code)
        
        # Define polygon coordinates based on bounding box
        polygon_coords = [
            QgsPointXY(min_lon, min_lat),  # Bottom-left corner
            QgsPointXY(max_lon, min_lat),  # Bottom-right corner
            QgsPointXY(max_lon, max_lat),  # Top-right corner
            QgsPointXY(min_lon, max_lat),  # Top-left corner
            QgsPointXY(min_lon, min_lat)   # Closing the polygon
        ]
        
        # Calculate lat/long lengths for bbox dimensions (using haversine if required)
        lat_len = haversine(min_lat, min_lon, max_lat, min_lon)
        lon_len = haversine(min_lat, min_lon, min_lat, max_lon)
        
        # Format bbox dimensions
        bbox_width = f'{round(lon_len / 1000, 1)} km' if lon_len >= 10000 else f'{round(lon_len, 1)} m'
        bbox_height = f'{round(lat_len / 1000, 1)} km' if lat_len >= 10000 else f'{round(lat_len, 1)} m'

        # Create QgsFeature and set geometry
        feature = QgsFeature()
        feature.setGeometry(QgsGeometry.fromPolygonXY([polygon_coords]))
        
        fields = QgsFields()
        fields.append(QgsField('geohash', QVariant.String))
        fields.append(QgsField('center_lat', QVariant.Double))
        fields.append(QgsField('center_lon', QVariant.Double))
        fields.append(QgsField('bbox_height', QVariant.String))
        fields.append(QgsField('bbox_width', QVariant.String))
        fields.append(QgsField('resolution', QVariant.Int))
        feature.setFields(fields)


        feature.setAttribute('geohash', geohash_code)
        feature.setAttribute('center_lat', center_lat)
        feature.setAttribute('center_lon', center_lon)
        feature.setAttribute('resolution', resolution)
        feature.setAttribute('bbox_width', bbox_width)
        feature.setAttribute('bbox_height', bbox_height)
        
        return feature
    else:
        return None

def georef2qgsfeature(georef_code):
    center_lat, center_lon, min_lat, min_lon, max_lat, max_lon,resolution = georef.georefcell(georef_code)

    lat_len = haversine(min_lat, min_lon, max_lat, min_lon)
    lon_len = haversine(min_lat, min_lon, min_lat, max_lon)
  
    bbox_width =  f'{round(lon_len,1)} m'
    bbox_height =  f'{round(lat_len,1)} m'
    
    if lon_len >= 10000:
        bbox_width = f'{round(lon_len/1000,1)} km'
        bbox_height = f'{round(lat_len/1000,1)} km'
        
    if center_lat:
        # Define the polygon based on the bounding box
        polygon_coords = [
            QgsPointXY(min_lon, min_lat),  # Bottom-left corner
            QgsPointXY(max_lon, min_lat),  # Bottom-right corner
            QgsPointXY(max_lon, max_lat),  # Top-right corner
            QgsPointXY(min_lon, max_lat),  # Top-left corner
            QgsPointXY(min_lon, min_lat)   # Closing the polygon
        ]
          # Format bbox dimensions
        bbox_width = f'{round(lon_len / 1000, 1)} km' if lon_len >= 10000 else f'{round(lon_len, 1)} m'
        bbox_height = f'{round(lat_len / 1000, 1)} km' if lat_len >= 10000 else f'{round(lat_len, 1)} m'

        # Create QgsFeature and set geometry
        feature = QgsFeature()
        feature.setGeometry(QgsGeometry.fromPolygonXY([polygon_coords]))
        
        fields = QgsFields()
        fields.append(QgsField('georef', QVariant.String))
        fields.append(QgsField('center_lat', QVariant.Double))
        fields.append(QgsField('center_lon', QVariant.Double))
        fields.append(QgsField('bbox_height', QVariant.String))
        fields.append(QgsField('bbox_width', QVariant.String))
        fields.append(QgsField('resolution', QVariant.Int))
        feature.setFields(fields)


        feature.setAttribute('georef', georef_code)
        feature.setAttribute('center_lat', center_lat)
        feature.setAttribute('center_lon', center_lon)
        feature.setAttribute('resolution', resolution)
        feature.setAttribute('bbox_width', bbox_width)
        feature.setAttribute('bbox_height', bbox_height)
        
        return feature
    else:
        return None
    
def tilecode2qgsfeature(vcode):
    """
    Converts a tile code in 'zXxYyZ' format to a QgsFeature with polygon geometry and attributes.

    Args:
        vcode (str): The tile code in the format 'zXxYyZ'.

    Returns:
        QgsFeature: A QGIS feature with polygon geometry and attributes from the vcode.
    """
    # Extract z, x, y from the vcode using regex
    match = re.match(r'z(\d+)x(\d+)y(\d+)', vcode)
    if not match:
        raise ValueError("Invalid vcode format. Expected format: 'zXxYyZ'")

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

        # Calculate the center point of the tile
        center_lat = (min_lat + max_lat) / 2
        center_lon = (min_lon + max_lon) / 2

        # Calculate bounding box dimensions
        lat_len = haversine(min_lat, min_lon, max_lat, min_lon)
        lon_len = haversine(min_lat, min_lon, min_lat, max_lon)

        # Format the bounding box dimensions
        bbox_width = f'{round(lon_len / 1000, 1)} km' if lon_len >= 10000 else f'{round(lon_len, 1)} m'
        bbox_height = f'{round(lat_len / 1000, 1)} km' if lat_len >= 10000 else f'{round(lat_len, 1)} m'

        # Define polygon coordinates for QGIS
        polygon_coords = [
            QgsPointXY(min_lon, min_lat),  # Bottom-left corner
            QgsPointXY(max_lon, min_lat),  # Bottom-right corner
            QgsPointXY(max_lon, max_lat),  # Top-right corner
            QgsPointXY(min_lon, max_lat),  # Top-left corner
            QgsPointXY(min_lon, min_lat)   # Closing the polygon
        ]

        # Create a new QgsFeature and set geometry
        feature = QgsFeature()
        feature.setGeometry(QgsGeometry.fromPolygonXY([polygon_coords]))

        # Define fields and set attributes for the feature
                # Set feature attributes
        fields  = QgsFields()
        fields.append(QgsField('vcode', QVariant.String))
        fields.append(QgsField('center_lat', QVariant.Double))
        fields.append(QgsField('center_lon', QVariant.Double))
        fields.append(QgsField('bbox_height', QVariant.String))
        fields.append(QgsField('bbox_width', QVariant.String))
        fields.append(QgsField('resolution', QVariant.Int))
        feature.setFields(fields)

        feature.setAttribute('vcode', vcode)
        feature.setAttribute('center_lat', center_lat)
        feature.setAttribute('center_lon', center_lon)
        feature.setAttribute('bbox_width', bbox_width)
        feature.setAttribute('bbox_height', bbox_height)
        feature.setAttribute('resolution', z)

        return feature

def maidenhead2qgsfeature(maidenhead_code):
    # Decode the Maidenhead code to get the bounding box and center coordinates
    center_lat, center_lon, min_lat, min_lon, max_lat, max_lon, _ = maidenhead.maidenGrid(maidenhead_code)
    resolution = int(len(maidenhead_code) / 2)
    
    # Calculate the bounding box width and height
    lat_len = haversine(min_lat, min_lon, max_lat, min_lon)
    lon_len = haversine(min_lat, min_lon, min_lat, max_lon)

    # Format bounding box dimensions
    bbox_width = f'{round(lon_len / 1000, 1)} km' if lon_len >= 10000 else f'{round(lon_len, 1)} m'
    bbox_height = f'{round(lat_len / 1000, 1)} km' if lat_len >= 10000 else f'{round(lat_len, 1)} m'
    
    # Define polygon coordinates for QGIS
    polygon_coords = [
        QgsPointXY(min_lon, min_lat),  # Bottom-left corner
        QgsPointXY(max_lon, min_lat),  # Bottom-right corner
        QgsPointXY(max_lon, max_lat),  # Top-right corner
        QgsPointXY(min_lon, max_lat),  # Top-left corner
        QgsPointXY(min_lon, min_lat)   # Closing the polygon
    ]

    # Create the QgsFeature and set the geometry as a polygon
    feature = QgsFeature()
    feature.setGeometry(QgsGeometry.fromPolygonXY([polygon_coords]))

    # Set the attributes for the feature
    fields  = QgsFields()
    fields.append(QgsField('maidenhead', QVariant.String))
    fields.append(QgsField('center_lat', QVariant.Double))
    fields.append(QgsField('center_lon', QVariant.Double))
    fields.append(QgsField('bbox_height', QVariant.String))
    fields.append(QgsField('bbox_width', QVariant.String))
    fields.append(QgsField('resolution', QVariant.Int))
    feature.setFields(fields)


    feature.setAttribute('maidenhead', maidenhead_code)
    feature.setAttribute('center_lat', center_lat)
    feature.setAttribute('center_lon', center_lon)
    feature.setAttribute('bbox_width', bbox_width)
    feature.setAttribute('bbox_height', bbox_height)
    feature.setAttribute('resolution', resolution)

    return feature


def gars2qgsfeature(gars_code):
    # Create a GARS grid object and retrieve the polygon
    gars_grid = gars.GARSGrid(gars_code)
    wkt_polygon = gars_grid.polygon  # Assumes polygon is provided as a WKT polygon

    if wkt_polygon:
        # Extract the bounding box coordinates for the polygon
        x, y = wkt_polygon.exterior.xy  # Assuming exterior.xy returns lists of x and y coordinates
        resolution_minute = gars_grid.resolution
        
        # Determine min/max latitudes and longitudes
        min_lon = min(x)
        max_lon = max(x)
        min_lat = min(y)
        max_lat = max(y)

        # Calculate center latitude and longitude
        center_lon = (min_lon + max_lon) / 2
        center_lat = (min_lat + max_lat) / 2

        # Calculate bounding box width and height
        lat_len = haversine(min_lat, min_lon, max_lat, min_lon)
        lon_len = haversine(min_lat, min_lon, min_lat, max_lon)

        # Format the bounding box dimensions
        bbox_width = f'{round(lon_len / 1000, 1)} km' if lon_len >= 10000 else f'{round(lon_len, 1)} m'
        bbox_height = f'{round(lat_len / 1000, 1)} km' if lat_len >= 10000 else f'{round(lat_len, 1)} m'

        # Create polygon coordinates for QGIS
        polygon_coords = [QgsPointXY(lon, lat) for lon, lat in wkt_polygon.exterior.coords]

        # Create the QgsFeature and set the geometry as a polygon
        feature = QgsFeature()
        feature.setGeometry(QgsGeometry.fromPolygonXY([polygon_coords]))

        # Set fields for the feature
        fields  = QgsFields()
        fields.append(QgsField('gars', QVariant.String))
        fields.append(QgsField('center_lat', QVariant.Double))
        fields.append(QgsField('center_lon', QVariant.Double))
        fields.append(QgsField('bbox_height', QVariant.String))
        fields.append(QgsField('bbox_width', QVariant.String))
        fields.append(QgsField('resolution_minute', QVariant.Int))
        feature.setFields(fields)

        feature.setAttribute('gars', gars_code)
        feature.setAttribute('center_lat', center_lat)
        feature.setAttribute('center_lon', center_lon)
        feature.setAttribute('bbox_width', bbox_width)
        feature.setAttribute('bbox_height', bbox_height)
        feature.setAttribute('resolution_minute', resolution_minute)

        return feature
