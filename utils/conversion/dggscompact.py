from vgrid.utils import s2, olc, mercantile
from vgrid.utils import qtm
import h3

from vgrid.utils.rhealpixdggs.dggs import RHEALPixDGGS
from vgrid.utils.rhealpixdggs.ellipsoids import WGS84_ELLIPSOID
import platform,re
if (platform.system() == 'Windows'):   
    from vgrid.utils.eaggr.enums.shape_string_format import ShapeStringFormat
    from vgrid.utils.eaggr.eaggr import Eaggr
    from vgrid.utils.eaggr.shapes.dggs_cell import DggsCell
    from vgrid.utils.eaggr.enums.model import Model
    from vgrid.generator.isea4tgrid import fix_isea4t_wkt, fix_isea4t_antimeridian_cells


if (platform.system() == 'Linux'):
    from vgrid.utils.dggrid4py import DGGRIDv7, dggs_types
    from vgrid.utils.dggrid4py.dggrid_runner import input_address_types



from shapely.wkt import loads
from shapely.geometry import Polygon

from vgrid.generator.h3grid import fix_h3_antimeridian_cells

from vgrid.utils.antimeridian import fix_polygon
from vgrid.generator.settings import graticule_dggs_metrics, geodesic_dggs_metrics

from vgrid.conversion.dggs2geojson import rhealpix_cell_to_polygon
from vgrid.generator.geohashgrid import geohash_to_polygon
from vgrid.conversion.dggscompact import *
from pyproj import Geod
geod = Geod(ellps="WGS84")
E = WGS84_ELLIPSOID

from qgis.core import (
    QgsVectorLayer, QgsFeature, QgsGeometry, QgsField, QgsFields, QgsProcessingException,
    QgsWkbTypes, QgsVectorFileWriter, QgsProject, QgsCoordinateReferenceSystem
)
from PyQt5.QtCore import QVariant
from shapely.geometry import Polygon


########################## 
# H3
# ########################
def h3compact(h3_layer: QgsVectorLayer, H3ID_field=None,feedback=None) -> QgsVectorLayer:
    if not H3ID_field:
        H3ID_field = 'h3'
        
    fields = QgsFields()
    fields.append(QgsField("h3", QVariant.String))
    fields.append(QgsField("resolution", QVariant.Int))
    fields.append(QgsField("center_lat", QVariant.Double))
    fields.append(QgsField("center_lon", QVariant.Double))
    fields.append(QgsField("avg_edge_len", QVariant.Double))
    fields.append(QgsField("cell_area", QVariant.Double))

    crs = h3_layer.crs().toWkt()
    mem_layer = QgsVectorLayer("Polygon?crs=" + crs, "h3_compacted", "memory")
    mem_provider = mem_layer.dataProvider()
    mem_provider.addAttributes(fields)
    mem_layer.updateFields()

    h3_ids = [
        feature[H3ID_field]
        for feature in h3_layer.getFeatures()
        if feature[H3ID_field]
    ]
    h3_ids = list(set(h3_ids))
    
    if h3_ids:
        try:
            h3_ids_compact = h3.compact_cells(h3_ids)
        except:
            raise QgsProcessingException("Compact cells failed. Please check your H3 ID field.")

        total_cells = len(h3_ids_compact)

        for i, h3_id_compact in enumerate(h3_ids_compact):
            if feedback:
                feedback.setProgress(int((i / total_cells) * 100))
                if feedback.isCanceled():
                    return None

            cell_boundary = h3.cell_to_boundary(h3_id_compact)
            filtered_boundary = fix_h3_antimeridian_cells(cell_boundary)
            reversed_boundary = [(lon, lat) for lat, lon in filtered_boundary]
            cell_polygon = Polygon(reversed_boundary)
            
            if not cell_polygon.is_valid:
                continue
            
            resolution = h3.get_resolution(h3_id_compact)
            num_edges = 5 if h3.is_pentagon(h3_id_compact) else 6
            center_lat, center_lon, avg_edge_len, cell_area = geodesic_dggs_metrics(cell_polygon, num_edges)
            
            cell_geom = QgsGeometry.fromWkt(cell_polygon.wkt)
            h3_feature = QgsFeature(fields)
            h3_feature.setGeometry(cell_geom)
            
            attributes = {
                "h3": h3_id_compact,
                "resolution": resolution,
                "center_lat": center_lat,
                "center_lon": center_lon,
                "avg_edge_len": avg_edge_len,
                "cell_area": cell_area,
                }
            h3_feature.setAttributes([attributes[field.name()] for field in fields])
            mem_provider.addFeatures([h3_feature])

        if feedback:
            feedback.setProgress(100)
            feedback.pushInfo("H3 Compact completed.")
                
        return mem_layer


