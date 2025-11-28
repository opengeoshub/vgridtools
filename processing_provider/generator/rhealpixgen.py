# -*- coding: utf-8 -*-
"""
rhealpixgen.py
***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 2 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************
"""
#  Need to be checked and tested

__author__ = "Thang Quach"  # type: ignore
__date__ = "2024-11-20"
__copyright__ = "(L) 2024, Thang Quach"

from qgis.core import (  # type: ignore
    QgsApplication,
    QgsProject,
    QgsCoordinateTransform,
    QgsFeatureSink,
    QgsProcessingLayerPostProcessorInterface,
    QgsProcessingParameterExtent,
    QgsProcessingParameterNumber,
    QgsProcessingException,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterBoolean,
    QgsProcessingAlgorithm,
    QgsFields,
    QgsField,
    QgsFeature,
    QgsGeometry,
    QgsWkbTypes,
    QgsCoordinateReferenceSystem,
    QgsVectorLayer,
    QgsPalLayerSettings,
    QgsVectorLayerSimpleLabeling,
)
from qgis.PyQt.QtGui import QIcon, QColor  # type: ignore
from qgis.PyQt.QtCore import QCoreApplication, Qt
from qgis.utils import iface
from PyQt5.QtCore import QVariant  # type: ignore
import os
import processing  # type: ignore

from collections import deque
from vgrid.utils.geometry import geodesic_dggs_metrics
from vgrid.dggs.rhealpixdggs.dggs import RHEALPixDGGS
from ...utils.imgs import Imgs  # type: ignore
from shapely.geometry import box
from shapely.wkt import loads as wkt_loads
from ...settings import settings  # type: ignore
from vgrid.utils.io import validate_coordinate
from ...utils.latlon import epsg4326
from vgrid.conversion.dggs2geo import rhealpix2geo

rhealpix_dggs = RHEALPixDGGS()  # type: ignore


