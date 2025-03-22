from qgis.core import QgsFeature, QgsGeometry, QgsPointXY, QgsField, QgsFields
from PyQt5.QtCore import QVariant
import re, os

from vgrid.generator.h3grid import fix_h3_antimeridian_cells
from vgrid.utils import s2, qtm, olc,geohash, georef, mgrs, maidenhead
from vgrid.utils.gars.garsgrid import GARSGrid  
from vgrid.conversion.dggs2geojson import rhealpix_cell_to_polygon
from vgrid.utils.rhealpixdggs.dggs import RHEALPixDGGS
from vgrid.utils.rhealpixdggs.ellipsoids import WGS84_ELLIPSOID
import platform
if (platform.system() == 'Windows'):
    from vgrid.utils.eaggr.eaggr import Eaggr
    from vgrid.utils.eaggr.shapes.dggs_cell import DggsCell
    from vgrid.utils.eaggr.enums.shape_string_format import ShapeStringFormat
    from vgrid.utils.eaggr.enums.model import Model
    from vgrid.generator.isea4tgrid import fix_isea4t_wkt, fix_isea4t_antimeridian_cells
    from vgrid.conversion.dggs2geojson import isea3h_cell_to_polygon
    from vgrid.generator.settings import isea3h_accuracy_res_dict
    
from vgrid.utils.easedggs.constants import levels_specs
from vgrid.utils.easedggs.dggs.grid_addressing import grid_ids_to_geos
from vgrid.utils import mercantile
import geopandas as gpd
import json
from shapely.geometry import Polygon,shape
from shapely.wkt import loads
import h3 
from vgrid.utils.antimeridian import fix_polygon
from vgrid.generator.settings import geodesic_dggs_metrics, graticule_dggs_metrics

from pyproj import Geod
geod = Geod(ellps="WGS84")
from qgis.core import (
    QgsVectorLayer,
    QgsFeature
)

    
def h32qgsfeature(feature, h3_id):
      # Get the boundary coordinates of the H3 cell
    cell_boundary = h3.cell_to_boundary(h3_id)    
    if cell_boundary:
        filtered_boundary = fix_h3_antimeridian_cells(cell_boundary)
        # Reverse lat/lon to lon/lat for GeoJSON compatibility
        reversed_boundary = [(lon, lat) for lat, lon in filtered_boundary]
        cell_polygon = Polygon(reversed_boundary)
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
    
    if rhealpix_cell:
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
        isea4t_dggs = Eaggr(Model.ISEA4T)
        cell_to_shape = isea4t_dggs.convert_dggs_cell_outline_to_shape_string(DggsCell(isea4t_id),ShapeStringFormat.WKT)
        cell_to_shape_fixed = loads(fix_isea4t_wkt(cell_to_shape))
    
        if isea4t_id.startswith('00') or isea4t_id.startswith('09') or isea4t_id.startswith('14')\
            or isea4t_id.startswith('04') or isea4t_id.startswith('19'):
            cell_to_shape_fixed = fix_isea4t_antimeridian_cells(cell_to_shape_fixed)
        
        if cell_to_shape_fixed:
            resolution = len(isea4t_id)-2
            cell_polygon = Polygon(list(cell_to_shape_fixed.exterior.coords))

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
        isea3h_dggs = Eaggr(Model.ISEA3H)        
        cell_polygon = isea3h_cell_to_polygon(isea3h_id)

        cell_centroid = cell_polygon.centroid
        center_lat =  round(cell_centroid.y, 7)
        center_lon = round(cell_centroid.x, 7)
        
        cell_area = abs(geod.geometry_area_perimeter(cell_polygon)[0])
        cell_perimeter = abs(geod.geometry_area_perimeter(cell_polygon)[1])
        isea3h2point = isea3h_dggs.convert_dggs_cell_to_point(DggsCell(isea3h_id))      
        
        accuracy = isea3h2point._accuracy
            
        avg_edge_len = cell_perimeter / 6
        
        resolution  = isea3h_accuracy_res_dict.get(accuracy)
        
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
    try:
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
        
        if not cell_polygon.is_valid:
            raise ValueError("Generated polygon is invalid")

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
        new_attributes = [ease_id, level, center_lat, center_lon, avg_edge_len,cell_area]
        all_attributes = original_attributes + new_attributes
        
        ease_feature.setAttributes(all_attributes)    
        
        return ease_feature
    except Exception as e:
        print(f"Error in ease2qgsfeature: {str(e)}")
        return []
  

