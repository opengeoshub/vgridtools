from shapely.geometry import Polygon, box
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

# S2
from vgrid.dggs import s2
from vgrid.utils.antimeridian import fix_polygon


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

            # Build S2 covering for the extent at the chosen resolution
            region = s2.LatLngRect.from_point_pair(
                s2.LatLng.from_degrees(min_lat, min_lon),
                s2.LatLng.from_degrees(max_lat, max_lon),
            )
            coverer = s2.RegionCoverer()
            coverer.min_level = resolution
            coverer.max_level = resolution
            cells = coverer.get_covering(region)

            for cell_id in cells:
                cell = s2.Cell(cell_id)
                vertices = []
                for i in range(4):
                    vertex = cell.get_vertex(i)
                    latlng = s2.LatLng.from_point(vertex)
                    vertices.append([latlng.lng().degrees, latlng.lat().degrees])
                vertices.append(vertices[0])
                cell_polygon = fix_polygon(Polygon(vertices))

                geom = QgsGeometry.fromWkt(cell_polygon.wkt)
                if epsg4326 != canvas_crs:
                    trans = QgsCoordinateTransform(
                        epsg4326, canvas_crs, QgsProject.instance()
                    )
                    geom.transform(trans)
                self.s2_marker.addGeometry(geom, None)

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

    def enable_s2(self, enabled: bool):
        self.s2_enabled = bool(enabled)
        if not self.s2_enabled:
            self.removeMarker()

    def _refreshS2GridOnExtent(self):
        if self.s2_enabled:
            self.s2_grid()

    def _get_s2_resolution(self, scale):
        # Map scale to approximate zoom, then to S2 resolution by flooring zoom
        from math import log2, floor

        zoom = 29.1402 - log2(scale)
        res = int(floor(zoom))

        # Respect configured bounds
        min_res, max_res, _ = settings.getResolution("S2")
        if res < min_res:
            return min_res
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


