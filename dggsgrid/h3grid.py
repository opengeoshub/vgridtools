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

import h3
from ..utils.latlon import epsg4326
from ..settings import settings
from vgrid.conversion.dggs2geo.h32geo import h32geo
from math import log2, floor        
from vgrid.utils.io import validate_coordinate
from vgrid.utils.geometry import geodesic_buffer
from vgrid.utils.constants import DGGS_TYPES

class H3Grid(QObject):
    def __init__(self, vgridtools, canvas, iface):
        super(H3Grid, self).__init__()
        self.canvas = canvas
        self.vgridtools = vgridtools
        self.iface = iface

        self.h3_marker = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
        self.h3_marker.setStrokeColor(settings.h3Color)
        self.h3_marker.setWidth(settings.gridWidth)

        # H3 auto-update toggle and debounced extent listener
        self.h3_enabled = False
        self._extentTimer = QTimer(self)
        self._extentTimer.setSingleShot(True)
        self._extentTimer.setInterval(150)
        self.canvas.extentsChanged.connect(self._onExtentsChanged)
        self._extentTimer.timeout.connect(self._refreshH3GridOnExtent)
        self.removeMarker()

    def _onExtentsChanged(self):
        self._extentTimer.start()

    def h3_grid(self):
        try:
            # Clear previous grid before drawing a new one
            self.removeMarker()
            self.h3_marker.reset(QgsWkbTypes.PolygonGeometry)
            self.h3_marker.setStrokeColor(settings.h3Color)
            self.h3_marker.setWidth(settings.gridWidth)

            canvas_extent = self.canvas.extent()
            canvas_crs = QgsProject.instance().crs()

            scale = self.canvas.scale()
            resolution = self._get_h3_resolution(scale)
            if settings.zoomLevel:
                zoom = 29.1402 - log2(scale)
                self.iface.mainWindow().statusBar().showMessage(
                    f"Zoom Level: {zoom:.2f} | H3 resolution:{resolution}"
                )

            if resolution == 0:
                base_cells = h3.get_res0_cells()
                for cell in base_cells:
                    child_cells = h3.cell_to_children(cell, resolution)
                    # Progress bar for child cells
                    for child_cell in child_cells:
                        if settings.splitAntimeridian:    
                            cell_polygon = h32geo(child_cell, fix_antimeridian='split')
                        else: cell_polygon = h32geo(child_cell, fix_antimeridian='shift_west')
                        if epsg4326 != canvas_crs:
                            trans_to_canvas = QgsCoordinateTransform(
                                epsg4326, canvas_crs, QgsProject.instance()
                            )                           
                            cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)
                            cell_geometry.transform(trans_to_canvas)
                        else:
                            cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)
                        self.h3_marker.addGeometry(cell_geometry, None)
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

                # buffer the extent because the h3.geo_to_cells function only returns the cells that are center_within the extent
                extent_bbox = box(min_lon, min_lat, max_lon, max_lat)
                distance = h3.average_hexagon_edge_length(resolution, unit="m")
                extent_bbox = geodesic_buffer(extent_bbox, distance)

                bbox_cells = h3.geo_to_cells(extent_bbox, resolution)
                for bbox_cell in bbox_cells:
                    if settings.splitAntimeridian:
                        cell_polygon = h32geo(bbox_cell, fix_antimeridian='split')
                    else:   
                        cell_polygon = h32geo(bbox_cell, fix_antimeridian='shift_west')  
                    if epsg4326 != canvas_crs:
                        trans_to_canvas = QgsCoordinateTransform(
                            epsg4326, canvas_crs, QgsProject.instance()
                        )
                        cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)
                        cell_geometry.transform(trans_to_canvas)
                    else:
                        cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)
                    self.h3_marker.addGeometry(cell_geometry, None)
            self.canvas.refresh()

        except Exception:
            return

    def enable_h3(self, enabled: bool):
        self.h3_enabled = bool(enabled)
        if not self.h3_enabled:
            self.removeMarker()

    def _refreshH3GridOnExtent(self):
        if self.h3_enabled:
            self.h3_grid()

    def _get_h3_resolution(self, scale):
        zoom = 29.1402 - log2(scale)
        min_res = DGGS_TYPES['h3']["min_res"]
        max_res = DGGS_TYPES['h3']["max_res"]
        res = min(max_res, max(min_res, int((floor(zoom) - 3) * 0.8)) )
        return res     

    @pyqtSlot()
    def removeMarker(self):
        self.h3_marker.reset(QgsWkbTypes.PolygonGeometry)

    def cleanup(self):
        # Disconnect signals and delete rubber band
        try:
            self._extentTimer.stop()
            try:
                self._extentTimer.timeout.disconnect(self._refreshH3GridOnExtent)
            except Exception:
                pass
            try:
                self.canvas.extentsChanged.disconnect(self._onExtentsChanged)
            except Exception:
                pass
        except Exception:
            pass

        try:
            self.h3_marker.reset(QgsWkbTypes.PolygonGeometry)
            self.h3_marker.deleteLater()
        except Exception:
            pass
