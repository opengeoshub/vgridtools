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
from vgrid.utils.io import validate_coordinate
from vgrid.utils.antimeridian import fix_polygon

# DGGAL imports
from dggal import *
from vgrid.utils.geometry import dggal_to_geo
from vgrid.utils.constants import DGGAL_TYPES

# Initialize dggal application
app = Application(appGlobals=globals())
pydggal_setup(app)


class DGGALRHEALPixGrid(QObject):
    def __init__(self, vgridtools, canvas, iface):
        super(DGGALRHEALPixGrid, self).__init__()
        self.canvas = canvas
        self.vgridtools = vgridtools
        self.iface = iface

        self.dggal_marker = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
        self.dggal_marker.setStrokeColor(settings.dggal_rhealpixColor)
        self.dggal_marker.setWidth(settings.gridWidth)

        # DGGAL auto-update toggle and debounced extent listener
        self.dggal_enabled = False
        self._extentTimer = QTimer(self)
        self._extentTimer.setSingleShot(True)
        self._extentTimer.setInterval(150)
        self.canvas.extentsChanged.connect(self._onExtentsChanged)
        self._extentTimer.timeout.connect(self._refreshDGGALGridOnExtent)
        self.removeMarker()

        # Initialize DGGAL instance for rhealpix type
        self.dggs_type = "rhealpix"
        dggs_class_name = DGGAL_TYPES[self.dggs_type]["class_name"]
        self.dggrs = globals()[dggs_class_name]()

    def _onExtentsChanged(self):
        self._extentTimer.start()

    def dggal_grid(self):
        try:
            # Clear previous grid before drawing a new one
            self.removeMarker()
            self.dggal_marker.reset(QgsWkbTypes.PolygonGeometry)
            self.dggal_marker.setStrokeColor(settings.dggal_rhealpixColor)
            self.dggal_marker.setWidth(settings.gridWidth)

            canvas_extent = self.canvas.extent()
            canvas_crs = QgsProject.instance().crs()

            scale = self.canvas.scale()
            resolution = self._get_dggal_resolution(scale)
            if settings.zoomLevel:
                zoom = 29.1402 - log2(scale)
                self.iface.mainWindow().statusBar().showMessage(
                    f"Zoom Level: {zoom:.2f} | DGGAL rHEALPix resolution:{resolution}"
                )

            if resolution <= 2:
                min_lon, min_lat, max_lon, max_lat = -180, -90, 180, 90
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
            # Define bbox in canvas CRS
            min_lat, min_lon, max_lat, max_lon = validate_coordinate(
                min_lat, min_lon, max_lat, max_lon
            )
            ll = GeoPoint(min_lat, min_lon)
            ur = GeoPoint(max_lat, max_lon)
            geo_extent = GeoExtent(ll, ur)

            # Get zones for the current extent and resolution
            zones = self.dggrs.listZones(resolution, geo_extent)

            # Draw cells
            for zone in zones:
                try:
                    zone_id = self.dggrs.getZoneTextID(zone)
                    # Convert zone to geometry using dggal_to_geo
                    cell_polygon = dggal_to_geo(self.dggs_type, zone_id)
                    if settings.splitAntimeridian:    
                        cell_polygon = fix_polygon(cell_polygon)

                    # Check if cell intersects with the canvas extent
                    # cell_geom = QgsGeometry.fromWkt(cell_polygon.wkt)
                    # if epsg4326 != canvas_crs:
                    #     trans_to_canvas = QgsCoordinateTransform(
                    #         epsg4326, canvas_crs, QgsProject.instance()
                    #     )
                    #     cell_geom.transform(trans_to_canvas)
                    # self.dggal_marker.addGeometry(cell_geom, None)
                    if epsg4326 != canvas_crs:
                        trans_to_canvas = QgsCoordinateTransform(
                            epsg4326, canvas_crs, QgsProject.instance()
                        )
                        cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)
                        cell_geometry.transform(trans_to_canvas)
                    else:
                        cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)
                    self.dggal_marker.addGeometry(cell_geometry, None)

                except Exception:
                    continue

            self.canvas.refresh()

        except Exception:
            return

    def enable_dggal(self, enabled: bool):
        self.dggal_enabled = bool(enabled)
        if not self.dggal_enabled:
            self.removeMarker()

    def _refreshDGGALGridOnExtent(self):
        if self.dggal_enabled:
            self.dggal_grid()

    def _get_dggal_resolution(self, scale):
        # Map scale to zoom, then to DGGAL resolution

        zoom = 29.1402 - log2(scale)
        min_res = DGGAL_TYPES[self.dggs_type]["min_res"]
        max_res = DGGAL_TYPES[self.dggs_type]["max_res"]
        res = max(min_res, int(floor(zoom / 1.7)))

        if res > max_res:
            return max_res
        return res

    @pyqtSlot()
    def removeMarker(self):
        self.dggal_marker.reset(QgsWkbTypes.PolygonGeometry)

    def cleanup(self):
        # Disconnect signals and delete rubber band
        try:
            self._extentTimer.stop()
            try:
                self._extentTimer.timeout.disconnect(self._refreshDGGALGridOnExtent)
            except Exception:
                pass
            try:
                self.canvas.extentsChanged.disconnect(self._onExtentsChanged)
            except Exception:
                pass
        except Exception:
            pass

        try:
            self.dggal_marker.reset(QgsWkbTypes.PolygonGeometry)
            self.dggal_marker.deleteLater()
        except Exception:
            pass
