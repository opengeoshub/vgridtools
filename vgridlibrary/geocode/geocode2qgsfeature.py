from . import olc,mgrs, maidenhead, geohash, georef, olc, s2
from .s2 import LatLng, CellId
from .gars import GARSGrid
import math, re, os
from ..utils import mercantile
import geopandas as gpd
from shapely.geometry import Polygon, Point
import json

from qgis.core import QgsFeature, QgsGeometry, QgsPointXY, QgsField, QgsFields
from PyQt5.QtCore import QVariant

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
        fields.append(QgsField('precision', QVariant.Int))
        
        feature.setFields(fields)

        # Set the attribute values
        center_lat, center_lon = coord.latitudeCenter, coord.longitudeCenter
        precision = coord.codeLength

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
        feature.setAttribute('precision', precision)

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
    origin_lat, origin_lon, min_lat, min_lon, max_lat, max_lon, precision = mgrs.mgrscell(mgrs_code)

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
    fields.append(QgsField('precision', QVariant.Int))
    feature.setFields(fields)


    feature.setAttribute("mgrs", mgrs_code)
    feature.setAttribute("origin_lat", origin_lat)
    feature.setAttribute("origin_lon", origin_lon)
    feature.setAttribute("bbox_height", bbox_height)
    feature.setAttribute("bbox_width", bbox_width)
    feature.setAttribute("precision", precision)
    
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

        # Calculate center and precision
        center_lat = (min_lat + max_lat) / 2
        center_lon = (min_lon + max_lon) / 2
        precision = len(geohash_code)
        
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
        fields.append(QgsField('precision', QVariant.Int))
        feature.setFields(fields)


        feature.setAttribute('geohash', geohash_code)
        feature.setAttribute('center_lat', center_lat)
        feature.setAttribute('center_lon', center_lon)
        feature.setAttribute('precision', precision)
        feature.setAttribute('bbox_width', bbox_width)
        feature.setAttribute('bbox_height', bbox_height)
        
        return feature
    else:
        return None

def georef2qgsfeature(georef_code):
    center_lat, center_lon, min_lat, min_lon, max_lat, max_lon,precision = georef.georefcell(georef_code)

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
        fields.append(QgsField('precision', QVariant.Int))
        feature.setFields(fields)


        feature.setAttribute('georef', georef_code)
        feature.setAttribute('center_lat', center_lat)
        feature.setAttribute('center_lon', center_lon)
        feature.setAttribute('precision', precision)
        feature.setAttribute('bbox_width', bbox_width)
        feature.setAttribute('bbox_height', bbox_height)
        
        return feature
    else:
        return None
    
def s22qgsfeature(cell_id_token):
    # Create an S2 cell from the given cell ID
    cell_id = CellId.from_token(cell_id_token)
    cell = s2.Cell(cell_id)
    
    if cell:
        # Get the vertices of the cell (4 vertices for a rectangular cell)
        vertices = [cell.get_vertex(i) for i in range(4)]
        
        # Convert vertices to QGIS coordinates format [longitude, latitude]
        polygon_coords = []
        for vertex in vertices:
            lat_lng = LatLng.from_point(vertex)
            longitude = lat_lng.lng().degrees
            latitude = lat_lng.lat().degrees
            polygon_coords.append(QgsPointXY(longitude, latitude))
        
        # Close the polygon by adding the first vertex again
        polygon_coords.append(polygon_coords[0])  # Closing the polygon
        
        # Create QgsFeature and set geometry as polygon
        feature = QgsFeature()
        feature.setGeometry(QgsGeometry.fromPolygonXY([polygon_coords]))
        
        # Get the center of the cell
        center = cell.get_center()
        center_lat_lng = LatLng.from_point(center)
        center_lat = center_lat_lng.lat().degrees
        center_lon = center_lat_lng.lng().degrees

        # Get rectangular bounds of the cell
        rect_bound = cell.get_rect_bound()
        min_lat = rect_bound.lat_lo().degrees
        max_lat = rect_bound.lat_hi().degrees
        min_lon = rect_bound.lng_lo().degrees
        max_lon = rect_bound.lng_hi().degrees
        
        # Calculate width and height of the bounding box
        lat_len = haversine(min_lat, min_lon, max_lat, min_lon)
        lon_len = haversine(min_lat, min_lon, min_lat, max_lon)
        
        # Format bbox dimensions for better readability
        bbox_width = f'{round(lon_len / 1000, 1)} km' if lon_len >= 10000 else f'{round(lon_len, 1)} m'
        bbox_height = f'{round(lat_len / 1000, 1)} km' if lat_len >= 10000 else f'{round(lat_len, 1)} m'

        # Set feature attributes
        fields  = QgsFields()
        fields.append(QgsField('s2', QVariant.String))
        fields.append(QgsField('center_lat', QVariant.Double))
        fields.append(QgsField('center_lon', QVariant.Double))
        fields.append(QgsField('bbox_height', QVariant.String))
        fields.append(QgsField('bbox_width', QVariant.String))
        fields.append(QgsField('level', QVariant.Int))
        feature.setFields(fields)


        feature.setAttribute('s2', cell_id_token)
        feature.setAttribute('center_lat', center_lat)
        feature.setAttribute('center_lon', center_lon)
        feature.setAttribute('bbox_width', bbox_width)
        feature.setAttribute('bbox_height', bbox_height)
        feature.setAttribute('level', cell_id.level())
        
        return feature
    else:
        return None

def vcode2qgsfeature(vcode):
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
        fields.append(QgsField('precision', QVariant.Int))
        feature.setFields(fields)

        feature.setAttribute('vcode', vcode)
        feature.setAttribute('center_lat', center_lat)
        feature.setAttribute('center_lon', center_lon)
        feature.setAttribute('bbox_width', bbox_width)
        feature.setAttribute('bbox_height', bbox_height)
        feature.setAttribute('precision', z)

        return feature

def maidenhead2qgsfeature(maidenhead_code):
    # Decode the Maidenhead code to get the bounding box and center coordinates
    center_lat, center_lon, min_lat, min_lon, max_lat, max_lon, _ = maidenhead.maidenGrid(maidenhead_code)
    precision = int(len(maidenhead_code) / 2)
    
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
    fields.append(QgsField('precision', QVariant.Int))
    feature.setFields(fields)


    feature.setAttribute('maidenhead', maidenhead_code)
    feature.setAttribute('center_lat', center_lat)
    feature.setAttribute('center_lon', center_lon)
    feature.setAttribute('bbox_width', bbox_width)
    feature.setAttribute('bbox_height', bbox_height)
    feature.setAttribute('precision', precision)

    return feature


def gars2qgsfeature(gars_code):
    # Create a GARS grid object and retrieve the polygon
    gars_grid = GARSGrid(gars_code)
    wkt_polygon = gars_grid.polygon  # Assumes polygon is provided as a WKT polygon

    if wkt_polygon:
        # Extract the bounding box coordinates for the polygon
        x, y = wkt_polygon.exterior.xy  # Assuming exterior.xy returns lists of x and y coordinates
        precision_minute = gars_grid.resolution
        
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
        fields.append(QgsField('precision_minute', QVariant.Int))
        feature.setFields(fields)

        feature.setAttribute('gars', gars_code)
        feature.setAttribute('center_lat', center_lat)
        feature.setAttribute('center_lon', center_lon)
        feature.setAttribute('bbox_width', bbox_width)
        feature.setAttribute('bbox_height', bbox_height)
        feature.setAttribute('precision_minute', precision_minute)

        return feature
