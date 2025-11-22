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

from math import log2, floor

from ..utils.latlon import epsg4326
from ..settings import settings
from vgrid.conversion.dggs2geo.s22geo import s22geo

# S2
from vgrid.dggs import s2


class S2Grid(QObject):
    def __init__(self, vgridtools, canvas, iface):
        super(S2Grid, self).__init__()
        self.canvas = canvas
        self.vgridtools = vgridtools
        self.iface = iface

        self.s2_marker = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
        self.s2_marker.setStrokeColor(settings.s2Color)
        self.s2_marker.setWidth(settings.gridWidth)

        # S2 auto-update toggle and debounced extent listener
        self.s2_enabled = False
        self._extentTimer = QTimer(self)
        self._extentTimer.setSingleShot(True)
        self._extentTimer.setInterval(150)
        self.canvas.extentsChanged.connect(self._onExtentsChanged)
        self._extentTimer.timeout.connect(self._refreshS2GridOnExtent)
        self.removeMarker()

    def _onExtentsChanged(self):
        self._extentTimer.start()

    def s2_grid(self):
        try:
            # Clear previous grid before drawing a new one
            self.removeMarker()
            self.s2_marker.reset(QgsWkbTypes.PolygonGeometry)

            canvas_extent = self.canvas.extent()
            scale = self.canvas.scale()
            resolution = self._get_s2_resolution(scale)
            if settings.zoomLevel:
                zoom = 29.1402 - log2(scale)
                self.iface.mainWindow().statusBar().showMessage(
                    f"Zoom Level: {zoom:.2f} | S2 resolution:{resolution}"
                )
            canvas_crs = self.canvas.mapSettings().destinationCrs()
            coverer = s2.RegionCoverer()
            coverer.min_level = resolution
            coverer.max_level = resolution
            if resolution <= 3:
                min_lon, min_lat, max_lon, max_lat = -180, -90, 180, 90
                region = s2.LatLngRect(
                    s2.LatLng.from_degrees(min_lat, min_lon),
                    s2.LatLng.from_degrees(max_lat, max_lon),
                )
            else:
                canvas_extent_bbox = box(
                    canvas_extent.xMinimum(),
                    canvas_extent.yMinimum(),
                    canvas_extent.xMaximum(),
                    canvas_extent.yMaximum(),
                )

                # Transform extent to EPSG:4326 if needed
                if epsg4326 != canvas_crs:
                    extent_geom = QgsGeometry.fromWkt(canvas_extent_bbox.wkt)
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
                        canvas_extent_bbox.bounds[0],
                        canvas_extent_bbox.bounds[1],
                        canvas_extent_bbox.bounds[2],
                        canvas_extent_bbox.bounds[3],
                    )

                # Build S2 covering for the extent at the chosen resolution
                region = s2.LatLngRect.from_point_pair(
                    s2.LatLng.from_degrees(min_lat, min_lon),
                    s2.LatLng.from_degrees(max_lat, max_lon),
                )

            cells = coverer.get_covering(region)
            for cell_id in cells:
                s2_token = s2.CellId.to_token(cell_id)
                if settings.splitAntimeridian:
                    cell_polygon = s22geo(s2_token, fix_antimeridian='split')
                else:
                    cell_polygon = s22geo(s2_token, fix_antimeridian='shift_east')  
                cell_geom = QgsGeometry.fromWkt(cell_polygon.wkt)
                if epsg4326 != canvas_crs:
                    trans = QgsCoordinateTransform(
                        epsg4326, canvas_crs, QgsProject.instance()
                    )
                    cell_geom.transform(trans)
                self.s2_marker.addGeometry(cell_geom, None)

            self.canvas.refresh()

        except Exception:
            return

    def enable_s2(self, enabled: bool):
        self.s2_enabled = bool(enabled)
        if not self.s2_enabled:
            self.removeMarker()

    def _refreshS2GridOnExtent(self):
        if self.s2_enabled:
            self.s2_grid()

    def _get_s2_resolution(self, scale):
        # Map scale to approximate zoom, then to S2 resolution by flooring zoom
        zoom = 29.1402 - log2(scale)
        # Respect configured bounds
        min_res, max_res, _ = settings.getResolution("S2")
        res = max(min_res, int(floor(zoom)))
        if res > max_res:
            return max_res
        return res

    @pyqtSlot()
    def removeMarker(self):
        self.s2_marker.reset(QgsWkbTypes.PolygonGeometry)

    def cleanup(self):
        # Disconnect signals and delete rubber band
        try:
            self._extentTimer.stop()
            try:
                self._extentTimer.timeout.disconnect(self._refreshS2GridOnExtent)
            except Exception:
                pass
            try:
                self.canvas.extentsChanged.disconnect(self._onExtentsChanged)
            except Exception:
                pass
        except Exception:
            pass

        try:
            self.s2_marker.reset(QgsWkbTypes.PolygonGeometry)
            self.s2_marker.deleteLater()
        except Exception:
            pass
