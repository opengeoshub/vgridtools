from vgrid.utils import olc,mgrs, maidenhead, geohash, georef, olc, s2, gars, tilecode
from vgrid.utils import mercantile
from vgrid.utils.rhealpixdggs.dggs import RHEALPixDGGS
from vgrid.generator.h3grid import fix_h3_antimeridian_cells, geodesic_buffer
from vgrid.conversion.cell2geojson import rhealpix_cell_to_polygon
from vgrid.generator.geohashgrid import geohash_to_polygon

from vgrid.utils import qtm
p90_n180, p90_n90, p90_p0, p90_p90, p90_p180 = (90.0, -180.0), (90.0, -90.0), (90.0, 0.0), (90.0, 90.0), (90.0, 180.0)
p0_n180, p0_n90, p0_p0, p0_p90, p0_p180 = (0.0, -180.0), (0.0, -90.0), (0.0, 0.0), (0.0, 90.0), (0.0, 180.0)
n90_n180, n90_n90, n90_p0, n90_p90, n90_p180 = (-90.0, -180.0), (-90.0, -90.0), (-90.0, 0.0), (-90.0, 90.0), (-90.0, 180.0)


from shapely.geometry import Polygon, box, shape, mapping
import h3 

from vgrid.utils.antimeridian import fix_polygon
import platform

if (platform.system() == 'Windows'):
    from vgrid.utils.eaggr.eaggr import Eaggr
    from vgrid.utils.eaggr.shapes.dggs_cell import DggsCell
    from vgrid.utils.eaggr.enums.model import Model
    from vgrid.utils.eaggr.enums.shape_string_format import ShapeStringFormat
    from vgrid.utils.eaggr.shapes.lat_long_point import LatLongPoint
    from vgrid.generator.isea4tgrid import isea4t_cell_to_polygon, isea4t_res_accuracy_dict,\
                                                fix_isea4t_antimeridian_cells, get_isea4t_children_cells_within_bbox
    isea4t_dggs = Eaggr(Model.ISEA4T)

    from vgrid.generator.isea3hgrid import isea3h_cell_to_polygon, isea3h_res_accuracy_dict,get_isea3h_children_cells_within_bbox                                   
    isea3h_dggs = Eaggr(Model.ISEA3H)
    
from qgis.core import QgsFeature, QgsGeometry, QgsPointXY, QgsField, QgsFields,QgsWkbTypes
from PyQt5.QtCore import QVariant
from pyproj import Geod
geod = Geod(ellps="WGS84")


#######################
# QgsFeatures to H3
#######################
def qgsfeature2h3(feature, resolution):
    geometry = feature.geometry()
    if geometry.wkbType() == QgsWkbTypes.Point:
        return point2h3(feature, resolution)
    elif geometry.wkbType() == QgsWkbTypes.LineString or geometry.wkbType() == QgsWkbTypes.Polygon:
        return poly2h3(feature, resolution)
  
def point2h3(feature, resolution): 
    # Extract point geometry from feature
    feature_geometry = feature.geometry()
    point = feature_geometry.asPoint()
    latitude = point.y()
    longitude = point.x()
    
    h3_cell = h3.latlng_to_cell(latitude, longitude, resolution)
    cell_boundary = h3.cell_to_boundary(h3_cell)
    
    # Ensure correct orientation for QGIS compatibility
    filtered_boundary = fix_h3_antimeridian_cells(cell_boundary)
    # Reverse lat/lon to lon/lat for GeoJSON compatibility
    reversed_boundary = [(lon, lat) for lat, lon in filtered_boundary]
    cell_polygon = Polygon(reversed_boundary)
    h3_feature = []
    
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
    new_attributes = [str(h3_cell), resolution, center_lat, center_lon, avg_edge_len, cell_area]
    all_attributes = original_attributes + new_attributes
    
    h3_feature.setAttributes(all_attributes)
    
    return [h3_feature]

