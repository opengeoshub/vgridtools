import re, os
from shapely.geometry import Polygon,shape
from shapely.wkt import loads
import json

from vgrid.dggs import s2, qtm, olc, geohash, georef, mgrs, maidenhead
from vgrid.dggs.gars.garsgrid import GARSGrid  
from vgrid.dggs.rhealpixdggs.dggs import RHEALPixDGGS
from vgrid.dggs.rhealpixdggs.ellipsoids import WGS84_ELLIPSOID
import platform
if (platform.system() == 'Windows'):
    from vgrid.dggs.eaggr.eaggr import Eaggr
    from vgrid.dggs.eaggr.shapes.dggs_cell import DggsCell
    from vgrid.dggs.eaggr.enums.shape_string_format import ShapeStringFormat
    from vgrid.dggs.eaggr.enums.model import Model
    isea3h_dggs = Eaggr(Model.ISEA3H)   
    
from vgrid.dggs import mercantile
import h3 
from vgrid.utils.geometry import (
    graticule_dggs_metrics, geodesic_dggs_metrics,rhealpix_cell_to_polygon,
    isea3h_cell_to_polygon
)
from vgrid.generator.settings import ISEA3H_ACCURACY_RES_DICT
from vgrid.conversion.dggs2geo.h32geo import h32geo
from vgrid.conversion.dggs2geo.s22geo import s22geo
from vgrid.conversion.dggs2geo.isea4t2geo import isea4t2geo
from vgrid.conversion.dggs2geo.ease2geo import ease2geo
from vgrid.conversion.dggs2geo.qtm2geo import qtm2geo
from vgrid.conversion.dggs2geo.olc2geo import olc2geo
from vgrid.conversion.dggs2geo.geohash2geo import geohash2geo
from vgrid.conversion.dggs2geo.maidenhead2geo import maidenhead2geo

from pyproj import Geod
geod = Geod(ellps="WGS84")

from PyQt5.QtCore import QVariant

from qgis.core import (
    QgsCoordinateReferenceSystem, 
    QgsCoordinateTransform,
    QgsProject,
    QgsFeature,
    QgsGeometry,
    QgsField,
    QgsFields,
    QgsPointXY
)
    
def h32qgsfeature(feature, h3_id):
    cell_polygon = h32geo(h3_id)
    num_edges = 6       
    if (h3.is_pentagon(h3_id)):
        num_edges = 5  
    resolution = h3.get_resolution(h3_id)       
        
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
    center_lat, center_lon, avg_edge_len, cell_area = geodesic_dggs_metrics(cell_polygon, num_edges)
    
    new_attributes = [h3_id,resolution, center_lat, center_lon, avg_edge_len,cell_area]
    all_attributes = original_attributes + new_attributes
    
    h3_feature.setAttributes(all_attributes)    
    return h3_feature
   
def s22qgsfeature(feature, s2_token):
    cell_id = s2.CellId.from_token(s2_token)
    cell_polygon = s22geo(s2_token)
    resolution = cell_id.level()
    num_edges = 4
    center_lat, center_lon, avg_edge_len, cell_area = geodesic_dggs_metrics(cell_polygon, num_edges)
    
    cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt) 
    
    s2_feature = QgsFeature()
    s2_feature.setGeometry(cell_geometry)
    
    # Get all attributes from the input feature
    original_attributes = feature.attributes()
    original_fields = feature.fields()
    
    # Define new H3-related attributes
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
    new_attributes = [s2_token,resolution, center_lat, center_lon, avg_edge_len,cell_area]
    all_attributes = original_attributes + new_attributes
    
    s2_feature.setAttributes(all_attributes)    
    return s2_feature

