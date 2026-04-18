from qgis.core import (
    QgsWkbTypes,
    QgsCoordinateTransform,
    QgsGeometry,
    QgsProject,
)
from qgis.PyQt.QtCore import QObject, QTimer
from qgis.gui import QgsRubberBand
from qgis.PyQt.QtCore import pyqtSlot
from collections import deque

from ..utils.latlon import epsg4326
from ..settings import settings
from vgrid.utils.io import validate_coordinate
from vgrid.utils.antimeridian import fix_polygon

# A5 converters
from vgrid.conversion.dggs2geo.a52geo import a52geo, a52geo_u64
from vgrid.conversion.latlon2dggs import latlon2a5
from math import log2, floor
from vgrid.utils.constants import DGGS_TYPES
from vgrid.utils.geometry import get_a5_resolution_from_scale_denominator
from shapely.geometry import box
import a5

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
            self.a5_marker.setStrokeColor(settings.a5Color)
            self.a5_marker.setWidth(settings.gridWidth)

            canvas_extent = self.canvas.extent()
            canvas_crs = QgsProject.instance().crs()

            scale = self.canvas.scale()
            resolution = get_a5_resolution_from_scale_denominator(
                scale, relative_depth=8, mm_per_pixel=0.28
            )
            if settings.zoomLevel:
                zoom = 29.1402 - log2(scale)
                self.iface.mainWindow().statusBar().showMessage(
                    f"Zoom Level: {zoom:.2f} | A5 resolution: {resolution}"
                )

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

            min_lat, min_lon, max_lat, max_lon = validate_coordinate(
                min_lat, min_lon, max_lat, max_lon
            )

            bbox_polygon = box(min_lon, min_lat, max_lon, max_lat)
            bbox_center_lon = bbox_polygon.centroid.x
            bbox_center_lat = bbox_polygon.centroid.y

            seed_cell_id = a5.lonlat_to_cell((bbox_center_lon, bbox_center_lat), resolution)
            seed_cell_polygon = a52geo_u64(
                seed_cell_id, split_antimeridian=settings.splitAntimeridian
            )
            if seed_cell_polygon is None:
                return

            # Fast path: single cell fully contains the extent
            if seed_cell_polygon.contains(bbox_polygon):
                if settings.splitAntimeridian:
                    seed_cell_polygon = fix_polygon(seed_cell_polygon)
                if epsg4326 != canvas_crs:
                    trans_to_canvas = QgsCoordinateTransform(
                        epsg4326, canvas_crs, QgsProject.instance()
                    )
                    cell_geometry = QgsGeometry.fromWkt(seed_cell_polygon.wkt)
                    cell_geometry.transform(trans_to_canvas)
                else:
                    cell_geometry = QgsGeometry.fromWkt(seed_cell_polygon.wkt)
                self.a5_marker.addGeometry(cell_geometry, None)
                self.canvas.refresh()
                return

            intersecting_cells = {}
            covered_cells = set()
            queue = deque([seed_cell_id])

            while queue:
                current_cell_id = queue.popleft()
                if current_cell_id in covered_cells:
                    continue
                covered_cells.add(current_cell_id)

                cell_polygon = a52geo_u64(
                    current_cell_id, split_antimeridian=settings.splitAntimeridian
                )
                if cell_polygon is None:
                    continue

                if cell_polygon.intersects(bbox_polygon):
                    intersecting_cells[current_cell_id] = cell_polygon
                    neighbors = a5.uncompact(a5.grid_disk_vertex(current_cell_id, 1), resolution)
                    for neighbor_id in neighbors:
                        if neighbor_id not in covered_cells:
                            queue.append(neighbor_id)

            if epsg4326 != canvas_crs:
                trans_to_canvas = QgsCoordinateTransform(
                    epsg4326, canvas_crs, QgsProject.instance()
                )
            else:
                trans_to_canvas = None

            for cell_polygon in intersecting_cells.values():
                draw_polygon = cell_polygon
                if settings.splitAntimeridian:
                    draw_polygon = fix_polygon(draw_polygon)
                cell_geometry = QgsGeometry.fromWkt(draw_polygon.wkt)
                if trans_to_canvas is not None:
                    cell_geometry.transform(trans_to_canvas)
                self.a5_marker.addGeometry(cell_geometry, None)

            self.canvas.refresh()

        except Exception:
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
        min_res = DGGS_TYPES['a5']["min_res"]
        max_res = DGGS_TYPES['a5']["max_res"]
        res = min(max_res, max(min_res, floor(zoom*0.95)))
        return res

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