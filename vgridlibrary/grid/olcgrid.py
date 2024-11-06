#Reference: https://github.com/google/open-location-code/tree/main/tile_server/gridserver
# https://github.com/google/open-location-code

import argparse
import vgrid.geocode.olc as olc
from tqdm import tqdm
from shapely.geometry import Polygon, mapping
import geopandas as gpd
import pandas as pd


def generate_all_olcs(length):
    """Generate all OLC codes of a given length."""
    olc_chars = '23456789CFGHJMPQRVWX'
    if length < 2:
        raise ValueError("OLC length should be at least 2.")

    def olc_generator(prefix, depth):
        if depth == length:
            yield prefix
        else:
            for char in olc_chars:
                yield from olc_generator(prefix + char, depth + 1)

    return olc_generator("", 0)

def create_polygon_for_olc(olc_code):
    """Create a Shapely Polygon feature for a given OLC code."""
    decoded = olc.decode(olc_code)
    coordinates = [
        (decoded.longitudeLo, decoded.latitudeLo),
        (decoded.longitudeLo, decoded.latitudeHi),
        (decoded.longitudeHi, decoded.latitudeHi),
        (decoded.longitudeHi, decoded.latitudeLo),
        (decoded.longitudeLo, decoded.latitudeLo)
    ]
    polygon = Polygon(coordinates)
    return polygon

def is_within_bounding_box(decoded, bbox):
    """Check if the OLC's bounding box is within the specified bounding box."""
    return (decoded.longitudeLo < bbox[2] and decoded.longitudeHi > bbox[0] and
            decoded.latitudeLo < bbox[3] and decoded.latitudeHi > bbox[1])

def generate_shapefile_for_olc_length(length, bbox):
    """Generate a GeoDataFrame of OLC polygons of a given length within a bounding box."""
    features = []
    total_codes = 20 ** length  # Total number of possible codes of the given length
    for olc_code in tqdm(generate_all_olcs(length), total=total_codes, desc="Generating Shapefile"):
        decoded = olc.decode(olc_code)
        if is_within_bounding_box(decoded, bbox):
            polygon = create_polygon_for_olc(olc_code)
            features.append({
                "geometry": polygon,
                "olc": olc_code  # Directly use pluscode as a column
            })
    
    # Convert list of features to DataFrame
    df = pd.DataFrame(features)
    # Create GeoDataFrame
    gdf = gpd.GeoDataFrame(df, geometry='geometry', crs="EPSG:4326")
    return gdf

def main():
    parser = argparse.ArgumentParser(description="Generate Shapefile with OLC codes and centroids.")
    parser.add_argument('-p', '--precision', type=int, required=True, help="Length of the plus code [2,4,8]")
    parser.add_argument('-o', '--output', type=str, required=True, help="Output filename for the Shapefile")
    
    args = parser.parse_args()
    
    length = args.precision
    if length not in [2, 4, 8]:
        print("Error: Precision (code length) must be one of [2, 4, 8].")
        return
    
    bbox = [-180, -85.051129, 180, 85.051129]  # Bounding box for the entire globe
    
    gdf = generate_shapefile_for_olc_length(length, bbox)
    
    output_filename = args.output
    if not output_filename.lower().endswith('.shp'):
        output_filename += '.shp'
    
    gdf.to_file(output_filename, driver='ESRI Shapefile')
    print(f"Shapefile saved as {output_filename}")

if __name__ == "__main__":
    main()