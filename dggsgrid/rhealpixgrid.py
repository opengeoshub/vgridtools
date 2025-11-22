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

from pyproj import Geod
from math import log2, floor

from vgrid.dggs.rhealpixdggs.dggs import RHEALPixDGGS

geod = Geod(ellps="WGS84")
rhealpix_dggs = RHEALPixDGGS()

from ..utils.latlon import epsg4326
from ..settings import settings

from vgrid.dggs.rhealpixdggs.dggs import RHEALPixDGGS
from vgrid.conversion.dggs2geo import rhealpix2geo


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
            if settings.zoomLevel:
                zoom = 29.1402 - log2(scale)
                self.iface.mainWindow().statusBar().showMessage(
                    f"Zoom Level: {zoom:.2f} | rHEALPix resolution:{resolution}"
                )
            canvas_crs = self.canvas.mapSettings().destinationCrs()
            if resolution <= 2:
                min_lon, min_lat, max_lon, max_lat = -180, -90, 180, 90
                rhealpix_cells = rhealpix_dggs.grid(resolution)
                for rhealpix_cell in rhealpix_cells:
                    rhealpix_id = str(rhealpix_cell)
                    # Apply antimeridian fix if requested
                    if settings.splitAntimeridian:
                        cell_polygon = rhealpix2geo(rhealpix_id, fix_antimeridian='split')
                    else:
                        cell_polygon = rhealpix2geo(rhealpix_id, fix_antimeridian='shift_east')
                    # cell_geom = QgsGeometry.fromWkt(cell_polygon.wkt)
                    # if epsg4326 != canvas_crs:
                    #     trans = QgsCoordinateTransform(
                    #         epsg4326, canvas_crs, QgsProject.instance()
                    #     )
                    #     cell_geom.transform(trans)
                    # self.rhealpix_marker.addGeometry(cell_geom, None)
                    if epsg4326 != canvas_crs:
                        trans_to_canvas = QgsCoordinateTransform(
                            epsg4326, canvas_crs, QgsProject.instance()
                        )
                        cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)
                        cell_geometry.transform(trans_to_canvas)
                    else:
                        cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)
                    self.rhealpix_marker.addGeometry(cell_geometry, None)
            else:
                # Define bbox in canvas CRS
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

                extent_bbox = box(min_lon, min_lat, max_lon, max_lat)
                # Seed cell from bbox center
                bbox_center_lon = (min_lon + max_lon) / 2.0
                bbox_center_lat = (min_lat + max_lat) / 2.0
                seed_point = (bbox_center_lon, bbox_center_lat)

                seed_cell = self._rhealpix_dggs.cell_from_point(
                    resolution, seed_point, plane=False
                )
                seed_cell_id = str(seed_cell)
                # Apply antimeridian fix if requested for intersection check
                if settings.splitAntimeridian:
                    seed_cell_polygon = rhealpix2geo(seed_cell_id, fix_antimeridian='split')
                else:
                    seed_cell_polygon = rhealpix2geo(seed_cell_id, fix_antimeridian='shift_east')

                cells_to_draw_ids = set()

                # If one cell fully contains the bbox, just draw it
                if seed_cell_polygon.contains(extent_bbox):
                    cells_to_draw_ids.add(seed_cell_id)
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

                        # Apply antimeridian fix if requested for intersection check
                        if settings.splitAntimeridian:
                            cell_polygon = rhealpix2geo(current_id, fix_antimeridian='split')
                        else:
                            cell_polygon = rhealpix2geo(current_id, fix_antimeridian='shift_east')
                        if cell_polygon.intersects(extent_bbox):
                            cells_to_draw_ids.add(current_id)
                            neighbors = current_cell.neighbors(plane=False)
                            for _, neighbor in neighbors.items():
                                neighbor_id = str(neighbor)
                                if neighbor_id not in covered_ids:
                                    queue.append(neighbor)

                # Draw collected cells
                for cell_id in cells_to_draw_ids:
                    # Apply antimeridian fix if requested
                    if settings.splitAntimeridian:
                        cell_polygon = rhealpix2geo(cell_id, fix_antimeridian='split')
                    else:
                        cell_polygon = rhealpix2geo(cell_id, fix_antimeridian='shift_east') 
                    if not cell_polygon.intersects(extent_bbox):
                        continue
                    # cell_geom = QgsGeometry.fromWkt(cell_polygon.wkt)
                    # if epsg4326 != canvas_crs:
                    #     trans = QgsCoordinateTransform(
                    #         epsg4326, canvas_crs, QgsProject.instance()
                    #     )
                    #     cell_geom.transform(trans)
                    # self.rhealpix_marker.addGeometry(cell_geom, None)
                    if epsg4326 != canvas_crs:
                        trans_to_canvas = QgsCoordinateTransform(
                            epsg4326, canvas_crs, QgsProject.instance()
                        )
                        cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)
                        cell_geometry.transform(trans_to_canvas)
                    else:
                        cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)
                    self.rhealpix_marker.addGeometry(cell_geometry, None)

            self.canvas.refresh()

        except Exception:
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
        from math import log2

        zoom = 29.1402 - log2(scale)
        min_res, max_res, _ = settings.getResolution("rHEALPix")
        res = max(min_res, int(floor(zoom / 1.7)))
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
