import platform
from qgis.core import (
    QgsRasterLayer,
    QgsRaster,
    QgsFeature,
    QgsGeometry,
    QgsVectorLayer,
    QgsFields,
    QgsField,
    QgsPointXY
)
from PyQt5.QtCore import QVariant
import math
import h3 


from vgrid.dggs import s2, qtm, olc, geohash, tilecode
from vgrid.conversion.latlon2dggs import *
from vgrid.conversion.dggs2geo.h32geo import h32geo
from vgrid.conversion.dggs2geo.s22geo import s22geo
from vgrid.conversion.dggs2geo.a52geo import a52geo
from vgrid.conversion.dggs2geo.isea4t2geo import isea4t2geo
from vgrid.conversion.dggs2geo.qtm2geo import qtm2geo
from vgrid.conversion.dggs2geo.olc2geo import olc2geo
from vgrid.conversion.dggs2geo.geohash2geo import geohash2geo
from vgrid.conversion.dggs2geo.tilecode2geo import tilecode2geo
from vgrid.conversion.dggs2geo.quadkey2geo import quadkey2geo
from vgrid.conversion.dggs2geo.dggal2geo import dggal2geo
from vgrid.utils.constants import DGGAL_TYPES
from dggal import *
from vgrid.dggs.rhealpixdggs.dggs import RHEALPixDGGS
from vgrid.utils.geometry import (
    graticule_dggs_metrics, geodesic_dggs_metrics,
    rhealpix_cell_to_polygon
)
from vgrid.dggs.rhealpixdggs.ellipsoids import WGS84_ELLIPSOID

E = WGS84_ELLIPSOID

if (platform.system() == 'Windows'):
    from vgrid.dggs.eaggr.eaggr import Eaggr
    from vgrid.dggs.eaggr.shapes.dggs_cell import DggsCell
    from vgrid.dggs.eaggr.enums.model import Model
    isea4t_dggs = Eaggr(Model.ISEA4T)
    isea3h_dggs = Eaggr(Model.ISEA3H)

from pyproj import Geod
geod = Geod(ellps="WGS84")
p90_n180, p90_n90, p90_p0, p90_p90, p90_p180 = (90.0, -180.0), (90.0, -90.0), (90.0, 0.0), (90.0, 90.0), (90.0, 180.0)
p0_n180, p0_n90, p0_p0, p0_p90, p0_p180 = (0.0, -180.0), (0.0, -90.0), (0.0, 0.0), (0.0, 90.0), (0.0, 180.0)
n90_n180, n90_n90, n90_p0, n90_p90, n90_p180 = (-90.0, -180.0), (-90.0, -90.0), (-90.0, 0.0), (-90.0, 90.0), (-90.0, 180.0)

########################## 
# H3
# ########################
def raster2h3(raster_layer: QgsRasterLayer, resolution: int, feedback=None) -> QgsVectorLayer:
    if not raster_layer.isValid():
        raise ValueError("Invalid raster layer.")

    provider = raster_layer.dataProvider()
    extent = raster_layer.extent()
    width, height = raster_layer.width(), raster_layer.height()
    crs = raster_layer.crs()
    band_count = provider.bandCount()

    pixel_size_x = extent.width() / width
    pixel_size_y = extent.height() / height

    h3_cells = set()

    for row in range(height):
        if feedback and feedback.isCanceled():
            return None
        for col in range(width):
            x = extent.xMinimum() + col * pixel_size_x
            y = extent.yMaximum() - row * pixel_size_y
            h3_index = h3.latlng_to_cell(y, x, resolution)
            h3_cells.add(h3_index)
        if feedback:
            feedback.setProgress(int(row / height * 100))

    if feedback:
        feedback.pushInfo(f"{len(h3_cells)} pixels processed.")
        feedback.setProgress(0)
        feedback.pushInfo("Generating H3 DGGS...")

    mem_layer = QgsVectorLayer(f"Polygon?crs={crs.authid()}", "H3 Grid", "memory")
    mem_provider = mem_layer.dataProvider()

    fields = QgsFields()
    fields.append(QgsField("h3", QVariant.String))
    fields.append(QgsField("resolution", QVariant.Int))
    fields.append(QgsField("center_lat", QVariant.Double))
    fields.append(QgsField("center_lon", QVariant.Double))
    fields.append(QgsField("avg_edge_len", QVariant.Double))
    fields.append(QgsField("cell_area", QVariant.Double))
    fields.append(QgsField("cell_perimeter", QVariant.Double))
    for i in range(band_count):
        fields.append(QgsField(f"band_{i + 1}", QVariant.Double))
    mem_provider.addAttributes(fields)
    mem_layer.updateFields()

    for i, h3_index in enumerate(h3_cells):
        if feedback and feedback.isCanceled():
            return None
        lat, lon = h3.cell_to_latlng(h3_index)
        point = QgsPointXY(lon, lat)
        ident = provider.identify(point, QgsRaster.IdentifyFormatValue)
        if not ident.isValid():
            continue
        results = ident.results()
        if all(results.get(i + 1) is None or math.isnan(results.get(i + 1, float('nan'))) for i in range(band_count)):
            continue

        # Use h32geo to get the cell polygon with proper antimeridian handling
        cell_polygon = h32geo(h3_index)
        if not cell_polygon:
            continue        

        num_edges = 5 if h3.is_pentagon(h3_index) else 6
        center_lat, center_lon, avg_edge_len, cell_area,cell_perimeter = geodesic_dggs_metrics(cell_polygon, num_edges)
        cell_geom = QgsGeometry.fromWkt(cell_polygon.wkt)
        feature = QgsFeature()
        feature.setGeometry(cell_geom)
        attributes = {
            "h3": h3_index,
            "resolution": resolution,
            "center_lat": center_lat,
            "center_lon": center_lon,
            "avg_edge_len": avg_edge_len,
            "cell_area": cell_area,
            "cell_perimeter": cell_perimeter,
        }
        for i in range(band_count):
            attributes[f"band_{i + 1}"] = results.get(i + 1, None)
        feature.setAttributes([attributes[field.name()] for field in fields])
        mem_provider.addFeatures([feature])
        if feedback and i % 100 == 0:
            feedback.setProgress(int(100 * i / len(h3_cells)))

    if feedback:
        feedback.setProgress(100)
        feedback.pushInfo("Raster to H3 DGGS completed.")
            
    return mem_layer