def rhealpix2qgsfeature(feature, rhealpix_id):
    rhealpix_id = str(rhealpix_id)
    rhealpix_uids = (rhealpix_id[0],) + tuple(map(int, rhealpix_id[1:]))
    rhealpix_dggs = RHEALPixDGGS(ellipsoid= WGS84_ELLIPSOID, north_square=1, south_square=3, N_side=3) 
    rhealpix_cell = rhealpix_dggs.cell(rhealpix_uids)      
    resolution = rhealpix_cell.resolution        
    cell_polygon = rhealpix_cell_to_polygon(rhealpix_cell)
    
    num_edges = 4
    if rhealpix_cell.ellipsoidal_shape() == 'dart':
        num_edges = 3
    
    center_lat, center_lon, avg_edge_len, cell_area = geodesic_dggs_metrics(cell_polygon, num_edges)
    
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
    new_attributes = [rhealpix_id, resolution, center_lat, center_lon, avg_edge_len,cell_area]
    all_attributes = original_attributes + new_attributes
    
    rhealpix_feature.setAttributes(all_attributes)    
    return rhealpix_feature
    

def isea4t2qgsfeature(feature, isea4t_id):
    if (platform.system() == 'Windows'):        
        resolution = len(isea4t_id)-2
        cell_polygon = isea4t2geo(isea4t_id)

        num_edges = 3              
        center_lat, center_lon, avg_edge_len, cell_area = geodesic_dggs_metrics(cell_polygon, num_edges)
    
        cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt) 
        isea4t_feature = QgsFeature()
        isea4t_feature.setGeometry(cell_geometry)
        
        # Get all attributes from the input feature
        original_attributes = feature.attributes()
        original_fields = feature.fields()
        
        # Define new H3-related attributes
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
        new_attributes = [isea4t_id, resolution, center_lat, center_lon, avg_edge_len,cell_area]
        all_attributes = original_attributes + new_attributes
        
        isea4t_feature.setAttributes(all_attributes)    
        return isea4t_feature
            

def isea3h2qgsfeature(feature, isea3h_id):
    if (platform.system() == 'Windows'):           
        isea3h_cell = DggsCell(isea3h_id)  
        cell_polygon = isea3h_cell_to_polygon(isea3h_cell)
        cell_centroid = cell_polygon.centroid
        center_lat =  round(cell_centroid.y, 7)
        center_lon = round(cell_centroid.x, 7)
        
        cell_area = abs(geod.geometry_area_perimeter(cell_polygon)[0])
        cell_perimeter = abs(geod.geometry_area_perimeter(cell_polygon)[1])
        isea3h2point = isea3h_dggs.convert_dggs_cell_to_point(DggsCell(isea3h_id))      
        
        accuracy = isea3h2point._accuracy
            
        avg_edge_len = cell_perimeter / 6
        
        resolution  = ISEA3H_ACCURACY_RES_DICT.get(accuracy)
        
        if (resolution == 0): # icosahedron faces at resolution = 0
            avg_edge_len = cell_perimeter / 3
        
        if accuracy == 0.0:
            if round(avg_edge_len,2) == 0.06:
                resolution = 33
            elif round(avg_edge_len,2) == 0.03:
                resolution = 34
            elif round(avg_edge_len,2) == 0.02:
                resolution = 35
            elif round(avg_edge_len,2) == 0.01:
                resolution = 36
            
            elif round(avg_edge_len,3) == 0.007:
                resolution = 37
            elif round(avg_edge_len,3) == 0.004:
                resolution = 38
            elif round(avg_edge_len,3) == 0.002:
                resolution = 39
            elif round(avg_edge_len,3) <= 0.001:
                resolution = 40
        
        cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt) 
        isea3h_feature = QgsFeature()
        isea3h_feature.setGeometry(cell_geometry)
        
        # Get all attributes from the input feature
        original_attributes = feature.attributes()
        original_fields = feature.fields()
        
        # Define new H3-related attributes
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
        new_attributes = [isea3h_id, resolution, center_lat, center_lon, round(avg_edge_len,3),round(cell_area,3)]
        all_attributes = original_attributes + new_attributes
        
        isea3h_feature.setAttributes(all_attributes)    
        return isea3h_feature
        

