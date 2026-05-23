from math import log2

from shapely.geometry import Polygon
from qgis.core import (
    QgsWkbTypes,
    QgsCoordinateTransform,
    QgsGeometry,
    QgsProject,
)
from qgis.PyQt.QtCore import QObject, QTimer, pyqtSlot
from qgis.gui import QgsRubberBand

from ..utils.latlon import epsg4326
from ..settings import settings
from vgrid.dggs import qtm
from vgrid.dggs.qtm import QTM_INITIAL_FACETS
from vgrid.utils.io import validate_coordinate, validate_qtm_resolution
from vgrid.utils.geometry import get_qtm_resolution_from_scale_denominator


class QTMGrid(QObject):
    def __init__(self, vgridtools, canvas, iface):
        super(QTMGrid, self).__init__()
        self.canvas = canvas
        self.vgridtools = vgridtools
        self.iface = iface

        self.qtm_marker = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
        self.qtm_marker.setStrokeColor(settings.qtmColor)
        self.qtm_marker.setWidth(settings.gridWidth)

        self.qtm_enabled = False
        self._extentTimer = QTimer(self)
        self._extentTimer.setSingleShot(True)
        self._extentTimer.setInterval(150)
        self.canvas.extentsChanged.connect(self._onExtentsChanged)
        self._extentTimer.timeout.connect(self._refreshQTMGridOnExtent)
        self.removeMarker()

    def _onExtentsChanged(self):
        self._extentTimer.start()

    def _canvas_bbox_4326(self):
        """Return (min_lon, min_lat, max_lon, max_lat) for the current canvas extent."""
        canvas_extent = self.canvas.extent()
        canvas_crs = QgsProject.instance().crs()
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
        return validate_coordinate(min_lon, min_lat, max_lon, max_lat)

    def _bbox_polygon(self, min_lon, min_lat, max_lon, max_lat):
        return Polygon(
            [
                (min_lon, min_lat),
                (max_lon, min_lat),
                (max_lon, max_lat),
                (min_lon, max_lat),
                (min_lon, min_lat),
            ]
        )

    def _add_cell_geometry(self, facet_geom, canvas_crs):
        geom = QgsGeometry.fromWkt(facet_geom.wkt)
        if epsg4326 != canvas_crs:
            trans_to_canvas = QgsCoordinateTransform(
                epsg4326, canvas_crs, QgsProject.instance()
            )
            geom.transform(trans_to_canvas)
        self.qtm_marker.addGeometry(geom, None)

    def qtm_grid(self):
        """Draw QTM cells for the canvas extent (aligned with vgrid qtm_grid_within_bbox)."""
        try:
            self.removeMarker()
            self.qtm_marker.reset(QgsWkbTypes.PolygonGeometry)
            self.qtm_marker.setStrokeColor(settings.qtmColor)
            self.qtm_marker.setWidth(settings.gridWidth)

            canvas_crs = QgsProject.instance().crs()
            scale = self.canvas.scale()
            resolution = validate_qtm_resolution(
                get_qtm_resolution_from_scale_denominator(
                    scale, relative_depth=8, mm_per_pixel=0.28
                )
            )
            if settings.zoomLevel:
                zoom = 29.1402 - log2(scale)
                self.iface.mainWindow().statusBar().showMessage(
                    f"Zoom Level: {zoom:.2f} | QTM resolution: {resolution}"
                )

            min_lon, min_lat, max_lon, max_lat = self._canvas_bbox_4326()
            bbox_poly = self._bbox_polygon(min_lon, min_lat, max_lon, max_lat)

            level_facets = {}
            qtm_ids = {}

            for lvl in range(resolution):
                level_facets[lvl] = []
                qtm_ids[lvl] = []

                if lvl == 0:
                    for i, facet in enumerate(QTM_INITIAL_FACETS):
                        qtm_ids[0].append(str(i + 1))
                        facet_geom = qtm.constructGeometry(facet)
                        level_facets[0].append(facet)
                        if facet_geom.intersects(bbox_poly) and resolution == 1:
                            self._add_cell_geometry(facet_geom, canvas_crs)
                else:
                    for i, parent_facet in enumerate(level_facets[lvl - 1]):
                        for j, subfacet in enumerate(qtm.divideFacet(parent_facet)):
                            subfacet_geom = qtm.constructGeometry(subfacet)
                            if subfacet_geom.intersects(bbox_poly):
                                new_id = qtm_ids[lvl - 1][i] + str(j)
                                qtm_ids[lvl].append(new_id)
                                level_facets[lvl].append(subfacet)
                                if lvl == resolution - 1:
                                    self._add_cell_geometry(subfacet_geom, canvas_crs)

            self.canvas.refresh()

        except Exception:
            return

    def enable_qtm(self, enabled: bool):
        self.qtm_enabled = bool(enabled)
        if not self.qtm_enabled:
            self.removeMarker()

    def _refreshQTMGridOnExtent(self):
        if self.qtm_enabled:
            self.qtm_grid()

    @pyqtSlot()
    def removeMarker(self):
        self.qtm_marker.reset(QgsWkbTypes.PolygonGeometry)

    def cleanup(self):
        try:
            self._extentTimer.stop()
            try:
                self._extentTimer.timeout.disconnect(self._refreshQTMGridOnExtent)
            except Exception:
                pass
            try:
                self.canvas.extentsChanged.disconnect(self._onExtentsChanged)
            except Exception:
                pass
        except Exception:
            pass

        try:
            self.qtm_marker.reset(QgsWkbTypes.PolygonGeometry)
            self.qtm_marker.deleteLater()
        except Exception:
            pass