########################## 
# S2
# ########################
def raster2s2(raster_layer: QgsRasterLayer, resolution, feedback=None) -> QgsVectorLayer:
    if not raster_layer.isValid():
        raise ValueError("Invalid raster layer.")

    provider = raster_layer.dataProvider()
    extent = raster_layer.extent()
    width, height = raster_layer.width(), raster_layer.height()
    crs = raster_layer.crs()
    band_count = provider.bandCount()

    pixel_size_x = extent.width() / width
    pixel_size_y = extent.height() / height

    s2_tokens = set()

    for row in range(height):
        if feedback and feedback.isCanceled():
            return None
        for col in range(width):
            x = extent.xMinimum() + col * pixel_size_x
            y = extent.yMaximum() - row * pixel_size_y
            s2_token = latlon2s2(y, x, resolution)
            s2_tokens.add(s2_token)
        if feedback:
            feedback.setProgress(int(row / height * 100))

    if feedback:
        feedback.pushInfo(f"{len(s2_tokens)} pixels processed.")
        feedback.setProgress(0)
        feedback.pushInfo("Generating S2 DGGS...")

    mem_layer = QgsVectorLayer(f"Polygon?crs={crs.authid()}", "S2 Grid", "memory")
    mem_provider = mem_layer.dataProvider()

    fields = QgsFields()
    fields.append(QgsField("s2", QVariant.String))
    fields.append(QgsField("resolution", QVariant.Int))
    fields.append(QgsField("center_lat", QVariant.Double))
    fields.append(QgsField("center_lon", QVariant.Double))
    fields.append(QgsField("avg_edge_len", QVariant.Double))
    fields.append(QgsField("cell_area", QVariant.Double))
    fields.append(QgsField("cell_perimeter", QVariant.Double))
    for i in range(band_count):
        fields.append(QgsField(f"band_{i+1}", QVariant.Double))
    mem_provider.addAttributes(fields)
    mem_layer.updateFields()

    for i, s2_token in enumerate(s2_tokens):
        if feedback and feedback.isCanceled():
            return None

        s2_id = s2.CellId.from_token(s2_token)
        s2_cell = s2.Cell(s2_id)
        centroid_latlng = s2.LatLng.from_point(s2_cell.get_center())
        lat, lon = centroid_latlng.lat().degrees, centroid_latlng.lng().degrees
        center_point = QgsPointXY(lon, lat)

        ident = provider.identify(center_point, QgsRaster.IdentifyFormatValue)
        if not ident.isValid():
            continue
        results = ident.results()
        if all(results.get(i + 1) is None or math.isnan(results.get(i + 1, float("nan"))) for i in range(band_count)):
            continue
        cell_polygon = s22geo(s2_token)
        num_edges = 4
        center_lat, center_lon, avg_edge_len, cell_area,cell_perimeter = geodesic_dggs_metrics(cell_polygon, num_edges)
        cell_geom = QgsGeometry.fromWkt(cell_polygon.wkt)

        feature = QgsFeature()
        feature.setGeometry(cell_geom)
        attr_values = [
            s2_token,
            resolution,
            center_lat,
            center_lon,
            avg_edge_len,
            cell_area,
            cell_perimeter,
        ]
        attr_values.extend(results.get(i + 1, None) for i in range(band_count))
        feature.setAttributes(attr_values)
        mem_provider.addFeatures([feature])
        if feedback and i % 100 == 0:
            feedback.setProgress(int(100 * i / len(s2_tokens)))

    if feedback:
        feedback.setProgress(100)
        feedback.pushInfo("Raster to S2 DGGS completed.")
    

    return mem_layer