########################## 
# S2
# ########################
def s2compact(s2_layer: QgsVectorLayer, S2ID_field=None, feedback=None) -> QgsVectorLayer:
    if not S2ID_field:
        S2ID_field = 's2'

    fields = QgsFields()
    fields.append(QgsField("s2", QVariant.String))
    fields.append(QgsField("resolution", QVariant.Int))
    fields.append(QgsField("center_lat", QVariant.Double))
    fields.append(QgsField("center_lon", QVariant.Double))
    fields.append(QgsField("avg_edge_len", QVariant.Double))
    fields.append(QgsField("cell_area", QVariant.Double))

    crs = s2_layer.crs().toWkt()
    mem_layer = QgsVectorLayer("Polygon?crs=" + crs, "s2_compacted", "memory")
    mem_provider = mem_layer.dataProvider()
    mem_provider.addAttributes(fields)
    mem_layer.updateFields()

    s2_tokens = [
        feature[S2ID_field]
        for feature in s2_layer.getFeatures()
        if feature[S2ID_field]
    ]
    
    try:
        s2_ids = [s2.CellId.from_token(token) for token in s2_tokens]
        s2_ids = list(set(s2_ids))
        if s2_ids:        
            covering = s2.CellUnion(s2_ids)
            covering.normalize()
            s2_tokens_compact = [cell_id.to_token() for cell_id in covering.cell_ids()]
    except:
        raise QgsProcessingException("Compact cells failed. Please check your S2 ID field.")

    total_cells = len(s2_tokens_compact)
    
    for i, s2_token_compact in enumerate(s2_tokens_compact):
        if feedback:
            feedback.setProgress(int((i / total_cells) * 100))
            if feedback.isCanceled():
                return None

        s2_id_compact = s2.CellId.from_token(s2_token_compact)
        s2_cell = s2.Cell(s2_id_compact)    
        # Get the vertices of the cell (4 vertices for a rectangular cell)
        vertices = [s2_cell.get_vertex(i) for i in range(4)]
        # Prepare vertices in (longitude, latitude) format for Shapely
        shapely_vertices = []
        for vertex in vertices:
            lat_lng = s2.LatLng.from_point(vertex)  # Convert Point to LatLng
            longitude = lat_lng.lng().degrees  # Access longitude in degrees
            latitude = lat_lng.lat().degrees   # Access latitude in degrees
            shapely_vertices.append((longitude, latitude))

        # Close the polygon by adding the first vertex again
        shapely_vertices.append(shapely_vertices[0])  # Closing the polygon
        # Create a Shapely Polygon
        cell_polygon = fix_polygon(Polygon(shapely_vertices)) # Fix antimeridian
            
        if not cell_polygon.is_valid:
            continue
        
        resolution = s2_id_compact.level() 
        num_edges = 4
        center_lat, center_lon, avg_edge_len, cell_area = geodesic_dggs_metrics(cell_polygon, num_edges)
        
        cell_geom = QgsGeometry.fromWkt(cell_polygon.wkt)
        s2_feature = QgsFeature(fields)
        s2_feature.setGeometry(cell_geom)
        
        attributes = {
            "s2": s2_token_compact,
            "resolution": resolution,
            "center_lat": center_lat,
            "center_lon": center_lon,
            "avg_edge_len": avg_edge_len,
            "cell_area": cell_area,
            }
        s2_feature.setAttributes([attributes[field.name()] for field in fields])
        mem_provider.addFeatures([s2_feature])

    if feedback:
        feedback.setProgress(100)
        feedback.pushInfo("S2 Compact completed.")
            
    return mem_layer