class rHEALPixGen(QgsProcessingAlgorithm):
    EXTENT = "EXTENT"
    RESOLUTION = "RESOLUTION"
    SHIFT_ANTIMERIDIAN = "SHIFT_ANTIMERIDIAN"
    SPLIT_ANTIMERIDIAN = "SPLIT_ANTIMERIDIAN"
    OUTPUT = "OUTPUT"

    LOC = QgsApplication.locale()[:2]

    def translate(self, string):
        return QCoreApplication.translate("Processing", string)

    def tr(self, *string):
        # Translate to Vietnamese: arg[0] - English (translate), arg[1] - Vietnamese
        if self.LOC == "vi":
            if len(string) == 2:
                return string[1]
            else:
                return self.translate(string[0])
        else:
            return self.translate(string[0])

    def createInstance(self):
        return rHEALPixGen()

    def name(self):
        return "rhealpix_gen"

    def icon(self):
        return QIcon(
            os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "../images/generator/grid_rhealpix.svg",
            )
        )

    def displayName(self):
        return self.tr("rHEALPix", "rHEALPix")

    def group(self):
        return self.tr("Generator", "Generator")

    def groupId(self):
        return "generator"

    def tags(self):
        return self.tr("DGGS, rHEALPix, generator").split(",")

    txt_en = "rHEALPix DGGS Generator"
    txt_vi = "rHEALPix DGGS Generator"
    figure = "../images/tutorial/grid_rhealpix.png"

    def shortHelpString(self):
        social_BW = Imgs().social_BW
        footer = (
            '''<div align="center">
                      <img src="'''
            + os.path.join(os.path.dirname(os.path.dirname(__file__)), self.figure)
            + """">
                    </div>
                    <div align="right">
                      <p align="right">
                      <b>"""
            + self.tr("Author: Thang Quach", "Author: Thang Quach")
            + """</b>
                      </p>"""
            + social_BW
            + """
                    </div>
                    """
        )
        return self.tr(self.txt_en, self.txt_vi) + footer

    def initAlgorithm(self, config=None):
        param = QgsProcessingParameterExtent(
            self.EXTENT, self.tr("Grid extent"), optional=True
        )
        self.addParameter(param)

        min_res, max_res, _ = settings.getResolution("rHEALPix")
        param = QgsProcessingParameterNumber(
            self.RESOLUTION,
            self.tr(f"Resolution [{min_res}..{max_res}]"),
            QgsProcessingParameterNumber.Integer,
            defaultValue=1,
            minValue=min_res,
            maxValue=max_res,
            optional=False,
        )
        self.addParameter(param)

        param = QgsProcessingParameterBoolean(
            self.SHIFT_ANTIMERIDIAN,
            self.tr("Shift at Antimeridian"),
            defaultValue=True,
        )
        self.addParameter(param)

        param = QgsProcessingParameterBoolean(
            self.SPLIT_ANTIMERIDIAN,
            self.tr("Split at Antimeridian"),
            defaultValue=False,
        )
        self.addParameter(param)

        param = QgsProcessingParameterFeatureSink(self.OUTPUT, "rHEALPix")
        self.addParameter(param)

    def prepareAlgorithm(self, parameters, context, feedback):
        self.resolution = self.parameterAsInt(parameters, self.RESOLUTION, context)
        # Get the extent parameter
        self.canvas_extent = self.parameterAsExtent(parameters, self.EXTENT, context)
        self.shift_antimeridian = self.parameterAsBoolean(
            parameters, self.SHIFT_ANTIMERIDIAN, context
        )
        self.split_antimeridian = self.parameterAsBoolean(
            parameters, self.SPLIT_ANTIMERIDIAN, context
        )
        if self.resolution > 5 and (
            self.canvas_extent is None or self.canvas_extent.isEmpty()
        ):
            feedback.reportError(
                "For performance reason, when resolution is greater than 4, the canvas extent must be set."
            )
            return False

        return True

    def outputFields(self):
        output_fields = QgsFields()
        output_fields.append(QgsField("rhealpix", QVariant.String))
        output_fields.append(QgsField("resolution", QVariant.Int))
        output_fields.append(QgsField("center_lat", QVariant.Double))
        output_fields.append(QgsField("center_lon", QVariant.Double))
        output_fields.append(QgsField("avg_edge_len", QVariant.Double))
        output_fields.append(QgsField("cell_area", QVariant.Double))
        output_fields.append(QgsField("cell_perimeter", QVariant.Double))
        return output_fields

    def processAlgorithm(self, parameters, context, feedback):
        fields = self.outputFields()
        # Output layer initialization
        (sink, dest_id) = self.parameterAsSink(
            parameters,
            self.OUTPUT,
            context,
            fields,
            QgsWkbTypes.Polygon,
            QgsCoordinateReferenceSystem("EPSG:4326"),
        )

        if not sink:
            raise QgsProcessingException(self.invalidSinkError(parameters, self.OUTPUT))

        canvas_crs = QgsProject.instance().crs()
        if self.canvas_extent is None or self.canvas_extent.isEmpty():
            min_lon, min_lat, max_lon, max_lat = -180, -90, 180, 90
        else:
            try:
                min_lon, min_lat, max_lon, max_lat = (
                    self.canvas_extent.xMinimum(),
                    self.canvas_extent.yMinimum(),
                    self.canvas_extent.xMaximum(),
                    self.canvas_extent.yMaximum(),
                )
                # Transform extent to EPSG:4326 if needed
                if epsg4326 != canvas_crs:
                    trans_to_4326 = QgsCoordinateTransform(
                        canvas_crs, epsg4326, QgsProject.instance()
                    )
                    self.canvas_extent = trans_to_4326.transform(self.canvas_extent)
                    min_lon, min_lat, max_lon, max_lat = (
                        self.canvas_extent.xMinimum(),
                        self.canvas_extent.yMinimum(),
                        self.canvas_extent.xMaximum(),
                        self.canvas_extent.yMaximum(),
                    )
            except Exception:
                # min_lon, min_lat, max_lon, max_lat = -180.0, -85.05112878, 180.0, 85.05112878
                min_lon, min_lat, max_lon, max_lat = -180, -90, 180, 90

        min_lat, min_lon, max_lat, max_lon = validate_coordinate(
            min_lat, min_lon, max_lat, max_lon
        )

        extent_bbox = box(min_lon, min_lat, max_lon, max_lat)
        if extent_bbox:
            bbox_center_lon = extent_bbox.centroid.x
            bbox_center_lat = extent_bbox.centroid.y
            seed_point = (bbox_center_lon, bbox_center_lat)

            seed_cell = rhealpix_dggs.cell_from_point(
                self.resolution, seed_point, plane=False
            )
            seed_cell_id = str(seed_cell)  # Unique identifier for the current cell
            # Apply antimeridian fix if requested
            if self.shift_antimeridian:
                seed_cell_polygon = rhealpix2geo(seed_cell_id, fix_antimeridian='shift_east')
            elif self.split_antimeridian:
                seed_cell_polygon = rhealpix2geo(seed_cell_id, fix_antimeridian='split')
            else:
                seed_cell_polygon = rhealpix2geo(seed_cell_id)

            if seed_cell_polygon.contains(extent_bbox):
                num_edges = 4
                if seed_cell.ellipsoidal_shape() == "dart":
                    num_edges = 3

                seed_cell_geometry = QgsGeometry.fromWkt(seed_cell_polygon.wkt)

                rhealpix_feature = QgsFeature()
                rhealpix_feature.setGeometry(seed_cell_geometry)

                center_lat, center_lon, avg_edge_len, cell_area, cell_perimeter = (
                    geodesic_dggs_metrics(seed_cell_polygon, num_edges)
                )
                rhealpix_feature.setAttributes(
                    [
                        seed_cell_id,
                        self.resolution,
                        center_lat,
                        center_lon,
                        avg_edge_len,
                        cell_area,
                        cell_perimeter,
                    ]
                )
                sink.addFeature(rhealpix_feature, QgsFeatureSink.FastInsert)

            else:
                # Store intersecting cells with their polygons and cell objects
                intersecting_cells = {}  # {cell_id: (cell, polygon)}
                covered_cells = set()  # Cells that have been processed (by their unique ID)
                queue = deque([seed_cell])  # Queue for BFS exploration
                
                while queue:
                    current_cell = queue.popleft()  # BFS: FIFO
                    current_cell_id = str(current_cell)  # Unique identifier for the current cell

                    if current_cell_id in covered_cells:
                        continue
                    # Add current cell to the covered set
                    covered_cells.add(current_cell_id)
                    
                    # Apply antimeridian fix if requested (apply once during BFS)
                    if self.shift_antimeridian:
                        cell_polygon = rhealpix2geo(current_cell_id, fix_antimeridian='shift_east')
                    elif self.split_antimeridian:
                        cell_polygon = rhealpix2geo(current_cell_id, fix_antimeridian='split')
                    else:
                        cell_polygon = rhealpix2geo(current_cell_id)
                    
                    # Skip cells that do not intersect the bounding box
                    if cell_polygon.intersects(extent_bbox):
                        # Store for later processing (no double conversion)
                        intersecting_cells[current_cell_id] = (current_cell, cell_polygon)
                        
                        # Get neighbors and add to queue
                        neighbors = current_cell.neighbors(plane=False)
                        for _, neighbor in neighbors.items():
                            neighbor_id = str(neighbor)  # Unique identifier for the neighbor
                            if neighbor_id not in covered_cells:
                                queue.append(neighbor)
                    
                    if feedback.isCanceled():
                        break

                # Process only intersecting cells (no double conversion)
                # Note: fix_antimeridian already applied when creating polygon in BFS loop
                for idx, (cell_id, (cell, cell_polygon)) in enumerate(intersecting_cells.items()):
                    progress = int((idx / len(intersecting_cells)) * 100)
                    feedback.setProgress(progress)

                    cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)
                    rhealpix_feature = QgsFeature()
                    rhealpix_feature.setGeometry(cell_geometry)

                    num_edges = 4
                    if cell.ellipsoidal_shape() == "dart":
                        num_edges = 3

                    (
                        center_lat,
                        center_lon,
                        avg_edge_len,
                        cell_area,
                        cell_perimeter,
                    ) = geodesic_dggs_metrics(cell_polygon, num_edges)
                    rhealpix_feature.setAttributes(
                        [
                            cell_id,
                            self.resolution,
                            center_lat,
                            center_lon,
                            avg_edge_len,
                            cell_area,
                            cell_perimeter,
                        ]
                    )
                    sink.addFeature(rhealpix_feature, QgsFeatureSink.FastInsert)

                    if feedback.isCanceled():
                        break

        else:
            total_cells = rhealpix_dggs.num_cells(self.resolution)
            feedback.pushInfo(f"Total cells to be generated: {total_cells}.")
            rhealpix_grid = rhealpix_dggs.grid(self.resolution)
            for idx, cell in enumerate(rhealpix_grid):
                progress = int((idx / total_cells) * 100)
                feedback.setProgress(progress)
                
                rhealpix_id = str(cell)
                # Apply antimeridian fix if requested
                if self.shift_antimeridian:
                    cell_polygon = rhealpix2geo(rhealpix_id, fix_antimeridian='shift_east')
                elif self.split_antimeridian:
                    cell_polygon = rhealpix2geo(rhealpix_id, fix_antimeridian='split')
                else:
                    cell_polygon = rhealpix2geo(rhealpix_id)
                
                cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)

                rhealpix_feature = QgsFeature()
                rhealpix_feature.setGeometry(cell_geometry)

                num_edges = 4
                if cell.ellipsoidal_shape() == "dart":
                    num_edges = 3
                center_lat, center_lon, avg_edge_len, cell_area, cell_perimeter = (
                    geodesic_dggs_metrics(cell_polygon, num_edges)
                )
                rhealpix_feature.setAttributes(
                    [
                        rhealpix_id,
                        self.resolution,
                        center_lat,
                        center_lon,
                        avg_edge_len,
                        cell_area,
                        cell_perimeter,
                    ]
                )
                sink.addFeature(rhealpix_feature, QgsFeatureSink.FastInsert)
                if feedback.isCanceled():
                    break

        feedback.pushInfo("rHEALPix DGGS generation completed.")
        if context.willLoadLayerOnCompletion(dest_id):
            lineColor = settings.rhealpixColor
            fontColor = QColor("#000000")
            context.layerToLoadOnCompletionDetails(dest_id).setPostProcessor(
                StylePostProcessor.create(lineColor, fontColor)
            )

        return {self.OUTPUT: dest_id}