########################## 
# A5
# ########################
def raster2a5(raster_layer: QgsRasterLayer, resolution, feedback=None) -> QgsVectorLayer:
    if not raster_layer.isValid():
        raise ValueError("Invalid raster layer.")

    provider = raster_layer.dataProvider()
    extent = raster_layer.extent()
    width, height = raster_layer.width(), raster_layer.height()
    crs = raster_layer.crs()
    band_count = provider.bandCount()

    pixel_size_x = extent.width() / width
    pixel_size_y = extent.height() / height

    a5_hexes = set()

    for row in range(height):
        if feedback and feedback.isCanceled():
            return None
        for col in range(width):
            x = extent.xMinimum() + col * pixel_size_x
            y = extent.yMaximum() - row * pixel_size_y
            a5_hex = latlon2a5(y, x, resolution)
            a5_hexes.add(a5_hex)
        if feedback:
            feedback.setProgress(int(row / height * 100))

    if feedback:
        feedback.pushInfo(f"{len(a5_hexes)} pixels processed.")
        feedback.setProgress(0)
        feedback.pushInfo("Generating A5 DGGS...")

    mem_layer = QgsVectorLayer(f"Polygon?crs={crs.authid()}", "A5 Grid", "memory")
    mem_provider = mem_layer.dataProvider()

    fields = QgsFields()
    fields.append(QgsField("a5", QVariant.String))
    fields.append(QgsField("resolution", QVariant.Int))
    fields.append(QgsField("center_lat", QVariant.Double))
    fields.append(QgsField("center_lon", QVariant.Double))
    fields.append(QgsField("avg_edge_len", QVariant.Double))
    fields.append(QgsField("cell_area", QVariant.Double))
    fields.append(QgsField("cell_perimeter", QVariant.Double))
    for i in range(band_count):
        fields.append(QgsField(f"band_{i+1}", QVariant.Double))
    mem_provider.addAttributes(fields)
    mem_layer.updateFields()

    for i, a5_hex in enumerate(a5_hexes):
        if feedback and feedback.isCanceled():
            return None

        cell_polygon = a52geo(a5_hex)
        if not cell_polygon:
            continue
        
        center_point = QgsPointXY(cell_polygon.centroid.x, cell_polygon.centroid.y)

        ident = provider.identify(center_point, QgsRaster.IdentifyFormatValue)
        if not ident.isValid():
            continue
        results = ident.results()
        if all(results.get(i + 1) is None or math.isnan(results.get(i + 1, float("nan"))) for i in range(band_count)):
            continue
        
        cell_geom = QgsGeometry.fromWkt(cell_polygon.wkt)   
                
        num_edges = 5 
        center_lat, center_lon, avg_edge_len, cell_area,cell_perimeter = geodesic_dggs_metrics(cell_polygon, num_edges)

        feature = QgsFeature()
        feature.setGeometry(cell_geom)
        attr_values = [
            a5_hex,
            resolution,
            center_lat,
            center_lon,
            avg_edge_len,
            cell_area,
            cell_perimeter,
        ]
        attr_values.extend(results.get(i + 1, None) for i in range(band_count))
        feature.setAttributes(attr_values)
        mem_provider.addFeatures([feature])
        if feedback and i % 100 == 0:
            feedback.setProgress(int(100 * i / len(a5_hexes)))

    if feedback:
        feedback.setProgress(100)
        feedback.pushInfo("Raster to A5 DGGS completed.")
    

    return mem_layer


########################## 
# rHEALpix
# ########################
def raster2rhealpix(raster_layer: QgsRasterLayer, resolution, feedback=None) -> QgsVectorLayer:
    rhealpix_dggs = RHEALPixDGGS(ellipsoid=E, north_square=1, south_square=3, N_side=3)

    if not raster_layer.isValid():
        raise ValueError("Invalid raster layer.")

    provider = raster_layer.dataProvider()
    extent = raster_layer.extent()
    width, height = raster_layer.width(), raster_layer.height()
    crs = raster_layer.crs()
    band_count = provider.bandCount()

    pixel_size_x = extent.width() / width
    pixel_size_y = extent.height() / height

    rhealpix_ids = set()
    total_pixels = width * height
    processed_pixels = 0

    for row in range(height):
        for col in range(width):
            if feedback and feedback.isCanceled():
                return None

            x = extent.xMinimum() + col * pixel_size_x
            y = extent.yMaximum() - row * pixel_size_y
            rhealpix_id = latlon2rhealpix(y, x, resolution)
            rhealpix_ids.add(rhealpix_id)

            processed_pixels += 1
            if feedback and processed_pixels % 10000 == 0:
                feedback.setProgress(int(100 * processed_pixels / total_pixels))

    if feedback:
        feedback.pushInfo(f"{len(rhealpix_ids)} pixels processed.")
        feedback.setProgress(0)
        feedback.pushInfo("Generating rHEALpix DGGS...")

    mem_layer = QgsVectorLayer(f"Polygon?crs={crs.authid()}", "rHEALpix Grid", "memory")
    mem_provider = mem_layer.dataProvider()

    fields = QgsFields()
    fields.append(QgsField("rhealpix", QVariant.String))
    fields.append(QgsField("resolution", QVariant.Int))
    fields.append(QgsField("center_lat", QVariant.Double))
    fields.append(QgsField("center_lon", QVariant.Double))
    fields.append(QgsField("avg_edge_len", QVariant.Double))
    fields.append(QgsField("cell_area", QVariant.Double))
    fields.append(QgsField("cell_perimeter", QVariant.Double))
    for i in range(band_count):
        fields.append(QgsField(f"band_{i+1}", QVariant.Double))

    mem_provider.addAttributes(fields)
    mem_layer.updateFields()

    for i, rhealpix_id in enumerate(rhealpix_ids):
        if feedback and feedback.isCanceled():
            return None

        rhealpix_uids = (rhealpix_id[0],) + tuple(map(int, rhealpix_id[1:]))
        rhealpix_cell = rhealpix_dggs.cell(rhealpix_uids)

        lon, lat = rhealpix_cell.centroid(plane=False)
        center_point = QgsPointXY(lon, lat)

        ident = provider.identify(center_point, QgsRaster.IdentifyFormatValue)
        if not ident.isValid():
            continue

        results = ident.results()
        if all(results.get(i + 1) is None or math.isnan(results.get(i + 1, float("nan"))) for i in range(band_count)):
            continue

        cell_polygon = rhealpix_cell_to_polygon(rhealpix_cell)
        if not cell_polygon:
            continue    
        num_edges = 3 if rhealpix_cell.ellipsoidal_shape() == 'dart' else 4
        center_lat, center_lon, avg_edge_len, cell_area,cell_perimeter = geodesic_dggs_metrics(cell_polygon, num_edges)
        cell_geom = QgsGeometry.fromWkt(cell_polygon.wkt)

        feature = QgsFeature()
        feature.setGeometry(cell_geom)
        attr_values = [
            rhealpix_id,
            resolution,
            center_lat,
            center_lon,
            avg_edge_len,
            cell_area,
            cell_perimeter,
            ]
        attr_values.extend(results.get(i + 1, None) for i in range(band_count))
        feature.setAttributes(attr_values)

        mem_provider.addFeatures([feature])

        if feedback and i % 100 == 0:
            feedback.setProgress(int(100 * i / len(rhealpix_ids)))

    if feedback:
        feedback.setProgress(100)
        feedback.pushInfo("Raster to rHEALpix DGGS completed.")

    return mem_layer


