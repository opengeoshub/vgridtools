
# https://github.com/corteva/gars-field
from vgrid.geocode import georef
# georef_code = georef.encode(10.534535345,106.4343242,3)
# print(georef_code)
# georef_decode = georef.decode(georef_code)
# print(georef_decode)
import geopandas as gpd
from shapely.geometry import Polygon
import numpy as np
import shapely.geometry as geom
from pyproj import CRS

def generate_georef_grid():
    # Define bounds for the whole planet
    lon_min, lon_max = -180.0, 180.0
    lat_min, lat_max = -90.0, 90.0
    
    # Initialize a list to store GARS grid polygons
    gars_grid = []
    res = 1
    # Use numpy to generate ranges with floating-point steps
    longitudes = np.arange(lon_min, lon_max, res)
    latitudes = np.arange(lat_min, lat_max, res)
    
    # Loop over longitudes and latitudes in 30-minute intervals
    for lon in longitudes:
        for lat in latitudes:
            # Create a polygon for each GARS cell
            poly = geom.box(lon, lat, lon + res, lat + res)
            # gars_code = EDGARSGrid.from_latlon(lat, lon,1)  
            gars_code = georef.encode(lat,lon,0) 
            # poly = gars_code.polygon
            # print(gars_code)
            # print(poly)
            gars_grid.append({'geometry': poly, 'georef': str(gars_code)})
    
    print(gars_grid)
    
    # # Create a GeoDataFrame
    gars_gdf = gpd.GeoDataFrame(gars_grid, crs=CRS.from_epsg(4326))
    
    # # Save the grid
    gars_gdf.to_file('./data/georef/georef_grid_15minutes.geojson', driver='GeoJSON')

# Run the function
generate_georef_grid()


