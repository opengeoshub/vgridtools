from vgrid.geocode import mgrs, maidenhead, geohash, georef, olc, s2
from vgrid.geocode.s2 import LatLng, CellId
from vgrid.geocode.gars import GARSGrid
import h3
import math
import json, os
import geopandas as gpd
from shapely.geometry import Polygon, Point
import argparse

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

def olc2geojson(olc_code):
    # Decode the Open Location Code into a CodeArea object
    coord = olc.decode(olc_code)
    
    if coord:
        # Create the bounding box coordinates for the polygon
        min_lat, min_lon = coord.latitudeLo, coord.longitudeLo
        max_lat, max_lon = coord.latitudeHi, coord.longitudeHi

        center_lat, center_lon = coord.latitudeCenter, coord.longitudeCenter
        precision = coord.codeLength 
       
        lat_len = haversine(min_lat, min_lon, max_lat, min_lon)
        lon_len = haversine(min_lat, min_lon, min_lat, max_lon)

        bbox_width =  f'{round(lon_len,1)} m'
        bbox_height =  f'{round(lat_len,1)} m'
        if lon_len >= 10000:
            bbox_width = f'{round(lon_len/1000,1)} km'
            bbox_height = f'{round(lat_len/1000,1)} km'

        # Define the polygon based on the bounding box
        polygon_coords = [
            [min_lon, min_lat],  # Bottom-left corner
            [max_lon, min_lat],  # Bottom-right corner
            [max_lon, max_lat],  # Top-right corner
            [min_lon, max_lat],  # Top-left corner
            [min_lon, min_lat]   # Closing the polygon (same as the first point)
        ]
        
        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [polygon_coords]
            },
            "properties": {
                "olc": olc_code,  # Include the OLC as a property
                "center_lat": center_lat,
                "center_lon": center_lon,
                "bbox_height": bbox_height,
                "bbox_width": bbox_width,
                "precision": precision
            }
        }

        feature_collection = {
            "type": "FeatureCollection",
            "features": [feature]
        }
        
        return feature_collection

def olc2geojson_cli():
    """
    Command-line interface for olc2geojson.
    """
    parser = argparse.ArgumentParser(description="Convert OLC/ Google Plus Codes to GeoJSON")
    parser.add_argument("olc", help="Input OLC, e.g., olc2geojson 7P28QPG4+4P7")
    args = parser.parse_args()
    geojson_data = olc2geojson(args.olc)
    print(geojson_data)


def maidenhead2geojson(maidenhead_code):
    # Decode the Open Location Code into a CodeArea object
    center_lat, center_lon, min_lat, min_lon, max_lat, max_lon, _ = maidenhead.maidenGrid(maidenhead_code)
    precision = int(len(maidenhead_code)/2)
    
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
            [min_lon, min_lat],  # Bottom-left corner
            [max_lon, min_lat],  # Bottom-right corner
            [max_lon, max_lat],  # Top-right corner
            [min_lon, max_lat],  # Top-left corner
            [min_lon, min_lat]   # Closing the polygon (same as the first point)
        ]

        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [polygon_coords]
            },
            "properties": {
                "maidenhead": maidenhead_code,  # Include the OLC as a property
                "center_lat": center_lat,
                "center_lon": center_lon,
                "bbox_height": bbox_height,
                "bbox_width": bbox_width,
                "precision": precision
            }
        }

        feature_collection = {
            "type": "FeatureCollection",
            "features": [feature]
        }
        
        return feature_collection

def maidenhead2geojson_cli():
    """
    Command-line interface for maidenhead2geojson.
    """
    parser = argparse.ArgumentParser(description="Convert Maidenhead code to GeoJSON")
    parser.add_argument("maidenhead", help="Input Maidenhead code, e.g., maidenhead2geojson OK30is46")
    args = parser.parse_args()
    geojson_data = maidenhead2geojson(args.maidenhead)
    print(geojson_data)