def poly2h3(feature, resolution):    
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
        
    h3_features = []
    
    for bbox_buffer_cell in bbox_buffer_cells:
        cell_boundary = h3.cell_to_boundary(bbox_buffer_cell)
        filtered_boundary = fix_h3_antimeridian_cells(cell_boundary)
        reversed_boundary = [(lon, lat) for lat, lon in filtered_boundary]
        cell_polygon = Polygon(reversed_boundary)

        center_lat, center_lon = h3.cell_to_latlng(bbox_buffer_cell)
        center_lat = round(center_lat, 7)
        center_lon = round(center_lon, 7)
        cell_area = round(abs(geod.geometry_area_perimeter(cell_polygon)[0]), 2)
        cell_perimeter = abs(geod.geometry_area_perimeter(cell_polygon)[1])
        avg_edge_len = round(cell_perimeter / 6, 2)

        if h3.is_pentagon(bbox_buffer_cell):
            avg_edge_len = round(cell_perimeter / 5, 2)

        # if cell_polygon.intersects(feature):
        cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)    
          # **Check for intersection with the input feature**
        if not cell_geometry.intersects(feature_geometry):
            continue  # Skip non-intersecting cells
      
        # Create a single QGIS feature
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
        new_attributes = [str(bbox_buffer_cell),resolution, center_lat, center_lon,  avg_edge_len, cell_area]
        all_attributes = original_attributes + new_attributes
        
        h3_feature.setAttributes(all_attributes)    

        h3_features.append(h3_feature)
    
    return h3_features


#######################
# QgsFeatures to S2
#######################
def s2cell_to_polygon(cell_id):
    cell = s2.Cell(cell_id)
    vertices = []
    for i in range(4):
        vertex = s2.LatLng.from_point(cell.get_vertex(i))
        vertices.append((vertex.lng().degrees, vertex.lat().degrees))
    
    vertices.append(vertices[0])  # Close the polygon
    
    # Create a Shapely Polygon
    polygon = Polygon(vertices)
    #  Fix Antimerididan:
    fixed_polygon = fix_polygon(polygon)    
    return fixed_polygon

def qgsfeature2s2(feature, resolution):
    geometry = feature.geometry()
    if geometry.wkbType() == QgsWkbTypes.Point:
        return point2s2(feature, resolution)
    elif geometry.wkbType() == QgsWkbTypes.LineString or geometry.wkbType() == QgsWkbTypes.Polygon:
        return poly2s2(feature, resolution)
  
def point2s2(feature, resolution): 
    # Convert point to the seed cell
    feature_geometry = feature.geometry()
    point = feature_geometry.asPoint()
    latitude = point.y()
    longitude = point.x()
    
    lat_lng = s2.LatLng.from_degrees(latitude, longitude)
    cell_id_max_res = s2.CellId.from_lat_lng(lat_lng)
    cell_id = cell_id_max_res.parent(resolution)
    s2_cell = s2.Cell(cell_id)
    cell_token = s2.CellId.to_token(s2_cell.id())
    
    if s2_cell:
        cell_polygon = s2cell_to_polygon(cell_id) # Fix antimeridian
        lat_lng = cell_id.to_lat_lng()            
        # Extract latitude and longitude in degrees
        center_lat = round(lat_lng.lat().degrees,7)
        center_lon = round(lat_lng.lng().degrees,7)

        cell_area = round(abs(geod.geometry_area_perimeter(cell_polygon)[0]),2) # Area in square meters     
        cell_perimeter = abs(geod.geometry_area_perimeter(cell_polygon)[1])  # Perimeter in meters  
        avg_edge_len = round(cell_perimeter/4,2)
        # Extract point geometry from feature        
        
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
        new_attributes = [str(cell_token), resolution, center_lat, center_lon, avg_edge_len, cell_area]
        all_attributes = original_attributes + new_attributes
        
        s2_feature.setAttributes(all_attributes)
        
        return [s2_feature]

def poly2s2(feature, resolution):    
    feature_geometry = feature.geometry()

    feature_rect = feature_geometry.boundingBox()
    min_x = feature_rect.xMinimum()
    min_y = feature_rect.yMinimum()
    max_x = feature_rect.xMaximum()
    max_y = feature_rect.yMaximum()
    # Create a Shapely box
    # Define the cell level (S2 uses a level system for zoom, where level 30 is the highest resolution)
    level = resolution
    # Create a list to store the S2 cell IDs
    cell_ids = []
    # Define the cell covering
    coverer = s2.RegionCoverer()
    coverer.min_level = level
    coverer.max_level = level
 
    region = s2.LatLngRect(
        s2.LatLng.from_degrees(min_y, min_x),
        s2.LatLng.from_degrees(max_y, max_x)
    )

    # Get the covering cells
    covering = coverer.get_covering(region)

    # Convert the covering cells to S2 cell IDs
    for cell_id in covering:
        cell_ids.append(cell_id)

    s2_features = []
    
    for cell_id in cell_ids:
        cell_polygon = s2cell_to_polygon(cell_id)
        lat_lng = cell_id.to_lat_lng()      
        cell_token = s2.CellId.to_token(cell_id)      
        # Extract latitude and longitude in degrees
        center_lat = round(lat_lng.lat().degrees,7)
        center_lon = round(lat_lng.lng().degrees,7)

        cell_area = round(abs(geod.geometry_area_perimeter(cell_polygon)[0]),2) # Area in square meters     
        cell_perimeter = abs(geod.geometry_area_perimeter(cell_polygon)[1])  # Perimeter in meters  
        avg_edge_len = round(cell_perimeter/4,2)
         # if cell_polygon.intersects(feature):
        cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)    
          # **Check for intersection with the input feature**
        if not cell_geometry.intersects(feature_geometry):
            continue  # Skip non-intersecting cells
      
        # Create a single QGIS feature
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
        new_attributes = [cell_token, resolution, center_lat, center_lon, avg_edge_len, cell_area]
        all_attributes = original_attributes + new_attributes
        
        s2_feature.setAttributes(all_attributes)    

        s2_features.append(s2_feature)
    
    return s2_features


