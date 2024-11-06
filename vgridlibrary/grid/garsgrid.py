# from gars_field import EDGARSGrid

# # from latlon
# ggrid = EDGARSGrid.from_latlon(-89.55, -179.57, resolution=6)
# print(ggrid)
# # from GARS ID
# # ggrid = EDGARSGrid("D01AA23")

# # get bounding poly
# grid_poly = ggrid.polygon
# print(grid_poly)
# # get GARS ID
# gars_id = str(ggrid)
# print(gars_id)
# # UTM CRS EPSG Code
# epsg_code = ggrid.utm_epsg
# print(epsg_code)
# https://github.com/Moustikitos/gryd/blob/c79edde94f19d46e3b3532ae14eb351e91d55322/Gryd/geodesy.py
import geopandas as gpd
import shapely.geometry as geom
from pyproj import CRS
from vgrid.geocode.gars import GARSGrid
import numpy as np
import math


def gars(longitude, latitude):
    base = "ABCDEFGHJKLMNPQRSTUVWXYZ"
    longitude = (longitude+180) % 360
    latitude = (latitude+90) % 180

    lon_idx = longitude / 0.5
    lat_idx = latitude / 0.5

    quadrant = "%03d" % (lon_idx+1) + base[int(math.floor(lat_idx//24))] + base[int(math.floor(lat_idx%24))]
    
    lon_num_idx = (lon_idx - math.floor(lon_idx)) * 2.
    lat_num_idx = (lat_idx - math.floor(lat_idx)) * 2.
    j = math.floor(lon_num_idx)
    i = 1-math.floor(lat_num_idx)
    number = i*(j+1)+j+1

    lon_key_idx = (lon_num_idx - math.floor(lon_num_idx)) * 3.
    lat_key_idx = (lat_num_idx - math.floor(lat_num_idx)) * 3.
    j = math.floor(lon_key_idx)
    i = 2-math.floor(lat_key_idx)
    key = i*(j+1)+j+1

    return quadrant+str(number)+str(key)

def from_gars(gars, anchor=""):
	"""return Geodesic object from gars. Optional anchor value to define where to handle 5minx5min tile"""
	base = "ABCDEFGHJKLMNPQRSTUVWXYZ"
	longitude = 5./60. * (0 if "w" in anchor else 1 if "e" in anchor else 0.5)
	latitude = 5./60. * (0 if "s" in anchor else 1 if "n" in anchor else 0.5)

	key = gars[6]
	longitude += 5./60. * (0 if key in "147" else 1 if key in "258" else 2)
	latitude += 5./60. * (0 if key in "789" else 1 if key in "456" else 2)
	
	number = gars[5]
	longitude += 15./60. * (0 if number in "13" else 1)
	latitude += 15./60. * (0 if number in "34" else 1)

	longitude += (int(gars[:3])-1)*0.5
	latitude += (base.index(gars[3])*24 + base.index(gars[4]))*0.5

	return (longitude-180, latitude-90)


def generate_gars_grid():
    # Define bounds for the whole planet
    lon_min, lon_max = -180.0, 180.0
    lat_min, lat_max = -90.0, 90.0
    
    # Initialize a list to store GARS grid polygons
    gars_grid = []
    res = 0.25
    # Use numpy to generate ranges with floating-point steps
    longitudes = np.arange(lon_min, lon_max, res)
    latitudes = np.arange(lat_min, lat_max, res)
    
    # Loop over longitudes and latitudes in 30-minute intervals
    for lon in longitudes:
        for lat in latitudes:
            # Create a polygon for each GARS cell
            poly = geom.box(lon, lat, lon + res, lat + res)
            # gars_code = EDGARSGrid.from_latlon(lat, lon,1)  
            gars_code = GARSGrid.from_latlon(lat,lon,res*60) 
            # poly = gars_code.polygon
            # print(gars_code)
            # print(poly)
            gars_grid.append({'geometry': poly, 'gars': str(gars_code)})
    
    print(gars_grid)
    
    # # Create a GeoDataFrame
    gars_gdf = gpd.GeoDataFrame(gars_grid, crs=CRS.from_epsg(4326))
    
    # # Save the grid
    gars_gdf.to_file('./data/grid/gars/gars_grid_15minutes.geojson', driver='GeoJSON')

# Run the function
generate_gars_grid()
