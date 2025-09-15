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
from math import log2, floor

from ..utils import tr
from ..utils.latlon import epsg4326
from ..settings import settings

# Geohash imports
from vgrid.conversion.dggs2geo.geohash2geo import geohash2geo


class GeohashGrid(QObject):
    def __init__(self, vgridtools, canvas, iface):
        super(GeohashGrid, self).__init__()
        self.canvas = canvas
        self.vgridtools = vgridtools
        self.iface = iface

        self.geohash_marker = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
        self.geohash_marker.setStrokeColor(settings.geohashColor)
        self.geohash_marker.setWidth(settings.gridWidth)

        # Geohash auto-update toggle and debounced extent listener
        self.geohash_enabled = False
        self._extentTimer = QTimer(self)
        self._extentTimer.setSingleShot(True)
        self._extentTimer.setInterval(150)
        self.canvas.extentsChanged.connect(self._onExtentsChanged)
        self._extentTimer.timeout.connect(self._refreshGeohashGridOnExtent)
        self.removeMarker()

    def _onExtentsChanged(self):
        self._extentTimer.start()

    def geohash_grid(self):
        try:
            # Clear previous grid before drawing a new one
            self.removeMarker()
            self.geohash_marker.reset(QgsWkbTypes.PolygonGeometry)

            canvas_extent = self.canvas.extent()
            scale = self.canvas.scale()
            resolution = self._get_geohash_resolution(scale)
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

            # Create extent bbox for intersection testing
            extent_bbox = box(min_lon, min_lat, max_lon, max_lat)

            # Initial geohashes covering the world at the lowest resolution
            initial_geohashes = [
                "b",
                "c",
                "f",
                "g",
                "u",
                "v",
                "y",
                "z",
                "8",
                "9",
                "d",
                "e",
                "s",
                "t",
                "w",
                "x",
                "0",
                "1",
                "2",
                "3",
                "p",
                "q",
                "r",
                "k",
                "m",
                "n",
                "h",
                "j",
                "4",
                "5",
                "6",
                "7",
            ]

            # Generate geohash cells
            if extent_bbox:
                # Generate grid within bounding box
                intersected_geohashes = []
                for gh in initial_geohashes:
                    cell_polygon = geohash2geo(gh)
                    if cell_polygon.intersects(extent_bbox):
                        intersected_geohashes.append(gh)

                # Expand each intersected geohash to the target resolution
                for gh in intersected_geohashes:
                    self._expand_geohash_within_extent(
                        gh, resolution, extent_bbox, canvas_crs
                    )
            else:
                # Generate global grid when no extent is provided
                for gh in initial_geohashes:
                    self._expand_geohash(gh, resolution, canvas_crs)

            self.canvas.refresh()

        except Exception as e:
            print(e)
            return

    def _expand_geohash(self, gh, target_length, canvas_crs):
        """Recursive function to expand geohashes to target resolution and draw them."""
        if len(gh) == target_length:
            cell_polygon = geohash2geo(gh)
            geom = QgsGeometry.fromWkt(cell_polygon.wkt)
            if epsg4326 != canvas_crs:
                trans = QgsCoordinateTransform(
                    epsg4326, canvas_crs, QgsProject.instance()
                )
                geom.transform(trans)
            self.geohash_marker.addGeometry(geom, None)
            return

        # Expand the geohash with all possible characters
        for char in "0123456789bcdefghjkmnpqrstuvwxyz":
            self._expand_geohash(gh + char, target_length, canvas_crs)

    def _expand_geohash_within_extent(self, gh, target_length, extent_bbox, canvas_crs):
        """Recursive function to expand geohashes to target resolution within extent and draw them."""
        cell_polygon = geohash2geo(gh)
        if not cell_polygon.intersects(extent_bbox):
            return

        if len(gh) == target_length:
            geom = QgsGeometry.fromWkt(cell_polygon.wkt)
            if epsg4326 != canvas_crs:
                trans = QgsCoordinateTransform(
                    epsg4326, canvas_crs, QgsProject.instance()
                )
                geom.transform(trans)
            self.geohash_marker.addGeometry(geom, None)
            return

        # If not at the target length, expand the geohash with all possible characters
        for char in "0123456789bcdefghjkmnpqrstuvwxyz":
            self._expand_geohash_within_extent(
                gh + char, target_length, extent_bbox, canvas_crs
            )

    def enable_geohash(self, enabled: bool):
        self.geohash_enabled = bool(enabled)
        if not self.geohash_enabled:
            self.removeMarker()

    def _refreshGeohashGridOnExtent(self):
        if self.geohash_enabled:
            self.geohash_grid()

    def _get_geohash_resolution(self, scale):
        # Map scale to zoom, then to Geohash resolution

        zoom = 29.1402 - log2(scale)
        min_res, max_res, _ = settings.getResolution("Geohash")
        res = max(min_res, int(floor(zoom / 2.2)))

        # Get Geohash resolution bounds from settings
        if res > max_res:
            return max_res
        return res

    @pyqtSlot()
    def removeMarker(self):
        self.geohash_marker.reset(QgsWkbTypes.PolygonGeometry)

    def cleanup(self):
        # Disconnect signals and delete rubber band
        try:
            self._extentTimer.stop()
            try:
                self._extentTimer.timeout.disconnect(self._refreshGeohashGridOnExtent)
            except Exception:
                pass
            try:
                self.canvas.extentsChanged.disconnect(self._onExtentsChanged)
            except Exception:
                pass
        except Exception:
            pass

        try:
            self.geohash_marker.reset(QgsWkbTypes.PolygonGeometry)
            self.geohash_marker.deleteLater()
        except Exception:
            pass
