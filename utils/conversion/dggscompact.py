from shapely.wkt import loads
from shapely.geometry import Polygon
from vgrid.dggs import s2, olc, mercantile
import h3
import a5

from vgrid.dggs.rhealpixdggs.dggs import RHEALPixDGGS
from vgrid.dggs.rhealpixdggs.ellipsoids import WGS84_ELLIPSOID
import platform,re
if (platform.system() == 'Windows'):   
    from vgrid.dggs.eaggr.eaggr import Eaggr
    from vgrid.dggs.eaggr.enums.model import Model
    from vgrid.conversion.dggscompact.isea4tcompact import isea4t_compact
    from vgrid.conversion.dggscompact.isea4tcompact import get_isea4t_resolution
    from vgrid.conversion.dggscompact.isea3hcompact import isea3h_compact
    from vgrid.conversion.dggscompact.isea3hcompact import get_isea3h_resolution
    from vgrid.conversion.dggs2geo.isea4t2geo import isea4t2geo
    from vgrid.conversion.dggs2geo.isea3h2geo import isea3h2geo
    isea3h_dggs = Eaggr(Model.ISEA3H)
    isea4t_dggs = Eaggr(Model.ISEA4T)

from vgrid.utils.geometry import (
     rhealpix_cell_to_polygon, graticule_dggs_metrics, geodesic_dggs_metrics     
)
from vgrid.conversion.dggs2geo.h32geo import h32geo 
from vgrid.conversion.dggs2geo.s22geo import s22geo
from vgrid.conversion.dggs2geo.a52geo import a52geo
from vgrid.conversion.dggscompact.a5compact import a5_compact
from vgrid.conversion.dggscompact.rhealpixcompact import rhealpix_compact
from vgrid.conversion.dggs2geo.qtm2geo import qtm2geo
from vgrid.conversion.dggscompact.qtmcompact import qtm_compact,get_qtm_resolution
from vgrid.conversion.dggs2geo.olc2geo import olc2geo
from vgrid.conversion.dggscompact.olccompact import olc_compact, get_olc_resolution
from vgrid.conversion.dggs2geo.geohash2geo import geohash2geo
from vgrid.conversion.dggscompact.geohashcompact import geohash_compact,get_geohash_resolution
from vgrid.conversion.dggscompact.tilecodecompact import tilecode_compact
from vgrid.conversion.dggs2geo.tilecode2geo import tilecode2geo
from vgrid.conversion.dggscompact.quadkeycompact import quadkey_compact
from vgrid.conversion.dggs2geo.quadkey2geo import quadkey2geo
from vgrid.dggs.tilecode import tilecode_resolution, quadkey_resolution

from vgrid.conversion.dggscompact import *
from pyproj import Geod
geod = Geod(ellps="WGS84")
E = WGS84_ELLIPSOID

from qgis.core import (
    QgsVectorLayer, QgsFeature, QgsGeometry, QgsField, QgsFields, QgsProcessingException
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
    fields.append(QgsField("cell_perimeter", QVariant.Double))

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

            cell_polygon = h32geo(h3_id_compact)
            
            if not cell_polygon.is_valid:
                continue
            
            resolution = h3.get_resolution(h3_id_compact)
            num_edges = 5 if h3.is_pentagon(h3_id_compact) else 6
            center_lat, center_lon, avg_edge_len, cell_area,cell_perimeter = geodesic_dggs_metrics(cell_polygon, num_edges)
            
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
                "cell_perimeter": cell_perimeter,
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
    fields.append(QgsField("cell_perimeter", QVariant.Double))
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

        cell_polygon = s22geo(s2_token_compact)
            
        if not cell_polygon.is_valid:
            continue
        
        resolution = s2.CellId.from_token(s2_token_compact).level() 
        num_edges = 4
        center_lat, center_lon, avg_edge_len, cell_area,cell_perimeter = geodesic_dggs_metrics(cell_polygon, num_edges)
        
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
            "cell_perimeter": cell_perimeter,
            }
        s2_feature.setAttributes([attributes[field.name()] for field in fields])
        mem_provider.addFeatures([s2_feature])

    if feedback:
        feedback.setProgress(100)
        feedback.pushInfo("S2 Compact completed.")
            
    return mem_layer


