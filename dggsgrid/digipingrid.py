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

from math import log2
from ..utils.latlon import epsg4326
from ..settings import settings
from vgrid.utils.io import validate_coordinate
from vgrid.utils.io import validate_digipin_coordinate

# DIGIPIN imports
from vgrid.conversion.latlon2dggs import latlon2digipin
from vgrid.conversion.dggs2geo.digipin2geo import digipin2geo
from vgrid.utils.io import validate_digipin_coordinate



class DIGIPINGrid(QObject):
    def __init__(self, vgridtools, canvas, iface):
        super(DIGIPINGrid, self).__init__()
        self.canvas = canvas
        self.vgridtools = vgridtools
        self.iface = iface

        self.digipin_marker = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
        self.digipin_marker.setStrokeColor(settings.digipinColor if hasattr(settings, 'digipinColor') else settings.digipinColor)
        self.digipin_marker.setWidth(settings.gridWidth)

        # DIGIPIN auto-update toggle and debounced extent listener
        self.digipin_enabled = False
        self._extentTimer = QTimer(self)
        self._extentTimer.setSingleShot(True)
        self._extentTimer.setInterval(150)
        self.canvas.extentsChanged.connect(self._onExtentsChanged)
        self._extentTimer.timeout.connect(self._refreshDigipinGridOnExtent)
        self.removeMarker()

    def _onExtentsChanged(self):
        self._extentTimer.start()

    def digipin_grid(self):
        try:
            # Clear previous grid before drawing a new one
            self.removeMarker()
            self.digipin_marker.reset(QgsWkbTypes.PolygonGeometry)
            self.digipin_marker.setStrokeColor(
                settings.digipinColor if hasattr(settings, 'digipinColor') else settings.digipinColor
            )
            self.digipin_marker.setWidth(settings.gridWidth)

            canvas_extent = self.canvas.extent()
            canvas_crs = QgsProject.instance().crs()

            scale = self.canvas.scale()
            resolution = self._get_digipin_resolution(scale)
            zoom = 29.1402 - log2(scale)
            if settings.zoomLevel:
                self.iface.mainWindow().statusBar().showMessage(
                    f"Zoom Level: {zoom:.2f} | DIGIPIN resolution:{resolution}"
                )

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

            min_lat, min_lon, max_lat, max_lon = validate_digipin_coordinate(
                min_lat, min_lon, max_lat, max_lon
            )

            # Calculate sampling density based on resolution
            # Each level divides the cell by 4 (2x2 grid)
            base_width = 9.0  # degrees at resolution 1
            factor = 0.25 ** (resolution - 1)  # each level divides by 4
            sample_width = base_width * factor

            seen_cells = set()

            # Sample points across the bounding box
            lon = min_lon
            while lon <= max_lon:
                lat = min_lat
                while lat <= max_lat:
                    try:
                        # Get DIGIPIN code for this point at the specified resolution
                        digipin_code = latlon2digipin(lat, lon, resolution)

                        if digipin_code == 'Out of Bound':
                            lat += sample_width
                            continue

                        if digipin_code in seen_cells:
                            lat += sample_width
                            continue

                        seen_cells.add(digipin_code)

                        # Get the bounds for this DIGIPIN cell
                        cell_polygon = digipin2geo(digipin_code)

                        if isinstance(cell_polygon, str):  # Error like 'Invalid DIGIPIN'
                            lat += sample_width
                            continue

                        # Convert to QgsGeometry and add to rubber band
                        cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)
                        if epsg4326 != canvas_crs:
                            trans = QgsCoordinateTransform(
                                epsg4326, canvas_crs, QgsProject.instance()
                            )
                            cell_geometry.transform(trans)
                        self.digipin_marker.addGeometry(cell_geometry, None)

                    except Exception:
                        # Skip cells with errors
                        pass

                    lat += sample_width
                lon += sample_width

            self.canvas.refresh()

        except Exception:
            return

    def enable_digipin(self, enabled: bool):
        self.digipin_enabled = bool(enabled)
        if not self.digipin_enabled:
            self.removeMarker()

    def _refreshDigipinGridOnExtent(self):
        if self.digipin_enabled:
            self.digipin_grid()

    def _get_digipin_resolution(self, scale):
        # Map scale to zoom, then to DIGIPIN resolution
        zoom = 29.1402 - log2(scale)        
        # Map zoom levels to DIGIPIN precision (1-10 characters)
        if zoom < 4:
            return 1
        if zoom < 6:
            return 2
        if zoom < 8:
            return 3
        if zoom < 10:
            return 4
        if zoom < 12:
            return 5
        if zoom < 14:
            return 6
        if zoom < 16:
            return 7
        if zoom < 18:
            return 8
        if zoom < 20:
            return 9
        return 10

    @pyqtSlot()
    def removeMarker(self):
        self.digipin_marker.reset(QgsWkbTypes.PolygonGeometry)

    def cleanup(self):
        # Disconnect signals and delete rubber band
        try:
            self._extentTimer.stop()
            try:
                self._extentTimer.timeout.disconnect(self._refreshDigipinGridOnExtent)
            except Exception:
                pass
            try:
                self.canvas.extentsChanged.disconnect(self._onExtentsChanged)
            except Exception:
                pass
        except Exception:
            pass

        try:
            self.digipin_marker.reset(QgsWkbTypes.PolygonGeometry)
            self.digipin_marker.deleteLater()
        except Exception:
            pass

