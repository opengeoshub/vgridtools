from shapely.geometry import Polygon
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

# Maidenhead imports
from vgrid.dggs import maidenhead
from vgrid.utils.io import validate_coordinate

# Grid parameters for different resolutions
grid_params = {
    1: (18, 18, 20, 10),  # Fields: 20° lon, 10° lat
    2: (180, 180, 2, 1),  # Squares: 2° lon, 1° lat
    3: (4320, 4320, 0.083333, 0.041666),  # Subsquare: 5' lon, 2.5' lat
    4: (43200, 43200, 0.008333, 0.004167),  # Extended: 30" lon, 15" lat
}


class MaidenheadGrid(QObject):
    def __init__(self, vgridtools, canvas, iface):
        super(MaidenheadGrid, self).__init__()
        self.canvas = canvas
        self.vgridtools = vgridtools
        self.iface = iface

        self.maidenhead_marker = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
        self.maidenhead_marker.setStrokeColor(settings.maidenheadColor)
        self.maidenhead_marker.setWidth(settings.gridWidth)

        # Maidenhead auto-update toggle and debounced extent listener
        self.maidenhead_enabled = False
        self._extentTimer = QTimer(self)
        self._extentTimer.setSingleShot(True)
        self._extentTimer.setInterval(150)
        self.canvas.extentsChanged.connect(self._onExtentsChanged)
        self._extentTimer.timeout.connect(self._refreshMaidenheadGridOnExtent)
        self.removeMarker()

    def _onExtentsChanged(self):
        self._extentTimer.start()

    def maidenhead_grid(self):
        try:
            # Clear previous grid before drawing a new one
            self.removeMarker()
            self.maidenhead_marker.reset(QgsWkbTypes.PolygonGeometry)
            self.maidenhead_marker.setStrokeColor(settings.maidenheadColor)
            self.maidenhead_marker.setWidth(settings.gridWidth)

            canvas_extent = self.canvas.extent()
            canvas_crs = QgsProject.instance().crs()

            scale = self.canvas.scale()
            resolution = self._get_maidenhead_resolution(scale)
            if settings.zoomLevel:
                zoom = 29.1402 - log2(scale)
                self.iface.mainWindow().statusBar().showMessage(
                    f"Zoom Level: {zoom:.2f} | Maidenhead resolution:{resolution}"
                )

            if resolution <= 1:
                min_lon, min_lat, max_lon, max_lat = -180, -90, 180, 90
            else:
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
            # Get grid parameters for the resolution
            x_cells, y_cells, lon_width, lat_width = grid_params[resolution]
            base_lat, base_lon = -90.0, -180.0

            # Calculate the cell indices corresponding to the extent bounds
            min_x = max(0, int((min_lon - base_lon) / lon_width))
            max_x = min(x_cells, int((max_lon - base_lon) / lon_width) + 1)
            min_y = max(0, int((min_lat - base_lat) / lat_width))
            max_y = min(y_cells, int((max_lat - base_lat) / lat_width) + 1)

            # Generate maidenhead cells within extent
            for i in range(min_x, max_x):
                for j in range(min_y, max_y):
                    cell_min_lon = base_lon + i * lon_width
                    cell_max_lon = cell_min_lon + lon_width
                    cell_min_lat = base_lat + j * lat_width
                    cell_max_lat = cell_min_lat + lat_width

                    cell_center_lat = (cell_min_lat + cell_max_lat) / 2
                    cell_center_lon = (cell_min_lon + cell_max_lon) / 2

                    maidenhead_id = maidenhead.toMaiden(
                        cell_center_lat, cell_center_lon, resolution
                    )
                    (
                        _,
                        _,
                        min_lat_maiden,
                        min_lon_maiden,
                        max_lat_maiden,
                        max_lon_maiden,
                        _,
                    ) = maidenhead.maidenGrid(maidenhead_id)

                    # Define the polygon based on the bounding box
                    cell_polygon = Polygon(
                        [
                            [min_lon_maiden, min_lat_maiden],  # Bottom-left corner
                            [max_lon_maiden, min_lat_maiden],  # Bottom-right corner
                            [max_lon_maiden, max_lat_maiden],  # Top-right corner
                            [min_lon_maiden, max_lat_maiden],  # Top-left corner
                            [min_lon_maiden, min_lat_maiden],  # Closing the polygon
                        ]
                    )

                    cell_geom = QgsGeometry.fromWkt(cell_polygon.wkt)
                    if epsg4326 != canvas_crs:
                        trans_to_canvas = QgsCoordinateTransform(
                            epsg4326, canvas_crs, QgsProject.instance()
                        )
                        cell_geom.transform(trans_to_canvas)
                    self.maidenhead_marker.addGeometry(cell_geom, None)

            self.canvas.refresh()

        except Exception:
            return

    def enable_maidenhead(self, enabled: bool):
        self.maidenhead_enabled = bool(enabled)
        if not self.maidenhead_enabled:
            self.removeMarker()

    def _refreshMaidenheadGridOnExtent(self):
        if self.maidenhead_enabled:
            self.maidenhead_grid()

    def _get_maidenhead_resolution(
        self, scale
    ):  # Map scale to zoom, then to Maidenhead resolution
        zoom = 29.1402 - log2(scale)
        min_res, max_res, _ = settings.getResolution("Maidenhead")
        # Maidenhead resolution mapping - similar to other grids
        res = max(min_res, int(floor(zoom / 3.1)))

        if res > max_res:
            return max_res
        return res

    @pyqtSlot()
    def removeMarker(self):
        self.maidenhead_marker.reset(QgsWkbTypes.PolygonGeometry)

    def cleanup(self):
        # Disconnect signals and delete rubber band
        try:
            self._extentTimer.stop()
            try:
                self._extentTimer.timeout.disconnect(
                    self._refreshMaidenheadGridOnExtent
                )
            except Exception:
                pass
            try:
                self.canvas.extentsChanged.disconnect(self._onExtentsChanged)
            except Exception:
                pass
        except Exception:
            pass

        try:
            self.maidenhead_marker.reset(QgsWkbTypes.PolygonGeometry)
            self.maidenhead_marker.deleteLater()
        except Exception:
            pass