#######################
# QgsFeatures to Rhealpix
#######################
rhealpix_dggs = RHEALPixDGGS()

def qgsfeature2rhealpix(feature, resolution):
    geometry = feature.geometry()
    if geometry.wkbType() == QgsWkbTypes.Point:
        return point2rhealpix(feature, resolution)
    elif geometry.wkbType() == QgsWkbTypes.LineString or geometry.wkbType() == QgsWkbTypes.Polygon:
        return poly2rhealpix(feature, resolution)


def point2rhealpix(feature, resolution):
    # Extract point geometry from feature
    feature_geometry = feature.geometry()
    point = feature_geometry.asPoint()
    longitude = point.x()
    latitude = point.y()
    
    # Convert point to the seed cell
    seed_cell = rhealpix_dggs.cell_from_point(resolution, (longitude, latitude), plane=False)
    seed_cell_id = str(seed_cell)  # Unique identifier for the current cell
    seed_cell_polygon = rhealpix_cell_to_polygon(seed_cell)
    
    # Get the bounds and area of the cell
    center_lat = round(seed_cell_polygon.centroid.y,7)
    center_lon = round(seed_cell_polygon.centroid.x,7)
    cell_area = round(abs(geod.geometry_area_perimeter(seed_cell_polygon)[0]),2)
    cell_perimeter = abs(geod.geometry_area_perimeter(seed_cell_polygon)[1])
    avg_edge_len = round(cell_perimeter/4,2)
    if seed_cell.ellipsoidal_shape() == 'dart':
        avg_edge_len = round(cell_perimeter/3,2)  
    
    cell_geometry = QgsGeometry.fromWkt(seed_cell_polygon.wkt)
    
    if cell_geometry:
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
        

def poly2rhealpix(feature, resolution):
    feature_geometry = feature.geometry()

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

    rhealpix_features = []     
    if seed_cell_polygon.contains(bbox_polygon):
        center_lat = round(seed_cell_polygon.centroid.y,7)
        center_lon = round(seed_cell_polygon.centroid.x,7)
        cell_area = round(abs(geod.geometry_area_perimeter(seed_cell_polygon)[0]),2)  # Area in square meters                
        cell_perimeter = abs(geod.geometry_area_perimeter(seed_cell_polygon)[1])
        avg_edge_len = round(cell_perimeter/4,2)
        if seed_cell.ellipsoidal_shape() == 'dart':
            avg_edge_len = round(cell_perimeter/3,2)  
        
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
        new_attributes = [seed_cell_id, resolution, center_lat, center_lon, avg_edge_len, cell_area]
        all_attributes = original_attributes + new_attributes
        
        rhealpix_feature.setAttributes(all_attributes)    

        rhealpix_features.append(rhealpix_feature)
    
  
    else:
        # Initialize sets and queue
        covered_cells = set()  # Cells that have been processed (by their unique ID)
        queue = [seed_cell]  # Queue for BFS exploration
        while queue:
            current_cell = queue.pop()
            current_cell_id = str(current_cell)  # Unique identifier for the current cell

            if current_cell_id in covered_cells:
                continue

            # Add current cell to the covered set
            covered_cells.add(current_cell_id)

            # Convert current cell to polygon
            cell_polygon = rhealpix_cell_to_polygon(current_cell)

            # Skip cells that do not intersect the bounding box
            if not cell_polygon.intersects(bbox_polygon):
                continue

            # Get neighbors and add to queue
            neighbors = current_cell.neighbors(plane=False)
            for _, neighbor in neighbors.items():
                neighbor_id = str(neighbor)  # Unique identifier for the neighbor
                if neighbor_id not in covered_cells:
                    queue.append(neighbor)

        for cell_id in covered_cells:
            rhealpix_uids = (cell_id[0],) + tuple(map(int, cell_id[1:]))
            cell = rhealpix_dggs.cell(rhealpix_uids)   
            cell_polygon = rhealpix_cell_to_polygon(cell)
            center_lat = round(cell_polygon.centroid.y,7)
            center_lon = round(cell_polygon.centroid.x,7)
            cell_area = round(abs(geod.geometry_area_perimeter(cell_polygon)[0]),2) # Area in square meters                
            cell_perimeter = abs(geod.geometry_area_perimeter(cell_polygon)[1])
            avg_edge_len = round(cell_perimeter/4,2)
            if seed_cell.ellipsoidal_shape() == 'dart':
                avg_edge_len = round(cell_perimeter/3,2)  
            
            cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)
            if not cell_geometry.intersects(feature_geometry):
                continue  # Skip non-intersecting cells      
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
            new_attributes = [cell_id, resolution, center_lat, center_lon, avg_edge_len, cell_area]
            all_attributes = original_attributes + new_attributes
            
            rhealpix_feature.setAttributes(all_attributes)    

            rhealpix_features.append(rhealpix_feature)
        
    return rhealpix_features