class StylePostProcessor(QgsProcessingLayerPostProcessorInterface):
    instance = None
    line_color = None
    font_color = None

    def __init__(self, line_color, font_color):
        self.line_color = line_color
        self.font_color = font_color
        super().__init__()

    def postProcessLayer(self, layer, context, feedback):
        if not isinstance(layer, QgsVectorLayer):
            return
        sym = layer.renderer().symbol().symbolLayer(0)
        sym.setBrushStyle(Qt.NoBrush)
        sym.setStrokeColor(self.line_color)
        if settings.gridLabel:
            label = QgsPalLayerSettings()
            label.fieldName = "rhealpix"
            format = label.format()
            format.setColor(self.font_color)
            format.setSize(8)
            label.setFormat(format)
            labeling = QgsVectorLayerSimpleLabeling(label)
            layer.setLabeling(labeling)
            layer.setLabelsEnabled(True)

        iface.layerTreeView().refreshLayerSymbology(layer.id())
        root = QgsProject.instance().layerTreeRoot()
        layer_node = root.findLayer(layer.id())
        if layer_node:
            layer_node.setCustomProperty("showFeatureCount", True)

        # iface.mapCanvas().setExtent(layer.extent())
        iface.mapCanvas().refresh()

    # Hack to work around sip bug!
    @staticmethod
    def create(line_color, font_color) -> "StylePostProcessor":
        """
        Returns a new instance of the post processor, keeping a reference to the sip
        wrapper so that sip doesn't get confused with the Python subclass and call
        the base wrapper implementation instead... ahhh sip, you wonderful piece of sip
        """
        StylePostProcessor.instance = StylePostProcessor(line_color, font_color)
        return StylePostProcessor.instance