########################## 
# rHEALPix
# ########################
def rhealpixcompact(rhealpix_layer: QgsVectorLayer, rHEALPixID_field=None,feedback=None) -> QgsVectorLayer:
    if not rHEALPixID_field:
        rHEALPixID_field = 'rhealpix'

    rhealpix_dggs = RHEALPixDGGS()
    
    fields = QgsFields()
    fields.append(QgsField("rhealpix", QVariant.String))
    fields.append(QgsField("resolution", QVariant.Int))
    fields.append(QgsField("center_lat", QVariant.Double))
    fields.append(QgsField("center_lon", QVariant.Double))
    fields.append(QgsField("avg_edge_len", QVariant.Double))
    fields.append(QgsField("cell_area", QVariant.Double))

    crs = rhealpix_layer.crs().toWkt()
    mem_layer = QgsVectorLayer("Polygon?crs=" + crs, "rhealpix_compacted", "memory")
    mem_provider = mem_layer.dataProvider()
    mem_provider.addAttributes(fields)
    mem_layer.updateFields()

    rhealpix_ids = [
        feature[rHEALPixID_field]
        for feature in rhealpix_layer.getFeatures()
        if feature[rHEALPixID_field]
    ]
    
    if rhealpix_ids:
        try:
            rhealpix_ids_compact = rhealpix_compact(rhealpix_dggs,rhealpix_ids)
        except:
            raise QgsProcessingException("Compact cells failed. Please check your rHEALPix ID field.")
        
        total_cells = len(rhealpix_ids_compact)

        for i, rhealpix_id_compact in enumerate(rhealpix_ids_compact):
            if feedback:
                feedback.setProgress(int((i / total_cells) * 100))
                if feedback.isCanceled():
                    return None
            try:
                rhealpix_uids = (rhealpix_id_compact[0],) + tuple(map(int, rhealpix_id_compact[1:]))       
                rhealpix_cell = rhealpix_dggs.cell(rhealpix_uids)
                cell_polygon = rhealpix_cell_to_polygon(rhealpix_cell)                
            except:
                raise QgsProcessingException("Compact cells failed. Please check your rHEALPix ID field.")
            
            resolution = rhealpix_cell.resolution        
            num_edges = 3 if rhealpix_cell.ellipsoidal_shape() == 'dart' else 4
            
            center_lat, center_lon, avg_edge_len, cell_area = geodesic_dggs_metrics(cell_polygon, num_edges)
            
            cell_geom = QgsGeometry.fromWkt(cell_polygon.wkt)
            rhealpix_feature = QgsFeature(fields)
            rhealpix_feature.setGeometry(cell_geom)
            
            attributes = {
                "rhealpix": rhealpix_id_compact,
                "resolution": resolution,
                "center_lat": center_lat,
                "center_lon": center_lon,
                "avg_edge_len": avg_edge_len,
                "cell_area": cell_area,
                }
            rhealpix_feature.setAttributes([attributes[field.name()] for field in fields])
            mem_provider.addFeatures([rhealpix_feature])

        if feedback:
            feedback.setProgress(100)
            feedback.pushInfo("rHEALPix Compact completed.")
                
        return mem_layer