########################## 
# ISEA4T
# ########################
def raster2isea4t(raster_layer: QgsRasterLayer, resolution, feedback=None) -> QgsVectorLayer:
    if (platform.system() == 'Windows'):        

        if not raster_layer.isValid():
            raise ValueError("Invalid raster layer.")

        provider = raster_layer.dataProvider()
        extent = raster_layer.extent()
        width, height = raster_layer.width(), raster_layer.height()
        crs = raster_layer.crs()
        band_count = provider.bandCount()

        pixel_size_x = extent.width() / width
        pixel_size_y = extent.height() / height

        isea4t_ids = set()
        total_pixels = width * height
        processed_pixels = 0

        for row in range(height):
            for col in range(width):
                if feedback and feedback.isCanceled():
                    return None

                x = extent.xMinimum() + col * pixel_size_x
                y = extent.yMaximum() - row * pixel_size_y
                isea4t_id = latlon2isea4t(y, x, resolution)
                isea4t_ids.add(isea4t_id)

                processed_pixels += 1
                if feedback and processed_pixels % 10000 == 0:
                    feedback.setProgress(int(100 * processed_pixels / total_pixels))

        if feedback:
            feedback.pushInfo(f"{len(isea4t_ids)} pixels processed.")
            feedback.setProgress(0)
            feedback.pushInfo("Generating ISEA4T DGGS...")

        mem_layer = QgsVectorLayer(f"Polygon?crs={crs.authid()}", "isea4t Grid", "memory")
        mem_provider = mem_layer.dataProvider()

        fields = QgsFields()
        fields.append(QgsField("isea4t", QVariant.String))
        fields.append(QgsField("resolution", QVariant.Int))
        fields.append(QgsField("center_lat", QVariant.Double))
        fields.append(QgsField("center_lon", QVariant.Double))
        fields.append(QgsField("avg_edge_len", QVariant.Double))
        fields.append(QgsField("cell_area", QVariant.Double))
        fields.append(QgsField("cell_perimeter", QVariant.Double))
        for i in range(band_count):
            fields.append(QgsField(f"band_{i+1}", QVariant.Double))

        mem_provider.addAttributes(fields)
        mem_layer.updateFields()

        for i, isea4t_id in enumerate(isea4t_ids):
            if feedback and feedback.isCanceled():
                return None
                        
            isea4t_cell=DggsCell(isea4t_id)
            lat_long_point = isea4t_dggs.convert_dggs_cell_to_point(isea4t_cell)
            lat, lon = lat_long_point._latitude, lat_long_point._longitude
            center_point = QgsPointXY(lon, lat)

            ident = provider.identify(center_point, QgsRaster.IdentifyFormatValue)
            if not ident.isValid():
                continue

            results = ident.results()
            if all(results.get(i + 1) is None or math.isnan(results.get(i + 1, float("nan"))) for i in range(band_count)):
                continue

            cell_polygon = isea4t2geo(isea4t_id)
            if not cell_polygon:
                continue
            
            num_edges = 3
            
            center_lat, center_lon, avg_edge_len, cell_area,cell_perimeter = geodesic_dggs_metrics(cell_polygon, num_edges)

            cell_geom = QgsGeometry.fromWkt(cell_polygon.wkt)

            feature = QgsFeature()
            feature.setGeometry(cell_geom)
            attr_values = [
                isea4t_id,
                resolution,
                center_lat,
                center_lon,
                avg_edge_len,
                cell_area,
                cell_perimeter,
            ]
            attr_values.extend(results.get(i + 1, None) for i in range(band_count))
            feature.setAttributes(attr_values)

            mem_provider.addFeatures([feature])

            if feedback and i % 100 == 0:
                feedback.setProgress(int(100 * i / len(isea4t_ids)))

        if feedback:
            feedback.setProgress(100)
            feedback.pushInfo("Raster to ISEA4T DGGS completed.")

        return mem_layer


