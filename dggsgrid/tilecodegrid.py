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

from ..utils import tr
from ..utils.latlon import epsg4326
from ..settings import settings

# Tilecode imports
from vgrid.dggs import mercantile


class TilecodeGrid(QObject):
    def __init__(self, vgridtools, canvas, iface):
        super(TilecodeGrid, self).__init__()
        self.canvas = canvas
        self.vgridtools = vgridtools
        self.iface = iface

        self.tilecode_marker = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
        self.tilecode_marker.setStrokeColor(settings.tilecodeColor)
        self.tilecode_marker.setWidth(settings.gridWidth)

        # Tilecode auto-update toggle and debounced extent listener
        self.tilecode_enabled = False
        self._extentTimer = QTimer(self)
        self._extentTimer.setSingleShot(True)
        self._extentTimer.setInterval(150)
        self.canvas.extentsChanged.connect(self._onExtentsChanged)
        self._extentTimer.timeout.connect(self._refreshTilecodeGridOnExtent)
        self.removeMarker()

    def _onExtentsChanged(self):
        self._extentTimer.start()

    def tilecode_grid(self):
        try:
            # Clear previous grid before drawing a new one
            self.removeMarker()
            self.tilecode_marker.reset(QgsWkbTypes.PolygonGeometry)

            canvas_extent = self.canvas.extent()
            scale = self.canvas.scale()
            resolution = self._get_tilecode_resolution(scale)
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

            # Generate tilecode cells
            if extent_polygon_canvas:
                # Generate grid within bounding box
                tiles = list(mercantile.tiles(min_lon, min_lat, max_lon, max_lat, resolution))
            else:
                # Generate global grid when no extent is provided
                tiles = list(mercantile.tiles(-180.0, -85.05112878, 180.0, 85.05112878, resolution))

            # Iterate over each tile to create features
            for tile in tiles:
                # Get the tile's bounding box in geographic coordinates
                bounds = mercantile.bounds(tile)

                # Create a Shapely polygon
                cell_polygon = Polygon([
                    (bounds.west, bounds.south),
                    (bounds.east, bounds.south),
                    (bounds.east, bounds.north),
                    (bounds.west, bounds.north),
                    (bounds.west, bounds.south),  # Closing the polygon
                ])

                geom = QgsGeometry.fromWkt(cell_polygon.wkt)
                if epsg4326 != canvas_crs:
                    trans = QgsCoordinateTransform(
                        epsg4326, canvas_crs, QgsProject.instance()
                    )
                    geom.transform(trans)
                self.tilecode_marker.addGeometry(geom, None)

            self.canvas.refresh()

        except Exception as e:
            print(e)
            traceback.print_exc()
            return

    def enable_tilecode(self, enabled: bool):
        self.tilecode_enabled = bool(enabled)
        if not self.tilecode_enabled:
            self.removeMarker()

    def _refreshTilecodeGridOnExtent(self):
        if self.tilecode_enabled:
            self.tilecode_grid()

    def _get_tilecode_resolution(self, scale):
        # Map scale to zoom, then to Tilecode resolution
        from math import log2, floor

        zoom = 29.1402 - log2(scale)
        min_res, max_res, _ = settings.getResolution("Tilecode")

        # Tilecode resolution mapping - similar to other grids
        res = max(min_res, int(floor(zoom*1.1)))

        if res > max_res:
            return max_res
        return res

    @pyqtSlot()
    def removeMarker(self):
        self.tilecode_marker.reset(QgsWkbTypes.PolygonGeometry)

    def cleanup(self):
        # Disconnect signals and delete rubber band
        try:
            self._extentTimer.stop()
            try:
                self._extentTimer.timeout.disconnect(self._refreshTilecodeGridOnExtent)
            except Exception:
                pass
            try:
                self.canvas.extentsChanged.disconnect(self._onExtentsChanged)
            except Exception:
                pass
        except Exception:
            pass

        try:
            self.tilecode_marker.reset(QgsWkbTypes.PolygonGeometry)
            self.tilecode_marker.deleteLater()
        except Exception:
            pass