########################## 
# ISEA4T
# ########################
def isea4tcompact(isea4t_layer: QgsVectorLayer, ISEA4TID_field=None,feedback=None) -> QgsVectorLayer:
    if platform.system() == 'Windows':    
        if not ISEA4TID_field:
            ISEA4TID_field = 'isea4t'

        isea4t_dggs = Eaggr(Model.ISEA4T)
        
        fields = QgsFields()
        fields.append(QgsField("isea4t", QVariant.String))
        fields.append(QgsField("resolution", QVariant.Int))
        fields.append(QgsField("center_lat", QVariant.Double))
        fields.append(QgsField("center_lon", QVariant.Double))
        fields.append(QgsField("avg_edge_len", QVariant.Double))
        fields.append(QgsField("cell_area", QVariant.Double))

        crs = isea4t_layer.crs().toWkt()
        mem_layer = QgsVectorLayer("Polygon?crs=" + crs, "isea4t_compacted", "memory")
        mem_provider = mem_layer.dataProvider()
        mem_provider.addAttributes(fields)
        mem_layer.updateFields()

        isea4t_ids = [
            feature[ISEA4TID_field]
            for feature in isea4t_layer.getFeatures()
            if feature[ISEA4TID_field]
        ]

        if isea4t_ids:
            try:
                isea4t_ids_compact = isea4t_compact(isea4t_dggs,isea4t_ids)
            except:
                raise QgsProcessingException("Compact cells failed. Please check your ISEA4T ID field.")
        
            total_cells = len(isea4t_ids_compact)

            for i, isea4t_id_compact in enumerate(isea4t_ids_compact):
                if feedback:
                    feedback.setProgress(int((i / total_cells) * 100))
                    if feedback.isCanceled():
                        return None
                try:
                    isea4t_cell_compact = DggsCell(isea4t_id_compact)
                    cell_to_shape = isea4t_dggs.convert_dggs_cell_outline_to_shape_string(isea4t_cell_compact,ShapeStringFormat.WKT)
                    cell_to_shape_fixed = loads(fix_isea4t_wkt(cell_to_shape))
                    if isea4t_id_compact.startswith('00') or isea4t_id_compact.startswith('09') or isea4t_id_compact.startswith('14')\
                        or isea4t_id_compact.startswith('04') or isea4t_id_compact.startswith('19'):
                        cell_to_shape_fixed = fix_isea4t_antimeridian_cells(cell_to_shape_fixed)                    
                    cell_polygon = Polygon(list(cell_to_shape_fixed.exterior.coords))                
                except:
                    raise QgsProcessingException("Compact cells failed. Please check your ISEA4T ID field.")
                
                resolution = len(isea4t_id_compact) -2
                num_edges = 3
                
                center_lat, center_lon, avg_edge_len, cell_area = geodesic_dggs_metrics(cell_polygon, num_edges)
                
                cell_geom = QgsGeometry.fromWkt(cell_polygon.wkt)
                ISEA4T_feature = QgsFeature(fields)
                ISEA4T_feature.setGeometry(cell_geom)
                
                attributes = {
                    "isea4t": isea4t_id_compact,
                    "resolution": resolution,
                    "center_lat": center_lat,
                    "center_lon": center_lon,
                    "avg_edge_len": avg_edge_len,
                    "cell_area": cell_area,
                    }
                ISEA4T_feature.setAttributes([attributes[field.name()] for field in fields])
                mem_provider.addFeatures([ISEA4T_feature])

            if feedback:
                feedback.setProgress(100)
                feedback.pushInfo("ISEA4T Compact completed.")
                    
            return mem_layer

