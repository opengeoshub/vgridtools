import h3
from shapely.geometry import Point, LineString, Polygon, mapping, box
import argparse
import json
from tqdm import tqdm
from pyproj import Geod
geod = Geod(ellps="WGS84")
import os 
from vgrid.generator.h3grid import fix_h3_antimeridian_cells

chunk_size = 10_000  # Adjust the chunk size as needed

def chunk_list(data, chunk_size):
    """Yield successive chunks from a list."""
    for i in range(0, len(data), chunk_size):
        yield data[i:i + chunk_size]

# Function to generate grid for Point
def point_to_grid(resolution, point):
    features = []
    # Convert point to the seed cell
    latitude = point.y
    longitude = point.x
    h3_cell = h3.latlng_to_cell(latitude, longitude, resolution)
    
    cell_boundary = h3.cell_to_boundary(h3_cell)     
    # Wrap and filter the boundary
    filtered_boundary = fix_h3_antimeridian_cells(cell_boundary)
    # Reverse lat/lon to lon/lat for GeoJSON compatibility
    reversed_boundary = [(lon, lat) for lat, lon in filtered_boundary]
    cell_polygon = Polygon(reversed_boundary)
    
    center_lat, center_lon = h3.cell_to_latlng(h3_cell)
    center_lat = round(center_lat,7)
    center_lon = round(center_lon,7)
    cell_area = round(abs(geod.geometry_area_perimeter(cell_polygon)[0]),2)  # Area in square meters     
    cell_perimeter = abs(geod.geometry_area_perimeter(cell_polygon)[1])  # Perimeter in meters  
    avg_edge_len = round(cell_perimeter/6,2)
    if (h3.is_pentagon(h3_cell)):
        avg_edge_len = round(cell_perimeter/5,2)
                
    features.append({
                    "type": "Feature",
                    "geometry": mapping(cell_polygon),
                    "properties": {
                        "h3": h3_cell,
                        "center_lat": center_lat,
                        "center_lon": center_lon,
                        "cell_area": cell_area,
                        "avg_edge_len": avg_edge_len,
                        "resolution": resolution
                    }
                })
    return {
        "type": "FeatureCollection",
        "features": features,
    }

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

# Function to generate grid for Polyline
def polyline_to_grid(resolution, geometry):
    features = []

    if geometry.geom_type == 'LineString':
        polylines = [geometry]
    elif geometry.geom_type == 'MultiLineString':
        polylines = list(geometry)

    for polyline in polylines:
        bbox = box(*polyline.bounds)
        distance = h3.average_hexagon_edge_length(resolution, unit='m') * 2
        bbox_buffer = geodesic_buffer(bbox, distance)
        bbox_buffer_cells = h3.geo_to_cells(bbox_buffer, resolution)

        # Process in chunks
        for chunk in tqdm(chunk_list(bbox_buffer_cells, chunk_size), desc=f"Processing chunks of {chunk_size} cells"):
            for bbox_buffer_cell in chunk:
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

                if cell_polygon.intersects(polyline):
                    features.append({
                        "type": "Feature",
                        "geometry": mapping(cell_polygon),
                        "properties": {
                            "h3": bbox_buffer_cell,
                            "center_lat": center_lat,
                            "center_lon": center_lon,
                            "cell_area": cell_area,
                            "avg_edge_len": avg_edge_len,
                            "resolution": resolution
                        }
                    })

    return {
        "type": "FeatureCollection",
        "features": features,
    }
       