def qtm2qgsfeature(feature, qtm_cellid):
    facet = qtm.qtm_id_to_facet(qtm_cellid)
    if facet:
        resolution = len(qtm_cellid)
        cell_polygon = qtm.constructGeometry(facet)   
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
        new_attributes = [qtm_cellid, resolution, center_lat, center_lon,  avg_edge_len, cell_area]
        all_attributes = original_attributes + new_attributes
        
        qtm_feature.setAttributes(all_attributes)
        
        return qtm_feature

def olc2qgsfeature(feature, olc_cellid):
    # Decode the Open Location Code into a CodeArea object
    coord = olc.decode(olc_cellid)   

    if coord:
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
        new_attributes = [olc_cellid, resolution, center_lat, center_lon, cell_width, cell_height,cell_area]
        all_attributes = original_attributes + new_attributes
        
        olc_feature.setAttributes(all_attributes)    
        
        return olc_feature

def mgrs2qgsfeature(feature, mgrs_id):
    # Assuming mgrs.mgrscell returns cell bounds and origin
    origin_lat, origin_lon, min_lat, min_lon, max_lat, max_lon, resolution = mgrs.mgrscell(mgrs_id)
    # Define the polygon coordinates for the MGRS cell
    cell_polygon  = Polygon([
        [min_lon, min_lat],  # Bottom-left corner
        [max_lon, min_lat],  # Bottom-right corner
        [max_lon, max_lat],  # Top-right corner
        [min_lon, max_lat],  # Top-left corner
        [min_lon, min_lat]   # Closing the polygon
    ])
    def is_fully_within(mgrs_feature, gzd_features):
        mgrs_geom = mgrs_feature.geometry()  # Get geometry of mgrs_feature
        
        for gzd_feature in gzd_features:
            gzd_geom = gzd_feature.geometry()  # Get geometry of gzd_feature
            
            if gzd_geom.contains(mgrs_geom):  # Check if gzd_geom fully contains mgrs_geom
                return True  # At least one GZD feature fully contains the MGRS feature
        
        return False  # No GZD feature fully contains the MGRS feature

    def get_intersection(mgrs_feature, gzd_features):
        mgrs_geom = mgrs_feature.geometry()
        try:
            for gzd_feature in gzd_features:
                gzd_geom = gzd_feature.geometry()
                # Check if GZD feature has the same mgrs_id
                if gzd_feature["mgrs"] == mgrs_feature["mgrs"][:3]:
                    intersection = gzd_geom.intersection(mgrs_geom)  # Get intersection geometry
                    if not intersection.isEmpty():
                        intersected_feature = QgsFeature()
                        intersected_feature.setGeometry(intersection)  # Set intersection geometry
                        intersected_feature.setAttributes(mgrs_feature.attributes())  # Copy attributes
                        return intersected_feature  # Return the new feature
        except:
            return mgrs_feature  # No intersection found

    cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt) 
    center_lat, center_lon, cell_width, cell_height, cell_area = graticule_dggs_metrics(cell_polygon)
    
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
    

    # Load the GZD GeoJSON file
    gzd_json_path = os.path.join(os.path.dirname(__file__), 'gzd.geojson')   
    gzd_layer = QgsVectorLayer(gzd_json_path, "geojson_layer", "ogr")
    gzd_features = [feature for feature in gzd_layer.getFeatures()]
    
    if mgrs_feature["mgrs"][2] not in {"A", "B", "Y", "Z"}:
        if not is_fully_within(mgrs_feature, gzd_features):
            mgrs_feature = get_intersection(mgrs_feature, gzd_features)
    return mgrs_feature
   
   
def geohash2qgsfeature(feature, geohash_id):
    # Decode the Geohash to get bounding box coordinates
    bbox = geohash.bbox(geohash_id)        
    if bbox:
        # Define the bounding box corners
        min_lat, min_lon = bbox['s'], bbox['w']  # Southwest corner
        max_lat, max_lon = bbox['n'], bbox['e']  # Northeast corner
        resolution = len(geohash_id)
        
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
    # Decode the Maidenhead code to get the bounding box and center coordinates
    center_lat, center_lon, min_lat, min_lon, max_lat, max_lon, _ = maidenhead.maidenGrid(maidenhead_id)
    if center_lat:
        cell_polygon = Polygon([
            [min_lon, min_lat],  # Bottom-left corner
            [max_lon, min_lat],  # Bottom-right corner
            [max_lon, max_lat],  # Top-right corner
            [min_lon, max_lat],  # Top-left corner
            [min_lon, min_lat]   # Closing the polygon (same as the first point)
        ])
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
        new_attributes = [gars_id,resolution_minute, center_lat, center_lon, cell_width, cell_height,cell_area]
        all_attributes = original_attributes + new_attributes
        
        gars_feature.setAttributes(all_attributes) 
        
        return gars_feature              