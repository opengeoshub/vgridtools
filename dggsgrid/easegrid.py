from shapely.geometry import box, Polygon
from qgis.core import (
    QgsWkbTypes,
    QgsCoordinateTransform,
    QgsGeometry,
    QgsProject,
)
from qgis.PyQt.QtCore import QObject, QTimer
from qgis.gui import QgsRubberBand
from qgis.PyQt.QtCore import pyqtSlot

from math import log2

from ..utils.latlon import epsg4326
from ..settings import settings
from vgrid.utils.io import validate_coordinate
from vgrid.utils.antimeridian import fix_polygon

# EASE-DGGS helpers
from ease_dggs.constants import levels_specs, geo_crs, ease_crs
from ease_dggs.dggs.grid_addressing import (
    grid_ids_to_geos,
    geo_polygon_to_grid_ids,
)


class EASEGrid(QObject):
    def __init__(self, vgridtools, canvas, iface):
        super(EASEGrid, self).__init__()
        self.canvas = canvas
        self.vgridtools = vgridtools
        self.iface = iface

        self.ease_marker = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
        self.ease_marker.setStrokeColor(settings.easeColor)
        self.ease_marker.setWidth(settings.gridWidth)

        # Auto-update toggle and debounced extent listener
        self.ease_enabled = False
        self._extentTimer = QTimer(self)
        self._extentTimer.setSingleShot(True)
        self._extentTimer.setInterval(150)
        self.canvas.extentsChanged.connect(self._onExtentsChanged)
        self._extentTimer.timeout.connect(self._refreshEASEGridOnExtent)
        self.removeMarker()

    def _onExtentsChanged(self):
        self._extentTimer.start()

    def ease_grid(self):
        try:
            # Reset rubber band
            self.removeMarker()
            self.ease_marker.reset(QgsWkbTypes.PolygonGeometry)
            self.ease_marker.setStrokeColor(settings.easeColor)
            self.ease_marker.setWidth(settings.gridWidth)

            canvas_extent = self.canvas.extent()
            canvas_crs = QgsProject.instance().crs()

            scale = self.canvas.scale()
            resolution = self._get_ease_resolution(scale)
            zoom = 29.1402 - log2(scale)
            if settings.zoomLevel:
                self.iface.mainWindow().statusBar().showMessage(
                    f"Zoom Level: {zoom:.2f} | EASE resolution:{resolution}"
                )
            if zoom >= 8:
                # Extent in canvas CRS
                min_lon, min_lat, max_lon, max_lat = (
                    canvas_extent.xMinimum(),
                    canvas_extent.yMinimum(),
                    canvas_extent.xMaximum(),
                    canvas_extent.yMaximum(),
                )

                # Transform to EPSG:4326 if needed
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

                # Validate and construct extent bbox
                min_lat, min_lon, max_lat, max_lon = validate_coordinate(
                    min_lat, min_lon, max_lat, max_lon
                )
                extent_bbox = box(min_lon, min_lat, max_lon, max_lat)

                # Query EASE cell IDs intersecting bbox
                extent_bbox_wkt = extent_bbox.wkt
                cells_bbox = geo_polygon_to_grid_ids(
                    extent_bbox_wkt,
                    level=resolution,
                    source_crs=geo_crs,
                    target_crs=ease_crs,
                    levels_specs=levels_specs,
                    return_centroids=True,
                    wkt_geom=True,
                )
                cells = (cells_bbox or {}).get("result", {}).get("data", [])

                if not cells:
                    self.canvas.refresh()
                    return

                # Cell dimensions at this level
                level_spec = levels_specs[resolution]
                n_row = level_spec["n_row"]
                n_col = level_spec["n_col"]
                half_cell_lat = 180 / (2 * n_row)
                half_cell_lon = 360 / (2 * n_col)

                for cell_id in cells:
                    try:
                        geo = grid_ids_to_geos([cell_id])
                        center_lon, center_lat = geo["result"]["data"][0]

                        cell_min_lat = center_lat - half_cell_lat
                        cell_max_lat = center_lat + half_cell_lat
                        cell_min_lon = center_lon - half_cell_lon
                        cell_max_lon = center_lon + half_cell_lon

                        poly = Polygon(
                            [
                                [cell_min_lon, cell_min_lat],
                                [cell_max_lon, cell_min_lat],
                                [cell_max_lon, cell_max_lat],
                                [cell_min_lon, cell_max_lat],
                                [cell_min_lon, cell_min_lat],
                            ]
                        )

                        if settings.fixAntimeridian:
                            poly = fix_polygon(poly)

                        geom = QgsGeometry.fromWkt(poly.wkt)
                        if epsg4326 != canvas_crs:
                            trans_to_canvas = QgsCoordinateTransform(
                                epsg4326, canvas_crs, QgsProject.instance()
                            )
                            geom.transform(trans_to_canvas)
                        self.ease_marker.addGeometry(geom, None)
                    except Exception:
                        continue

                self.canvas.refresh()

        except Exception:
            return

    def enable_ease(self, enabled: bool):
        self.ease_enabled = bool(enabled)
        if not self.ease_enabled:
            self.removeMarker()

    def _refreshEASEGridOnExtent(self):
        if self.ease_enabled:
            self.ease_grid()

    def _get_ease_resolution(self, scale):
        # Map scale to zoom, then to EASE resolution within configured bounds
        zoom = 29.1402 - log2(scale)
        if zoom >= 8:
            res = 0
        if zoom >= 10:
            res = 1
        if zoom >= 12:
            res = 2
        if zoom >= 14:
            res = 3
        if zoom >= 16:
            res = 4
        if zoom >= 18:
            res = 5
        if zoom >= 20:
            res = 6
        return res

    @pyqtSlot()
    def removeMarker(self):
        self.ease_marker.reset(QgsWkbTypes.PolygonGeometry)

    def cleanup(self):
        # Disconnect signals and delete rubber band
        try:
            self._extentTimer.stop()
            try:
                self._extentTimer.timeout.disconnect(self._refreshEASEGridOnExtent)
            except Exception:
                pass
            try:
                self.canvas.extentsChanged.disconnect(self._onExtentsChanged)
            except Exception:
                pass
        except Exception:
            pass

        try:
            self.ease_marker.reset(QgsWkbTypes.PolygonGeometry)
            self.ease_marker.deleteLater()
        except Exception:
            pass