########################## 
# ISEA3H
# ########################
def isea3hcompact(isea3h_layer: QgsVectorLayer, ISEA3HID_field=None,feedback=None) -> QgsVectorLayer:
    if platform.system() == 'Windows':    
        if not ISEA3HID_field:
            ISEA3HID_field = 'isea3h'

        isea3h_dggs = Eaggr(Model.ISEA3H)
        
        fields = QgsFields()
        fields.append(QgsField("isea3h", QVariant.String))
        fields.append(QgsField("resolution", QVariant.Int))
        fields.append(QgsField("center_lat", QVariant.Double))
        fields.append(QgsField("center_lon", QVariant.Double))
        fields.append(QgsField("avg_edge_len", QVariant.Double))
        fields.append(QgsField("cell_area", QVariant.Double))

        crs = isea3h_layer.crs().toWkt()
        mem_layer = QgsVectorLayer("Polygon?crs=" + crs, "isea3h_compacted", "memory")
        mem_provider = mem_layer.dataProvider()
        mem_provider.addAttributes(fields)
        mem_layer.updateFields()

        isea3h_ids = [
            feature[ISEA3HID_field]
            for feature in isea3h_layer.getFeatures()
            if feature[ISEA3HID_field]
        ]
        
        if isea3h_ids:
            try:
                isea3h_ids_compact = isea3h_compact(isea3h_dggs,isea3h_ids)
            except:
                raise QgsProcessingException("Compact cells failed. Please check your ISEA3H ID field.")
        
            total_cells = len(isea3h_ids_compact)

            for i, isea3h_id_compact in enumerate(isea3h_ids_compact):
                if feedback:
                    feedback.setProgress(int((i / total_cells) * 100))
                    if feedback.isCanceled():
                        return None
                try:
                    isea3h_cell = DggsCell(isea3h_id_compact)            
                    cell_polygon = isea3h_cell_to_polygon(isea3h_dggs,isea3h_cell)
                except:
                    raise QgsProcessingException("Compact cells failed. Please check your ISEA3H ID field.")
                            
                
                cell_centroid = cell_polygon.centroid
                center_lat =  round(cell_centroid.y, 7)
                center_lon = round(cell_centroid.x, 7)
                cell_area = round(abs(geod.geometry_area_perimeter(cell_polygon)[0]),3)
                cell_perimeter = abs(geod.geometry_area_perimeter(cell_polygon)[1])
                
                isea3h2point = isea3h_dggs.convert_dggs_cell_to_point(isea3h_cell)      
                cell_accuracy = isea3h2point._accuracy
                    
                avg_edge_len = cell_perimeter / 6
                cell_resolution  = isea3h_accuracy_res_dict.get(cell_accuracy)
                
                if (cell_resolution == 0): # icosahedron faces at resolution = 0
                    avg_edge_len = cell_perimeter / 3
                
                if cell_accuracy == 0.0:
                    if round(avg_edge_len,2) == 0.06:
                        cell_resolution = 33
                    elif round(avg_edge_len,2) == 0.03:
                        cell_resolution = 34
                    elif round(avg_edge_len,2) == 0.02:
                        cell_resolution = 35
                    elif round(avg_edge_len,2) == 0.01:
                        cell_resolution = 36
                    
                    elif round(avg_edge_len,3) == 0.007:
                        cell_resolution = 37
                    elif round(avg_edge_len,3) == 0.004:
                        cell_resolution = 38
                    elif round(avg_edge_len,3) == 0.002:
                        cell_resolution = 39
                    elif round(avg_edge_len,3) <= 0.001:
                        cell_resolution = 40
                
                cell_geom = QgsGeometry.fromWkt(cell_polygon.wkt)
                isea3h_feature = QgsFeature(fields)
                isea3h_feature.setGeometry(cell_geom)
                
                attributes = {
                    "isea3h": isea3h_id_compact,
                    "resolution": cell_resolution,
                    "center_lat": center_lat,
                    "center_lon": center_lon,
                    "avg_edge_len": avg_edge_len,
                    "cell_area": cell_area,
                    }
                isea3h_feature.setAttributes([attributes[field.name()] for field in fields])
                mem_provider.addFeatures([isea3h_feature])

            if feedback:
                feedback.setProgress(100)
                feedback.pushInfo("ISEA3H Compact completed.")
                    
            return mem_layer


########################## 
# QTM
# ########################
def qtmcompact(qtm_layer: QgsVectorLayer, QTMID_field=None,feedback=None) -> QgsVectorLayer:
    if not QTMID_field:
        QTMID_field = 'qtm'
        
    fields = QgsFields()
    fields.append(QgsField("qtm", QVariant.String))
    fields.append(QgsField("resolution", QVariant.Int))
    fields.append(QgsField("center_lat", QVariant.Double))
    fields.append(QgsField("center_lon", QVariant.Double))
    fields.append(QgsField("avg_edge_len", QVariant.Double))
    fields.append(QgsField("cell_area", QVariant.Double))

    crs = qtm_layer.crs().toWkt()
    mem_layer = QgsVectorLayer("Polygon?crs=" + crs, "qtm_compacted", "memory")
    mem_provider = mem_layer.dataProvider()
    mem_provider.addAttributes(fields)
    mem_layer.updateFields()

    qtm_ids = [
        feature[QTMID_field]
        for feature in qtm_layer.getFeatures()
        if feature[QTMID_field]
    ]
    
    if qtm_ids:
        try:
            qtm_ids_compact = qtm_compact(qtm_ids)
        except:
            raise QgsProcessingException("Compact cells failed. Please check your QTM ID field.")
        
        total_cells = len(qtm_ids_compact)

        for i, qtm_id_compact in enumerate(qtm_ids_compact):
            if feedback:
                feedback.setProgress(int((i / total_cells) * 100))
                if feedback.isCanceled():
                    return None
            try:
                facet = qtm.qtm_id_to_facet(qtm_id_compact)
                cell_polygon = qtm.constructGeometry(facet)    
            except:
                raise QgsProcessingException("Compact cells failed. Please check your QTM ID field.")
                            
           
            resolution = len(qtm_id_compact)
            num_edges = 3
            center_lat, center_lon, avg_edge_len, cell_area = geodesic_dggs_metrics(cell_polygon, num_edges)
            
            cell_geom = QgsGeometry.fromWkt(cell_polygon.wkt)
            qtm_feature = QgsFeature(fields)
            qtm_feature.setGeometry(cell_geom)
            
            attributes = {
                "qtm": qtm_id_compact,
                "resolution": resolution,
                "center_lat": center_lat,
                "center_lon": center_lon,
                "avg_edge_len": avg_edge_len,
                "cell_area": cell_area,
                }
            qtm_feature.setAttributes([attributes[field.name()] for field in fields])
            mem_provider.addFeatures([qtm_feature])

        if feedback:
            feedback.setProgress(100)
            feedback.pushInfo("QTM Compact completed.")
                
        return mem_layer


