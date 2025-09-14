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

import traceback

from ..utils import tr
from ..utils.latlon import epsg4326
from ..settings import settings

# OLC imports
from vgrid.dggs import olc
from vgrid.generator.olcgrid import olc_refine_cell
from vgrid.utils.geometry import graticule_dggs_to_feature


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

    def _onExtentsChanged(self):
        self._extentTimer.start()

    def olc_grid(self):
        try:
            # Clear previous grid before drawing a new one
            self.removeMarker()
            self.olc_marker.reset(QgsWkbTypes.PolygonGeometry)

            canvas_extent = self.canvas.extent()
            scale = self.canvas.scale()
            resolution = self._get_olc_resolution(scale)
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

            # Generate OLC cells
            if extent_bbox:
                # Generate grid within bounding box
                # Step 1: Generate base cells at the lowest resolution (e.g., resolution 2)
                base_resolution = 2
                base_cells = self._generate_olc_grid(base_resolution)

                # Step 2: Identify seed cells that intersect with the bounding box
                seed_cells = []
                for base_cell in base_cells["features"]:
                    base_cell_poly = Polygon(base_cell["geometry"]["coordinates"][0])
                    if extent_bbox.intersects(base_cell_poly):
                        seed_cells.append(base_cell)

                refined_features = []

                # Step 3: Iterate over seed cells and refine to the output resolution
                for seed_cell in seed_cells:
                    seed_cell_poly = Polygon(seed_cell["geometry"]["coordinates"][0])

                    if (
                        seed_cell_poly.contains(extent_bbox)
                        and resolution == base_resolution
                    ):
                        # Append the seed cell directly if fully contained and resolution matches
                        refined_features.append(seed_cell)
                    else:
                        # Refine the seed cell to the output resolution and add it to the output
                        refined_features.extend(
                            olc_refine_cell(
                                seed_cell_poly.bounds,
                                base_resolution,
                                resolution,
                                extent_bbox,
                            )
                        )

                resolution_features = [
                    feature
                    for feature in refined_features
                    if feature["resolution"] == resolution
                ]

                final_features = []
                seen_olc_ids = set()  # Reset the set for final feature filtering

                for feature in resolution_features:
                    olc_id = feature["olc"]
                    if (
                        olc_id not in seen_olc_ids
                    ):  # Check if OLC code is already in the set
                        final_features.append(feature)
                        seen_olc_ids.add(olc_id)

                # Draw cells
                for feature in final_features:
                    cell_polygon = feature["geometry"]
                    if cell_polygon.intersects(extent_bbox):
                        geom = QgsGeometry.fromWkt(cell_polygon.wkt)
                        if epsg4326 != canvas_crs:
                            trans = QgsCoordinateTransform(
                                epsg4326, canvas_crs, QgsProject.instance()
                            )
                            geom.transform(trans)
                        self.olc_marker.addGeometry(geom, None)
            else:
                # Generate global grid when no extent is provided
                global_cells = self._generate_olc_grid(resolution)

                # Draw cells
                for feature in global_cells["features"]:
                    cell_polygon = Polygon(feature["geometry"]["coordinates"][0])
                    if cell_polygon.intersects(extent_bbox):
                        geom = QgsGeometry.fromWkt(cell_polygon.wkt)
                        if epsg4326 != canvas_crs:
                            trans = QgsCoordinateTransform(
                                epsg4326, canvas_crs, QgsProject.instance()
                            )
                            geom.transform(trans)
                        self.olc_marker.addGeometry(geom, None)

            self.canvas.refresh()

        except Exception as e:
            print(e)
            return

    def _generate_olc_grid(self, resolution):
        """
        Generate a global grid of Open Location Codes (Plus Codes) at the specified precision
        as a GeoJSON-like feature collection.
        """
        # Define the boundaries of the world
        sw_lat, sw_lng = -90, -180
        ne_lat, ne_lng = 90, 180

        # Get the precision step size
        area = olc.decode(olc.encode(sw_lat, sw_lng, resolution))
        lat_step = area.latitudeHi - area.latitudeLo
        lng_step = area.longitudeHi - area.longitudeLo

        olc_features = []

        lat = sw_lat
        while lat < ne_lat:
            lng = sw_lng
            while lng < ne_lng:
                # Generate the Plus Code for the center of the cell
                center_lat = lat + lat_step / 2
                center_lon = lng + lng_step / 2
                olc_id = olc.encode(center_lat, center_lon, resolution)
                cell_polygon = Polygon(
                    [
                        [lng, lat],  # SW
                        [lng, lat + lat_step],  # NW
                        [lng + lng_step, lat + lat_step],  # NE
                        [lng + lng_step, lat],  # SE
                        [lng, lat],  # Close the polygon
                    ]
                )
                olc_feature = graticule_dggs_to_feature(
                    "olc", olc_id, resolution, cell_polygon
                )
                olc_features.append(olc_feature)
                lng += lng_step
            lat += lat_step

        # Return the feature collection
        return {"type": "FeatureCollection", "features": olc_features}

    def enable_olc(self, enabled: bool):
        self.olc_enabled = bool(enabled)
        if not self.olc_enabled:
            self.removeMarker()

    def _refreshOLCGridOnExtent(self):
        if self.olc_enabled:
            self.olc_grid()

    def _get_olc_resolution(self, scale):
        # Map scale to zoom, then to OLC resolution
        from math import log2, floor

        zoom = 29.1402 - log2(scale)
        min_res, max_res, _ = settings.getResolution("OLC")
        res = max(min_res, int(floor(zoom / 1.7)))

        # Get OLC resolution bounds from settings
        if res > max_res:
            return max_res
        
        # OLC only supports specific resolutions: [2, 4, 6, 8, 10, 11, 12, 13, 14, 15]
        valid_resolutions = [2, 4, 6, 8, 10, 11, 12, 13, 14, 15]
        if res not in valid_resolutions:
            # Find the closest valid resolution
            closest_res = min(valid_resolutions, key=lambda x: abs(x - res))
            return closest_res
        
        return res

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