def ease2qgsfeature(feature, ease_id):
    resolution = int(ease_id[1])  # Get the level (e.g., 'L0' -> 0)
    cell_polygon = ease2geo(ease_id)
    
    num_edges = 4        
    center_lat, center_lon, avg_edge_len, cell_area = geodesic_dggs_metrics(cell_polygon, num_edges)
    
    cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt) 
    ease_feature = QgsFeature()
    ease_feature.setGeometry(cell_geometry)
    
    # Get all attributes from the input feature
    original_attributes = feature.attributes()
    original_fields = feature.fields()
    
    # Define new H3-related attributes
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
    new_attributes = [ease_id, resolution, center_lat, center_lon, avg_edge_len,cell_area]
    all_attributes = original_attributes + new_attributes
    
    ease_feature.setAttributes(all_attributes)    
    
    return ease_feature


def qtm2qgsfeature(feature, qtm_id):
    cell_polygon = qtm2geo(qtm_id)
    resolution = len(qtm_id)
    num_edges = 3              
    center_lat, center_lon, avg_edge_len, cell_area = geodesic_dggs_metrics(cell_polygon, num_edges)
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
    new_attributes = [qtm_id, resolution, center_lat, center_lon,  avg_edge_len, cell_area]
    all_attributes = original_attributes + new_attributes
    
    qtm_feature.setAttributes(all_attributes)
    
    return qtm_feature

def olc2qgsfeature(feature, olc_id):
    cell_polygon = olc2geo(olc_id)
    coord = olc.decode(olc_id)         
    resolution = coord.codeLength 
    center_lat, center_lon, cell_width, cell_height, cell_area = graticule_dggs_metrics(cell_polygon)

    # Get all attributes from the input feature
    original_attributes = feature.attributes()
    original_fields = feature.fields()
    
    # Define new H3-related attributes
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
    new_attributes = [olc_id, resolution, center_lat, center_lon, cell_width, cell_height,cell_area]
    all_attributes = original_attributes + new_attributes
    
    olc_feature.setAttributes(all_attributes)    
    
    return olc_feature