########################## 
# OLC
# ########################
def olccompact(olc_layer: QgsVectorLayer, OLCID_field=None,feedback=None) -> QgsVectorLayer:
    if not OLCID_field:
        OLCID_field = 'olc'
        
    fields = QgsFields()
    fields.append(QgsField("olc", QVariant.String))
    fields.append(QgsField("resolution", QVariant.Int))
    fields.append(QgsField("center_lat", QVariant.Double))
    fields.append(QgsField("center_lon", QVariant.Double))
    fields.append(QgsField("cell_width", QVariant.Double))
    fields.append(QgsField("cell_height", QVariant.Double))
    fields.append(QgsField("cell_area", QVariant.Double))

    crs = olc_layer.crs().toWkt()
    mem_layer = QgsVectorLayer("Polygon?crs=" + crs, "olc_compacted", "memory")
    mem_provider = mem_layer.dataProvider()
    mem_provider.addAttributes(fields)
    mem_layer.updateFields()

    olc_ids = [
        feature[OLCID_field]
        for feature in olc_layer.getFeatures()
        if feature[OLCID_field]
    ]
    
    if olc_ids:
        try:
            olc_ids_compact = olc_compact(olc_ids)
        except:
                raise QgsProcessingException("Compact cells failed. Please check your OLC ID field.")
        
        total_cells = len(olc_ids_compact)

        for i, olc_id_compact in enumerate(olc_ids_compact):
            if feedback:
                feedback.setProgress(int((i / total_cells) * 100))
                if feedback.isCanceled():
                    return None
            try:
                coord = olc.decode(olc_id_compact)    
                min_lat, min_lon = coord.latitudeLo, coord.longitudeLo
                max_lat, max_lon = coord.latitudeHi, coord.longitudeHi        
                cell_resolution = coord.codeLength 

                # Define the polygon based on the bounding box
                cell_polygon = Polygon([
                    [min_lon, min_lat],  # Bottom-left corner
                    [max_lon, min_lat],  # Bottom-right corner
                    [max_lon, max_lat],  # Top-right corner
                    [min_lon, max_lat],  # Top-left corner
                    [min_lon, min_lat]   # Closing the polygon (same as the first point)
                ])
            except:
                raise QgsProcessingException("Compact cells failed. Please check your OLC ID field.")
                            
           
            center_lat, center_lon, cell_width, cell_height, cell_area = graticule_dggs_metrics(cell_polygon)
            
            cell_geom = QgsGeometry.fromWkt(cell_polygon.wkt)
            olc_feature = QgsFeature(fields)
            olc_feature.setGeometry(cell_geom)
            
            attributes = {
                "olc": olc_id_compact,
                "resolution": cell_resolution,
                "center_lat": center_lat,
                "center_lon": center_lon,
                "cell_width": cell_width,
                "cell_height": cell_height,
                "cell_area": cell_area
                }
            olc_feature.setAttributes([attributes[field.name()] for field in fields])
            mem_provider.addFeatures([olc_feature])

        if feedback:
            feedback.setProgress(100)
            feedback.pushInfo("OLC Compact completed.")
                
        return mem_layer


