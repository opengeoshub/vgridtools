from shapely.geometry import box
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

from ..utils import tr
from ..utils.latlon import epsg4326
from ..settings import settings

# A5 converters
from vgrid.conversion.dggs2geo.a52geo import a52geo
from vgrid.conversion.latlon2dggs import latlon2a5
from math import log2, floor

class A5Grid(QObject):
    def __init__(self, vgridtools, canvas, iface):
        super(A5Grid, self).__init__()
        self.canvas = canvas
        self.vgridtools = vgridtools
        self.iface = iface

        self.a5_marker = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
        self.a5_marker.setStrokeColor(settings.a5Color)
        self.a5_marker.setWidth(settings.gridWidth)

        # A5 auto-update toggle and debounced extent listener
        self.a5_enabled = False
        self._extentTimer = QTimer(self)
        self._extentTimer.setSingleShot(True)
        self._extentTimer.setInterval(150)
        self.canvas.extentsChanged.connect(self._onExtentsChanged)
        self._extentTimer.timeout.connect(self._refreshA5GridOnExtent)
        self.removeMarker()

    def _onExtentsChanged(self):
        self._extentTimer.start()

    def a5_grid(self):
        try:
            # Clear previous grid before drawing a new one
            self.removeMarker()
            self.a5_marker.reset(QgsWkbTypes.PolygonGeometry)

            canvas_extent = self.canvas.extent()
            scale = self.canvas.scale()
            resolution = self._get_a5_resolution(scale)
            canvas_crs = self.canvas.mapSettings().destinationCrs()

            # Define bbox in EPSG:4326
            extent_polygon = box(
                canvas_extent.xMinimum(),
                canvas_extent.yMinimum(),
                canvas_extent.xMaximum(),
                canvas_extent.yMaximum(),
            )

            # Transform extent to EPSG:4326 if needed
            if epsg4326 != canvas_crs:
                # Build QgsGeometry rectangle and transform
                extent_geom = QgsGeometry.fromWkt(extent_polygon.wkt)
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
                    extent_polygon.bounds[0],
                    extent_polygon.bounds[1],
                    extent_polygon.bounds[2],
                    extent_polygon.bounds[3],
                )

            # Determine lon/lat step based on resolution (aligned with processing a5)
            lon_width, lat_width = self._resolution_to_step(resolution)

            # Iterate over bbox grid
            seen = set()
            lon = min_lon
            while lon < max_lon:
                lat = min_lat
                while lat < max_lat:
                    centroid_lat = lat + lat_width / 2.0
                    centroid_lon = lon + lon_width / 2.0
                    try:
                        a5_id = latlon2a5(centroid_lat, centroid_lon, resolution)
                        if a5_id in seen:
                            lat += lat_width
                            continue
                        seen.add(a5_id)
                        poly = a52geo(a5_id)
                        if poly is None:
                            lat += lat_width
                            continue
                        geom = QgsGeometry.fromWkt(poly.wkt)
                        if epsg4326 != canvas_crs:
                            trans = QgsCoordinateTransform(
                                epsg4326, canvas_crs, QgsProject.instance()
                            )
                            geom.transform(trans)
                        self.a5_marker.addGeometry(geom, None)
                    except Exception:
                        pass
                    lat += lat_width
                lon += lon_width

            self.canvas.refresh()

        except Exception as e:
            traceback.print_exc()
            self.iface.messageBar().pushMessage(
                "",
                tr("Invalid Coordinate: {}").format(str(e)),
                level=Qgis.Warning,
                duration=2,
            )
            return

    def enable_a5(self, enabled: bool):
        self.a5_enabled = bool(enabled)
        if not self.a5_enabled:
            self.removeMarker()

    def _refreshA5GridOnExtent(self):
        if self.a5_enabled:
            self.a5_grid()

    def _get_a5_resolution(self, scale):
        # Map scale to approximate zoom, then to A5 resolution similar cadence as H3

        zoom = 29.1402 - log2(scale)

        # Base mapping: floor(zoom), but not less than 1
        res = max(1, int(floor(zoom/1.7)))

        # Respect configured bounds
        min_res, max_res, _ = settings.getResolution("A5")
        if res < min_res:
            return min_res
        if res > max_res:
            return max_res
        return res

    def _resolution_to_step(self, resolution):
        # Mirror logic from processing a5 grid
        if resolution == 0:
            return 35, 35
        if resolution == 1:
            return 18, 18
        if resolution == 2:
            return 10, 10
        if resolution == 3:
            return 5, 5
        # finer than 3 halves each step
        base_width = 5
        factor = 0.5 ** (resolution - 3)
        step = base_width * factor
        return step, step

    @pyqtSlot()
    def removeMarker(self):
        self.a5_marker.reset(QgsWkbTypes.PolygonGeometry)

    def cleanup(self):
        # Disconnect signals and delete rubber band
        try:
            self._extentTimer.stop()
            try:
                self._extentTimer.timeout.disconnect(self._refreshA5GridOnExtent)
            except Exception:
                pass
            try:
                self.canvas.extentsChanged.disconnect(self._onExtentsChanged)
            except Exception:
                pass
        except Exception:
            pass

        try:
            self.a5_marker.reset(QgsWkbTypes.PolygonGeometry)
            self.a5_marker.deleteLater()
        except Exception:
            pass