#######################
# QgsFeatures to OpenEAGGR ISEA4T
#######################

def qgsfeature2isea4t(feature, resolution):
    if (platform.system() == 'Windows'):
        geometry = feature.geometry()
        if geometry.wkbType() == QgsWkbTypes.Point:
            return point2isea4t(feature, resolution)
        elif geometry.wkbType() == QgsWkbTypes.LineString or geometry.wkbType() == QgsWkbTypes.Polygon:
            return poly2isea4t(feature, resolution)


def point2isea4t(feature, resolution):
    feature_geometry = feature.geometry()
    point = feature_geometry.asPoint()
    longitude = point.x()
    latitude = point.y()    
    accuracy = isea4t_res_accuracy_dict.get(resolution)
    lat_long_point = LatLongPoint(latitude, longitude,accuracy)

    isea4t_cell = isea4t_dggs.convert_point_to_dggs_cell(lat_long_point)

    isea4t_cell_id = isea4t_cell.get_cell_id() # Unique identifier for the current cell
    cell_polygon = isea4t_cell_to_polygon(isea4t_dggs,isea4t_cell)
    
    if isea4t_cell_id.startswith('00') or isea4t_cell_id.startswith('09') or isea4t_cell_id.startswith('14') or isea4t_cell_id.startswith('04') or isea4t_cell_id.startswith('19'):
            cell_polygon = fix_isea4t_antimeridian_cells(cell_polygon)
    
    center_lat = round(cell_polygon.centroid.y,7)
    center_lon = round(cell_polygon.centroid.x,7)

    cell_area = round(abs(geod.geometry_area_perimeter(cell_polygon)[0]),2)
    cell_perimeter = abs(geod.geometry_area_perimeter(cell_polygon)[1])
    avg_edge_len = round(cell_perimeter/3,2)
    
   
    cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)
    
    if cell_geometry:
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
        new_attributes = [isea4t_cell_id, resolution, center_lat, center_lon,  avg_edge_len, cell_area]
        all_attributes = original_attributes + new_attributes
        
        isea4t_feature.setAttributes(all_attributes)
        
        return [isea4t_feature]
        
def poly2isea4t(feature, resolution):
    feature_geometry = feature.geometry()
    feature_rect = feature_geometry.boundingBox()
    min_x = feature_rect.xMinimum()
    min_y = feature_rect.yMinimum()
    max_x = feature_rect.xMaximum()
    max_y = feature_rect.yMaximum()

    # Create a bounding box polygon
    bounding_box = box(min_x, min_y, max_x, max_y)
    bounding_box_wkt = bounding_box.wkt  # Create a bounding box polygon
    accuracy = isea4t_res_accuracy_dict.get(resolution)
    shapes = isea4t_dggs.convert_shape_string_to_dggs_shapes(bounding_box_wkt, ShapeStringFormat.WKT, accuracy)
    
    isea4t_features = [] 
    for shape in shapes:
        bbox_cells = shape.get_shape().get_outer_ring().get_cells()
        bounding_cell = isea4t_dggs.get_bounding_dggs_cell(bbox_cells)
        bounding_children_cells = get_isea4t_children_cells_within_bbox(isea4t_dggs,bounding_cell.get_cell_id(), bounding_box,resolution)
        for child in bounding_children_cells:
            isea4t_cell = DggsCell(child)
            cell_polygon = isea4t_cell_to_polygon(isea4t_dggs,isea4t_cell)
            isea4t_cell_id = isea4t_cell.get_cell_id()

            if isea4t_cell_id.startswith('00') or isea4t_cell_id.startswith('09') or isea4t_cell_id.startswith('14') or isea4t_cell_id.startswith('04') or isea4t_cell_id.startswith('19'):
                cell_polygon = fix_isea4t_antimeridian_cells(cell_polygon)
            
            cell_centroid = cell_polygon.centroid
            center_lat =  round(cell_centroid.y, 7)
            center_lon = round(cell_centroid.x, 7)
            cell_area = round(abs(geod.geometry_area_perimeter(cell_polygon)[0]),5)
            cell_perimeter = abs(geod.geometry_area_perimeter(cell_polygon)[1])
            avg_edge_len = round(cell_perimeter / 3,5)
            
            cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)
            if not cell_geometry.intersects(feature_geometry):
                continue  # Skip non-intersecting cells      
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
            new_attributes = [isea4t_cell_id, resolution, center_lat, center_lon, avg_edge_len, cell_area]
            all_attributes = original_attributes + new_attributes
            
            isea4t_feature.setAttributes(all_attributes)    

            isea4t_features.append(isea4t_feature)
        
    return isea4t_features