########################## 
# Geohash
# ########################
def geohashcompact(geohash_layer: QgsVectorLayer, GeohashID_field=None,feedback=None) -> QgsVectorLayer:
    if not GeohashID_field:
        GeohashID_field = 'geohash'
        
    fields = QgsFields()
    fields.append(QgsField("geohash", QVariant.String))
    fields.append(QgsField("resolution", QVariant.Int))
    fields.append(QgsField("center_lat", QVariant.Double))
    fields.append(QgsField("center_lon", QVariant.Double))
    fields.append(QgsField("cell_width", QVariant.Double))
    fields.append(QgsField("cell_height", QVariant.Double))
    fields.append(QgsField("cell_area", QVariant.Double))

    crs = geohash_layer.crs().toWkt()
    mem_layer = QgsVectorLayer("Polygon?crs=" + crs, "geohash_compacted", "memory")
    mem_provider = mem_layer.dataProvider()
    mem_provider.addAttributes(fields)
    mem_layer.updateFields()

    geohash_ids = [
        feature[GeohashID_field]
        for feature in geohash_layer.getFeatures()
        if feature[GeohashID_field]
    ]
    
    if geohash_ids:
        try:
            geohash_ids_compact = geohash_compact(geohash_ids)
        except:
                raise QgsProcessingException("Compact cells failed. Please check your geohash ID field.")
        
        total_cells = len(geohash_ids_compact)

        for i, geohash_id_compact in enumerate(geohash_ids_compact):
            if feedback:
                feedback.setProgress(int((i / total_cells) * 100))
                if feedback.isCanceled():
                    return None
            try:
                cell_polygon = geohash_to_polygon(geohash_id_compact)                
            except:
                raise QgsProcessingException("Compact cells failed. Please check your geohash ID field.")
                            
            resolution =  len(geohash_id_compact)
            center_lat, center_lon, cell_width, cell_height, cell_area = graticule_dggs_metrics(cell_polygon)
            
            cell_geom = QgsGeometry.fromWkt(cell_polygon.wkt)
            geohash_feature = QgsFeature(fields)
            geohash_feature.setGeometry(cell_geom)
            
            attributes = {
                "geohash": geohash_id_compact,
                "resolution": resolution,
                "center_lat": center_lat,
                "center_lon": center_lon,
                "cell_width": cell_width,
                "cell_height": cell_height,
                "cell_area": cell_area
                }
            geohash_feature.setAttributes([attributes[field.name()] for field in fields])
            mem_provider.addFeatures([geohash_feature])

        if feedback:
            feedback.setProgress(100)
            feedback.pushInfo("geohash Compact completed.")
                
        return mem_layer


########################## 
# Tilecode
# ########################
def tilecodecompact(tilecode_layer: QgsVectorLayer, TilecodeID_field=None,feedback=None) -> QgsVectorLayer:
    if not TilecodeID_field:
        TilecodeID_field = 'tilecode'
        
    fields = QgsFields()
    fields.append(QgsField("tilecode", QVariant.String))
    fields.append(QgsField("resolution", QVariant.Int))
    fields.append(QgsField("center_lat", QVariant.Double))
    fields.append(QgsField("center_lon", QVariant.Double))
    fields.append(QgsField("cell_width", QVariant.Double))
    fields.append(QgsField("cell_height", QVariant.Double))
    fields.append(QgsField("cell_area", QVariant.Double))

    crs = tilecode_layer.crs().toWkt()
    mem_layer = QgsVectorLayer("Polygon?crs=" + crs, "tilecode_compacted", "memory")
    mem_provider = mem_layer.dataProvider()
    mem_provider.addAttributes(fields)
    mem_layer.updateFields()

    tilecode_ids = [
        feature[TilecodeID_field]
        for feature in tilecode_layer.getFeatures()
        if feature[TilecodeID_field]
    ]
    
    if tilecode_ids:
        try:
            tilecode_ids_compact = tilecode_compact(tilecode_ids)
        except:
            raise QgsProcessingException("Compact cells failed. Please check your tilecode ID field.")
        
        total_cells = len(tilecode_ids_compact)

        for i, tilecode_id_compact in enumerate(tilecode_ids_compact):
            if feedback:
                feedback.setProgress(int((i / total_cells) * 100))
                if feedback.isCanceled():
                    return None
            try:
                match = re.match(r'z(\d+)x(\d+)y(\d+)', tilecode_id_compact)
                # Convert matched groups to integers
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
                
                resolution = z               
            except:
                raise QgsProcessingException("Compact cells failed. Please check your Tilecode ID field.")
                            
            center_lat, center_lon, cell_width, cell_height, cell_area = graticule_dggs_metrics(cell_polygon)
            
            cell_geom = QgsGeometry.fromWkt(cell_polygon.wkt)
            tilecode_feature = QgsFeature(fields)
            tilecode_feature.setGeometry(cell_geom)
            
            attributes = {
                "tilecode": tilecode_id_compact,
                "resolution": resolution,
                "center_lat": center_lat,
                "center_lon": center_lon,
                "cell_width": cell_width,
                "cell_height": cell_height,
                "cell_area": cell_area
                }
            tilecode_feature.setAttributes([attributes[field.name()] for field in fields])
            mem_provider.addFeatures([tilecode_feature])

        if feedback:
            feedback.setProgress(100)
            feedback.pushInfo("Tilecode Compact completed.")
                
        return mem_layer


