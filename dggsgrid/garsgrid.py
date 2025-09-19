from shapely.geometry import Polygon
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
from vgrid.utils.constants import GARS_RESOLUTION_MINUTES
from gars_field.garsgrid import GARSGrid as GARSGRID  # Ensure the correct import path


class GARSGrid(QObject):
    def __init__(self, vgridtools, canvas, iface):
        super(GARSGrid, self).__init__()
        self.canvas = canvas
        self.vgridtools = vgridtools
        self.iface = iface

        self.gars_marker = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
        self.gars_marker.setStrokeColor(settings.garsColor)
        self.gars_marker.setWidth(settings.gridWidth)

        # GARS auto-update toggle and debounced extent listener
        self.gars_enabled = False
        self._extentTimer = QTimer(self)
        self._extentTimer.setSingleShot(True)
        self._extentTimer.setInterval(150)
        self.canvas.extentsChanged.connect(self._onExtentsChanged)
        self._extentTimer.timeout.connect(self._refreshGARSGridOnExtent)
        self.removeMarker()

    def _onExtentsChanged(self):
        self._extentTimer.start()

    def gars_grid(self):
        # try:
        # Clear previous grid before drawing a new one
        self.removeMarker()
        self.gars_marker.reset(QgsWkbTypes.PolygonGeometry)
        self.gars_marker.setStrokeColor(settings.garsColor)
        self.gars_marker.setWidth(settings.gridWidth)

        canvas_extent = self.canvas.extent()
        canvas_crs = QgsProject.instance().crs()

        scale = self.canvas.scale()
        resolution = self._get_gars_resolution(scale)
        zoom = 29.1402 - log2(scale)
        if settings.zoomLevel:
            self.iface.mainWindow().statusBar().showMessage(
                f"Zoom Level: {zoom:.2f} | GARS resolution:{resolution}"
            )

        resolution_minutes = GARS_RESOLUTION_MINUTES.get(resolution)
        resolution_degrees = resolution_minutes / 60.0

        if zoom >= 8:
            min_lon, min_lat, max_lon, max_lat = (
                canvas_extent.xMinimum(),
                canvas_extent.yMinimum(),
                canvas_extent.xMaximum(),
                canvas_extent.yMaximum(),
            )

            # Transform to EPSG:4326 if needed
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

            # Validate and construct extent bbox
            min_lat, min_lon, max_lat, max_lon = validate_coordinate(
                min_lat, min_lon, max_lat, max_lon
            )

            longitudes = np.arange(min_lon, max_lon, resolution_degrees)
            latitudes = np.arange(min_lat, max_lat, resolution_degrees)

            for lon in longitudes:
                for lat in latitudes:
                    gars_cell = GARSGRID.from_latlon(lat, lon, resolution_minutes)
                    wkt_polygon = gars_cell.polygon
                    cell_polygon = Polygon(list(wkt_polygon.exterior.coords))
                    try:
                        cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)
                        if epsg4326 != canvas_crs:
                            trans = QgsCoordinateTransform(
                                epsg4326, canvas_crs, QgsProject.instance()
                            )
                            cell_geometry.transform(trans)
                        self.gars_marker.addGeometry(cell_geometry, None)
                    except Exception:
                        continue

            self.canvas.refresh()

    # except Exception as e:
    #     return

    def enable_gars(self, enabled: bool):
        self.gars_enabled = bool(enabled)
        if not self.gars_enabled:
            self.removeMarker()

    def _refreshGARSGridOnExtent(self):
        if self.gars_enabled:
            self.gars_grid()

    def _get_gars_resolution(self, scale):
        # Map scale to zoom, then to GARS resolution
        zoom = 29.1402 - log2(scale)
        res = 1
        if zoom >= 8:
            res = 1
        if zoom >= 10:
            res = 2
        if zoom >= 12:
            res = 3
        if zoom >= 14:
            res = 4
        return res

    @pyqtSlot()
    def removeMarker(self):
        self.gars_marker.reset(QgsWkbTypes.PolygonGeometry)

    def cleanup(self):
        # Disconnect signals and delete rubber band
        try:
            self._extentTimer.stop()
            try:
                self._extentTimer.timeout.disconnect(self._refreshGARSGridOnExtent)
            except Exception:
                pass
            try:
                self.canvas.extentsChanged.disconnect(self._onExtentsChanged)
            except Exception:
                pass
        except Exception:
            pass

        try:
            self.gars_marker.reset(QgsWkbTypes.PolygonGeometry)
            self.gars_marker.deleteLater()
        except Exception:
            pass

    def enable_gars(self, enabled: bool):
        self.gars_enabled = bool(enabled)
        if not self.gars_enabled:
            self.removeMarker()

    def _refreshGARSGridOnExtent(self):
        if self.gars_enabled:
            self.gars_grid()

    @pyqtSlot()
    def removeMarker(self):
        self.gars_marker.reset(QgsWkbTypes.PolygonGeometry)

    def cleanup(self):
        # Disconnect signals and delete rubber band
        try:
            self._extentTimer.stop()
            try:
                self._extentTimer.timeout.disconnect(self._refreshGARSGridOnExtent)
            except Exception:
                pass
            try:
                self.canvas.extentsChanged.disconnect(self._onExtentsChanged)
            except Exception:
                pass
        except Exception:
            pass

        try:
            self.gars_marker.reset(QgsWkbTypes.PolygonGeometry)
            self.gars_marker.deleteLater()
        except Exception:
            pass