########################## 
# QTM
# ########################
def raster2qtm(raster_layer: QgsRasterLayer, resolution, feedback=None) -> QgsVectorLayer:
    if not raster_layer.isValid():
        raise ValueError("Invalid raster layer.")

    provider = raster_layer.dataProvider()
    extent = raster_layer.extent()
    width, height = raster_layer.width(), raster_layer.height()
    crs = raster_layer.crs()
    band_count = provider.bandCount()

    pixel_size_x = extent.width() / width
    pixel_size_y = extent.height() / height

    qtm_ids = set()
    total_pixels = width * height
    processed_pixels = 0

    for row in range(height):
        for col in range(width):
            if feedback and feedback.isCanceled():
                return None

            x = extent.xMinimum() + col * pixel_size_x
            y = extent.yMaximum() - row * pixel_size_y
            qtm_id = latlon2qtm(y, x, resolution)
            qtm_ids.add(qtm_id)

            processed_pixels += 1
            if feedback and processed_pixels % 10000 == 0:
                feedback.setProgress(int(100 * processed_pixels / total_pixels))

    if feedback:
        feedback.pushInfo(f"{len(qtm_ids)} pixels processed.")
        feedback.setProgress(0)
        feedback.pushInfo("Generating QTM DGGS...")

    mem_layer = QgsVectorLayer(f"Polygon?crs={crs.authid()}", "QTM Grid", "memory")
    mem_provider = mem_layer.dataProvider()

    fields = QgsFields()
    fields.append(QgsField("qtm", QVariant.String))
    fields.append(QgsField("resolution", QVariant.Int))
    fields.append(QgsField("center_lat", QVariant.Double))
    fields.append(QgsField("center_lon", QVariant.Double))
    fields.append(QgsField("avg_edge_len", QVariant.Double))
    fields.append(QgsField("cell_area", QVariant.Double))
    fields.append(QgsField("cell_perimeter", QVariant.Double))
    for i in range(band_count):
        fields.append(QgsField(f"band_{i+1}", QVariant.Double))

    mem_provider.addAttributes(fields)
    mem_layer.updateFields()

    for i, qtm_id in enumerate(qtm_ids):
        if feedback and feedback.isCanceled():
            return None
        lat,lon = qtm.qtm_id_to_latlon(qtm_id)
        center_point = QgsPointXY(lon, lat)

        ident = provider.identify(center_point, QgsRaster.IdentifyFormatValue)
        if not ident.isValid():
            continue

        results = ident.results()
        if all(results.get(i + 1) is None or math.isnan(results.get(i + 1, float("nan"))) for i in range(band_count)):
            continue
        
        cell_polygon = qtm2geo(qtm_id)
        if not cell_polygon:
            continue
        num_edges = 3
        center_lat, center_lon, avg_edge_len, cell_area,cell_perimeter = geodesic_dggs_metrics(cell_polygon, num_edges)

        cell_geom = QgsGeometry.fromWkt(cell_polygon.wkt)

        feature = QgsFeature()
        feature.setGeometry(cell_geom)
        attr_values = [
            qtm_id,
            resolution,
            center_lat,
            center_lon,
            avg_edge_len,
            cell_area,
            cell_perimeter,
        ]
        attr_values.extend(results.get(i + 1, None) for i in range(band_count))
        feature.setAttributes(attr_values)

        mem_provider.addFeatures([feature])

        if feedback and i % 100 == 0:
            feedback.setProgress(int(100 * i / len(qtm_ids)))

    if feedback:
        feedback.setProgress(100)
        feedback.pushInfo("Raster to QTM DGGS completed.")

    return mem_layer

########################## 
# OLC
# ########################
def raster2olc(raster_layer: QgsRasterLayer, resolution, feedback=None) -> QgsVectorLayer:
    if not raster_layer.isValid():
        raise ValueError("Invalid raster layer.")

    provider = raster_layer.dataProvider()
    extent = raster_layer.extent()
    width, height = raster_layer.width(), raster_layer.height()
    crs = raster_layer.crs()
    band_count = provider.bandCount()

    pixel_size_x = extent.width() / width
    pixel_size_y = extent.height() / height

    olc_ids = set()
    total_pixels = width * height
    processed_pixels = 0

    for row in range(height):
        for col in range(width):
            if feedback and feedback.isCanceled():
                return None

            x = extent.xMinimum() + col * pixel_size_x
            y = extent.yMaximum() - row * pixel_size_y
            olc_id = latlon2olc(y, x, resolution)
            olc_ids.add(olc_id)

            processed_pixels += 1
            if feedback and processed_pixels % 10000 == 0:
                feedback.setProgress(int(100 * processed_pixels / total_pixels))

    if feedback:
        feedback.pushInfo(f"{len(olc_ids)} pixels processed.")
        feedback.setProgress(0)
        feedback.pushInfo("Generating OLC DGGS...")

    mem_layer = QgsVectorLayer(f"Polygon?crs={crs.authid()}", "OLC Grid", "memory")
    mem_provider = mem_layer.dataProvider()

    fields = QgsFields()
    fields.append(QgsField("olc", QVariant.String))
    fields.append(QgsField("resolution", QVariant.Int))
    fields.append(QgsField("center_lat", QVariant.Double))
    fields.append(QgsField("center_lon", QVariant.Double))
    fields.append(QgsField("cell_width", QVariant.Double))
    fields.append(QgsField("cell_height", QVariant.Double))
    fields.append(QgsField("cell_area", QVariant.Double))
    fields.append(QgsField("cell_perimeter", QVariant.Double))
    for i in range(band_count):
        fields.append(QgsField(f"band_{i+1}", QVariant.Double))

    mem_provider.addAttributes(fields)
    mem_layer.updateFields()

    for i, olc_id in enumerate(olc_ids):
        if feedback and feedback.isCanceled():
            return None
        
        lat,lon = olc.olc_to_latlon(olc_id)
        center_point = QgsPointXY(lon, lat)

        ident = provider.identify(center_point, QgsRaster.IdentifyFormatValue)
        if not ident.isValid():
            continue

        results = ident.results()
        if all(results.get(i + 1) is None or math.isnan(results.get(i + 1, float("nan"))) for i in range(band_count)):
            continue

        cell_polygon = olc2geo(olc_id)
        if not cell_polygon:
            continue       
        
        center_lat, center_lon, cell_width, cell_height, cell_area,cell_perimeter = graticule_dggs_metrics(cell_polygon)

        cell_geom = QgsGeometry.fromWkt(cell_polygon.wkt)

        feature = QgsFeature()
        feature.setGeometry(cell_geom)
        attr_values = [
            olc_id,
            resolution,
            center_lat,
            center_lon,
            cell_width,
            cell_height,
            cell_area,
            cell_perimeter,
        ]
        attr_values.extend(results.get(i + 1, None) for i in range(band_count))
        feature.setAttributes(attr_values)

        mem_provider.addFeatures([feature])

        if feedback and i % 100 == 0:
            feedback.setProgress(int(100 * i / len(olc_ids)))

    if feedback:
        feedback.setProgress(100)
        feedback.pushInfo("Raster to OLC DGGS completed.")

    return mem_layer


