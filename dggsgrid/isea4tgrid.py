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
import platform

from ..utils import tr
from ..utils.latlon import epsg4326
from ..settings import settings

if platform.system() == "Windows":
    from vgrid.dggs.eaggr.eaggr import Eaggr
    from vgrid.dggs.eaggr.shapes.dggs_cell import DggsCell
    from vgrid.dggs.eaggr.enums.shape_string_format import ShapeStringFormat
    from vgrid.dggs.eaggr.enums.model import Model
    from vgrid.generator.isea4tgrid import (
        get_isea4t_children_cells,
        get_isea4t_children_cells_within_bbox,
    )
    from vgrid.utils.geometry import (
        isea4t_cell_to_polygon,
        fix_isea4t_antimeridian_cells,
    )
    from vgrid.utils.constants import ISEA4T_BASE_CELLS, ISEA4T_RES_ACCURACY_DICT
    from vgrid.utils.antimeridian import fix_polygon

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

            canvas_extent = self.canvas.extent()
            scale = self.canvas.scale()
            resolution = self._get_isea4t_resolution(scale)
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

            if extent_bbox:
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
                    isea4t_cell = DggsCell(cell_id)
                    isea4t_id = isea4t_cell.get_cell_id()
                    cell_polygon = isea4t_cell_to_polygon(isea4t_cell)

                    # Fix antimeridian issues following the same logic as processing provider
                    if resolution == 0:
                        cell_polygon = fix_polygon(cell_polygon)
                    elif (
                        isea4t_id.startswith("00")
                        or isea4t_id.startswith("09")
                        or isea4t_id.startswith("14")
                        or isea4t_id.startswith("04")
                        or isea4t_id.startswith("19")
                    ):
                        cell_polygon = fix_isea4t_antimeridian_cells(cell_polygon)

                    geom = QgsGeometry.fromWkt(cell_polygon.wkt)
                    if epsg4326 != canvas_crs:
                        trans = QgsCoordinateTransform(
                            epsg4326, canvas_crs, QgsProject.instance()
                        )
                        geom.transform(trans)
                    self.isea4t_marker.addGeometry(geom, None)
                except Exception:
                    continue

            self.canvas.refresh()

        except Exception as e:
            print(e)
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
        from math import log2, floor

        zoom = 29.1402 - log2(scale)    
        # ISEA4T resolution mapping - more conservative than other grids
        min_res, max_res, _ = settings.getResolution("ISEA4T")
        res = max(min_res, int(floor(zoom)))
        if res > max_res:
            return max_res
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
