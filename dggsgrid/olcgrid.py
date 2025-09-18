from shapely.geometry import box, Polygon
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

from ..utils.latlon import epsg4326
from ..settings import settings
from math import log2
# OLC imports
from vgrid.generator.olcgrid import olc_grid as olc_grid_vgrid, olc_refine_cell
from vgrid.utils.io import validate_coordinate

class OLCGrid(QObject):
    def __init__(self, vgridtools, canvas, iface):
        super(OLCGrid, self).__init__()
        self.canvas = canvas
        self.vgridtools = vgridtools
        self.iface = iface

        self.olc_marker = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
        self.olc_marker.setStrokeColor(settings.olcColor)
        self.olc_marker.setWidth(settings.gridWidth)

        # OLC auto-update toggle and debounced extent listener
        self.olc_enabled = False
        self._extentTimer = QTimer(self)
        self._extentTimer.setSingleShot(True)
        self._extentTimer.setInterval(150)
        self.canvas.extentsChanged.connect(self._onExtentsChanged)
        self._extentTimer.timeout.connect(self._refreshOLCGridOnExtent)
        self.removeMarker()

    def olc_grid(self):
        try:
            # Clear previous grid before drawing a new one
            self.removeMarker()
            self.olc_marker.reset(QgsWkbTypes.PolygonGeometry)
            self.olc_marker.setStrokeColor(settings.olcColor)
            self.olc_marker.setWidth(settings.gridWidth)

            canvas_extent = self.canvas.extent()
            canvas_crs = QgsProject.instance().crs()        

            scale = self.canvas.scale()
            resolution = self._get_olc_resolution(scale)
            if settings.zoomLevel:
                zoom = 29.1402 - log2(scale)
                self.iface.mainWindow().statusBar().showMessage(
                    f"Zoom Level: {zoom:.2f} | OLC resolution:{resolution}"
                )   

            base_resolution = 2
            base_gdf = olc_grid_vgrid(base_resolution, verbose=False)
            if resolution == 2:
                for idx, base_cell in base_gdf.iterrows():
                    cell_polygon = base_cell["geometry"]
                    geom = QgsGeometry.fromWkt(cell_polygon.wkt)
                    if epsg4326 != canvas_crs:
                        trans_to_canvas = QgsCoordinateTransform(
                            epsg4326, canvas_crs, QgsProject.instance()
                        )
                        geom.transform(trans_to_canvas)
                    self.olc_marker.addGeometry(geom, None)     
            else:
                min_lon, min_lat, max_lon, max_lat = (
                    canvas_extent.xMinimum(),
                    canvas_extent.yMinimum(),
                    canvas_extent.xMaximum(),
                    canvas_extent.yMaximum(),
                )
                if epsg4326 != canvas_crs:
                    trans_to_4326 = QgsCoordinateTransform(canvas_crs, epsg4326, QgsProject.instance())
                    transformed_extent = trans_to_4326.transform(canvas_extent)              
                    min_lon, min_lat, max_lon, max_lat = (
                        transformed_extent.xMinimum(),
                        transformed_extent.yMinimum(),
                        transformed_extent.xMaximum(),
                        transformed_extent.yMaximum(),
                    )       

                min_lat, min_lon, max_lat, max_lon = validate_coordinate(min_lat, min_lon, max_lat, max_lon)  
                extent_bbox = box(min_lon, min_lat, max_lon, max_lat)
                # Generate grid within bounding box using seed cell refinement
                seed_cells = []
                for idx, base_cell in base_gdf.iterrows():
                    base_cell_poly = base_cell["geometry"]
                    if extent_bbox.intersects(base_cell_poly):
                        seed_cells.append(base_cell)

                refined_records = []

                # Step 3: Iterate over seed cells and refine to the output resolution
                for seed_cell in seed_cells:
                    seed_cell_poly = seed_cell["geometry"]

                    if seed_cell_poly.contains(extent_bbox) and resolution == base_resolution:
                        # Append the seed cell directly if fully contained and resolution matches
                        refined_records.append(seed_cell)
                    else:
                        # Refine the seed cell to the output resolution and add it to the output
                        refined_records.extend(
                            olc_refine_cell(
                                seed_cell_poly.bounds, base_resolution, resolution, extent_bbox
                            )
                        )

                # Filter to target resolution and remove duplicates
                final_records = [
                    record for record in refined_records 
                    if record["resolution"] == resolution
                ]

                # Remove duplicates based on OLC ID
                seen_olc_ids = set()
                unique_records = []
                for record in final_records:
                    olc_id = record["olc"]
                    if olc_id not in seen_olc_ids:
                        unique_records.append(record)
                        seen_olc_ids.add(olc_id)
                
                for record in unique_records:
                    cell_polygon = record["geometry"]
                    geom = QgsGeometry.fromWkt(cell_polygon.wkt)
                    if epsg4326 != canvas_crs:
                        trans_to_canvas = QgsCoordinateTransform(
                            epsg4326, canvas_crs, QgsProject.instance()
                        )
                        geom.transform(trans_to_canvas)
                    self.olc_marker.addGeometry(geom, None)
            self.canvas.refresh()
              
        except Exception as e:
            return


    def enable_olc(self, enabled: bool):
        self.olc_enabled = bool(enabled)
        if not self.olc_enabled:
            self.removeMarker()

    def _onExtentsChanged(self):
        self._extentTimer.start()
   
    def _refreshOLCGridOnExtent(self):
        if self.olc_enabled:
            self.olc_grid()

    def _get_olc_resolution(self, scale):
        # Map scale to zoom, then to OLC resolution
        zoom = 29.1402 - log2(scale)
        if zoom <= 6:
            return 2
        elif zoom <= 10:
            return 4
        elif zoom <= 14:
            return 6
        elif zoom <= 18:
            return 8
        elif zoom <= 22:
            return 10
        elif zoom <= 26:
            return 11
        elif zoom <= 30:
            return 12
        return 13

    @pyqtSlot()
    def removeMarker(self):
        self.olc_marker.reset(QgsWkbTypes.PolygonGeometry)

    def cleanup(self):
        # Disconnect signals and delete rubber band
        try:
            self._extentTimer.stop()
            try:
                self._extentTimer.timeout.disconnect(self._refreshOLCGridOnExtent)
            except Exception:
                pass
            try:
                self.canvas.extentsChanged.disconnect(self._onExtentsChanged)
            except Exception:
                pass
        except Exception:
            pass

        try:
            self.olc_marker.reset(QgsWkbTypes.PolygonGeometry)
            self.olc_marker.deleteLater()
        except Exception:
            pass
