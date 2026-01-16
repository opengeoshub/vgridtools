from qgis.core import (
    QgsWkbTypes,
    QgsCoordinateTransform,
    QgsGeometry,
    QgsProject,
)
from qgis.PyQt.QtCore import QObject, QTimer
from qgis.gui import QgsRubberBand
from qgis.PyQt.QtCore import pyqtSlot

from math import log2
import numpy as np

from ..utils.latlon import epsg4326
from ..settings import settings
from vgrid.utils.io import validate_coordinate
from vgrid.utils.constants import GEOREF_RESOLUTION_DEGREES
from vgrid.conversion.latlon2dggs import latlon2georef
from vgrid.conversion.dggs2geo import georef2geo
from vgrid.utils.constants import DGGS_TYPES
from math import floor  
from vgrid.utils.geometry import get_georef_resolution_from_scale_denominator

class GEOREFGrid(QObject):  
    def __init__(self, vgridtools, canvas, iface):
        super(GEOREFGrid, self).__init__()
        self.canvas = canvas
        self.vgridtools = vgridtools
        self.iface = iface

        self.georef_marker = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
        self.georef_marker.setStrokeColor(settings.georefColor)
        self.georef_marker.setWidth(settings.gridWidth)

        # GEOREF auto-update toggle and debounced extent listener
        self.georef_enabled = False
        self._extentTimer = QTimer(self)
        self._extentTimer.setSingleShot(True)
        self._extentTimer.setInterval(150)
        self.canvas.extentsChanged.connect(self._onExtentsChanged)
        self._extentTimer.timeout.connect(self._refreshGeorefGridOnExtent)
        self.removeMarker()

    def _onExtentsChanged(self):
        self._extentTimer.start()

    def georef_grid(self):
        try:
            # Clear previous grid before drawing a new one
            self.removeMarker()
            self.georef_marker.reset(QgsWkbTypes.PolygonGeometry)
            self.georef_marker.setStrokeColor(settings.georefColor)
            self.georef_marker.setWidth(settings.gridWidth)

            canvas_extent = self.canvas.extent()
            canvas_crs = QgsProject.instance().crs()

            scale = self.canvas.scale()
            resolution = self._get_georef_resolution(scale)
            # resolution = get_georef_resolution_from_scale_denominator(scale,relative_depth=2,mm_per_pixel = 0.28)
            if settings.zoomLevel:
                zoom = 29.1402 - log2(scale)
                self.iface.mainWindow().statusBar().showMessage(
                    f"Zoom Level: {zoom:.2f} | GEOREF resolution:{resolution}"
                )

            # Determine processing extent in EPSG:4326
            if resolution == 0:
                min_lon, min_lat, max_lon, max_lat = -180.0, -90.0, 180.0, 90.0
            else:
                min_lon, min_lat, max_lon, max_lat = (
                    canvas_extent.xMinimum(),
                    canvas_extent.yMinimum(),
                    canvas_extent.xMaximum(),
                    canvas_extent.yMaximum(),
                )
                # Transform extent to EPSG:4326 if needed
                if epsg4326 != canvas_crs:
                    trans_to_4326 = QgsCoordinateTransform(
                        canvas_crs, epsg4326, QgsProject.instance()
                    )
                    transformed_extent = trans_to_4326.transform(canvas_extent)
                    min_lon, min_lat, max_lon, max_lat = (
                        transformed_extent.xMinimum(),
                        transformed_extent.yMinimum(),
                        transformed_extent.xMaximum(),
                        transformed_extent.yMaximum(),
                    )

            # Clamp to valid bounds
            min_lat, min_lon, max_lat, max_lon = validate_coordinate(
                min_lat, min_lon, max_lat, max_lon
            )

            # Iterate GEOREF cells for the extent
            step_deg = GEOREF_RESOLUTION_DEGREES.get(resolution)
            if step_deg is None or step_deg <= 0:
                return

            longitudes = np.arange(min_lon, max_lon, step_deg)
            latitudes = np.arange(min_lat, max_lat, step_deg)

            for lon in longitudes:
                for lat in latitudes:
                    georef_id = latlon2georef(lat, lon, resolution)
                    cell_polygon = georef2geo(georef_id)
                    cell_geom = QgsGeometry.fromWkt(cell_polygon.wkt)
                    if epsg4326 != canvas_crs:
                        trans_to_canvas = QgsCoordinateTransform(
                            epsg4326, canvas_crs, QgsProject.instance()
                        )
                        cell_geom.transform(trans_to_canvas)
                    self.georef_marker.addGeometry(cell_geom, None)

            self.canvas.refresh()

        except Exception:
            return

    def enable_georef(self, enabled: bool):
        self.georef_enabled = bool(enabled)
        if not self.georef_enabled:
            self.removeMarker()

    def _refreshGeorefGridOnExtent(self):
        if self.georef_enabled:
            self.georef_grid()

    # def _get_georef_resolution_old(self, scale):
    #     # Map scale to zoom, then to GEOREF resolution (0..10)
    #     zoom = 29.1402 - log2(scale)
    #     if zoom <= 6:
    #         return 0
    #     elif zoom <= 10:
    #         return 1
    #     elif zoom <= 15:
    #         return 2
    #     elif zoom <= 19:
    #         return 3
    #     elif zoom <= 22:
    #         return 4
    #     elif zoom <= 24:
    #         return 5
    #     return 6
    
    def _get_georef_resolution(self, scale):
        # Map scale to zoom, then to GEOREF resolution using formula:
        zoom = 29.1402 - log2(scale)
        min_res = DGGS_TYPES['georef']["min_res"]
        max_res = DGGS_TYPES['georef']["max_res"]
        res = min(max_res, max(min_res, floor(zoom*0.2)))
        return res

        
    @pyqtSlot()
    def removeMarker(self):
        self.georef_marker.reset(QgsWkbTypes.PolygonGeometry)

    def cleanup(self):
        # Disconnect signals and delete rubber band
        try:
            self._extentTimer.stop()
            try:
                self._extentTimer.timeout.disconnect(self._refreshGeorefGridOnExtent)
            except Exception:
                pass
            try:
                self.canvas.extentsChanged.disconnect(self._onExtentsChanged)
            except Exception:
                pass
        except Exception:
            pass

        try:
            self.georef_marker.reset(QgsWkbTypes.PolygonGeometry)
            self.georef_marker.deleteLater()
        except Exception:
            pass