# SOS: Convert gars_code object to str first
def gars2geojson(gars_code):
    gars_grid = GARSGrid(gars_code)
    wkt_polygon = gars_grid.polygon
    if wkt_polygon:
        # # Create the bounding box coordinates for the polygon
        x, y = wkt_polygon.exterior.xy
        precision_minute = gars_grid.resolution
        
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
 
        bbox_width =  f'{round(lon_len,1)} m'
        bbox_height =  f'{round(lat_len,1)} m'

        if lon_len >= 10000:
            bbox_width = f'{round(lon_len/1000,1)} km'
            bbox_height = f'{round(lat_len/1000,1)} km'

        polygon_coords = list(wkt_polygon.exterior.coords)

        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [polygon_coords]  # Directly use the coordinates list
            },
            "properties": {
                "gars": gars_code,
                "center_lat": center_lat,
                "center_lon": center_lon,
                "bbox_height": bbox_height,
                "bbox_width": bbox_width,
                "precision_minute": precision_minute
                }
            }
        
        feature_collection = {
            "type": "FeatureCollection",
            "features": [feature]
        }
        
        return feature_collection
     
def gars2geojson_cli():
    """
    Command-line interface for gars2geojson.
    """
    parser = argparse.ArgumentParser(description="Convert GARS code to GeoJSON")
    parser.add_argument("gars", help="Input GARS code, e.g., gars2geojson 574JK1918")
    args = parser.parse_args()
    geojson_data = gars2geojson(args.gars)
    print(geojson_data)


def geohash2geojson(geohash_code):
    # Decode the Open Location Code into a CodeArea object
    bbox =  geohash.bbox(geohash_code)
    if bbox:
        min_lat, min_lon = bbox['s'], bbox['w']  # Southwest corner
        max_lat, max_lon = bbox['n'], bbox['e']  # Northeast corner
        
        center_lat = (min_lat + max_lat) / 2
        center_lon = (min_lon + max_lon) / 2
        
        precision =  len(geohash_code)

        lat_len = haversine(min_lat, min_lon, max_lat, min_lon)
        lon_len = haversine(min_lat, min_lon, min_lat, max_lon)
 
        bbox_width =  f'{round(lon_len,1)} m'
        bbox_height =  f'{round(lat_len,1)} m'
        if lon_len >= 10000:
            bbox_width = f'{round(lon_len/1000,1)} km'
            bbox_height = f'{round(lat_len/1000,1)} km'
            
        # Define the polygon based on the bounding box
        polygon_coords = [
            [min_lon, min_lat],  # Bottom-left corner
            [max_lon, min_lat],  # Bottom-right corner
            [max_lon, max_lat],  # Top-right corner
            [min_lon, max_lat],  # Top-left corner
            [min_lon, min_lat]   # Closing the polygon (same as the first point)
        ]

        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [polygon_coords]  # Directly use the coordinates list
            },
            "properties": {
                "geohash": geohash_code,
                "center_lat": center_lat,
                "center_lon": center_lon,
                "bbox_height": bbox_height,
                "bbox_width": bbox_width,
                "precision_minute": precision
                }
            }
        
        feature_collection = {
            "type": "FeatureCollection",
            "features": [feature]
        }
        
        return feature_collection
    
def geohash2geojson_cli():
    """
    Command-line interface for geohash2geojson.
    """
    parser = argparse.ArgumentParser(description="Convert Geohash code to GeoJSON")
    parser.add_argument("geohash", help="Input Geohash code, e.g., geohash2geojson w3gvk1td8")
    args = parser.parse_args()
    geojson_data = geohash2geojson(args.geohash)
    print(geojson_data)


