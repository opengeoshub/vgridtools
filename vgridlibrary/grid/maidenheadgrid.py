# https://github.com/ha8tks/Leaflet.Maidenhead
# https://ha8tks.github.io/Leaflet.Maidenhead/examples/
# https://www.sotamaps.org/

import json
import argparse
from vgrid.geocode import maidenhead
from tqdm import tqdm  
import fiona
from shapely.geometry import Point, Polygon, mapping


def maidenheadgrid(precision):
    # Define the grid parameters based on the precision
    if precision == 1:
        x_cells, y_cells, lon_width, lat_width = 18, 18, 20, 10
    elif precision == 2:
        x_cells, y_cells, lon_width, lat_width = 180, 180, 2, 1
    elif precision == 3:
        x_cells, y_cells, lon_width, lat_width = 1800, 1800, 0.2, 0.1
    elif precision == 4:
        x_cells, y_cells, lon_width, lat_width = 18000, 18000, 0.02, 0.01
    else:
        raise ValueError("Unsupported precision")

    cells = []
    base_lat, base_lon = -90, -180  # Starting latitude and longitude

    for i in tqdm(range(x_cells), desc="Generating cells", unit="cell"):
        for j in range(y_cells):
            # Calculate bounds
            min_lon = base_lon + i * lon_width
            max_lon = min_lon + lon_width
            min_lat = base_lat + j * lat_width
            max_lat = min_lat + lat_width
            center_lat = (min_lat + max_lat) / 2
            center_lon = (min_lon + max_lon) / 2
            maidenhead_code = maidenhead.toMaiden(center_lat, center_lon, precision)

            cells.append({
                'center_lat': center_lat,
                'center_lon': center_lon,
                'min_lat': min_lat,
                'min_lon': min_lon,
                'max_lat': max_lat,
                'max_lon': max_lon,
                'maidenhead': maidenhead_code
            })
    
    return cells

def maidengrid2geojson(cells):
    features = []

    for cell in cells:
        center_lat, center_lon, min_lat, min_lon, max_lat, max_lon, maiden_code = (
            cell['center_lat'], cell['center_lon'], cell['min_lat'], cell['min_lon'],
            cell['max_lat'], cell['max_lon'], cell['maiden_code']
        )
        
        # Create the polygon from the bounding box
        polygon_coords = [
            [min_lon, min_lat],  # Bottom-left
            [max_lon, min_lat],  # Bottom-right
            [max_lon, max_lat],  # Top-right
            [min_lon, max_lat],  # Top-left
            [min_lon, min_lat]   # Closing the polygon
        ]
        
        # Add Point Feature
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [center_lon, center_lat]  # [lon, lat]
            },
            "properties": {
                "maiden": maiden_code
            }
        })
        
        # Add Polygon Feature
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [polygon_coords]  # List of coordinates
            },
            "properties": {
                "maiden": maiden_code
            }
        })

    # Create GeoJSON structure
    geojson = {
        "type": "FeatureCollection",
        "features": features
    }

    return geojson

def maidengrid2shapefile(cells, output_path):
    # Define the schema for the Shapefile
    schema = {
        'geometry': 'Polygon',
        'properties': {'maiden': 'str'}
    }

    # Open a new Shapefile for writing
    with fiona.open(output_path, 'w', driver='ESRI Shapefile', schema=schema, crs='EPSG:4326') as shpfile:
        for cell in cells:
            # Extract cell data
            center_lat = cell['center_lat']
            center_lon = cell['center_lon']
            min_lat = cell['min_lat']
            min_lon = cell['min_lon']
            max_lat = cell['max_lat']
            max_lon = cell['max_lon']
            maiden_code = cell['maidenhead']

            # Create the polygon from the bounding box
            polygon_coords = [
                (min_lon, min_lat),  # Bottom-left
                (max_lon, min_lat),  # Bottom-right
                (max_lon, max_lat),  # Top-right
                (min_lon, max_lat),  # Top-left
                (min_lon, min_lat)   # Closing the polygon
            ]
            polygon = Polygon(polygon_coords)

            # Write the polygon feature to the Shapefile
            shpfile.write({
                'geometry': mapping(polygon),
                'properties': {'maiden': maiden_code}
            })


def main():
    parser = argparse.ArgumentParser(description="Generate Maidenhead grid cells and save as Shapefile")
    parser.add_argument('-p', '--precision', type=int, choices=[1, 2, 3, 4], default=1,
                        help="Precision level for Maidenhead grid (1 to 4)")
    parser.add_argument('-o', '--output', type=str, required=True,
                        help="Output file path for the Shapefile data (e.g., output.shp)")
    args = parser.parse_args()
    
    try:
        cells = maidenheadgrid(args.precision)
        maidengrid2shapefile(cells, args.output)

        print(f"Shapefile data for Maidenhead precision {args.precision} written to {args.output}")

    except Exception as e:
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    main()