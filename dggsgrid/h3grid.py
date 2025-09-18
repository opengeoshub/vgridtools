from shapely.geometry import box
from qgis.core import (
    QgsWkbTypes,
    QgsCoordinateTransform,
    QgsGeometry,
    QgsProject,
)
from qgis.PyQt.QtCore import QObject, QTimer
from qgis.gui import QgsRubberBand
from qgis.PyQt.QtCore import pyqtSlot
import h3
from ..utils.latlon import epsg4326
from ..settings import settings
from vgrid.conversion.dggs2geo.h32geo import h32geo
from math import log2    
from vgrid.utils.io import validate_coordinate

class H3Grid(QObject):
    def __init__(self, vgridtools, canvas, iface):
        super(H3Grid, self).__init__()
        self.canvas = canvas
        self.vgridtools = vgridtools
        self.iface = iface

        self.h3_marker = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
        self.h3_marker.setStrokeColor(settings.h3Color)
        self.h3_marker.setWidth(settings.gridWidth)

        # H3 auto-update toggle and debounced extent listener
        self.h3_enabled = False
        self._extentTimer = QTimer(self)
        self._extentTimer.setSingleShot(True)
        self._extentTimer.setInterval(150)
        self.canvas.extentsChanged.connect(self._onExtentsChanged)
        self._extentTimer.timeout.connect(self._refreshH3GridOnExtent)
        self.removeMarker()

    def _onExtentsChanged(self):
        self._extentTimer.start()

    def h3_grid(self):
        try:
            # Clear previous grid before drawing a new one
            self.removeMarker()
            self.h3_marker.reset(QgsWkbTypes.PolygonGeometry)
            self.h3_marker.setStrokeColor(settings.h3Color)
            self.h3_marker.setWidth(settings.gridWidth)

            canvas_extent = self.canvas.extent()
            canvas_crs = QgsProject.instance().crs()
            
            scale = self.canvas.scale()
            resolution = self._get_h3_resolution(scale)
            if settings.zoomLevel:
                zoom = 29.1402 - log2(scale)
                self.iface.mainWindow().statusBar().showMessage(
                    f"Zoom Level: {zoom:.2f} | H3 resolution:{resolution}"
                )   

            if resolution == 0:
                base_cells = h3.get_res0_cells()
                for cell in base_cells:
                    child_cells = h3.cell_to_children(cell, resolution)
                    # Progress bar for child cells
                    for child_cell in child_cells:
                        cell_polygon = h32geo(child_cell)
                        cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)
                        if epsg4326 != canvas_crs:
                            trans_to_canvas = QgsCoordinateTransform(
                                epsg4326, canvas_crs, QgsProject.instance()
                            )
                            cell_geometry.transform(trans_to_canvas)
                        self.h3_marker.addGeometry(cell_geometry, None)      
            
            else:                
                min_lon, min_lat, max_lon, max_lat = (
                    canvas_extent.xMinimum(),
                    canvas_extent.yMinimum(),
                    canvas_extent.xMaximum(),
                    canvas_extent.yMaximum(),
                )
                # Transform extent to EPSG:4326 if needed
                if epsg4326 != canvas_crs:
                    trans_to_4326 = QgsCoordinateTransform(canvas_crs, epsg4326, QgsProject.instance())
                    transformed_extent = trans_to_4326.transform(canvas_extent)              
                    min_lon, min_lat, max_lon, max_lat = (
                        transformed_extent.xMinimum(),
                        transformed_extent.yMinimum(),
                        transformed_extent.xMaximum(),
                        transformed_extent.yMaximum(),
                    )       

                min_lat, min_lon, max_lat, max_lon = validate_coordinate(min_lat, min_lon, max_lat, max_lon)  
                extent_bbox = box(min_lon, min_lat, max_lon, max_lat)
                bbox_cells = h3.geo_to_cells(extent_bbox, resolution)
                for bbox_cell in bbox_cells:
                    cell_polygon = h32geo(bbox_cell)
                    cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)
                    if epsg4326 != canvas_crs:
                        trans_to_canvas = QgsCoordinateTransform(
                            epsg4326, canvas_crs, QgsProject.instance()
                        )
                        cell_geometry.transform(trans_to_canvas)
                    self.h3_marker.addGeometry(cell_geometry, None)

            self.canvas.refresh()

        except Exception as e:
            return

    def enable_h3(self, enabled: bool):
        self.h3_enabled = bool(enabled)
        if not self.h3_enabled:
            self.removeMarker()

    def _refreshH3GridOnExtent(self):
        if self.h3_enabled:
            self.h3_grid()

    def _get_h3_resolution(self, scale):
        
        zoom = 29.1402 - log2(scale)

        if zoom <= 3.0:
            return 0
        if zoom <= 4.4:
            return 1
        if zoom <= 5.7:
            return 2
        if zoom <= 7.1:
            return 3
        if zoom <= 8.4:
            return 4
        if zoom <= 9.8:
            return 5
        if zoom <= 11.4:
            return 6
        if zoom <= 12.7:
            return 7
        if zoom <= 14.1:
            return 8
        if zoom <= 15.5:
            return 9
        if zoom <= 16.8:
            return 10
        if zoom <= 18.2:
            return 11
        if zoom <= 19.5:
            return 12
        if zoom <= 21.1:
            return 13
        if zoom <= 21.9:
            return 14
        return 15

    @pyqtSlot()
    def removeMarker(self):
        self.h3_marker.reset(QgsWkbTypes.PolygonGeometry)

    def cleanup(self):
        # Disconnect signals and delete rubber band
        try:
            self._extentTimer.stop()
            try:
                self._extentTimer.timeout.disconnect(self._refreshH3GridOnExtent)
            except Exception:
                pass
            try:
                self.canvas.extentsChanged.disconnect(self._onExtentsChanged)
            except Exception:
                pass
        except Exception:
            pass

        try:
            self.h3_marker.reset(QgsWkbTypes.PolygonGeometry)
            self.h3_marker.deleteLater()
        except Exception:
            pass
