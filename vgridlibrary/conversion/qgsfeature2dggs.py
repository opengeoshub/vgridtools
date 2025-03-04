from vgrid.utils import olc,mgrs, maidenhead, geohash, georef, olc, s2, gars
from vgrid.utils import mercantile
from vgrid.utils.rhealpixdggs.dggs import RHEALPixDGGS
from vgrid.utils.rhealpixdggs.dggs import my_round

# import sys, os
# sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "utils", "rhealpixdggs")))


from shapely.geometry import Polygon, box, mapping
import h3 
from vgrid.utils.antimeridian import fix_polygon
import shapely

from qgis.core import QgsFeature, QgsGeometry, QgsPointXY, QgsField, QgsFields,QgsWkbTypes


from PyQt5.QtCore import QVariant

from pyproj import Geod
geod = Geod(ellps="WGS84")

def fix_antimeridian_cells(hex_boundary, threshold=-128):
    if any(lon < threshold for _, lon in hex_boundary):
        # Adjust all longitudes accordingly
        return [(lat, lon - 360 if lon > 0 else lon) for lat, lon in hex_boundary]
    return hex_boundary


#######################
# QgsFeatures to H3
#######################

def geodesic_buffer(polygon, distance):
    buffered_coords = []
    for lon, lat in polygon.exterior.coords:
        # Generate points around the current vertex to approximate a circle
        circle_coords = [
            geod.fwd(lon, lat, azimuth, distance)[:2]  # Forward calculation: returns (lon, lat, back_azimuth)
            for azimuth in range(0, 360, 10)  # Generate points every 10 degrees
        ]
        buffered_coords.append(circle_coords)
    
    # Flatten the list of buffered points and form a Polygon
    all_coords = [coord for circle in buffered_coords for coord in circle]
    return Polygon(all_coords).convex_hull

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
    filtered_boundary = fix_antimeridian_cells(cell_boundary)
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
    new_attributes = [str(h3_cell), center_lat, center_lon, cell_area, avg_edge_len, resolution]
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
        filtered_boundary = fix_antimeridian_cells(cell_boundary)
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
        new_attributes = [str(bbox_buffer_cell), center_lat, center_lon, cell_area, avg_edge_len, resolution]
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
        
        s2_feature.setFields(all_fields)
        
        # Combine original attributes with new attributes
        new_attributes = [str(cell_token), center_lat, center_lon, cell_area, avg_edge_len, resolution]
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
        
        s2_feature.setFields(all_fields)
        
        # Combine original attributes with new attributes
        new_attributes = [cell_token, center_lat, center_lon, cell_area, avg_edge_len, resolution]
        all_attributes = original_attributes + new_attributes
        
        s2_feature.setAttributes(all_attributes)    

        s2_features.append(s2_feature)
    
    return s2_features


#######################
# QgsFeatures to Rhealpix
#######################
rhealpix_dggs = RHEALPixDGGS()

def rhealpix_cell_to_polygon(rhealpix_cell):
    vertices = [tuple(my_round(coord, 14) for coord in vertex) for vertex in rhealpix_cell.vertices(plane=False)]
    if vertices[0] != vertices[-1]:
        vertices.append(vertices[0])
    vertices = fix_antimeridian_cells(vertices)
    return Polygon(vertices)

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
        
        rhealpix_feature.setFields(all_fields)
        
        # Combine original attributes with new attributes
        new_attributes = [seed_cell_id, center_lat, center_lon, cell_area, avg_edge_len, resolution]
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
        cell_area = abs(geod.geometry_area_perimeter(seed_cell_polygon)[0])  # Area in square meters                
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
        new_fields.append(QgsField("rhealpix", QVariant.String))  # Dynamic cell ID field
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
        
        rhealpix_feature.setFields(all_fields)
        
        # Combine original attributes with new attributes
        new_attributes = [seed_cell_id, center_lat, center_lon, cell_area, avg_edge_len, resolution]
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
            cell_area = abs(geod.geometry_area_perimeter(cell_polygon)[0])  # Area in square meters                
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
            new_fields.append(QgsField("rhealpix", QVariant.String))  # Dynamic cell ID field
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
            
            rhealpix_feature.setFields(all_fields)
            
            # Combine original attributes with new attributes
            new_attributes = [cell_id, center_lat, center_lon, cell_area, avg_edge_len, resolution]
            all_attributes = original_attributes + new_attributes
            
            rhealpix_feature.setAttributes(all_attributes)    

            rhealpix_features.append(rhealpix_feature)
        
    return rhealpix_features
