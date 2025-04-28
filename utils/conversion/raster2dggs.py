import platform,re
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
from shapely.geometry import Polygon
from shapely.wkt import loads

import h3 
from vgrid.utils import s2, qtm, olc, geohash, tilecode
from vgrid.conversion.latlon2dggs import *
from vgrid.utils import mercantile
from vgrid.utils.rhealpixdggs.dggs import RHEALPixDGGS
from vgrid.generator.h3grid import fix_h3_antimeridian_cells
from vgrid.conversion.dggs2geojson import rhealpix_cell_to_polygon
from vgrid.generator.settings import graticule_dggs_metrics, geodesic_dggs_metrics

from vgrid.utils.rhealpixdggs.dggs import RHEALPixDGGS
from vgrid.utils.rhealpixdggs.ellipsoids import WGS84_ELLIPSOID

E = WGS84_ELLIPSOID

if (platform.system() == 'Windows'):
    from vgrid.utils.eaggr.eaggr import Eaggr
    from vgrid.utils.eaggr.shapes.dggs_cell import DggsCell
    from vgrid.utils.eaggr.enums.model import Model
    from vgrid.utils.eaggr.enums.shape_string_format import ShapeStringFormat
    from vgrid.generator.isea4tgrid import fix_isea4t_wkt, fix_isea4t_antimeridian_cells
    isea4t_dggs = Eaggr(Model.ISEA4T)

from vgrid.utils.antimeridian import fix_polygon

from pyproj import Geod
geod = Geod(ellps="WGS84")
p90_n180, p90_n90, p90_p0, p90_p90, p90_p180 = (90.0, -180.0), (90.0, -90.0), (90.0, 0.0), (90.0, 90.0), (90.0, 180.0)
p0_n180, p0_n90, p0_p0, p0_p90, p0_p180 = (0.0, -180.0), (0.0, -90.0), (0.0, 0.0), (0.0, 90.0), (0.0, 180.0)
n90_n180, n90_n90, n90_p0, n90_p90, n90_p180 = (-90.0, -180.0), (-90.0, -90.0), (-90.0, 0.0), (-90.0, 90.0), (-90.0, 180.0)

