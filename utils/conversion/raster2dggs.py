from shapely.geometry import Polygon, box, mapping
from shapely.wkt import loads as wkt_loads
import platform,re
from qgis.core import (
    QgsRasterLayer,
    QgsRaster,
    QgsFeature,
    QgsGeometry,
    QgsVectorLayer,
    QgsFields,
    QgsField,
    QgsPointXY,
    QgsWkbTypes,
    QgsCoordinateTransformContext,
    QgsProject
)
from PyQt5.QtCore import QVariant
from math import cos, radians

import h3 
from vgrid.utils import s2, qtm, olc, geohash, georef,mgrs,tilecode
from vgrid.generator.s2grid import s2_cell_to_polygon
from vgrid.utils import mercantile
from vgrid.utils.rhealpixdggs.dggs import RHEALPixDGGS
from vgrid.conversion.dggscompact import rhealpix_compact 

from vgrid.generator.h3grid import fix_h3_antimeridian_cells, geodesic_buffer
from vgrid.conversion.dggs2geojson import rhealpix_cell_to_polygon
from vgrid.generator.geohashgrid import geohash_to_polygon
from vgrid.generator.settings import graticule_dggs_metrics, geodesic_dggs_metrics

from vgrid.utils.easedggs.constants import levels_specs
from vgrid.utils.easedggs.dggs.grid_addressing import grid_ids_to_geos,geos_to_grid_ids

if (platform.system() == 'Windows'):
    from vgrid.utils.eaggr.eaggr import Eaggr
    from vgrid.utils.eaggr.shapes.dggs_cell import DggsCell
    from vgrid.utils.eaggr.enums.model import Model
    from vgrid.utils.eaggr.enums.shape_string_format import ShapeStringFormat
    from vgrid.utils.eaggr.shapes.lat_long_point import LatLongPoint
    from vgrid.generator.isea4tgrid import isea4t_cell_to_polygon, isea4t_res_accuracy_dict,\
                                                fix_isea4t_antimeridian_cells, get_isea4t_children_cells_within_bbox
    from vgrid.conversion.dggscompact import isea4t_compact, isea3h_compact
    isea4t_dggs = Eaggr(Model.ISEA4T)

    from vgrid.generator.isea3hgrid import isea3h_cell_to_polygon, isea3h_res_accuracy_dict,get_isea3h_children_cells_within_bbox                                   
    isea3h_dggs = Eaggr(Model.ISEA3H)

from vgrid.conversion.dggscompact import qtm_compact,olc_compact,geohash_compact,tilecode_compact,quadkey_compact

from vgrid.generator.geohashgrid import initial_geohashes, geohash_to_polygon, expand_geohash_bbox

from vgrid.conversion import latlon2dggs

from pyproj import Geod
geod = Geod(ellps="WGS84")
p90_n180, p90_n90, p90_p0, p90_p90, p90_p180 = (90.0, -180.0), (90.0, -90.0), (90.0, 0.0), (90.0, 90.0), (90.0, 180.0)
p0_n180, p0_n90, p0_p0, p0_p90, p0_p180 = (0.0, -180.0), (0.0, -90.0), (0.0, 0.0), (0.0, 90.0), (0.0, 180.0)
n90_n180, n90_n90, n90_p0, n90_p90, n90_p180 = (-90.0, -180.0), (-90.0, -90.0), (-90.0, 0.0), (-90.0, 90.0), (-90.0, 180.0)

def raster2h3(raster_layer: QgsRasterLayer, resolution) -> QgsVectorLayer:
    if not raster_layer.isValid():
        raise ValueError("Invalid raster layer.")

    provider = raster_layer.dataProvider()
    extent = raster_layer.extent()
    width = raster_layer.width()
    height = raster_layer.height()
    crs = raster_layer.crs()

    band_count = provider.bandCount()

    h3_cells = set()

    pixel_size_x = extent.width() / width
    pixel_size_y = extent.height() / height

    for row in range(height):
        for col in range(width):
            x = extent.xMinimum() + col * pixel_size_x
            y = extent.yMaximum() - row * pixel_size_y  # Top to bottom
            h3_index = h3.latlng_to_cell(y, x, resolution)
            h3_cells.add(h3_index)

    # Create a memory layer
    mem_layer = QgsVectorLayer(f"Polygon?crs={crs.authid()}", "H3 Grid", "memory")
    provider = mem_layer.dataProvider()

    # Define fields
    fields = QgsFields()
    fields.append(QgsField("h3", QVariant.String))
    fields.append(QgsField("resolution", QVariant.Int))
    for i in range(band_count):
        fields.append(QgsField(f"band_{i+1}", QVariant.Double))

    provider.addAttributes(fields)
    mem_layer.updateFields()

    for h3_index in h3_cells:
        lat, lon = h3.cell_to_latlng(h3_index)
        point = QgsPointXY(lon, lat)

        # Sample raster at the centroid point
        ident = raster_layer.dataProvider().identify(point, QgsRaster.IdentifyFormatValue)

        if ident.isValid():
            results = ident.results()

            # Create hexagon geometry
            boundary = h3.cell_to_boundary(h3_index)
            if boundary:
                fixed = fix_h3_antimeridian_cells(boundary)
                ring = [(lon, lat) for lat, lon in fixed]
                polygon = QgsGeometry.fromPolygonXY([[QgsPointXY(lon, lat) for lon, lat in ring]])

                feat = QgsFeature()
                feat.setGeometry(polygon)

                props = {
                    "h3": h3_index,
                    "resolution": resolution
                }

                for i in range(band_count):
                    props[f"band_{i+1}"] = results.get(i + 1, None)

                feat.setAttributes([props[field.name()] for field in fields])
                provider.addFeatures([feat])

    mem_layer.updateExtents()
    return mem_layer
