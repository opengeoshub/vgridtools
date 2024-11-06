#Reference: https://observablehq.com/@claude-ducharme/h3-map
# https://h3-snow.streamlit.app/

import argparse
import h3
from shapely.geometry import Polygon, mapping
import geojson
from tqdm import tqdm

def h3_to_polygon(h3_index):
    """Convert H3 index to a Shapely Polygon."""
    boundary = h3.h3_to_geo_boundary(h3_index, geo_json=True)
    polygon = Polygon(boundary)
    return polygon

def generate_h3_indices(resolution):
    """Generate H3 indices at a given resolution level covering the entire world."""
    if resolution < 0 or resolution > 15:
        raise ValueError("Resolution level must be between 0 and 15.")
    
    # Use H3's built-in methods to get all hexagons at a given resolution
    h3_indices = set()
    for lat in range(-90, 90):
        for lon in range(-180, 0): # western
        # for lon in range(0, 180):  # eastern
            h3_index = h3.geo_to_h3(lat, lon, resolution)
            h3_indices.update(h3.h3_to_children(h3_index, resolution))
    
    return h3_indices

def create_world_polygons_at_resolution(resolution):
    """Create a GeoJSON FeatureCollection of polygons at a given resolution level."""
    h3_polygons = []
    h3_indices = generate_h3_indices(resolution)
    
    for h3_index in tqdm(h3_indices, desc='Generating Polygons'):
        polygon = h3_to_polygon(h3_index)
        h3_polygons.append(geojson.Feature(
            geometry=mapping(polygon),
            properties={"h3": h3_index}
        ))
    
    feature_collection = geojson.FeatureCollection(h3_polygons)
    return feature_collection

def save_to_geojson(feature_collection, filename):
    """Save the FeatureCollection to a GeoJSON file."""
    with open(filename, 'w') as f:
        geojson.dump(feature_collection, f)

def main():
    parser = argparse.ArgumentParser(description='Generate world polygons based on H3 indices.')
    parser.add_argument('-r', '--resolution', type=int, required=True, help='Resolution level for the H3 indices (0-15)')
    args = parser.parse_args()
    
    try:
        resolution = args.resolution
        world_polygons = create_world_polygons_at_resolution(resolution)
        output_filename = f'./h3_western_{resolution}.geojson'
        save_to_geojson(world_polygons, output_filename)
        print(f"GeoJSON file saved as: {output_filename}")
    except ValueError as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
