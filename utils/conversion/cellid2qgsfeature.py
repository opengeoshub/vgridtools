from vgrid.utils import s2, qtm, olc,geohash, georef, mgrs, maidenhead
from vgrid.utils.gars.garsgrid import GARSGrid  

import math, re, os
from vgrid.generator.h3grid import fix_h3_antimeridian_cells
from vgrid.conversion.cell2geojson import rhealpix_cell_to_polygon
from vgrid.utils.rhealpixdggs.dggs import RHEALPixDGGS
from vgrid.utils.rhealpixdggs.ellipsoids import WGS84_ELLIPSOID
import platform
if (platform.system() == 'Windows'):
    from vgrid.utils.eaggr.eaggr import Eaggr
    from vgrid.utils.eaggr.shapes.dggs_cell import DggsCell
    from vgrid.utils.eaggr.enums.shape_string_format import ShapeStringFormat
    from vgrid.utils.eaggr.enums.model import Model
    from vgrid.generator.isea4tgrid import fix_isea4t_wkt, fix_isea4t_antimeridian_cells
    from vgrid.conversion.cell2geojson import isea3h_cell_to_polygon

from vgrid.utils.easedggs.constants import levels_specs
from vgrid.utils.easedggs.dggs.grid_addressing import grid_ids_to_geos


from vgrid.utils import mercantile
import geopandas as gpd
from shapely.geometry import Polygon, Point
from shapely.wkt import loads
import json
import h3 
from vgrid.utils.antimeridian import fix_polygon

from qgis.core import QgsFeature, QgsGeometry, QgsPointXY, QgsField, QgsFields
from PyQt5.QtCore import QVariant

from pyproj import Geod
geod = Geod(ellps="WGS84")

from qgis.core import QgsMessageLog, Qgis
    
    
def h32qgsfeature(feature, h3_cellid):
      # Get the boundary coordinates of the H3 cell
    cell_boundary = h3.cell_to_boundary(h3_cellid)    
    if cell_boundary:
        filtered_boundary = fix_h3_antimeridian_cells(cell_boundary)
        # Reverse lat/lon to lon/lat for GeoJSON compatibility
        reversed_boundary = [(lon, lat) for lat, lon in filtered_boundary]
        cell_polygon = Polygon(reversed_boundary)
        
        center_lat, center_lon = h3.cell_to_latlng(h3_cellid)
        center_lat = round(center_lat,7)
        center_lon = round(center_lon,7)

        cell_area = round(abs(geod.geometry_area_perimeter(cell_polygon)[0]),3)  # Area in square meters     
        cell_perimeter = abs(geod.geometry_area_perimeter(cell_polygon)[1])  # Perimeter in meters  
        avg_edge_len = round(cell_perimeter/6,2)
        
        if (h3.is_pentagon(h3_cellid)):
            avg_edge_len = round(cell_perimeter/5,2)   
        resolution = h3.get_resolution(h3_cellid)        
            
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
        new_attributes = [h3_cellid,resolution, center_lat, center_lon, avg_edge_len,cell_area]
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

def rhealpix2qgsfeature(feature, rhealpix_cellid):
    rhealpix_cellid = str(rhealpix_cellid)
    rhealpix_uids = (rhealpix_cellid[0],) + tuple(map(int, rhealpix_cellid[1:]))
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
        new_attributes = [rhealpix_cellid, resolution, center_lat, center_lon, avg_edge_len,cell_area]
        all_attributes = original_attributes + new_attributes
        
        rhealpix_feature.setAttributes(all_attributes)    
        return rhealpix_feature
    

