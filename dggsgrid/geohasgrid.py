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
from vgrid.utils.constants import INITIAL_GEOHASHES

# Geohash imports
from vgrid.conversion.dggs2geo.geohash2geo import geohash2geo
from vgrid.utils.io import validate_coordinate
from vgrid.utils.constants import DGGS_TYPES
from vgrid.utils.geometry import get_geohash_resolution_from_scale_denominator


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
            self.geohash_marker.setStrokeColor(settings.geohashColor)
            self.geohash_marker.setWidth(settings.gridWidth)

            canvas_extent = self.canvas.extent()
            canvas_crs = QgsProject.instance().crs()

            scale = self.canvas.scale()
            # resolution = self._get_geohash_resolution(scale)
            resolution = get_geohash_resolution_from_scale_denominator(scale,relative_depth=3,mm_per_pixel = 0.28)
            if settings.zoomLevel:
                zoom = 29.1402 - log2(scale)
                self.iface.mainWindow().statusBar().showMessage(
                    f"Zoom Level: {zoom:.2f} | Geohash resolution:{resolution}"
                )

            if resolution <= 2:
                for gh in INITIAL_GEOHASHES:
                    self._expand_geohash(gh, resolution, canvas_crs)
            else:
                min_lon, min_lat, max_lon, max_lat = (
                    canvas_extent.xMinimum(),
                    canvas_extent.yMinimum(),
                    canvas_extent.xMaximum(),
                    canvas_extent.yMaximum(),
                )
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

                min_lat, min_lon, max_lat, max_lon = validate_coordinate(
                    min_lat, min_lon, max_lat, max_lon
                )
                extent_bbox = box(min_lon, min_lat, max_lon, max_lat)
                intersected_geohashes = []
                for gh in INITIAL_GEOHASHES:
                    cell_polygon = geohash2geo(gh)
                    if cell_polygon.intersects(extent_bbox):
                        intersected_geohashes.append(gh)

                # Expand each intersected geohash to the target resolution
                for gh in intersected_geohashes:
                    self._expand_geohash_within_extent(
                        gh, resolution, extent_bbox, canvas_crs
                    )

            self.canvas.refresh()

        except Exception:
            return

    def _expand_geohash(self, gh, target_length, canvas_crs):
        """Recursive function to expand geohashes to target resolution and draw them."""
        if len(gh) == target_length:
            cell_polygon = geohash2geo(gh)
            cell_geom = QgsGeometry.fromWkt(cell_polygon.wkt)
            if epsg4326 != canvas_crs:
                trans_to_canvas = QgsCoordinateTransform(
                    epsg4326, canvas_crs, QgsProject.instance()
                )
                cell_geom.transform(trans_to_canvas)
            self.geohash_marker.addGeometry(cell_geom, None)
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
            cell_geom = QgsGeometry.fromWkt(cell_polygon.wkt)
            if epsg4326 != canvas_crs:
                trans_to_canvas = QgsCoordinateTransform(
                    epsg4326, canvas_crs, QgsProject.instance()
                )
                cell_geom.transform(trans_to_canvas)
            self.geohash_marker.addGeometry(cell_geom, None)
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
        min_res = DGGS_TYPES['geohash']["min_res"]
        max_res = DGGS_TYPES['geohash']["max_res"]
        res = min(max_res, max(min_res, floor(zoom*0.45)))
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