#######################
# QgsFeatures to OpenEAGGR ISEA3H
#######################

def qgsfeature2isea3h(feature, resolution):
    if (platform.system() == 'Windows'):
        geometry = feature.geometry()
        if geometry.wkbType() == QgsWkbTypes.Point:
            return point2isea3h(feature, resolution)
        elif geometry.wkbType() == QgsWkbTypes.LineString or geometry.wkbType() == QgsWkbTypes.Polygon:
            return poly2isea3h(feature, resolution)


def point2isea3h(feature, resolution):
    feature_geometry = feature.geometry()
    point = feature_geometry.asPoint()
    longitude = point.x()
    latitude = point.y()    
    accuracy = isea3h_res_accuracy_dict.get(resolution)

    lat_long_point = LatLongPoint(latitude, longitude, accuracy)

    isea3h_cell = isea3h_dggs.convert_point_to_dggs_cell(lat_long_point)

    isea3h_cell_id = isea3h_cell.get_cell_id() # Unique identifier for the current cell
    cell_polygon = isea3h_cell_to_polygon(isea3h_dggs,isea3h_cell)
    
    center_lat = round(cell_polygon.centroid.y,7)
    center_lon = round(cell_polygon.centroid.x,7)

    cell_area = round(abs(geod.geometry_area_perimeter(cell_polygon)[0]),2)
    cell_perimeter = abs(geod.geometry_area_perimeter(cell_polygon)[1])
    
    avg_edge_len = round(cell_perimeter/6,2)
    if resolution == 0:
        avg_edge_len = round(cell_perimeter / 3,2) # icosahedron faces
    
   
    cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)
    
    if cell_geometry:
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
        new_attributes = [isea3h_cell_id, resolution, center_lat, center_lon,  avg_edge_len, cell_area]
        all_attributes = original_attributes + new_attributes
        
        isea3h_feature.setAttributes(all_attributes)
        
        return [isea3h_feature]

def poly2isea3h(feature, resolution):
    feature_geometry = feature.geometry()
    feature_rect = feature_geometry.boundingBox()
    min_x = feature_rect.xMinimum()
    min_y = feature_rect.yMinimum()
    max_x = feature_rect.xMaximum()
    max_y = feature_rect.yMaximum()

    # Create a bounding box polygon
    bounding_box = box(min_x, min_y, max_x, max_y)
    bounding_box_wkt = bounding_box.wkt  # Create a bounding box polygon
    accuracy = isea3h_res_accuracy_dict.get(resolution)
    shapes = isea3h_dggs.convert_shape_string_to_dggs_shapes(bounding_box_wkt, ShapeStringFormat.WKT, accuracy)
    
    isea3h_features = [] 
    for shape in shapes:
        bbox_cells = shape.get_shape().get_outer_ring().get_cells()
        bounding_cell = isea3h_dggs.get_bounding_dggs_cell(bbox_cells)
        bounding_children_cells = get_isea3h_children_cells_within_bbox(isea3h_dggs,bounding_cell.get_cell_id(), bounding_box,resolution)
        for child in bounding_children_cells:
            isea3h_cell = DggsCell(child)
            cell_polygon = isea3h_cell_to_polygon(isea3h_dggs,isea3h_cell)
            isea3h_cell_id = isea3h_cell.get_cell_id()
            
            cell_centroid = cell_polygon.centroid
            center_lat =  round(cell_centroid.y, 7)
            center_lon = round(cell_centroid.x, 7)
            cell_area = round(abs(geod.geometry_area_perimeter(cell_polygon)[0]),2)
            cell_perimeter = abs(geod.geometry_area_perimeter(cell_polygon)[1])
            avg_edge_len = round(cell_perimeter/6,2)
            if resolution == 0:
                avg_edge_len = round(cell_perimeter / 3,2) # icosahedron faces
           
            cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)
            if cell_geometry:
                
                if not cell_geometry.intersects(feature_geometry):
                    continue  # Skip non-intersecting cells      
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
                new_attributes = [isea3h_cell_id, resolution, center_lat, center_lon, avg_edge_len, cell_area]
                all_attributes = original_attributes + new_attributes
                
                isea3h_feature.setAttributes(all_attributes)    

                isea3h_features.append(isea3h_feature)
            
    return isea3h_features




