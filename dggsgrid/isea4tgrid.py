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

import platform
from math import log2, floor

from ..utils.latlon import epsg4326
from ..settings import settings
from vgrid.utils.io import validate_coordinate  
from vgrid.utils.constants import DGGS_TYPES
    
if platform.system() == "Windows":
    from vgrid.dggs.eaggr.eaggr import Eaggr
    from vgrid.dggs.eaggr.shapes.dggs_cell import DggsCell
    from vgrid.dggs.eaggr.enums.shape_string_format import ShapeStringFormat
    from vgrid.dggs.eaggr.enums.model import Model
    from vgrid.generator.isea4tgrid import (
        get_isea4t_children_cells,
        get_isea4t_children_cells_within_bbox,
    )
    from vgrid.utils.constants import ISEA4T_BASE_CELLS, ISEA4T_RES_ACCURACY_DICT
    from vgrid.conversion.dggs2geo.isea4t2geo import isea4t2geo

    isea4t_dggs = Eaggr(Model.ISEA4T)


class ISEA4TGrid(QObject):
    def __init__(self, vgridtools, canvas, iface):
        super(ISEA4TGrid, self).__init__()
        self.canvas = canvas
        self.vgridtools = vgridtools
        self.iface = iface

        self.isea4t_marker = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
        self.isea4t_marker.setStrokeColor(settings.isea4tColor)
        self.isea4t_marker.setWidth(settings.gridWidth)

        # ISEA4T auto-update toggle and debounced extent listener
        self.isea4t_enabled = False
        self._extentTimer = QTimer(self)
        self._extentTimer.setSingleShot(True)
        self._extentTimer.setInterval(150)
        self.canvas.extentsChanged.connect(self._onExtentsChanged)
        self._extentTimer.timeout.connect(self._refreshISEA4TGridOnExtent)
        self.removeMarker()

    def _onExtentsChanged(self):
        self._extentTimer.start()

    def isea4t_grid(self):
        if platform.system() != "Windows":
            return
        try:
            # Clear previous grid before drawing a new one
            self.removeMarker()
            self.isea4t_marker.reset(QgsWkbTypes.PolygonGeometry)
            self.isea4t_marker.setStrokeColor(settings.isea4tColor)
            self.isea4t_marker.setWidth(settings.gridWidth)

            canvas_extent = self.canvas.extent()
            canvas_crs = QgsProject.instance().crs()

            scale = self.canvas.scale()
            resolution = self._get_isea4t_resolution(scale)
            if settings.zoomLevel:
                zoom = 29.1402 - log2(scale)
                self.iface.mainWindow().statusBar().showMessage(
                    f"Zoom Level: {zoom:.2f} | ISEA4T resolution:{resolution}"
                )

            if resolution <= 3:
                isea4t_cells = get_isea4t_children_cells(ISEA4T_BASE_CELLS, resolution)
                for child in isea4t_cells:
                    isea4t_cell = DggsCell(child)
                    isea4t_id = isea4t_cell.get_cell_id()
                    if settings.splitAntimeridian:
                        cell_polygon = isea4t2geo(isea4t_id, fix_antimeridian='split')
                    else:
                        cell_polygon = isea4t2geo(isea4t_id, fix_antimeridian='shift_west')
                    if epsg4326 != canvas_crs:
                        trans_to_canvas = QgsCoordinateTransform(
                            epsg4326, canvas_crs, QgsProject.instance()
                        )
                        cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)
                        cell_geometry.transform(trans_to_canvas)
                    else:
                        cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)
                    self.isea4t_marker.addGeometry(cell_geometry, None)
            else:
                # Define bbox in canvas CRS
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
                extent_bbox = box(min_lon, min_lat, max_lon, max_lat)

                accuracy = ISEA4T_RES_ACCURACY_DICT.get(resolution)
                extent_bbox_wkt = extent_bbox.wkt  # Create a bounding box polygon
                shapes = isea4t_dggs.convert_shape_string_to_dggs_shapes(
                    extent_bbox_wkt, ShapeStringFormat.WKT, accuracy
                )
                shape = shapes[0]
                bbox_cells = shape.get_shape().get_outer_ring().get_cells()
                bounding_cell = isea4t_dggs.get_bounding_dggs_cell(bbox_cells)
                cells_to_draw = get_isea4t_children_cells_within_bbox(
                    bounding_cell.get_cell_id(), extent_bbox, resolution
                )
                # Draw cells
                for cell_id in cells_to_draw:
                    try:
                        if settings.splitAntimeridian:
                            cell_polygon = isea4t2geo(cell_id, fix_antimeridian='split')
                        else:
                            cell_polygon = isea4t2geo(cell_id, fix_antimeridian='shift_west')
                        if epsg4326 != canvas_crs:
                            trans_to_canvas = QgsCoordinateTransform(
                                epsg4326, canvas_crs, QgsProject.instance()
                            )
                            cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)
                            cell_geometry.transform(trans_to_canvas)
                        else:
                            cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)
                        self.isea4t_marker.addGeometry(cell_geometry, None)
                    except Exception:
                        continue

            self.canvas.refresh()

        except Exception:
            return

    def enable_isea4t(self, enabled: bool):
        self.isea4t_enabled = bool(enabled)
        if not self.isea4t_enabled:
            self.removeMarker()

    def _refreshISEA4TGridOnExtent(self):
        if self.isea4t_enabled:
            self.isea4t_grid()

    def _get_isea4t_resolution(self, scale):
        # Map scale to zoom, then to ISEA4T resolution
        zoom = 29.1402 - log2(scale)
        min_res = DGGS_TYPES['isea4t']["min_res"]
        max_res = DGGS_TYPES['isea4t']["max_res"]
        res = min(max_res, max(min_res, int(floor(zoom)*0.95)))
        return res

    @pyqtSlot()
    def removeMarker(self):
        self.isea4t_marker.reset(QgsWkbTypes.PolygonGeometry)

    def cleanup(self):
        # Disconnect signals and delete rubber band
        try:
            self._extentTimer.stop()
            try:
                self._extentTimer.timeout.disconnect(self._refreshISEA4TGridOnExtent)
            except Exception:
                pass
            try:
                self.canvas.extentsChanged.disconnect(self._onExtentsChanged)
            except Exception:
                pass
        except Exception:
            pass

        try:
            self.isea4t_marker.reset(QgsWkbTypes.PolygonGeometry)
            self.isea4t_marker.deleteLater()
        except Exception:
            pass