def mgrs2geojson(mgrs_code,lat=None,lon=None):
    origin_lat, origin_lon, min_lat, min_lon, max_lat, max_lon,precision = mgrs.mgrscell(mgrs_code)

    lat_len = haversine(min_lat, min_lon, max_lat, min_lon)
    lon_len = haversine(min_lat, min_lon, min_lat, max_lon)
  
    bbox_width =  f'{round(lon_len,1)} m'
    bbox_height =  f'{round(lat_len,1)} m'
    
    if lon_len >= 10000:
        bbox_width = f'{round(lon_len/1000,1)} km'
        bbox_height = f'{round(lat_len/1000,1)} km'
        
    if origin_lat:
        # Define the polygon based on the bounding box
        polygon_coords = [
            [min_lon, min_lat],  # Bottom-left corner
            [max_lon, min_lat],  # Bottom-right corner
            [max_lon, max_lat],  # Top-right corner
            [min_lon, max_lat],  # Top-left corner
            [min_lon, min_lat]   # Closing the polygon (same as the first point)
        ]

        mgrs_polygon = Polygon(polygon_coords)
        
        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [polygon_coords]  # Directly use the coordinates list
            },
            "properties": {
                "mgrs": mgrs_code,
                "origin_lat": origin_lat,
                "origin_lon": origin_lon,
                "bbox_height": bbox_height,
                "bbox_width": bbox_width,
                "precision_minute": precision
                }
            }
        
        if lat is not None and lon is not None:
            # Load the GZD JSON file (treated as GeoJSON format) from the same folder
            gzd_json_path = os.path.join(os.path.dirname(__file__), 'gzd.geojson')
            with open(gzd_json_path) as f:
                gzd_json = json.load(f)

            # Convert the GZD JSON to a GeoDataFrame
            gzd_gdf = gpd.GeoDataFrame.from_features(gzd_json['features'], crs="EPSG:4326")

            # Convert the MGRS polygon to a GeoDataFrame for intersection
            mgrs_gdf = gpd.GeoDataFrame(geometry=[mgrs_polygon], crs="EPSG:4326")

            # Perform the intersection
            intersection_gdf = gpd.overlay(mgrs_gdf, gzd_gdf, how='intersection')

            # Check if the intersection result is empty
            if not intersection_gdf.empty:
                # Convert lat/lon to a Shapely point
                point = Point(lon, lat)

                # Check if the point is inside any of the intersection polygons
                for intersection_polygon in intersection_gdf.geometry:
                    if intersection_polygon.contains(point):
                        # Manually construct the intersection as a JSON-like structure
                        intersection_feature = {
                            "type": "Feature",
                            "geometry": {
                                "type": "Polygon",
                                "coordinates": [list(intersection_polygon.exterior.coords)]
                            },
                            "properties": {
                                "mgrs": mgrs_code,
                                "origin_lat": origin_lat,
                                "origin_lon": origin_lon,
                                "bbox_height": bbox_height,
                                "bbox_width": bbox_width,
                                "precision": precision
                            }
                        }

                        # Wrap the feature in a FeatureCollection
                        intersection_feature_collection = {
                            "type": "FeatureCollection",
                            "features": [intersection_feature]
                        }

                        return json.dumps(intersection_feature_collection)

        # If no intersection or point not contained, return the original MGRS GeoJSON
        feature_collection = {
            "type": "FeatureCollection",
            "features": [feature]
        }
        
        return feature_collection
    
def mgrs2geojson_cli():
    """
    Command-line interface for mgrs2geojson.
    """
    parser = argparse.ArgumentParser(description="Convert MGRS code to GeoJSON")
    parser.add_argument("mgrs", help="Input MGRS code, e.g., mgrs2geojson 34TGK56063228")
    args = parser.parse_args()
    geojson_data = mgrs2geojson(args.mgrs)
    print(geojson_data)


def georef2geojson(georef_code):
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
            [min_lon, min_lat],  # Bottom-left corner
            [max_lon, min_lat],  # Bottom-right corner
            [max_lon, max_lat],  # Top-right corner
            [min_lon, max_lat],  # Top-left corner
            [min_lon, min_lat]   # Closing the polygon (same as the first point)
        ]

        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [polygon_coords]  # Directly use the coordinates list
            },
            "properties": {
                "georef": georef_code,
                "center_lat": center_lat,
                "center_lon": center_lon,
                "bbox_height": bbox_height,
                "bbox_width": bbox_width,
                "precision_minute": precision
                }
            }
        
        feature_collection = {
            "type": "FeatureCollection",
            "features": [feature]
        }
        
        return feature_collection