#######################
# QgsFeatures to EASE-DGGS
#######################

def qgsfeature2ease(feature, resolution):
    geometry = feature.geometry()
    if geometry.wkbType() == QgsWkbTypes.Point:
        return point2ease(feature, resolution)
    elif geometry.wkbType() == QgsWkbTypes.LineString or geometry.wkbType() == QgsWkbTypes.Polygon:
        return poly2ease(feature, resolution)


def point2ease(feature, resolution):
    return

def poly2ease(feature, resolution):
    return


#######################
# QgsFeatures to QTM
#######################

def qgsfeature2qtm(feature, resolution):
    geometry = feature.geometry()
    if geometry.wkbType() == QgsWkbTypes.Point:
        return point2qtm(feature, resolution)
    elif geometry.wkbType() == QgsWkbTypes.LineString or geometry.wkbType() == QgsWkbTypes.Polygon:
        return poly2qtm(feature, resolution)


def point2qtm(feature, resolution):     
    feature_geometry = feature.geometry()
    point = feature_geometry.asPoint()
    longitude = point.x()
    latitude = point.y()    
    
    qtm_id = qtm.latlon_to_qtm_id(latitude, longitude, resolution) 
    facet = qtm.qtm_id_to_facet(qtm_id)
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
        new_attributes = [qtm_id, resolution, center_lat, center_lon,  avg_edge_len, cell_area]
        all_attributes = original_attributes + new_attributes
        
        qtm_feature.setAttributes(all_attributes)
        
        return [qtm_feature]

def poly2qtm(feature, resolution):
    feature_geometry = feature.geometry()
    qtm_features = []
    
    levelFacets = {}
    QTMID = {}
        
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
               
                cell_centroid = facet_geom.centroid
                center_lat =  round(cell_centroid.y, 7)
                center_lon = round(cell_centroid.x, 7)
                cell_area = round(abs(geod.geometry_area_perimeter(facet_geom)[0]),2)
                cell_perimeter = abs(geod.geometry_area_perimeter(facet_geom)[1])
                avg_edge_len = round(cell_perimeter / 3,2)
                
                levelFacets[0].append(facet)
                cell_geometry = QgsGeometry.fromWkt(facet_geom.wkt)      
                
                if cell_geometry.intersects(feature_geometry) and resolution == 1 :                                         
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
                        
                    return qtm_features            
        else:
            for i, pf in enumerate(levelFacets[lvl - 1]):
                subdivided_facets = qtm.divideFacet(pf)
                for j, subfacet in enumerate(subdivided_facets):
                    subfacet_geom = qtm.constructGeometry(subfacet)
                    cell_geometry = QgsGeometry.fromWkt(subfacet_geom.wkt) 
                    
                    if cell_geometry.intersects(feature_geometry):  # Only keep intersecting facets
                        new_id = QTMID[lvl - 1][i] + str(j)
                        QTMID[lvl].append(new_id)
                        levelFacets[lvl].append(subfacet)
                        if lvl == resolution - 1:  # Only store final resolution
                            cell_centroid = subfacet_geom.centroid
                            center_lat =  round(cell_centroid.y, 7)
                            center_lon = round(cell_centroid.x, 7)
                            cell_area = round(abs(geod.geometry_area_perimeter(subfacet_geom)[0]),2)
                            cell_perimeter = abs(geod.geometry_area_perimeter(subfacet_geom)[1])
                            avg_edge_len = round(cell_perimeter / 3,2)                            
                          
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
                        
    return qtm_features
        

#######################
# QgsFeatures to Geohash
#######################

def qgsfeature2geohash(feature, resolution):
    geometry = feature.geometry()
    if geometry.wkbType() == QgsWkbTypes.Point:
        return point2geohash(feature, resolution)
    elif geometry.wkbType() == QgsWkbTypes.LineString or geometry.wkbType() == QgsWkbTypes.Polygon:
        return poly2geohash(feature, resolution)