def mgrs2qgsfeature(feature, mgrs_id):           
    resolution, grid_size = mgrs.get_precision_and_grid_size(mgrs_id)
    zone, hemisphere, easting, northing = mgrs._mgrsToUtm(mgrs_id)

    min_x, min_y = easting, northing
    max_x, max_y = min_x + grid_size, min_y + grid_size  # Correct max_x, max_y calculation

    # Determine UTM EPSG code
    if hemisphere == 'N':
        epsg_code = 32600 + int(zone)
    else:
        epsg_code = 32700 + int(zone)

    utm_crs = QgsCoordinateReferenceSystem(epsg_code)
    wgs84_crs = QgsCoordinateReferenceSystem(4326)  # WGS84

    transform_context = QgsProject.instance().transformContext()
    transformer = QgsCoordinateTransform(utm_crs, wgs84_crs, transform_context)

    # utm_crs = CRS.from_epsg(epsg_code)
    # wgs84_crs = CRS.from_epsg(4326)
    # # # Create transformer from UTM to WGS84
    # transformer = Transformer.from_crs(utm_crs, wgs84_crs, always_xy=True)

    # Convert all four corners
    min_lon, min_lat = transformer.transform(min_x, min_y)
    max_lon, max_lat = transformer.transform(max_x, max_y)

    # Define the polygon coordinates for the MGRS cell
    cell_polygon = Polygon([
        (min_lon, min_lat),  # Bottom-left corner
        (max_lon, min_lat),  # Bottom-right corner
        (max_lon, max_lat),  # Top-right corner
        (min_lon, max_lat),  # Top-left corner
        (min_lon, min_lat)   # Closing the polygon
    ])
    
    cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt) 
    center_lat, center_lon, cell_width, cell_height, cell_area = graticule_dggs_metrics(cell_polygon)
    
    try:
        gzd_json_path = os.path.join(os.path.dirname(__file__), 'gzd.geojson')    
              
        with open(gzd_json_path, 'r') as f:
            gzd_data = json.load(f)
    
        gzd_features = gzd_data["features"]
        gzd_feature = [feature for feature in gzd_features if feature["properties"].get("gzd") == mgrs_id[:3]][0]
        gzd_geom = shape(gzd_feature["geometry"])
    
        if mgrs_id[2] not in {"A", "B", "Y", "Z"}: # not polar bands
            if cell_polygon.intersects(gzd_geom) and not gzd_geom.contains(cell_polygon):
                intersected_polygon = cell_polygon.intersection(gzd_geom)  
                if intersected_polygon:
                    cell_geometry = QgsGeometry.fromWkt(intersected_polygon.wkt) 
                    center_lat, center_lon, cell_width, cell_height, cell_area = graticule_dggs_metrics(intersected_polygon)
    except:
        pass    
    
      # Get all attributes from the input feature
    original_attributes = feature.attributes()
    original_fields = feature.fields()
    
    # Define new H3-related attributes
    new_fields = QgsFields()
    new_fields.append(QgsField("mgrs", QVariant.String))
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
        
    mgrs_feature = QgsFeature()
    mgrs_feature.setGeometry(cell_geometry)
    mgrs_feature.setFields(all_fields)
    
    # Combine original attributes with new attributes
    new_attributes = [mgrs_id, resolution, center_lat, center_lon, cell_width, cell_height,cell_area]
    all_attributes = original_attributes + new_attributes
    
    mgrs_feature.setAttributes(all_attributes)   
    
    return mgrs_feature
    return None
   
def geohash2qgsfeature(feature, geohash_id):
    cell_polygon = geohash2geo(geohash_id)
    resolution = len(geohash_id)
    center_lat, center_lon, cell_width, cell_height, cell_area = graticule_dggs_metrics(cell_polygon)
        
    # Get all attributes from the input feature
    original_attributes = feature.attributes()
    original_fields = feature.fields()
    
    # Define new H3-related attributes
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
    
    cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt) 
    geohash_feature = QgsFeature()
    geohash_feature.setGeometry(cell_geometry)
    geohash_feature.setFields(all_fields)
    
    # Combine original attributes with new attributes
    new_attributes = [geohash_id, resolution, center_lat, center_lon, cell_width, cell_height,cell_area]
    all_attributes = original_attributes + new_attributes
    
    geohash_feature.setAttributes(all_attributes) 
    
    return geohash_feature
     
def georef2qgsfeature(feature, georef_id):
    center_lat, center_lon, min_lat, min_lon, max_lat, max_lon,resolution = georef.georefcell(georef_id)        
    if center_lat:
        cell_polygon = Polygon([
            [min_lon, min_lat],  # Bottom-left corner
            [max_lon, min_lat],  # Bottom-right corner
            [max_lon, max_lat],  # Top-right corner
            [min_lon, max_lat],  # Top-left corner
            [min_lon, min_lat]   # Closing the polygon (same as the first point)
        ])

        center_lat, center_lon, cell_width, cell_height, cell_area = graticule_dggs_metrics(cell_polygon)
            
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
        new_attributes = [georef_id, resolution, center_lat, center_lon, cell_width, cell_height,cell_area]
        all_attributes = original_attributes + new_attributes
        
        georef_feature.setAttributes(all_attributes) 
        
        return georef_feature
        