def qgsgeometry_to_shapely(qgs_geom: QgsGeometry) -> Polygon:
    if not qgs_geom:
        return None

    if qgs_geom.isMultipart():
        rings = qgs_geom.asMultiPolygon()
    else:
        rings = [qgs_geom.asPolygon()]

    if not rings or not rings[0]:
        return None

    exterior = [(pt.x(), pt.y()) for pt in rings[0][0]]
    interiors = [[(pt.x(), pt.y()) for pt in ring] for ring in rings[0][1:]]

    return Polygon(exterior, interiors)

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
    for i in range(band_count):
        fields.append(QgsField(f"band_{i + 1}", QVariant.Double))
    mem_provider.addAttributes(fields)
    mem_layer.updateFields()

    for i, h3_index in enumerate(h3_cells):
        lat, lon = h3.cell_to_latlng(h3_index)
        point = QgsPointXY(lon, lat)
        ident = provider.identify(point, QgsRaster.IdentifyFormatValue)
        if not ident.isValid():
            continue
        results = ident.results()
        if all(results.get(i + 1) is None or math.isnan(results.get(i + 1, float('nan'))) for i in range(band_count)):
            continue

        boundary = h3.cell_to_boundary(h3_index)
        if not boundary:
            continue
        fixed_boundary = fix_h3_antimeridian_cells(boundary)
        ring = [(lon, lat) for lat, lon in fixed_boundary]
        qgs_ring = [QgsPointXY(lon, lat) for lon, lat in ring]
        cell_geom = QgsGeometry.fromPolygonXY([qgs_ring])
        shapely_poly = qgsgeometry_to_shapely(cell_geom)

        num_edges = 5 if h3.is_pentagon(h3_index) else 6
        center_lat, center_lon, avg_edge_len, cell_area = geodesic_dggs_metrics(shapely_poly, num_edges)

        feature = QgsFeature()
        feature.setGeometry(cell_geom)
        attributes = {
            "h3": h3_index,
            "resolution": resolution,
            "center_lat": center_lat,
            "center_lon": center_lon,
            "avg_edge_len": avg_edge_len,
            "cell_area": cell_area,
        }
        for i in range(band_count):
            attributes[f"band_{i + 1}"] = results.get(i + 1, None)
        feature.setAttributes([attributes[field.name()] for field in fields])
        mem_provider.addFeatures([feature])
        if feedback and i % 100 == 0:
            feedback.setProgress(int(100 * i / len(h3_cells)))

    if feedback:
        feedback.setProgress(100)
        feedback.pushInfo("H3 DGGS generation completed.")
            
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

        vertices = [s2_cell.get_vertex(i) for i in range(4)]
        coords = [(s2.LatLng.from_point(v).lng().degrees, s2.LatLng.from_point(v).lat().degrees) for v in vertices]
        coords.append(coords[0])  # close ring
        polygon = fix_polygon(Polygon(coords))
        qgs_polygon = QgsGeometry.fromPolygonXY([[QgsPointXY(lon, lat) for lon, lat in polygon.exterior.coords]])
        
        num_edges = 4
        center_lat, center_lon, avg_edge_len, cell_area = geodesic_dggs_metrics(polygon, num_edges)

        feature = QgsFeature()
        feature.setGeometry(qgs_polygon)
        attr_values = [
            s2_token,
            resolution,
            center_lat,
            center_lon,
            avg_edge_len,
            cell_area,
        ]
        attr_values.extend(results.get(i + 1, None) for i in range(band_count))
        feature.setAttributes(attr_values)
        mem_provider.addFeatures([feature])
        if feedback and i % 100 == 0:
            feedback.setProgress(int(100 * i / len(s2_tokens)))

    if feedback:
        feedback.setProgress(100)
        feedback.pushInfo("S2 DGGS generation completed.")
    

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
        num_edges = 3 if rhealpix_cell.ellipsoidal_shape() == 'dart' else 4
        center_lat, center_lon, avg_edge_len, cell_area = geodesic_dggs_metrics(cell_polygon, num_edges)

        qgs_polygon = QgsGeometry.fromPolygonXY(
            [[QgsPointXY(lon, lat) for lon, lat in cell_polygon.exterior.coords]]
        )

        feature = QgsFeature()
        feature.setGeometry(qgs_polygon)
        attr_values = [
            rhealpix_id,
            resolution,
            center_lat,
            center_lon,
            avg_edge_len,
            cell_area,
        ]
        attr_values.extend(results.get(i + 1, None) for i in range(band_count))
        feature.setAttributes(attr_values)

        mem_provider.addFeatures([feature])

        if feedback and i % 100 == 0:
            feedback.setProgress(int(100 * i / len(rhealpix_ids)))

    if feedback:
        feedback.setProgress(100)
        feedback.pushInfo("rHEALpix DGGS generation completed.")

    return mem_layer


