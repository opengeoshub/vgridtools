
from shapely.geometry import Polygon, box
from qgis.core import Qgis, QgsWkbTypes,QgsCoordinateTransform,QgsGeometry, QgsPoint, QgsPointXY, QgsProject, QgsRectangle
from qgis.PyQt.QtCore import QObject, QTimer
from qgis.PyQt.QtGui import QColor
from qgis.gui import QgsRubberBand
from qgis.PyQt.QtCore import pyqtSlot
from vgrid.utils.geometry import fix_h3_antimeridian_cells
import h3
import traceback
from .utils import tr
from .utils.latlon import epsg4326

class DGGSGen(QObject):
    def __init__(self, vgridtools, canvas, iface):
        super(DGGSGen, self).__init__()
        self.canvas = canvas
        self.vgridtools = vgridtools
        self.iface = iface
        self.polygon_marker = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
        self.polygon_marker.setStrokeColor(QColor('#FF0000'))
        self.polygon_marker.setWidth(2)

        # H3 auto-update toggle and debounced extent listener
        self.h3_enabled = False
        self._extentTimer = QTimer(self)
        self._extentTimer.setSingleShot(True)
        self._extentTimer.setInterval(150)
        self.canvas.extentsChanged.connect(lambda: self._extentTimer.start())
        self._extentTimer.timeout.connect(self._refreshH3GridOnExtent)

    def H3Grid(self):
        try:
            # Clear previous grid before drawing a new one
            self.polygon_marker.reset(QgsWkbTypes.PolygonGeometry)

            canvas_extent = self.canvas.extent()
            scale = self.canvas.scale()
            resolution = self._get_h3_resolution(scale)
            canvas_crs = self.canvas.mapSettings().destinationCrs()
            # Convert QgsRectangle to Shapely polygon for h3.geo_to_cells
            extent_bbox = box(
                canvas_extent.xMinimum(),
                canvas_extent.yMinimum(),
                canvas_extent.xMaximum(),
                canvas_extent.yMaximum(),
            )
            from shapely.ops import transform as shp_transform
            from pyproj import Transformer
            if epsg4326 != canvas_crs:
                transformer = Transformer.from_crs(epsg4326, canvas_crs, always_xy=True)
                extent_bbox = shp_transform(lambda x, y, z=None: transformer.transform(x, y), extent_bbox)

            bbox_cells = h3.geo_to_cells(extent_bbox, resolution)
            for bbox_cell in bbox_cells:
                hex_boundary = h3.cell_to_boundary(bbox_cell)
                filtered_boundary = fix_h3_antimeridian_cells(hex_boundary)
                reversed_boundary = [(lon, lat) for lat, lon in filtered_boundary]
                cell_polygon = Polygon(reversed_boundary)
                if not cell_polygon.intersects(extent_bbox):
                    continue
                cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)
                
                if epsg4326 != canvas_crs:
                    trans = QgsCoordinateTransform(epsg4326,canvas_crs,QgsProject.instance())
                    cell_geometry.transform(trans)
                    
                self.polygon_marker.addGeometry(cell_geometry, None)

            self.canvas.refresh()
        except Exception as e:
            traceback.print_exc()
            self.iface.messageBar().pushMessage("", tr("Invalid Coordinate: {}").format(str(e)), level=Qgis.Warning, duration=2)
            return                  


    def enable_h3(self, enabled: bool):
        self.h3_enabled = bool(enabled)
        if not self.h3_enabled:
            self.removeMarker()

    def _refreshH3GridOnExtent(self):
        if self.h3_enabled:
            self.H3Grid()

    def _get_h3_resolution(self, scale):
        # Convert map scale to approximate web-mercator-like zoom
        # zoom ~= 29.1402 - log2(scale)
        from math import log2
        zoom = 29.1402 - log2(scale)
        if (zoom <= 3.0): return 0
        if (zoom <= 4.4): return 1
        if (zoom <= 5.7): return 2
        if (zoom <= 7.1): return 3
        if (zoom <= 8.4): return 4
        if (zoom <= 9.8): return 5
        if (zoom <= 11.4): return 6
        if (zoom <= 12.7): return 7
        if (zoom <= 14.1): return 8
        if (zoom <= 15.5): return 9
        if (zoom <= 16.8): return 10
        if (zoom <= 18.2): return 11
        if (zoom <= 19.5): return 12
        if (zoom <= 21.1): return 13
        if (zoom <= 21.9): return 14
        return 15

    @pyqtSlot()
    def removeMarker(self):
        self.polygon_marker.reset(QgsWkbTypes.PolygonGeometry)
   