def isea4t2qgsfeature(feature, isea4t_cellid):
    if (platform.system() == 'Windows'): 
        isea4t_dggs = Eaggr(Model.ISEA4T)
        cell_to_shape = isea4t_dggs.convert_dggs_cell_outline_to_shape_string(DggsCell(isea4t_cellid),ShapeStringFormat.WKT)
        cell_to_shape_fixed = loads(fix_isea4t_wkt(cell_to_shape))
    
        if isea4t_cellid.startswith('00') or isea4t_cellid.startswith('09') or isea4t_cellid.startswith('14')\
            or isea4t_cellid.startswith('04') or isea4t_cellid.startswith('19'):
            cell_to_shape_fixed = fix_isea4t_antimeridian_cells(cell_to_shape_fixed)
        
        if cell_to_shape_fixed:
            resolution = len(isea4t_cellid)-2
            # Compute centroid
            cell_centroid = cell_to_shape_fixed.centroid
            center_lat, center_lon = round(cell_centroid.y,7), round(cell_centroid.x,7)
            # Compute area using PyProj Geod
            cell_polygon = Polygon(list(cell_to_shape_fixed.exterior.coords))

            cell_area = round(abs(geod.geometry_area_perimeter(cell_polygon)[0]),2)  # Area in square meters
            cell_perimeter = abs(geod.geometry_area_perimeter(cell_polygon)[1])  # Perimeter in meters  
            avg_edge_len = round(cell_perimeter/3,2)  

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
            new_attributes = [isea4t_cellid, resolution, center_lat, center_lon, avg_edge_len,cell_area]
            all_attributes = original_attributes + new_attributes
            
            isea4t_feature.setAttributes(all_attributes)    
            return isea4t_feature
            

def isea3h2qgsfeature(feature, isea3h_cellid):
    if (platform.system() == 'Windows'): 
        isea3h_dggs = Eaggr(Model.ISEA3H)
        accuracy_res_dict = {
                25_503_281_086_204.43: 0,
                17_002_187_390_802.953: 1,
                5_667_395_796_934.327: 2,
                1_889_131_932_311.4424: 3,
                629_710_644_103.8047: 4,
                209_903_548_034.5921: 5,
                69_967_849_344.8546: 6,
                23_322_616_448.284866: 7,
                7_774_205_482.77106: 8,
                2_591_401_827.5809155: 9,
                863_800_609.1842003: 10,
                287_933_536.4041716: 11,
                95_977_845.45861907: 12,
                31_992_615.152873024: 13,
                10_664_205.060395785: 14,
                3_554_735.0295700384: 15,
                1_184_911.6670852362: 16,
                394_970.54625696875: 17,
                131_656.84875232293: 18,
                43_885.62568888426: 19,
                14628.541896294753: 20,
                4_876.180632098251: 21,
                1_625.3841059227952: 22,
                541.7947019742651: 23,
                180.58879588146658: 24,
                60.196265293822194: 25,
                20.074859874562527: 26,
                6.6821818482323785: 27,
                2.2368320593659234: 28,
                0.7361725765001773: 29,
                0.2548289687885229: 30,
                0.0849429895961743: 31,
                0.028314329865391435: 32,
                
                0.0: 33, # isea3h2point._accuracy always returns 0.0 from res 33
                0.0: 34,
                0.0: 35,
                0.0: 36,
                0.0: 37,
                0.0: 38,
                0.0: 39,
                0.0: 40
            }

        cell_polygon = isea3h_cell_to_polygon(isea3h_cellid)
    
        cell_centroid = cell_polygon.centroid
        center_lat =  round(cell_centroid.y, 7)
        center_lon = round(cell_centroid.x, 7)
        
        cell_area = abs(geod.geometry_area_perimeter(cell_polygon)[0])
        cell_perimeter = abs(geod.geometry_area_perimeter(cell_polygon)[1])
        isea3h2point = isea3h_dggs.convert_dggs_cell_to_point(DggsCell(isea3h_cellid))      
        
        accuracy = isea3h2point._accuracy
            
        avg_edge_len = cell_perimeter / 6
        resolution  = accuracy_res_dict.get(accuracy)
        
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
        new_attributes = [isea3h_cellid, resolution, center_lat, center_lon, avg_edge_len,cell_area]
        all_attributes = original_attributes + new_attributes
        
        isea3h_feature.setAttributes(all_attributes)    
        return isea3h_feature
        

def ease2qgsfeature(feature, ease_cellid):
    level = int(ease_cellid[1])  # Get the level (e.g., 'L0' -> 0)
    # Get level specs
    level_spec = levels_specs[level]
    n_row = level_spec["n_row"]
    n_col = level_spec["n_col"]
    
    geo = grid_ids_to_geos([ease_cellid])
    if geo:
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

        cell_area = round(abs(geod.geometry_area_perimeter(cell_polygon)[0]),2)
        cell_perimeter = abs(geod.geometry_area_perimeter(cell_polygon)[1])       
        avg_edge_len = round(cell_perimeter / 6,2) 
        
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
        new_attributes = [ease_cellid, level, center_lat, center_lon, avg_edge_len,cell_area]
        all_attributes = original_attributes + new_attributes
        
        ease_feature.setAttributes(all_attributes)    
        
        return ease_feature
    


