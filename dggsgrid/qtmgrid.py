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

# QTM imports
from vgrid.dggs import qtm


class QTGrid(QObject):
    def __init__(self, vgridtools, canvas, iface):
        super(QTGrid, self).__init__()
        self.canvas = canvas
        self.vgridtools = vgridtools
        self.iface = iface

        self.qtm_marker = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
        self.qtm_marker.setStrokeColor(settings.qtmColor)
        self.qtm_marker.setWidth(settings.gridWidth)

        # QTM auto-update toggle and debounced extent listener
        self.qtm_enabled = False
        self._extentTimer = QTimer(self)
        self._extentTimer.setSingleShot(True)
        self._extentTimer.setInterval(150)
        self.canvas.extentsChanged.connect(self._onExtentsChanged)
        self._extentTimer.timeout.connect(self._refreshQTMGridOnExtent)
        self.removeMarker()

    def _onExtentsChanged(self):
        self._extentTimer.start()

    def qtm_grid(self):
        try:
            # Clear previous grid before drawing a new one
            self.removeMarker()
            self.qtm_marker.reset(QgsWkbTypes.PolygonGeometry)

            canvas_extent = self.canvas.extent()
            scale = self.canvas.scale()
            resolution = self._get_qtm_resolution(scale)
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

            # Create extent bbox for intersection testing
            extent_bbox = box(min_lon, min_lat, max_lon, max_lat)

            # QTM base facets (8 triangular faces)
            p90_n180, p90_n90, p90_p0, p90_p90, p90_p180 = (
                (90.0, -180.0),
                (90.0, -90.0),
                (90.0, 0.0),
                (90.0, 90.0),
                (90.0, 180.0),
            )
            p0_n180, p0_n90, p0_p0, p0_p90, p0_p180 = (
                (0.0, -180.0),
                (0.0, -90.0),
                (0.0, 0.0),
                (0.0, 90.0),
                (0.0, 180.0),
            )
            n90_n180, n90_n90, n90_p0, n90_p90, n90_p180 = (
                (-90.0, -180.0),
                (-90.0, -90.0),
                (-90.0, 0.0),
                (-90.0, 90.0),
                (-90.0, 180.0),
            )

            initial_facets = [
                [p0_n180, p0_n90, p90_n90, p90_n180, p0_n180, True],
                [p0_n90, p0_p0, p90_p0, p90_n90, p0_n90, True],
                [p0_p0, p0_p90, p90_p90, p90_p0, p0_p0, True],
                [p0_p90, p0_p180, p90_p180, p90_p90, p0_p90, True],
                [n90_n180, n90_n90, p0_n90, p0_n180, n90_n180, False],
                [n90_n90, n90_p0, p0_p0, p0_n90, n90_n90, False],
                [n90_p0, n90_p90, p0_p90, p0_p0, n90_p0, False],
                [n90_p90, n90_p180, p0_p180, p0_p90, n90_p90, False],
            ]

            # Generate QTM cells
            QTMID = {}
            levelFacets = {}
            
            for lvl in range(resolution):
                levelFacets[lvl] = []
                QTMID[lvl] = []

                if lvl == 0:
                    for i, facet in enumerate(initial_facets):
                        facet_geom = qtm.constructGeometry(facet)
                        QTMID[0].append(str(i + 1))
                        levelFacets[0].append(facet)
                        
                        # Check if facet intersects with extent
                        if facet_geom.intersects(extent_bbox):
                            geom = QgsGeometry.fromWkt(facet_geom.wkt)
                            if epsg4326 != canvas_crs:
                                trans = QgsCoordinateTransform(
                                    epsg4326, canvas_crs, QgsProject.instance()
                                )
                                geom.transform(trans)
                            self.qtm_marker.addGeometry(geom, None)
                else:
                    for i, pf in enumerate(levelFacets[lvl - 1]):
                        subdivided_facets = qtm.divideFacet(pf)
                        for j, subfacet in enumerate(subdivided_facets):
                            subfacet_geom = qtm.constructGeometry(subfacet)
                            new_id = QTMID[lvl - 1][i] + str(j)
                            QTMID[lvl].append(new_id)
                            levelFacets[lvl].append(subfacet)
                            
                            # Check if subfacet intersects with extent
                            if subfacet_geom.intersects(extent_bbox):
                                geom = QgsGeometry.fromWkt(subfacet_geom.wkt)
                                if epsg4326 != canvas_crs:
                                    trans = QgsCoordinateTransform(
                                        epsg4326, canvas_crs, QgsProject.instance()
                                    )
                                    geom.transform(trans)
                                self.qtm_marker.addGeometry(geom, None)

            self.canvas.refresh()

        except Exception as e:
            print(e)
            return

    def enable_qtm(self, enabled: bool):
        self.qtm_enabled = bool(enabled)
        if not self.qtm_enabled:
            self.removeMarker()

    def _refreshQTMGridOnExtent(self):
        if self.qtm_enabled:
            self.qtm_grid()

    def _get_qtm_resolution(self, scale):
        # Map scale to zoom, then to QTM resolution
        from math import log2, floor

        zoom = 29.1402 - log2(scale)
        min_res, max_res, _ = settings.getResolution("QTM")

        res = max(min_res, int(floor(zoom)))

        # Get QTM resolution bounds from settings
        if res > max_res:
            return max_res
        return res

    @pyqtSlot()
    def removeMarker(self):
        self.qtm_marker.reset(QgsWkbTypes.PolygonGeometry)

    def cleanup(self):
        # Disconnect signals and delete rubber band
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