########################## 
# Quadkey
# ########################
def quadkeycompact(quadkey_layer: QgsVectorLayer, QuadkeyID_field=None,feedback=None) -> QgsVectorLayer:
    if not QuadkeyID_field:
        QuadkeyID_field = 'quadkey'
        
    fields = QgsFields()
    fields.append(QgsField("quadkey", QVariant.String))
    fields.append(QgsField("resolution", QVariant.Int))
    fields.append(QgsField("center_lat", QVariant.Double))
    fields.append(QgsField("center_lon", QVariant.Double))
    fields.append(QgsField("cell_width", QVariant.Double))
    fields.append(QgsField("cell_height", QVariant.Double))
    fields.append(QgsField("cell_area", QVariant.Double))

    crs = quadkey_layer.crs().toWkt()
    mem_layer = QgsVectorLayer("Polygon?crs=" + crs, "quadkey_compacted", "memory")
    mem_provider = mem_layer.dataProvider()
    mem_provider.addAttributes(fields)
    mem_layer.updateFields()

    quadkey_ids = [
        feature[QuadkeyID_field]
        for feature in quadkey_layer.getFeatures()
        if feature[QuadkeyID_field]
    ]
    
    if quadkey_ids:
        try:
            quadkey_ids_compact = quadkey_compact(quadkey_ids)
        except:
            raise QgsProcessingException("Compact cells failed. Please check your Quadkey ID field.")
        
        total_cells = len(quadkey_ids_compact)

        for i, quadkey_id_compact in enumerate(quadkey_ids_compact):
            if feedback:
                feedback.setProgress(int((i / total_cells) * 100))
                if feedback.isCanceled():
                    return None
            try:
                quadkey_id_compact_tile = mercantile.quadkey_to_tile(quadkey_id_compact)
                z = quadkey_id_compact_tile.z
                x = quadkey_id_compact_tile.x
                y = quadkey_id_compact_tile.y

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
                resolution = z
                            
            except:
                raise QgsProcessingException("Compact cells failed. Please check your Quadkey ID field.")
                            
            center_lat, center_lon, cell_width, cell_height, cell_area = graticule_dggs_metrics(cell_polygon)
            
            cell_geom = QgsGeometry.fromWkt(cell_polygon.wkt)
            quadkey_feature = QgsFeature(fields)
            quadkey_feature.setGeometry(cell_geom)
            
            attributes = {
                "quadkey": quadkey_id_compact,
                "resolution": resolution,
                "center_lat": center_lat,
                "center_lon": center_lon,
                "cell_width": cell_width,
                "cell_height": cell_height,
                "cell_area": cell_area
                }
            quadkey_feature.setAttributes([attributes[field.name()] for field in fields])
            mem_provider.addFeatures([quadkey_feature])

        if feedback:
            feedback.setProgress(100)
            feedback.pushInfo("Quadkey Compact completed.")
                
        return mem_layer