########################## 
# A5
# ########################
def a5compact(a5_layer: QgsVectorLayer, A5ID_field=None, feedback=None) -> QgsVectorLayer:
    if not A5ID_field:
        A5ID_field = 'a5'
        
    fields = QgsFields()
    fields.append(QgsField("a5", QVariant.String))
    fields.append(QgsField("resolution", QVariant.Int))
    fields.append(QgsField("center_lat", QVariant.Double))
    fields.append(QgsField("center_lon", QVariant.Double))
    fields.append(QgsField("avg_edge_len", QVariant.Double))
    fields.append(QgsField("cell_area", QVariant.Double))
    fields.append(QgsField("cell_perimeter", QVariant.Double))
    crs = a5_layer.crs().toWkt()
    mem_layer = QgsVectorLayer("Polygon?crs=" + crs, "a5_compacted", "memory")
    mem_provider = mem_layer.dataProvider()
    mem_provider.addAttributes(fields)
    mem_layer.updateFields()

    a5_hexes = [
        feature[A5ID_field]
        for feature in a5_layer.getFeatures()
        if feature[A5ID_field]
    ]
    a5_hexes = list(set(a5_hexes))
    
    if a5_hexes:
        try:
            a5_hexes_compact = a5_compact(a5_hexes)
        except:
            raise QgsProcessingException("Compact cells failed. Please check your A5 ID field.")

        total_cells = len(a5_hexes_compact)

        for i, a5_hex_compact in enumerate(a5_hexes_compact):
            if feedback:
                feedback.setProgress(int((i / total_cells) * 100))
                if feedback.isCanceled():
                    return None

            try:
                cell_polygon = a52geo(a5_hex_compact)
            except:
                raise QgsProcessingException("Compact cells failed. Please check your A5 ID field.")
            
            if not cell_polygon.is_valid:
                continue
            
            resolution = a5.get_resolution(a5.hex_to_bigint(a5_hex_compact))
            num_edges = 5  # A5 cells are pentagons
            center_lat, center_lon, avg_edge_len, cell_area,cell_perimeter = geodesic_dggs_metrics(cell_polygon, num_edges)
            
            cell_geom = QgsGeometry.fromWkt(cell_polygon.wkt)
            a5_feature = QgsFeature(fields)
            a5_feature.setGeometry(cell_geom)
            
            attributes = {
                "a5": a5_hex_compact,
                "resolution": resolution,
                "center_lat": center_lat,
                "center_lon": center_lon,
                "avg_edge_len": avg_edge_len,
                "cell_area": cell_area,
                "cell_perimeter": cell_perimeter,
                }
            a5_feature.setAttributes([attributes[field.name()] for field in fields])
            mem_provider.addFeatures([a5_feature])

        if feedback:
            feedback.setProgress(100)
            feedback.pushInfo("A5 Compact completed.")
                
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
    fields.append(QgsField("cell_perimeter", QVariant.Double))
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
            
            center_lat, center_lon, avg_edge_len, cell_area,cell_perimeter = geodesic_dggs_metrics(cell_polygon, num_edges)
            
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
                "cell_perimeter": cell_perimeter,
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
        
        fields = QgsFields()
        fields.append(QgsField("isea4t", QVariant.String))
        fields.append(QgsField("resolution", QVariant.Int))
        fields.append(QgsField("center_lat", QVariant.Double))
        fields.append(QgsField("center_lon", QVariant.Double))
        fields.append(QgsField("avg_edge_len", QVariant.Double))
        fields.append(QgsField("cell_area", QVariant.Double))
        fields.append(QgsField("cell_perimeter", QVariant.Double))
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
                isea4t_ids_compact = isea4t_compact(isea4t_ids)
            except:
                raise QgsProcessingException("Compact cells failed. Please check your ISEA4T ID field.")
        
            total_cells = len(isea4t_ids_compact)

            for i, isea4t_id_compact in enumerate(isea4t_ids_compact):
                if feedback:
                    feedback.setProgress(int((i / total_cells) * 100))
                    if feedback.isCanceled():
                        return None
                
                cell_polygon = isea4t2geo(isea4t_id_compact)    
                
                resolution = get_isea4t_resolution(isea4t_id_compact)
                num_edges = 3
                
                center_lat, center_lon, avg_edge_len, cell_area,cell_perimeter = geodesic_dggs_metrics(cell_polygon, num_edges)
                
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
                    "cell_perimeter": cell_perimeter,
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
        
        fields = QgsFields()
        fields.append(QgsField("isea3h", QVariant.String))
        fields.append(QgsField("resolution", QVariant.Int))
        fields.append(QgsField("center_lat", QVariant.Double))
        fields.append(QgsField("center_lon", QVariant.Double))
        fields.append(QgsField("avg_edge_len", QVariant.Double))
        fields.append(QgsField("cell_area", QVariant.Double))
        fields.append(QgsField("cell_perimeter", QVariant.Double))
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
                isea3h_ids_compact = isea3h_compact(isea3h_ids)
            except:
                raise QgsProcessingException("Compact cells failed. Please check your ISEA3H ID field.")
        
            total_cells = len(isea3h_ids_compact)

            for i, isea3h_id_compact in enumerate(isea3h_ids_compact):
                if feedback:
                    feedback.setProgress(int((i / total_cells) * 100))
                    if feedback.isCanceled():
                        return None
                
                cell_polygon = isea3h2geo(isea3h_id_compact)               
                cell_resolution = get_isea3h_resolution(isea3h_id_compact)
                num_edges = 6
                
                center_lat, center_lon, avg_edge_len, cell_area,cell_perimeter = geodesic_dggs_metrics(cell_polygon, num_edges)

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
                    "cell_perimeter": cell_perimeter,
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
    fields.append(QgsField("cell_perimeter", QVariant.Double))
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
            cell_polygon = qtm2geo(qtm_id_compact)
            resolution = get_qtm_resolution(qtm_id_compact)
            num_edges = 3
            center_lat, center_lon, avg_edge_len, cell_area,cell_perimeter = geodesic_dggs_metrics(cell_polygon, num_edges)
            
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
                "cell_perimeter": cell_perimeter,
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
    fields.append(QgsField("cell_perimeter", QVariant.Double))
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
            cell_polygon = olc2geo(olc_id_compact)
            cell_resolution = get_olc_resolution(olc_id_compact)
            num_edges = 4
            center_lat, center_lon, cell_width, cell_height, cell_area,cell_perimeter = graticule_dggs_metrics(cell_polygon)

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
                "cell_area": cell_area,
                "cell_perimeter": cell_perimeter,
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
    fields.append(QgsField("cell_perimeter", QVariant.Double))
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
            cell_polygon = geohash2geo(geohash_id_compact)
            resolution = get_geohash_resolution(geohash_id_compact)
            center_lat, center_lon, cell_width, cell_height, cell_area,cell_perimeter = graticule_dggs_metrics(cell_polygon)
            
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
                "cell_area": cell_area,
                "cell_perimeter": cell_perimeter,
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
    fields.append(QgsField("cell_perimeter", QVariant.Double))      
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
            cell_polygon = tilecode2geo(tilecode_id_compact)
            resolution = tilecode_resolution(tilecode_id_compact)
            num_edges = 4
            center_lat, center_lon, cell_width, cell_height, cell_area,cell_perimeter = graticule_dggs_metrics(cell_polygon)
            
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
                "cell_area": cell_area,
                "cell_perimeter": cell_perimeter,
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
    fields.append(QgsField("cell_perimeter", QVariant.Double))
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
            cell_polygon = quadkey2geo(quadkey_id_compact)
            resolution = quadkey_resolution(quadkey_id_compact)
            center_lat, center_lon, cell_width, cell_height, cell_area,cell_perimeter = graticule_dggs_metrics(cell_polygon)
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
                "cell_area": cell_area,
                "cell_perimeter": cell_perimeter,
                }
            quadkey_feature.setAttributes([attributes[field.name()] for field in fields])
            mem_provider.addFeatures([quadkey_feature])

        if feedback:    
            feedback.setProgress(100)
            feedback.pushInfo("Quadkey Compact completed.")
                
        return mem_layer