def qtm2qgsfeature(feature, qtm_cellid):
    facet = qtm.qtm_id_to_facet(qtm_cellid)
    if facet:
        resolution = len(qtm_cellid)
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
        new_attributes = [olc_cellid, resolution, center_lat, center_lon, avg_edge_len,cell_area]
        all_attributes = original_attributes + new_attributes
        
        olc_feature.setAttributes(all_attributes)    
        
        return olc_feature

def mgrs2qgsfeature(mgrs_cellid, lat=None, lon=None):
    # Assuming mgrs.mgrscell returns cell bounds and origin
    origin_lat, origin_lon, min_lat, min_lon, max_lat, max_lon, resolution = mgrs.mgrscell(mgrs_cellid)

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


    feature.setAttribute("mgrs", mgrs_cellid)
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


def geohash2qgsfeature(feature, geohash_cellid):
    # Decode the Geohash to get bounding box coordinates
    bbox = geohash.bbox(geohash_cellid)        
    if bbox:
        # Define the bounding box corners
        min_lat, min_lon = bbox['s'], bbox['w']  # Southwest corner
        max_lat, max_lon = bbox['n'], bbox['e']  # Northeast corner
        resolution = len(geohash_cellid)
        
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
        new_attributes = [geohash_cellid, resolution, center_lat, center_lon, avg_edge_len,cell_area]
        all_attributes = original_attributes + new_attributes
        
        geohash_feature.setAttributes(all_attributes)    
        
        return geohash_feature

     
def georef2qgsfeature(feature, georef_cellid):
    center_lat, center_lon, min_lat, min_lon, max_lat, max_lon,resolution = georef.georefcell(georef_cellid)        
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
        new_attributes = [georef_cellid, resolution, center_lat, center_lon, avg_edge_len,cell_area]
        all_attributes = original_attributes + new_attributes
        
        georef_feature.setAttributes(all_attributes)    
        
        return georef_feature
        
def tilecode2qgsfeature(feature, tilecode_cellid):   
    # Extract z, x, y from the tilecode using regex
    match = re.match(r'z(\d+)x(\d+)y(\d+)', tilecode_cellid)
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
        new_attributes = [tilecode_cellid, z, center_lat, center_lon, avg_edge_len,cell_area]
        all_attributes = original_attributes + new_attributes
        
        tilecode_feature.setAttributes(all_attributes)    
        
        return tilecode_feature
    
       
def maidenhead2qgsfeature(feature, maidenhead_cellid):
    # Decode the Maidenhead code to get the bounding box and center coordinates
    center_lat, center_lon, min_lat, min_lon, max_lat, max_lon, _ = maidenhead.maidenGrid(maidenhead_cellid)
    if center_lat:
        cell_polygon = Polygon([
            [min_lon, min_lat],  # Bottom-left corner
            [max_lon, min_lat],  # Bottom-right corner
            [max_lon, max_lat],  # Top-right corner
            [min_lon, max_lat],  # Top-left corner
            [min_lon, min_lat]   # Closing the polygon (same as the first point)
        ])
        resolution = int(len(maidenhead_cellid) / 2)    
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
        new_attributes = [maidenhead_cellid, resolution, center_lat, center_lon, avg_edge_len,cell_area]
        all_attributes = original_attributes + new_attributes
        
        maidenhead_feature.setAttributes(all_attributes)    
        
        return maidenhead_feature    

def gars2qgsfeature(feature, gars_cellid):
    # Create a GARS grid object and retrieve the polygon
    gars_grid = GARSGrid(gars_cellid)
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
        new_attributes = [gars_cellid, resolution_minute, center_lat, center_lon, avg_edge_len,cell_area]
        all_attributes = original_attributes + new_attributes
        
        gars_feature.setAttributes(all_attributes)    
        
        return gars_feature   
              