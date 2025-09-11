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

from vgrid.dggs.rhealpixdggs.dggs import RHEALPixDGGS
from vgrid.utils.geometry import rhealpix_cell_to_polygon


class RhealpixGrid(QObject):
    def __init__(self, vgridtools, canvas, iface):
        super(RhealpixGrid, self).__init__()
        self.canvas = canvas
        self.vgridtools = vgridtools
        self.iface = iface

        self.rhealpix_marker = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
        self.rhealpix_marker.setStrokeColor(settings.rhealpixColor)
        self.rhealpix_marker.setWidth(settings.gridWidth)

        # rHEALPix auto-update toggle and debounced extent listener
        self.rhealpix_enabled = False
        self._extentTimer = QTimer(self)
        self._extentTimer.setSingleShot(True)
        self._extentTimer.setInterval(150)
        self.canvas.extentsChanged.connect(self._onExtentsChanged)
        self._extentTimer.timeout.connect(self._refreshRhealpixGridOnExtent)
        self.removeMarker()

        # Reuse one DGGS instance
        self._rhealpix_dggs = RHEALPixDGGS()

    def _onExtentsChanged(self):
        self._extentTimer.start()

    def rhealpix_grid(self):
        try:
            # Clear previous grid before drawing a new one
            self.removeMarker()
            self.rhealpix_marker.reset(QgsWkbTypes.PolygonGeometry)

            canvas_extent = self.canvas.extent()
            scale = self.canvas.scale()
            resolution = self._get_rhealpix_resolution(scale)
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

            extent_bbox = box(min_lon, min_lat, max_lon, max_lat)

            # Seed cell from bbox center
            bbox_center_lon = (min_lon + max_lon) / 2.0
            bbox_center_lat = (min_lat + max_lat) / 2.0
            seed_point = (bbox_center_lon, bbox_center_lat)

            seed_cell = self._rhealpix_dggs.cell_from_point(
                resolution, seed_point, plane=False
            )
            seed_cell_polygon = rhealpix_cell_to_polygon(seed_cell)

            cells_to_draw_ids = set()

            # If one cell fully contains the bbox, just draw it
            if seed_cell_polygon.contains(extent_bbox):
                cells_to_draw_ids.add(str(seed_cell))
            else:
                # BFS over neighbors to cover bbox extent
                covered_ids = set()
                queue = [seed_cell]
                while queue:
                    current_cell = queue.pop()
                    current_id = str(current_cell)
                    if current_id in covered_ids:
                        continue
                    covered_ids.add(current_id)

                    cell_polygon = rhealpix_cell_to_polygon(current_cell)
                    if cell_polygon.intersects(extent_bbox):
                        cells_to_draw_ids.add(current_id)
                        neighbors = current_cell.neighbors(plane=False)
                        for _, neighbor in neighbors.items():
                            neighbor_id = str(neighbor)
                            if neighbor_id not in covered_ids:
                                queue.append(neighbor)

            # Draw collected cells
            for cell_id in cells_to_draw_ids:
                rhealpix_uids = (cell_id[0],) + tuple(map(int, cell_id[1:]))
                cell = self._rhealpix_dggs.cell(rhealpix_uids)
                cell_polygon = rhealpix_cell_to_polygon(cell)
                if not cell_polygon.intersects(extent_bbox):
                    continue
                geom = QgsGeometry.fromWkt(cell_polygon.wkt)
                if epsg4326 != canvas_crs:
                    trans = QgsCoordinateTransform(
                        epsg4326, canvas_crs, QgsProject.instance()
                    )
                    geom.transform(trans)
                self.rhealpix_marker.addGeometry(geom, None)

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

    def enable_rhealpix(self, enabled: bool):
        self.rhealpix_enabled = bool(enabled)
        if not self.rhealpix_enabled:
            self.removeMarker()

    def _refreshRhealpixGridOnExtent(self):
        if self.rhealpix_enabled:
            self.rhealpix_grid()

    def _get_rhealpix_resolution(self, scale):
        # Map scale to zoom, then clamp to configured bounds
        from math import log2, floor

        zoom = 29.1402 - log2(scale)
        res = max(0, int(floor(zoom/1.7)))

        min_res, max_res, _ = settings.getResolution("rHEALPix")
        if res < min_res:
            return min_res
        if res > max_res:
            return max_res
        return res

    @pyqtSlot()
    def removeMarker(self):
        self.rhealpix_marker.reset(QgsWkbTypes.PolygonGeometry)

    def cleanup(self):
        # Disconnect signals and delete rubber band
        try:
            self._extentTimer.stop()
            try:
                self._extentTimer.timeout.disconnect(self._refreshRhealpixGridOnExtent)
            except Exception:
                pass
            try:
                self.canvas.extentsChanged.disconnect(self._onExtentsChanged)
            except Exception:
                pass
        except Exception:
            pass

        try:
            self.rhealpix_marker.reset(QgsWkbTypes.PolygonGeometry)
            self.rhealpix_marker.deleteLater()
        except Exception:
            pass


