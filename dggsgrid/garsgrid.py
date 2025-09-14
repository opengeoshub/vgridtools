from shapely.geometry import box, Polygon
from qgis.core import (
    Qgis,
    QgsWkbTypes,
    QgsCoordinateTransform,
    QgsGeometry,
    QgsProject,
)
from qgis.PyQt.QtCore import QObject, QTimer
from qgis.gui import QgsRubberBand
from qgis.PyQt.QtCore import pyqtSlot

import traceback
import numpy as np

from ..utils import tr
from ..utils.latlon import epsg4326
from ..settings import settings

# GARS imports
from gars_field.garsgrid import GARSGrid as GARSGRID


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
        try:
            # Clear previous grid before drawing a new one
            self.removeMarker()
            self.gars_marker.reset(QgsWkbTypes.PolygonGeometry)

            canvas_extent = self.canvas.extent()
            scale = self.canvas.scale()
            resolution = self._get_gars_resolution(scale)
            canvas_crs = self.canvas.mapSettings().destinationCrs()

            # Define bbox in canvas CRS
            extent_polygon_canvas = box(
                canvas_extent.xMinimum(),
                canvas_extent.yMinimum(),
                canvas_extent.xMaximum(),
                canvas_extent.yMaximum(),
            )

            # Transform extent to EPSG:4326 if needed
            if epsg4326 != canvas_crs:
                extent_geom = QgsGeometry.fromWkt(extent_polygon_canvas.wkt)
                trans_to_4326 = QgsCoordinateTransform(
                    canvas_crs, epsg4326, QgsProject.instance()
                )
                extent_geom.transform(trans_to_4326)
                rect = extent_geom.boundingBox()
                min_lon, min_lat, max_lon, max_lat = (
                    rect.xMinimum(),
                    rect.yMinimum(),
                    rect.xMaximum(),
                    rect.yMaximum(),
                )
            else:
                min_lon, min_lat, max_lon, max_lat = (
                    extent_polygon_canvas.bounds[0],
                    extent_polygon_canvas.bounds[1],
                    extent_polygon_canvas.bounds[2],
                    extent_polygon_canvas.bounds[3],
                )

            # GARS grid parameters
            lon_min, lon_max = -180.0, 180.0
            lat_min, lat_max = -90.0, 90.0
            minutes_map = {
                1: 30,  # 30 minutes
                2: 15,  # 15 minutes
                3: 5,   # 5 minutes
                4: 1,   # 1 minute
            }

            resolution_minutes = minutes_map[resolution]
            resolution_degrees = resolution_minutes / 60.0

            longitudes = np.arange(lon_min, lon_max, resolution_degrees)
            latitudes = np.arange(lat_min, lat_max, resolution_degrees)

            # Calculate the cell indices corresponding to the extent bounds
            min_x = max(0, int((min_lon - lon_min) / resolution_degrees))
            max_x = min(len(longitudes), int((max_lon - lon_min) / resolution_degrees) + 1)
            min_y = max(0, int((min_lat - lat_min) / resolution_degrees))
            max_y = min(len(latitudes), int((max_lat - lat_min) / resolution_degrees) + 1)

            # Generate GARS cells within extent
            for i in range(min_x, max_x):
                for j in range(min_y, max_y):
                    lon = longitudes[i]
                    lat = latitudes[j]
                    cell_polygon = Polygon([
                        (lon, lat),
                        (lon + resolution_degrees, lat),
                        (lon + resolution_degrees, lat + resolution_degrees),
                        (lon, lat + resolution_degrees),
                        (lon, lat),
                    ])

                    geom = QgsGeometry.fromWkt(cell_polygon.wkt)
                    if epsg4326 != canvas_crs:
                        trans = QgsCoordinateTransform(
                            epsg4326, canvas_crs, QgsProject.instance()
                        )
                        geom.transform(trans)
                    self.gars_marker.addGeometry(geom, None)

            self.canvas.refresh()

        except Exception as e:
            print(e)
            traceback.print_exc()
            return

    def enable_gars(self, enabled: bool):
        self.gars_enabled = bool(enabled)
        if not self.gars_enabled:
            self.removeMarker()

    def _refreshGARSGridOnExtent(self):
        if self.gars_enabled:
            self.gars_grid()

    def _get_gars_resolution(self, scale):
        # Map scale to zoom, then to GARS resolution
        from math import log2, floor

        zoom = 29.1402 - log2(scale)
        min_res, max_res, _ = settings.getResolution("GARS")
        res = max(min_res+1, int(floor(zoom / 5.0)))

        # Get GARS resolution bounds from settings
        min_res, max_res, _ = settings.getResolution("GARS")
        if res > max_res:
            return max_res
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