########################## 
# Geohash
# ########################
def raster2geohash(raster_layer: QgsRasterLayer, resolution, feedback=None) -> QgsVectorLayer:
    if not raster_layer.isValid():
        raise ValueError("Invalid raster layer.")

    provider = raster_layer.dataProvider()
    extent = raster_layer.extent()
    width, height = raster_layer.width(), raster_layer.height()
    crs = raster_layer.crs()
    band_count = provider.bandCount()

    pixel_size_x = extent.width() / width
    pixel_size_y = extent.height() / height

    geohash_ids = set()
    total_pixels = width * height
    processed_pixels = 0

    for row in range(height):
        for col in range(width):
            if feedback and feedback.isCanceled():
                return None

            x = extent.xMinimum() + col * pixel_size_x
            y = extent.yMaximum() - row * pixel_size_y
            geohash_id = latlon2geohash(y, x, resolution)
            geohash_ids.add(geohash_id)

            processed_pixels += 1
            if feedback and processed_pixels % 10000 == 0:
                feedback.setProgress(int(100 * processed_pixels / total_pixels))

    if feedback:
        feedback.pushInfo(f"{len(geohash_ids)} pixels processed.")
        feedback.setProgress(0)
        feedback.pushInfo("Raster to Geohash DGGS...")

    mem_layer = QgsVectorLayer(f"Polygon?crs={crs.authid()}", "Geohash Grid", "memory")
    mem_provider = mem_layer.dataProvider()

    fields = QgsFields()
    fields.append(QgsField("geohash", QVariant.String))
    fields.append(QgsField("resolution", QVariant.Int))
    fields.append(QgsField("center_lat", QVariant.Double))
    fields.append(QgsField("center_lon", QVariant.Double))
    fields.append(QgsField("cell_width", QVariant.Double))
    fields.append(QgsField("cell_height", QVariant.Double))
    fields.append(QgsField("cell_area", QVariant.Double))
    fields.append(QgsField("cell_perimeter", QVariant.Double))
    for i in range(band_count):
        fields.append(QgsField(f"band_{i+1}", QVariant.Double))

    mem_provider.addAttributes(fields)
    mem_layer.updateFields()

    for i, geohash_id in enumerate(geohash_ids):
        if feedback and feedback.isCanceled():
            return None
        lat,lon = geohash.decode(geohash_id)
        center_point = QgsPointXY(lon, lat)

        ident = provider.identify(center_point, QgsRaster.IdentifyFormatValue)
        if not ident.isValid():
            continue

        results = ident.results()
        if all(results.get(i + 1) is None or math.isnan(results.get(i + 1, float("nan"))) for i in range(band_count)):
            continue
        
        cell_polygon = geohash2geo(geohash_id)
        if not cell_polygon:
            continue

        
        
        center_lat, center_lon, cell_width, cell_height, cell_area,cell_perimeter = graticule_dggs_metrics(cell_polygon)

        cell_geom = QgsGeometry.fromWkt(cell_polygon.wkt)

        feature = QgsFeature()
        feature.setGeometry(cell_geom)
        attr_values = [
            geohash_id,
            resolution,
            center_lat,
            center_lon,
            cell_width,
            cell_height,
            cell_area,
            cell_perimeter,
        ]
        attr_values.extend(results.get(i + 1, None) for i in range(band_count))
        feature.setAttributes(attr_values)

        mem_provider.addFeatures([feature])

        if feedback and i % 100 == 0:
            feedback.setProgress(int(100 * i / len(geohash_ids)))

    if feedback:
        feedback.setProgress(100)
        feedback.pushInfo("Raster to Geohash DGGS completed.")

    return mem_layer