def tilecode2qgsfeature(feature, tilecode_id):   
    # Extract z, x, y from the tilecode using regex
    match = re.match(r'z(\d+)x(\d+)y(\d+)', tilecode_id)
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
        
        center_lat, center_lon, cell_width, cell_height, cell_area = graticule_dggs_metrics(cell_polygon)
            
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
        
        cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt) 
        tilecode_feature = QgsFeature()
        tilecode_feature.setGeometry(cell_geometry)
        tilecode_feature.setFields(all_fields)
        
        # Combine original attributes with new attributes
        new_attributes = [tilecode_id, z, center_lat, center_lon, cell_width, cell_height,cell_area]
        all_attributes = original_attributes + new_attributes
        
        tilecode_feature.setAttributes(all_attributes) 
        
        return tilecode_feature

def quadkey2qgsfeature(feature, quadkey_id):   
    tile = mercantile.quadkey_to_tile(quadkey_id)    
    z = tile.z
    x = tile.x
    y = tile.y    
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

        center_lat, center_lon, cell_width, cell_height, cell_area = graticule_dggs_metrics(cell_polygon)
            
        # Get all attributes from the input feature
        original_attributes = feature.attributes()
        original_fields = feature.fields()
        
        # Define new H3-related attributes
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
        
        cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt) 
        quadkey_feature = QgsFeature()
        quadkey_feature.setGeometry(cell_geometry)
        quadkey_feature.setFields(all_fields)
        
        # Combine original attributes with new attributes
        new_attributes = [quadkey_id, z, center_lat, center_lon, cell_width, cell_height,cell_area]
        all_attributes = original_attributes + new_attributes
        
        quadkey_feature.setAttributes(all_attributes) 
        
        return quadkey_feature

       
def maidenhead2qgsfeature(feature, maidenhead_id):
    cell_polygon = maidenhead2geo(maidenhead_id)
    resolution = int(len(maidenhead_id) / 2)    

    center_lat, center_lon, cell_width, cell_height, cell_area = graticule_dggs_metrics(cell_polygon)
        
    # Get all attributes from the input feature
    original_attributes = feature.attributes()
    original_fields = feature.fields()
    
    # Define new H3-related attributes
    new_fields = QgsFields()
    new_fields.append(QgsField("maidenhead", QVariant.String))
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
    maidenhead_feature = QgsFeature()
    maidenhead_feature.setGeometry(cell_geometry)
    maidenhead_feature.setFields(all_fields)
    
    # Combine original attributes with new attributes
    new_attributes = [maidenhead_id,resolution, center_lat, center_lon, cell_width, cell_height,cell_area]
    all_attributes = original_attributes + new_attributes
    
    maidenhead_feature.setAttributes(all_attributes) 
    
    return maidenhead_feature

def gars2qgsfeature(feature, gars_id):
    # Create a GARS grid object and retrieve the polygon
    gars_grid = GARSGrid(gars_id)
    wkt_polygon = gars_grid.polygon  

    if wkt_polygon:
        # Extract the bounding box coordinates for the polygon
        x, y = wkt_polygon.exterior.xy  # Assuming exterior.xy returns lists of x and y coordinates
        resolution_minute = gars_grid.resolution
        resolution = 1
        if resolution_minute == 30:
            resolution = 1
        elif resolution_minute == 15:
            resolution = 2
        elif resolution_minute == 5:
            resolution = 3
        elif resolution_minute == 1:
            resolution = 4
        
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

        center_lat, center_lon, cell_width, cell_height, cell_area = graticule_dggs_metrics(cell_polygon)
            
        # Get all attributes from the input feature
        original_attributes = feature.attributes()
        original_fields = feature.fields()
        
        # Define new H3-related attributes
        new_fields = QgsFields()
        new_fields.append(QgsField("gars", QVariant.String))
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
        gars_feature = QgsFeature()
        gars_feature.setGeometry(cell_geometry)
        gars_feature.setFields(all_fields)
        
        # Combine original attributes with new attributes
        new_attributes = [gars_id,resolution, center_lat, center_lon, cell_width, cell_height,cell_area]
        all_attributes = original_attributes + new_attributes
        
        gars_feature.setAttributes(all_attributes) 
        
        return gars_feature              