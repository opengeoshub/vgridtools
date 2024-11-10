from qgis.core import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from qgis.gui import QgsMessageBar
from math import *
import qgis.utils
from .geohashgrid import *
import geopandas as gpd
import os 

# def geohash_to_bbox(gh):
#     """Convert geohash to bounding box coordinates."""
#     lat, lon = geohash.decode(gh)
#     lat_err, lon_err = geohash.decode_exactly(gh)[2:]
    
#     bbox = {
#         'w': max(lon - lon_err, -180),
#         'e': min(lon + lon_err, 180),
#         's': max(lat - lat_err, -85.051129),
#         'n': min(lat + lat_err, 85.051129)
#     }
    
#     return bbox

# def geohash_to_polygon(gh):
#     """Convert geohash to a Shapely Polygon."""
#     bbox = geohash_to_bbox(gh)
#     polygon = Polygon([
#         (bbox['w'], bbox['s']),
#         (bbox['w'], bbox['n']),
#         (bbox['e'], bbox['n']),
#         (bbox['e'], bbox['s']),
#         (bbox['w'], bbox['s'])
#     ])
    
#     return polygon

# def generate_geohashes(precision):
#     """Generate geohashes at a given precision level."""
#     if precision < 1 or precision > 12:
#         raise ValueError("Precision level must be between 1 and 12.")
    
#     geohashes = set()
#     initial_geohashes = ["b", "c", "f", "g", "u", "v", "y", "z", "8", "9", "d", "e", "s", "t", "w", "x", "0", "1", "2", "3", "p", "q", "r", "k", "m", "n", "h", "j", "4", "5", "6", "7"]
    
#     def expand_geohash(gh, target_length):
#         if len(gh) == target_length:
#             geohashes.add(gh)
#             return
#         for char in "0123456789bcdefghjkmnpqrstuvwxyz":
#             expand_geohash(gh + char, target_length)
    
#     for gh in initial_geohashes:
#         expand_geohash(gh, precision)
    
#     return geohashes

# def create_world_polygons_at_precision(precision):
#     """Create a GeoDataFrame of polygons at a given precision level."""
#     geohash_polygons = []
#     geohashes = generate_geohashes(precision)
    
#     for gh in geohashes:
#         polygon = geohash_to_polygon(gh)
#         geohash_polygons.append({
#             'geometry': polygon,
#             'geohash': gh
#         })
    
#     gdf = gpd.GeoDataFrame(geohash_polygons, columns=['geometry', 'geohash'])
#     gdf.crs = 'EPSG:4326'  # Set the CRS to WGS84
#     return gdf


def geohash_grid(geohash_precision, outdir,status_callback = None):
    output_filename = f"{outdir}/geohash_{geohash_precision}.shp"
    # Check if the file already exists
    if os.path.exists(output_filename):
        QMessageBox.critical(None, "Error", f"The file '{output_filename}' already exists. Please choose another folder")
        return
        
    world_polygons_gdf = create_world_polygons_at_precision(geohash_precision)
    # save_to_shapefile(world_polygons_gdf, output_filename)
    world_polygons_gdf.to_file(output_filename, driver='ESRI Shapefile')
    if not os.path.exists(output_filename):
        QMessageBox.critical(None, "Error", f"Shapefile was not created: {output_filename}")
        return
    
    layer = QgsVectorLayer(output_filename, f'geohash_{geohash_precision}', 'ogr')

    if not layer.isValid():
        QMessageBox.critical(None, "Error", "Layer could not be loaded.")
        print(f"Failed to load layer from: {output_filename}")  # Debugging output
        return

    QgsProject.instance().addMapLayer(layer)
    qgis.utils.iface.layerTreeView().refreshLayerSymbology(layer.id())

    # percen_complete = i/len(wholelist)*100
    # if status_callback:
    #     status_callback(i,None)
    # i+=1

    # if status_callback:
    #     status_callback(100,None)
    
    try:
        qgis.utils.iface.setActiveLayer(layer)
        qgis.utils.iface.zoomToActiveLayer()
    except :
        pass
    
    return