def point2geohash(feature, resolution):
    feature_geometry = feature.geometry()
    point = feature_geometry.asPoint()
    longitude = point.x()
    latitude = point.y()    
    geohash_id = geohash.encode(latitude, longitude, resolution)
    bbox =  geohash.bbox(geohash_id)
    if bbox:
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
       
        center_lat = round(cell_polygon.centroid.y,7)
        center_lon = round(cell_polygon.centroid.x,7)

        cell_area = round(abs(geod.geometry_area_perimeter(cell_polygon)[0]),2)  # Area in square meters     
        cell_perimeter = abs(geod.geometry_area_perimeter(cell_polygon)[1])
        avg_edge_len = round(cell_perimeter/6,2)
        resolution =  len(geohash_id)
        cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)    
       
        # Create a single QGIS feature
        geohash_feature = QgsFeature()
        geohash_feature.setGeometry(cell_geometry)
        
        # Get all attributes from the input feature
        original_attributes = feature.attributes()
        original_fields = feature.fields()
        
        # Define new s2-related attributes
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
        
        geohash_feature.setFields(all_fields)
        
        # Combine original attributes with new attributes
        new_attributes = [geohash_id, resolution, center_lat, center_lon,  avg_edge_len, cell_area]
        all_attributes = original_attributes + new_attributes
        
        geohash_feature.setAttributes(all_attributes)
        
        return [geohash_feature]

def poly2geohash(feature, resolution):
    geohash_features = []
    feature_geometry = feature.geometry()
    feature_rect = feature_geometry.boundingBox()
    min_x = feature_rect.xMinimum()
    min_y = feature_rect.yMinimum()
    max_x = feature_rect.xMaximum()
    max_y = feature_rect.yMaximum()

    # Create a bounding box polygon
    bounding_box = box(min_x, min_y, max_x, max_y)
    
    bbox_center = ((bounding_box[0] + bounding_box[2]) / 2, (bounding_box[1] + bounding_box[3]) / 2)
    center_geohash = geohash.encode(bbox_center[1], bbox_center[0], precision=resolution)

    # Step 2: Find the ancestor geohash that fully contains the bounding box
    def find_ancestor_geohash(center_geohash, bbox):
        for r in range(1, len(center_geohash) + 1):
            ancestor = center_geohash[:r]
            polygon = geohash_to_polygon(ancestor)
            if polygon.contains(Polygon.from_bounds(*bbox)):
                return ancestor
        return None  # Fallback if no ancestor is found

    ancestor_geohash = find_ancestor_geohash(center_geohash, bounding_box)

    if not ancestor_geohash:
        raise ValueError("No ancestor geohash fully contains the bounding box.")

    # Step 3: Expand geohashes recursively from the ancestor
    bbox_polygon = Polygon.from_bounds(*bounding_box)

    def expand_geohash(gh, target_length, geohashes):
        """Expand geohash only if it intersects the bounding box."""
        polygon = geohash_to_polygon(gh)
        if not polygon.intersects(bbox_polygon):
            return  # Skip this branch if it doesn't intersect the bounding box

        if len(gh) == target_length:
            geohashes.add(gh)  # Add to the set if it reaches the target resolution
            return

        for char in "0123456789bcdefghjkmnpqrstuvwxyz":
            expand_geohash(gh + char, target_length, geohashes)

    geohashes = set()
    expand_geohash(ancestor_geohash, resolution, geohashes)

    # Step 4: Generate features for geohashes that intersect the bounding box
    for gh in geohashes:
        cell_polygon = geohash_to_polygon(gh)
        # if cell_polygon.intersects(feature):
        cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)    
            # **Check for intersection with the input feature**
        if not cell_geometry.intersects(feature_geometry):
            continue  # Skip non-intersecting cells
        
        # Create a single QGIS feature
        geohash_feature = QgsFeature()
        geohash_feature.setGeometry(cell_geometry)
        
        center_lat = round(cell_polygon.centroid.y,7)
        center_lon = round(cell_polygon.centroid.x,7)       
        cell_area = round(abs(geod.geometry_area_perimeter(cell_polygon)[0]),2)  # Area in square meters     
        cell_perimeter = abs(geod.geometry_area_perimeter(cell_polygon)[1])
        avg_edge_len = round(cell_perimeter/6,2)
    
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
        
        geohash_feature.setFields(all_fields)
        
        # Combine original attributes with new attributes
        new_attributes = [gh,resolution, center_lat, center_lon,  avg_edge_len, cell_area]
        all_attributes = original_attributes + new_attributes
        
        geohash_feature.setAttributes(all_attributes)    

        geohash_features.append(geohash_feature)
            
    return geohash_features
    

#######################
# QgsFeatures to Tilecode
#######################