def georef2geojson_cli():
    """
    Command-line interface for georef2geojson.
    """
    parser = argparse.ArgumentParser(description="Convert GEOREF code to GeoJSON")
    parser.add_argument("georef", help="Input GEOREF code, e.g., georef2geojson VGBL42404651")
    args = parser.parse_args()
    geojson_data = georef2geojson(args.georef)
    print(geojson_data)


def h32geojson(h3_code):
    # Get the boundary coordinates of the H3 cell
    boundary = h3.cell_to_boundary(h3_code)
    
    if boundary:
        # Get the center coordinates of the H3 cell
        center_lat, center_lon = h3.cell_to_latlng(h3_code)
        precision = h3.get_resolution(h3_code)
        edge_len = h3.average_hexagon_edge_length(precision,unit='m')
        
        boundary = list(boundary)
        # Ensure the polygon boundary is closed
        if boundary[0] != boundary[-1]:
            boundary.append(boundary[0])
        
        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
               "coordinates": [[
                [lon, lat] for lat, lon in boundary  # Convert boundary to the correct coordinate order
                ]]
            },
            "properties": {
                "h3": h3_code,
                "center_lat": center_lat,
                "center_lon": center_lon,
                "edge_len": edge_len,
                "precision": precision
            }
        }
        # Wrap the feature in a FeatureCollection
        feature_collection = {
            "type": "FeatureCollection",
            "features": [feature]
        }

        # Convert the feature collection to JSON formatted string
        return feature_collection

def h32geojson_cli():
    """
    Command-line interface for h32geojson.
    """
    parser = argparse.ArgumentParser(description="Convert H3 code to GeoJSON")
    parser.add_argument("h3", help="Input H3 code, e.g., h32geojson 8d65b56628e46bf")
    args = parser.parse_args()
    geojson_data = h32geojson(args.h3)
    print(geojson_data)


def s22geojson(cell_id_token):
    # Create an S2 cell from the given cell ID
    cell_id = CellId.from_token(cell_id_token)
    cell = s2.Cell(cell_id)
    
    if cell:
        # Get the vertices of the cell (4 vertices for a rectangular cell)
        vertices = [cell.get_vertex(i) for i in range(4)]
        
        # Prepare vertices in [longitude, latitude] format
        json_vertices = []
        for vertex in vertices:
            lat_lng = LatLng.from_point(vertex)  # Convert Point to LatLng
            longitude = lat_lng.lng().degrees  # Access longitude in degrees
            latitude = lat_lng.lat().degrees    # Access latitude in degrees
            json_vertices.append([longitude, latitude])

        # Close the polygon by adding the first vertex again
        json_vertices.append(json_vertices[0])  # Closing the polygon

        # Create a JSON-compatible polygon structure
        json_polygon = {
            "type": "Polygon",
            "coordinates": [json_vertices]
        }

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
  
        bbox_width = f'{round(lon_len, 1)} m'
        bbox_height = f'{round(lat_len, 1)} m'
        
        if lon_len >= 10000:
            bbox_width = f'{round(lon_len / 1000, 1)} km'
            bbox_height = f'{round(lat_len / 1000, 1)} km'

        # Create properties for the Feature
        properties = {
            # "s2": cell_id.id(),
            "s2": cell_id_token,
            "center_lat": center_lat,
            "center_lon": center_lon,
            "bbox_width": bbox_width,
            "bbox_height": bbox_height,
            "level": cell_id.level()
        }

        # Manually create the Feature and FeatureCollection
        feature = {
            "type": "Feature",
            "geometry": json_polygon,
            "properties": properties
        }
        
        # Create the FeatureCollection
        feature_collection = {
            "type": "FeatureCollection",
            "features": [feature]
        }

        # Convert to JSON format
        return feature_collection

def s22geojson_cli():
    """
    Command-line interface for s22geojson.
    """
    parser = argparse.ArgumentParser(description="Convert S2 cell token to GeoJSON")
    parser.add_argument("s2", help="Input S2 cell token, e.g., s22geojson 31752f45cc94")
    args = parser.parse_args()
    geojson_data = s22geojson(args.s2)
    print(geojson_data)