########################## 
# Tilecode
# ########################
def raster2tilecode(raster_layer: QgsRasterLayer, resolution, feedback=None) -> QgsVectorLayer:
    if not raster_layer.isValid():
        raise ValueError("Invalid raster layer.")

    provider = raster_layer.dataProvider()
    extent = raster_layer.extent()
    width, height = raster_layer.width(), raster_layer.height()
    crs = raster_layer.crs()
    band_count = provider.bandCount()

    pixel_size_x = extent.width() / width
    pixel_size_y = extent.height() / height

    tilecode_ids = set()
    total_pixels = width * height
    processed_pixels = 0

    for row in range(height):
        for col in range(width):
            if feedback and feedback.isCanceled():
                return None

            x = extent.xMinimum() + col * pixel_size_x
            y = extent.yMaximum() - row * pixel_size_y
            tilecode_id = latlon2tilecode(y, x, resolution)
            tilecode_ids.add(tilecode_id)

            processed_pixels += 1
            if feedback and processed_pixels % 10000 == 0:
                feedback.setProgress(int(100 * processed_pixels / total_pixels))

    if feedback:
        feedback.pushInfo(f"{len(tilecode_ids)} pixels processed.")
        feedback.setProgress(0)
        feedback.pushInfo("Raster to Tilecode DGGS...")

    mem_layer = QgsVectorLayer(f"Polygon?crs={crs.authid()}", "tilecode Grid", "memory")
    mem_provider = mem_layer.dataProvider()

    fields = QgsFields()
    fields.append(QgsField("tilecode", QVariant.String))
    fields.append(QgsField("resolution", QVariant.Int))
    fields.append(QgsField("center_lat", QVariant.Double))
    fields.append(QgsField("center_lon", QVariant.Double))
    fields.append(QgsField("cell_width", QVariant.Double))
    fields.append(QgsField("cell_height", QVariant.Double))
    fields.append(QgsField("cell_area", QVariant.Double))
    fields.append(QgsField("cell_perimeter", QVariant.Double))
    for i in range(band_count):
        fields.append(QgsField(f"band_{i+1}", QVariant.Double))

    mem_provider.addAttributes(fields)
    mem_layer.updateFields()

    for i, tilecode_id in enumerate(tilecode_ids):
        if feedback and feedback.isCanceled():
            return None
        lat,lon = tilecode.tilecode2latlon(tilecode_id)
        center_point = QgsPointXY(lon, lat)

        ident = provider.identify(center_point, QgsRaster.IdentifyFormatValue)
        if not ident.isValid():
            continue

        results = ident.results()
        if all(results.get(i + 1) is None or math.isnan(results.get(i + 1, float("nan"))) for i in range(band_count)):
            continue
                
        cell_polygon = tilecode2geo(tilecode_id)
        if not cell_polygon:
            continue

        center_lat, center_lon, cell_width, cell_height, cell_area,cell_perimeter = graticule_dggs_metrics(cell_polygon)

        cell_geom = QgsGeometry.fromWkt(cell_polygon.wkt)

        feature = QgsFeature()
        feature.setGeometry(cell_geom)
        attr_values = [
            tilecode_id,
            resolution,
            center_lat,
            center_lon,
            cell_width,
            cell_height,
            cell_area,
            cell_perimeter,
        ]
        attr_values.extend(results.get(i + 1, None) for i in range(band_count))
        feature.setAttributes(attr_values)

        mem_provider.addFeatures([feature])

        if feedback and i % 100 == 0:
            feedback.setProgress(int(100 * i / len(tilecode_ids)))

    if feedback:
        feedback.setProgress(100)
        feedback.pushInfo("Raster to Tilecode DGGS completed.")

    return mem_layer

########################## 
# Quadkey
# ########################
def raster2quadkey(raster_layer: QgsRasterLayer, resolution, feedback=None) -> QgsVectorLayer:
    if not raster_layer.isValid():
        raise ValueError("Invalid raster layer.")

    provider = raster_layer.dataProvider()
    extent = raster_layer.extent()
    width, height = raster_layer.width(), raster_layer.height()
    crs = raster_layer.crs()
    band_count = provider.bandCount()

    pixel_size_x = extent.width() / width
    pixel_size_y = extent.height() / height

    quadkey_ids = set()
    total_pixels = width * height
    processed_pixels = 0

    for row in range(height):
        for col in range(width):
            if feedback and feedback.isCanceled():
                return None

            x = extent.xMinimum() + col * pixel_size_x
            y = extent.yMaximum() - row * pixel_size_y
            quadkey_id = latlon2quadkey(y, x, resolution)
            quadkey_ids.add(quadkey_id)

            processed_pixels += 1
            if feedback and processed_pixels % 10000 == 0:
                feedback.setProgress(int(100 * processed_pixels / total_pixels))

    if feedback:
        feedback.pushInfo(f"{len(quadkey_ids)} pixels processed.")
        feedback.setProgress(0)
    feedback.pushInfo("Raster to Quadkey DGGS...")

    mem_layer = QgsVectorLayer(f"Polygon?crs={crs.authid()}", "Quadkey Grid", "memory")
    mem_provider = mem_layer.dataProvider()

    fields = QgsFields()
    fields.append(QgsField("quadkey", QVariant.String))
    fields.append(QgsField("resolution", QVariant.Int))
    fields.append(QgsField("center_lat", QVariant.Double))
    fields.append(QgsField("center_lon", QVariant.Double))
    fields.append(QgsField("cell_width", QVariant.Double))
    fields.append(QgsField("cell_height", QVariant.Double))
    fields.append(QgsField("cell_area", QVariant.Double))
    fields.append(QgsField("cell_perimeter", QVariant.Double))
    for i in range(band_count):
        fields.append(QgsField(f"band_{i+1}", QVariant.Double))

    mem_provider.addAttributes(fields)
    mem_layer.updateFields()

    for i, quadkey_id in enumerate(quadkey_ids):
        if feedback and feedback.isCanceled():
            return None
        lat,lon = tilecode.quadkey2latlon(quadkey_id)
        center_point = QgsPointXY(lon, lat)

        ident = provider.identify(center_point, QgsRaster.IdentifyFormatValue)
        if not ident.isValid():
            continue

        results = ident.results()
        if all(results.get(i + 1) is None or math.isnan(results.get(i + 1, float("nan"))) for i in range(band_count)):
            continue
        
        cell_polygon = quadkey2geo(quadkey_id)
        if not cell_polygon:
            continue
        
        
        center_lat, center_lon, cell_width, cell_height, cell_area,cell_perimeter = graticule_dggs_metrics(cell_polygon)

        cell_geom = QgsGeometry.fromWkt(cell_polygon.wkt)

        feature = QgsFeature()
        feature.setGeometry(cell_geom)
        attr_values = [
            quadkey_id,
            resolution,
            center_lat,
            center_lon,
            cell_width,
            cell_height,
            cell_area,
            cell_perimeter,
        ]
        attr_values.extend(results.get(i + 1, None) for i in range(band_count))
        feature.setAttributes(attr_values)

        mem_provider.addFeatures([feature])

        if feedback and i % 100 == 0:   
            feedback.setProgress(int(100 * i / len(quadkey_ids)))

    if feedback:
        feedback.setProgress(100)
        feedback.pushInfo("Raster to Quadkey DGGS completed.")

    return mem_layer