# Function to generate grid for Polygon
def polygon_to_grid(resolution, geometry):
    features = []

    if geometry.geom_type == 'Polygon':
        polygons = [geometry]
    elif geometry.geom_type == 'MultiPolygon':
        polygons = list(geometry)

    for polygon in polygons:
        bbox = box(*polygon.bounds)  # Create a bounding box polygon
        distance = h3.average_hexagon_edge_length(resolution, unit='m') * 2
        bbox_buffer = geodesic_buffer(bbox, distance)
        bbox_buffer_cells = h3.geo_to_cells(bbox_buffer, resolution)

        # Process in chunks
        for chunk in tqdm(chunk_list(bbox_buffer_cells, chunk_size), desc=f"Processing chunks of {chunk_size} cells"):
            for bbox_buffer_cell in chunk:
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

                if cell_polygon.intersects(polygon):
                    features.append({
                        "type": "Feature",
                        "geometry": mapping(cell_polygon),
                        "properties": {
                            "h3": bbox_buffer_cell,
                            "center_lat": center_lat,
                            "center_lon": center_lon,
                            "cell_area": cell_area,
                            "avg_edge_len": avg_edge_len,
                            "resolution": resolution
                        }
                    })

    return {
        "type": "FeatureCollection",
        "features": features,
    }
    

# Main function to handle different GeoJSON shapes
def main():
    parser = argparse.ArgumentParser(description="Generate H3 grid for shapes in GeoJSON format")
    parser.add_argument('-r', '--resolution', type=int, required=True, help="Resolution of the grid [0..15]")
    parser.add_argument(
        '-geojson', '--geojson', type=str, required=True, help="GeoJSON string with Point, Polyline or Polygon"
    )
    args = parser.parse_args()
    geojson = args.geojson
     # Initialize h3 DGGS
    resolution = args.resolution
    
    if resolution < 0 or resolution > 15:
        print(f"Please select a resolution in [0..15] range and try again ")
        return
    
    if not os.path.exists(geojson):
        print(f"Error: The file {geojson} does not exist.")
        return

    with open(geojson, 'r', encoding='utf-8') as f:
        geojson_data = json.load(f)
    
    geojson_features = []

    # Process GeoJSON features in chunks
    for feature_chunk in tqdm(chunk_list(geojson_data['features'], chunk_size), desc=f"Processing chunks of {chunk_size} features"):
        for feature in feature_chunk:
            if feature['geometry']['type'] in ['Point', 'MultiPoint']:
                coordinates = feature['geometry']['coordinates']
                if feature['geometry']['type'] == 'Point':
                    point = Point(coordinates)
                    point_features = point_to_grid(resolution, point)
                    geojson_features.extend(point_features['features'])

                elif feature['geometry']['type'] == 'MultiPoint':
                    for point_coords in coordinates:
                        point = Point(point_coords)
                        point_features = point_to_grid(resolution, point)
                        geojson_features.extend(point_features['features'])

            elif feature['geometry']['type'] in ['LineString', 'MultiLineString']:
                coordinates = feature['geometry']['coordinates']
                if feature['geometry']['type'] == 'LineString':
                    polyline = LineString(coordinates)
                    polyline_features = polyline_to_grid(resolution, polyline)
                    geojson_features.extend(polyline_features['features'])

                elif feature['geometry']['type'] == 'MultiLineString':
                    for line_coords in coordinates:
                        polyline = LineString(line_coords)
                        polyline_features = polyline_to_grid(resolution, polyline)
                        geojson_features.extend(polyline_features['features'])

            elif feature['geometry']['type'] in ['Polygon', 'MultiPolygon']:
                coordinates = feature['geometry']['coordinates']

                if feature['geometry']['type'] == 'Polygon':
                    exterior_ring = coordinates[0]
                    interior_rings = coordinates[1:]
                    polygon = Polygon(exterior_ring, interior_rings)
                    polygon_features = polygon_to_grid(resolution, polygon)
                    geojson_features.extend(polygon_features['features'])

                elif feature['geometry']['type'] == 'MultiPolygon':
                    for sub_polygon_coords in coordinates:
                        exterior_ring = sub_polygon_coords[0]
                        interior_rings = sub_polygon_coords[1:]
                        polygon = Polygon(exterior_ring, interior_rings)
                        polygon_features = polygon_to_grid(resolution, polygon)
                        geojson_features.extend(polygon_features['features'])

   
    # Save the results to GeoJSON
    geojson_path = f"geojson2h3_{resolution}.geojson"
    with open(geojson_path, 'w') as f:
        json.dump({"type": "FeatureCollection", "features": geojson_features}, f, indent=2)

    print(f"GeoJSON saved as {geojson_path}")


if __name__ == "__main__":
    main()
