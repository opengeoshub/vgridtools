import argparse
import geopandas as gpd
from shapely.geometry import Polygon
from pyproj import CRS, Transformer
from vgrid.geocode import mgrs
from tqdm import tqdm

# Need to be reviewed
def calculate_bbox(epsg):
    """
    Calculate the full bounding box for a UTM zone based on its EPSG code.

    Parameters:
    - epsg: EPSG code of the UTM zone (e.g., 32648 for zone 48N or 32748 for zone 48S).

    Returns:
    - bbox: Tuple representing (minx, miny, maxx, maxy) for the UTM zone.
    """
    crs = CRS.from_epsg(epsg)
    zone_number = int(str(epsg)[-2:])  # Extract the zone number from the EPSG code
    hemisphere = 'north' if str(epsg).startswith('326') else 'south'

    # Calculate the longitude bounds of the UTM zone
    west_longitude = (zone_number - 1) * 6 - 180  # Western boundary of the UTM zone in degrees
    east_longitude = west_longitude + 6  # Eastern boundary of the UTM zone in degrees

    # Set latitude range based on the hemisphere
    if hemisphere == 'north':
        south_latitude = 0  # UTM zones cover from 0 to 84 degrees north
        north_latitude = 84
    else:
        south_latitude = -80  # UTM zones cover from -80 to 0 degrees south
        north_latitude = 0

    # Set up a transformer from WGS84 (longitude, latitude) to the UTM zone coordinates
    transformer = Transformer.from_crs(CRS.from_epsg(4326), crs, always_xy=True)

    # Transform the corner points of the zone to UTM coordinates
    minx, miny = transformer.transform(west_longitude, south_latitude)
    maxx, maxy = transformer.transform(east_longitude, north_latitude)

    # Ensure min and max values are correctly assigned
    minx = min(minx, maxx)
    maxx = max(minx, maxx)
    miny = min(miny, maxy)
    maxy = max(miny, maxy)

    # Return the calculated bounding box
    return minx, miny, maxx, maxy

def create_mgrs_grid(minx, miny, maxx, maxy, cell_size, crs):
    """
    Create a grid of square polygons within a specified bounding box using UTM coordinates.

    Parameters:
    - minx, miny, maxx, maxy: Bounding box coordinates in meters.
    - cell_size: Size of each grid cell in meters.
    - crs: Coordinate reference system in UTM (e.g., EPSG:32648).

    Returns:
    - grid: GeoDataFrame containing grid polygons with unique MGRS codes.
    """
    # Calculate the number of rows and columns based on cell size
    if cell_size == 100000:
        precision = 0
    elif cell_size == 10000:
        precision = 1
    elif cell_size == 1000:
        precision = 2
    elif cell_size == 100:
        precision = 3
    elif cell_size == 10:
        precision = 4
    elif cell_size < 10:
        precision = 5

    rows = int((maxy - miny) / cell_size)
    cols = int((maxx - minx) / cell_size)
    
    # Initialize lists to hold grid polygons and MGRS codes
    polygons = []
    mgrs_codes = []
    
    # Set up transformer to convert UTM to WGS84 (longitude, latitude)
    transformer = Transformer.from_crs(crs, CRS.from_epsg(4326), always_xy=True)
    
    for i in tqdm(range(cols), desc="Processing grid columns"):
        for j in tqdm(range(rows), desc="Processing grid rows", leave=False):
            # Calculate the bounds of the cell
            x1 = minx + i * cell_size
            x2 = x1 + cell_size
            y1 = miny + j * cell_size
            y2 = y1 + cell_size
            
            # Create the polygon for the cell
            polygon = Polygon([(x1, y1), (x2, y1), (x2, y2), (x1, y2)])
            polygons.append(polygon)
            
            # Calculate the centroid of the polygon
            centroid = polygon.centroid
            
            # Convert the centroid coordinates from UTM to WGS84 (longitude, latitude)
            lon, lat = transformer.transform(centroid.x, centroid.y)
            
            # Convert the WGS84 coordinates to MGRS
            mgrs_code = mgrs.toMgrs(lat, lon, precision)
            mgrs_codes.append(mgrs_code)
    
    # Create a GeoDataFrame with the polygons and MGRS codes, and set the CRS
    grid = gpd.GeoDataFrame({'geometry': polygons, 'mgrs': mgrs_codes}, crs=crs)
    
    return grid


def main():
    # Set up argument parser
    parser = argparse.ArgumentParser(description="Create a UTM grid with specified cell size and save as a shapefile.")
    parser.add_argument("-o", "--output", required=True, help="Output shapefile path")
    parser.add_argument("-cellsize", type=int, required=True, help="Cell size in meters")
    parser.add_argument("-epsg", type=int, default=32648, help="EPSG code for the UTM CRS (default: 32648)")
    
    # Parse the arguments
    args = parser.parse_args()
    
    # Calculate the bounding box based on the EPSG code and cell size
    bbox = calculate_bbox(args.epsg)
    print (str(bbox))
    # Example for UTM zone 48N (EPSG:32648)
    # bbox = (100000, 0, 900000, 9500000) # for the North 
    # bbox = (100000, 100000, 900000, 10000000) # for the South 

    # bbox = (100000, 100000, 900000, 10000000)
    
    # Set up the CRS using the provided EPSG code
    crs = CRS.from_epsg(args.epsg)
    
    # Create the grid with the specified cell size
    grid = create_mgrs_grid(*bbox, args.cellsize, crs)
    
    # Save the grid as a shapefile
    grid.to_file(args.output)
    print(f"Grid saved to {args.output}")


if __name__ == "__main__":
    main()