########################## 
# DGGAL
#########################
def raster2dggal(raster_layer: QgsRasterLayer, resolution: int, feedback=None, dggal_type=None) -> QgsVectorLayer:
    if not raster_layer.isValid():
        raise ValueError("Invalid raster layer.")

    provider = raster_layer.dataProvider()
    extent = raster_layer.extent()
    width, height = raster_layer.width(), raster_layer.height()
    crs = raster_layer.crs()
    band_count = provider.bandCount()

    pixel_size_x = extent.width() / width
    pixel_size_y = extent.height() / height

    dggal_ids = set()
    total_pixels = width * height
    processed_pixels = 0

    for row in range(height):
        for col in range(width):
            if feedback and feedback.isCanceled():
                return None

            x = extent.xMinimum() + col * pixel_size_x
            y = extent.yMaximum() - row * pixel_size_y
            
            try:
                dggal_id = latlon2dggal(dggal_type, y, x, resolution)
                dggal_ids.add(dggal_id)
            except Exception:
                continue

            processed_pixels += 1
            if feedback and processed_pixels % 10000 == 0:
                feedback.setProgress(int(100 * processed_pixels / total_pixels))

    if feedback:
        feedback.pushInfo(f"{len(dggal_ids)} pixels processed.")
        feedback.setProgress(0)
    feedback.pushInfo(f"Raster to DGGAL {dggal_type.upper()}...")

    mem_layer = QgsVectorLayer(f"Polygon?crs={crs.authid()}", f"DGGAL {dggal_type.upper()} Grid", "memory")
    mem_provider = mem_layer.dataProvider()

    fields = QgsFields()
    field_name = f"dggal_{dggal_type}"
    fields.append(QgsField(field_name, QVariant.String))
    fields.append(QgsField("resolution", QVariant.Int))
    fields.append(QgsField("center_lat", QVariant.Double))
    fields.append(QgsField("center_lon", QVariant.Double))
    fields.append(QgsField("avg_edge_len", QVariant.Double))
    fields.append(QgsField("cell_area", QVariant.Double))
    fields.append(QgsField("cell_perimeter", QVariant.Double))
    for i in range(band_count):
        fields.append(QgsField(f"band_{i+1}", QVariant.Double))

    mem_provider.addAttributes(fields)
    mem_layer.updateFields()

    for i, dggal_id in enumerate(dggal_ids):
        if feedback and feedback.isCanceled():
            return None
            
        try:
            cell_polygon = dggal2geo(dggal_type, dggal_id)
            if not cell_polygon:
                continue
                
            # Get center point for raster value extraction
            center_point = cell_polygon.centroid
            center_lon, center_lat = center_point.x, center_point.y
            qgis_center_point = QgsPointXY(center_lon, center_lat)

            ident = provider.identify(qgis_center_point, QgsRaster.IdentifyFormatValue)
            if not ident.isValid():
                continue

            results = ident.results()
            if all(results.get(i + 1) is None or math.isnan(results.get(i + 1, float("nan"))) for i in range(band_count)):
                continue
            
            # Get resolution and edge count from DGGAL
            try:
                app = Application(appGlobals=globals())
                pydggal_setup(app)
                dggs_class_name = DGGAL_TYPES[dggal_type]["class_name"]
                dggrs = getattr(dggal, dggs_class_name)()
                zone = dggrs.getZoneFromTextID(dggal_id)
                zone_resolution = dggrs.getZoneLevel(zone)
                num_edges = dggrs.countZoneEdges(zone)
            except:
                # Fallback values if we can't get them from DGGAL
                zone_resolution = resolution
                num_edges = 6  # Default for hexagonal cells
            
            center_lat, center_lon, avg_edge_len, cell_area, cell_perimeter = geodesic_dggs_metrics(cell_polygon, num_edges)

            cell_geom = QgsGeometry.fromWkt(cell_polygon.wkt)

            feature = QgsFeature()
            feature.setGeometry(cell_geom)
            attr_values = [
                dggal_id,
                zone_resolution,
                center_lat,
                center_lon,
                avg_edge_len,
                cell_area,
                cell_perimeter,
            ]
            attr_values.extend(results.get(i + 1, None) for i in range(band_count))
            feature.setAttributes(attr_values)

            mem_provider.addFeatures([feature])

        except Exception as e:
            if feedback:
                feedback.pushInfo(f"Warning: Could not process DGGAL ID {dggal_id}: {str(e)}")
            continue

        if feedback and i % 100 == 0:   
            feedback.setProgress(int(100 * i / len(dggal_ids)))

    if feedback:
        feedback.setProgress(100)
        feedback.pushInfo(f"Raster to DGGAL {dggal_type.upper()} completed.")

    return mem_layer