def qgsfeature2tilecode(feature, resolution):
    geometry = feature.geometry()
    if geometry.wkbType() == QgsWkbTypes.Point:
        return point2tilecode(feature, resolution)
    elif geometry.wkbType() == QgsWkbTypes.LineString or geometry.wkbType() == QgsWkbTypes.Polygon:
        return poly2tilecode(feature, resolution)


def point2tilecode(feature, resolution):
    feature_geometry = feature.geometry()
    point = feature_geometry.asPoint()
    longitude = point.x()
    latitude = point.y()    
    tilecode_id = tilecode.latlon2tilecode(latitude, longitude,resolution)
    tilecode_cell = mercantile.tile(longitude, latitude, resolution)
    bounds = mercantile.bounds(tilecode_cell)
    if bounds:
        # Create the bounding box coordinates for the polygon
        min_lat, min_lon = bounds.south, bounds.west
        max_lat, max_lon = bounds.north, bounds.east        
        # quadkey = mercantile.quadkey(tilecode_cell)
        center_lat = round((min_lat + max_lat) / 2,7)
        center_lon = round((min_lon + max_lon) / 2,7)
        
        cell_polygon = Polygon([
            [min_lon, min_lat],  # Bottom-left corner
            [max_lon, min_lat],  # Bottom-right corner
            [max_lon, max_lat],  # Top-right corner
            [min_lon, max_lat],  # Top-left corner
            [min_lon, min_lat]   # Closing the polygon (same as the first point)
        ])
        cell_area = round(abs(geod.geometry_area_perimeter(cell_polygon)[0]),2)  # Area in square meters     
        cell_perimeter = abs(geod.geometry_area_perimeter(cell_polygon)[1])
        avg_edge_len = round(cell_perimeter/6,2)
        resolution = tilecode_cell.z 
        cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)
    
        if cell_geometry:
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
            new_fields.append(QgsField("avg_edge_len", QVariant.Double))
            new_fields.append(QgsField("cell_area", QVariant.Double))
            
            # Combine original fields and new fields
            all_fields = QgsFields()
            for field in original_fields:
                all_fields.append(field)
            for field in new_fields:
                all_fields.append(field)
            
            tilecode_feature.setFields(all_fields)
            
            # Combine original attributes with new attributes
            new_attributes = [tilecode_id, resolution, center_lat, center_lon,  avg_edge_len, cell_area]
            all_attributes = original_attributes + new_attributes
            
            tilecode_feature.setAttributes(all_attributes)
            
            return [tilecode_feature]

def poly2tilecode(feature, resolution):
    feature_geometry = feature.geometry()
    feature_rect = feature_geometry.boundingBox()
    min_x = feature_rect.xMinimum()
    min_y = feature_rect.yMinimum()
    max_x = feature_rect.xMaximum()
    max_y = feature_rect.yMaximum()

    tilecode_features = []
    tiles = mercantile.tiles(min_x, min_y, max_x, max_y, resolution)
    
    for tile in tiles:
        z, x, y = tile.z, tile.x, tile.y
        tilecode_id = f"z{tile.z}x{tile.x}y{tile.y}"
        bounds = mercantile.bounds(x, y, z)
        if bounds:
            # Create the bounding box coordinates for the polygon
            min_lat, min_lon = bounds.south, bounds.west
            max_lat, max_lon = bounds.north, bounds.east            
            # quadkey = mercantile.quadkey(tile)
            center_lat = round((min_lat + max_lat) / 2,7)
            center_lon = round((min_lon + max_lon) / 2,7)
            
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
            if not cell_geometry.intersects(feature_geometry):
                continue  # Skip non-intersecting cells
            
            # Create a single QGIS feature
            tilecode_feature = QgsFeature()
            tilecode_feature.setGeometry(cell_geometry)
            
            cell_area = round(abs(geod.geometry_area_perimeter(cell_polygon)[0]),2)  # Area in square meters     
            cell_perimeter = abs(geod.geometry_area_perimeter(cell_polygon)[1])
            avg_edge_len = round(cell_perimeter/6,2)
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
            new_fields.append(QgsField("avg_edge_len", QVariant.Double))
            new_fields.append(QgsField("cell_area", QVariant.Double))
            
            # Combine original fields and new fields
            all_fields = QgsFields()
            for field in original_fields:
                all_fields.append(field)
            for field in new_fields:
                all_fields.append(field)
            
            tilecode_feature.setFields(all_fields)
            
            # Combine original attributes with new attributes
            new_attributes = [tilecode_id,resolution, center_lat, center_lon,  avg_edge_len, cell_area]
            all_attributes = original_attributes + new_attributes
            
            tilecode_feature.setAttributes(all_attributes)    

            tilecode_features.append(tilecode_feature)
            
    return tilecode_features