########################## 
# ISEA4T
# ########################
def raster2isea4t(raster_layer: QgsRasterLayer, resolution, feedback=None) -> QgsVectorLayer:
    if (platform.system() == 'Windows'): 
        isea4t_dggs = Eaggr(Model.ISEA4T)

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

            cell_to_shape = isea4t_dggs.convert_dggs_cell_outline_to_shape_string(DggsCell(isea4t_id),ShapeStringFormat.WKT)
            cell_to_shape_fixed = loads(fix_isea4t_wkt(cell_to_shape))
            if isea4t_id.startswith('00') or isea4t_id.startswith('09') or isea4t_id.startswith('14')\
                or isea4t_id.startswith('04') or isea4t_id.startswith('19'):
                cell_to_shape_fixed = fix_isea4t_antimeridian_cells(cell_to_shape_fixed)
            
            num_edges = 3
            cell_polygon = Polygon(list(cell_to_shape_fixed.exterior.coords))
            
            center_lat, center_lon, avg_edge_len, cell_area = geodesic_dggs_metrics(cell_polygon, num_edges)

            qgs_polygon = QgsGeometry.fromPolygonXY(
                [[QgsPointXY(lon, lat) for lon, lat in cell_polygon.exterior.coords]]
            )

            feature = QgsFeature()
            feature.setGeometry(qgs_polygon)
            attr_values = [
                isea4t_id,
                resolution,
                center_lat,
                center_lon,
                avg_edge_len,
                cell_area,
            ]
            attr_values.extend(results.get(i + 1, None) for i in range(band_count))
            feature.setAttributes(attr_values)

            mem_provider.addFeatures([feature])

            if feedback and i % 100 == 0:
                feedback.setProgress(int(100 * i / len(isea4t_ids)))

        if feedback:
            feedback.setProgress(100)
            feedback.pushInfo("ISEA4T DGGS generation completed.")

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
        
        facet = qtm.qtm_id_to_facet(qtm_id)
        cell_polygon = qtm.constructGeometry(facet)    
        resolution = len(qtm_id)
        num_edges = 3
        center_lat, center_lon, avg_edge_len, cell_area = geodesic_dggs_metrics(cell_polygon, num_edges)

        qgs_polygon = QgsGeometry.fromPolygonXY(
            [[QgsPointXY(lon, lat) for lon, lat in cell_polygon.exterior.coords]]
        )

        feature = QgsFeature()
        feature.setGeometry(qgs_polygon)
        attr_values = [
            qtm_id,
            resolution,
            center_lat,
            center_lon,
            avg_edge_len,
            cell_area,
        ]
        attr_values.extend(results.get(i + 1, None) for i in range(band_count))
        feature.setAttributes(attr_values)

        mem_provider.addFeatures([feature])

        if feedback and i % 100 == 0:
            feedback.setProgress(int(100 * i / len(qtm_ids)))

    if feedback:
        feedback.setProgress(100)
        feedback.pushInfo("QTM DGGS generation completed.")

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

        coord = olc.decode(olc_id)    
        # Create the bounding box coordinates for the polygon
        min_lat, min_lon = coord.latitudeLo, coord.longitudeLo
        max_lat, max_lon = coord.latitudeHi, coord.longitudeHi        
        # Define the polygon based on the bounding box
        cell_polygon = Polygon([
            [min_lon, min_lat],  # Bottom-left corner
            [max_lon, min_lat],  # Bottom-right corner
            [max_lon, max_lat],  # Top-right corner
            [min_lon, max_lat],  # Top-left corner
            [min_lon, min_lat]   # Closing the polygon (same as the first point)
        ])
        
        center_lat, center_lon, cell_width, cell_height, cell_area = graticule_dggs_metrics(cell_polygon)

        qgs_polygon = QgsGeometry.fromPolygonXY(
            [[QgsPointXY(lon, lat) for lon, lat in cell_polygon.exterior.coords]]
        )

        feature = QgsFeature()
        feature.setGeometry(qgs_polygon)
        attr_values = [
            olc_id,
            resolution,
            center_lat,
            center_lon,
            cell_width,
            cell_height,
            cell_area
        ]
        attr_values.extend(results.get(i + 1, None) for i in range(band_count))
        feature.setAttributes(attr_values)

        mem_provider.addFeatures([feature])

        if feedback and i % 100 == 0:
            feedback.setProgress(int(100 * i / len(olc_ids)))

    if feedback:
        feedback.setProgress(100)
        feedback.pushInfo("OLC DGGS generation completed.")

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
        feedback.pushInfo("Generating Geohash DGGS...")

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
        
        bbox =  geohash.bbox(geohash_id)
        min_lat, min_lon = bbox['s'], bbox['w']  # Southwest corner
        max_lat, max_lon = bbox['n'], bbox['e']  # Northeast corner        

        # Define the polygon based on the bounding box
        cell_polygon = Polygon([
            [min_lon, min_lat],  # Bottom-left corner
            [max_lon, min_lat],  # Bottom-right corner
            [max_lon, max_lat],  # Top-right corner
            [min_lon, max_lat],  # Top-left corner
            [min_lon, min_lat]   # Closing the polygon (same as the first point)
        ])
        
        center_lat, center_lon, cell_width, cell_height, cell_area = graticule_dggs_metrics(cell_polygon)

        qgs_polygon = QgsGeometry.fromPolygonXY(
            [[QgsPointXY(lon, lat) for lon, lat in cell_polygon.exterior.coords]]
        )

        feature = QgsFeature()
        feature.setGeometry(qgs_polygon)
        attr_values = [
            geohash_id,
            resolution,
            center_lat,
            center_lon,
            cell_width,
            cell_height,
            cell_area
        ]
        attr_values.extend(results.get(i + 1, None) for i in range(band_count))
        feature.setAttributes(attr_values)

        mem_provider.addFeatures([feature])

        if feedback and i % 100 == 0:
            feedback.setProgress(int(100 * i / len(geohash_ids)))

    if feedback:
        feedback.setProgress(100)
        feedback.pushInfo("geohash DGGS generation completed.")

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
        feedback.pushInfo("Generating Tilecode DGGS...")

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
        
        match = re.match(r'z(\d+)x(\d+)y(\d+)', tilecode_id)
        z = int(match.group(1))
        x = int(match.group(2))
        y = int(match.group(3))

        bounds = mercantile.bounds(x, y, z)    
        min_lat, min_lon = bounds.south, bounds.west
        max_lat, max_lon = bounds.north, bounds.east
        cell_polygon = Polygon([
            [min_lon, min_lat],  # Bottom-left corner
            [max_lon, min_lat],  # Bottom-right corner
            [max_lon, max_lat],  # Top-right corner
            [min_lon, max_lat],  # Top-left corner
            [min_lon, min_lat]   # Closing the polygon (same as the first point)
        ])        

        center_lat, center_lon, cell_width, cell_height, cell_area = graticule_dggs_metrics(cell_polygon)

        qgs_polygon = QgsGeometry.fromPolygonXY(
            [[QgsPointXY(lon, lat) for lon, lat in cell_polygon.exterior.coords]]
        )

        feature = QgsFeature()
        feature.setGeometry(qgs_polygon)
        attr_values = [
            tilecode_id,
            resolution,
            center_lat,
            center_lon,
            cell_width,
            cell_height,
            cell_area
        ]
        attr_values.extend(results.get(i + 1, None) for i in range(band_count))
        feature.setAttributes(attr_values)

        mem_provider.addFeatures([feature])

        if feedback and i % 100 == 0:
            feedback.setProgress(int(100 * i / len(tilecode_ids)))

    if feedback:
        feedback.setProgress(100)
        feedback.pushInfo("Tilecode DGGS generation completed.")

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
        feedback.pushInfo("Generating Quadkey DGGS...")

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
        
        tile = mercantile.quadkey_to_tile(quadkey_id)    
        # Format as tilecode_id
        z = tile.z
        x = tile.x
        y = tile.y
        
        bounds = mercantile.bounds(x, y, z)    
        min_lat, min_lon = bounds.south, bounds.west
        max_lat, max_lon = bounds.north, bounds.east
        cell_polygon = Polygon([
            [min_lon, min_lat],  # Bottom-left corner
            [max_lon, min_lat],  # Bottom-right corner
            [max_lon, max_lat],  # Top-right corner
            [min_lon, max_lat],  # Top-left corner
            [min_lon, min_lat]   # Closing the polygon (same as the first point)
        ])        

        center_lat, center_lon, cell_width, cell_height, cell_area = graticule_dggs_metrics(cell_polygon)

        qgs_polygon = QgsGeometry.fromPolygonXY(
            [[QgsPointXY(lon, lat) for lon, lat in cell_polygon.exterior.coords]]
        )

        feature = QgsFeature()
        feature.setGeometry(qgs_polygon)
        attr_values = [
            quadkey_id,
            resolution,
            center_lat,
            center_lon,
            cell_width,
            cell_height,
            cell_area
        ]
        attr_values.extend(results.get(i + 1, None) for i in range(band_count))
        feature.setAttributes(attr_values)

        mem_provider.addFeatures([feature])

        if feedback and i % 100 == 0:
            feedback.setProgress(int(100 * i / len(quadkey_ids)))

    if feedback:
        feedback.setProgress(100)
        feedback.pushInfo("Quadkey DGGS generation completed.")

    return mem_layer

