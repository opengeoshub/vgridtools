# -*- coding: utf-8 -*-
"""Canvas overlay grids for DGGRID types (same pattern as DGGAL Viz)."""

from math import floor, log2

from qgis.core import (
    QgsCoordinateTransform,
    QgsGeometry,
    QgsProject,
    QgsWkbTypes,
)
from qgis.gui import QgsRubberBand
from qgis.PyQt.QtCore import QObject, QTimer, pyqtSlot

from vgrid.utils.constants import DGGRID_TYPES
from vgrid.utils.io import validate_coordinate

from ..settings import settings
from ..utils.dggrid_instance import (
    DGGRID_TYPES_NO_ANTIMERIDIAN,
    build_dggrid_options,
    generate_grid_qgis,
    get_plugin_dggrid_instance,
)
from ..utils.latlon import epsg4326


class DGGRIDGrid(QObject):
    def __init__(self, vgridtools, canvas, iface, dggs_type: str):
        super().__init__()
        self.vgridtools = vgridtools
        self.canvas = canvas
        self.iface = iface
        self.dggs_type = dggs_type

        self.dggrid_marker = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
        self.dggrid_marker.setStrokeColor(self._grid_color())
        self.dggrid_marker.setWidth(settings.gridWidth)

        self.dggrid_enabled = False
        self._extentTimer = QTimer(self)
        self._extentTimer.setSingleShot(True)
        self._extentTimer.setInterval(150)
        self.canvas.extentsChanged.connect(self._onExtentsChanged)
        self._extentTimer.timeout.connect(self._refreshDGGRIDGridOnExtent)
        self.removeMarker()

    def _grid_color(self):
        return getattr(
            settings, f"dggrid_{self.dggs_type.lower()}Color", settings.isea3hColor
        )

    def _onExtentsChanged(self):
        self._extentTimer.start()

    def _resolution_from_scale(self, scale: float) -> int:
        cfg = DGGRID_TYPES[self.dggs_type]
        zoom = 29.1402 - log2(scale)
        res = int(floor(zoom))
        return min(cfg["max_res"], max(cfg["min_res"], res))

    def dggrid_grid(self):
        try:
            self.removeMarker()
            self.dggrid_marker.reset(QgsWkbTypes.PolygonGeometry)
            self.dggrid_marker.setStrokeColor(self._grid_color())
            self.dggrid_marker.setWidth(settings.gridWidth)

            canvas_extent = self.canvas.extent()
            canvas_crs = QgsProject.instance().crs()
            scale = self.canvas.scale()
            resolution = self._resolution_from_scale(scale)

            if settings.zoomLevel:
                zoom = 29.1402 - log2(scale)
                self.iface.mainWindow().statusBar().showMessage(
                    f"Zoom Level: {zoom:.2f} | DGGRID {self.dggs_type} resolution: {resolution}"
                )

            if resolution <= 3:
                min_lon, min_lat, max_lon, max_lat = -180, -90, 180, 90
                bbox = [min_lon, min_lat, max_lon, max_lat]
            else:
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
                min_lat, min_lon, max_lat, max_lon = validate_coordinate(
                    min_lat, min_lon, max_lat, max_lon
                )
                bbox = [min_lon, min_lat, max_lon, max_lat]

            split_antimeridian = (
                settings.splitAntimeridian
                and self.dggs_type not in DGGRID_TYPES_NO_ANTIMERIDIAN
            )
            densification = settings.dggridDensificationSpinBox
            options = build_dggrid_options(densification)
            gdf = generate_grid_qgis(
                get_plugin_dggrid_instance(),
                self.dggs_type,
                resolution,
                bbox,
                output_address_type="SEQNUM",
                split_antimeridian=split_antimeridian,
                aggregate=False,
                options=options,
            )
            if gdf is None or gdf.empty:
                return

            trans_to_canvas = None
            if epsg4326 != canvas_crs:
                trans_to_canvas = QgsCoordinateTransform(
                    epsg4326, canvas_crs, QgsProject.instance()
                )

            for geom in gdf.geometry:
                if geom is None or geom.is_empty:
                    continue
                try:
                    cell_geom = QgsGeometry.fromWkt(geom.wkt)
                    if trans_to_canvas is not None:
                        cell_geom.transform(trans_to_canvas)
                    self.dggrid_marker.addGeometry(cell_geom, None)
                except Exception:
                    continue

            self.canvas.refresh()
        except Exception:
            return

    def enable_dggrid(self, enabled: bool):
        self.dggrid_enabled = bool(enabled)
        if not self.dggrid_enabled:
            self.removeMarker()

    def _refreshDGGRIDGridOnExtent(self):
        if self.dggrid_enabled:
            self.dggrid_grid()

    @pyqtSlot()
    def removeMarker(self):
        self.dggrid_marker.reset(QgsWkbTypes.PolygonGeometry)

    def cleanup(self):
        try:
            self._extentTimer.stop()
            try:
                self._extentTimer.timeout.disconnect(self._refreshDGGRIDGridOnExtent)
            except Exception:
                pass
            try:
                self.canvas.extentsChanged.disconnect(self._onExtentsChanged)
            except Exception:
                pass
        except Exception:
            pass
        try:
            self.dggrid_marker.reset(QgsWkbTypes.PolygonGeometry)
            self.dggrid_marker.deleteLater()
        except Exception:
            pass
