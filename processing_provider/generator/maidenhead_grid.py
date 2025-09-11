# -*- coding: utf-8 -*-
"""
maidenhead_grid.py
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

__author__ = "Thang Quach"
__date__ = "2024-11-20"
__copyright__ = "(L) 2024, Thang Quach"

from qgis.core import (
    QgsApplication,
    QgsProject,
    QgsFeatureSink,
    QgsProcessingLayerPostProcessorInterface,
    QgsProcessingParameterExtent,
    QgsProcessingParameterNumber,
    QgsProcessingException,
    QgsProcessingParameterFeatureSink,
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
from qgis.PyQt.QtGui import QIcon, QColor
from qgis.PyQt.QtCore import QCoreApplication, QSettings, Qt
from qgis.utils import iface
from PyQt5.QtCore import QVariant
import os

from vgrid.dggs import maidenhead
from ...utils.imgs import Imgs
from shapely.geometry import Polygon
from vgrid.utils.geometry import graticule_dggs_metrics
from ...settings import settings

grid_params = {
    1: (18, 18, 20, 10),  # Fields: 20° lon, 10° lat
    2: (180, 180, 2, 1),  # Squares: 2° lon, 1° lat
    3: (4320, 4320, 0.083333, 0.041666),  # Subsquare: 5' lon, 2.5' lat
    4: (43200, 43200, 0.008333, 0.004167),  # Extended: 30" lon, 15" lat
}


class MaidenheadGrid(QgsProcessingAlgorithm):
    EXTENT = "EXTENT"
    RESOLUTION = "RESOLUTION"
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
        return MaidenheadGrid()

    def name(self):
        return "grid_maidenhead"

    def icon(self):
        return QIcon(
            os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "../images/generator/grid_quad.svg",
            )
        )

    def displayName(self):
        return self.tr("Maidenhead", "Maidenhead")

    def group(self):
        return self.tr("Generator", "Generator")

    def groupId(self):
        return "grid"

    def tags(self):
        return self.tr("DGGS, grid, Maidenhead, generator").split(",")

    txt_en = "Maidenhead DGGS Generator"
    txt_vi = "Maidenhead DGGS Generator"
    figure = "../images/tutorial/grid_maidenhead.png"

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

        min_res, max_res, _ = settings.getResolution("Maidenhead")
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

        param = QgsProcessingParameterFeatureSink(self.OUTPUT, "Maidenhead")
        self.addParameter(param)

    def prepareAlgorithm(self, parameters, context, feedback):
        self.resolution = self.parameterAsInt(parameters, self.RESOLUTION, context)
        # Get the extent parameter
        self.grid_extent = self.parameterAsExtent(parameters, self.EXTENT, context)
        if self.resolution > 2 and (
            self.grid_extent is None or self.grid_extent.isEmpty()
        ):
            feedback.reportError(
                "For performance reason, when resolution is greater than 2, the grid extent must be set."
            )
            return False

        return True

    def outputFields(self):
        output_fields = QgsFields()
        output_fields.append(QgsField("maidenhead", QVariant.String))
        output_fields.append(QgsField("resolution", QVariant.Int))
        output_fields.append(QgsField("center_lat", QVariant.Double))
        output_fields.append(QgsField("center_lon", QVariant.Double))
        output_fields.append(QgsField("cell_width", QVariant.Double))
        output_fields.append(QgsField("cell_height", QVariant.Double))
        output_fields.append(QgsField("cell_area", QVariant.Double))
        output_fields.append(QgsField("cell_perimeter", QVariant.Double))
        return output_fields

    def processAlgorithm(self, parameters, context, feedback):
        fields = self.outputFields()
        # Get the output sink and its destination ID
        (sink, dest_id) = self.parameterAsSink(
            parameters,
            self.OUTPUT,
            context,
            fields,
            QgsWkbTypes.Polygon,
            QgsCoordinateReferenceSystem("EPSG:4326"),
        )

        if sink is None:
            raise QgsProcessingException("Failed to create output sink")

        x_cells, y_cells, lon_width, lat_width = grid_params[self.resolution]
        base_lat, base_lon = -90.0, -180.0

        if self.grid_extent is None or self.grid_extent.isEmpty():
            total_cells = x_cells * y_cells
            feedback.pushInfo(f"Total cells to be generated: {total_cells}.")
            cell_count = 0  # Counter to track progress
            for i in range(x_cells):
                for j in range(y_cells):
                    cell_min_lon = base_lon + i * lon_width
                    cell_max_lon = cell_min_lon + lon_width
                    cell_min_lat = base_lat + j * lat_width
                    cell_max_lat = cell_min_lat + lat_width

                    cell_center_lat = (cell_min_lat + cell_max_lat) / 2
                    cell_center_lon = (cell_min_lon + cell_max_lon) / 2

                    maidenhead_id = maidenhead.toMaiden(
                        cell_center_lat, cell_center_lon, self.resolution
                    )
                    (
                        _,
                        _,
                        min_lat_maiden,
                        min_lon_maiden,
                        max_lat_maiden,
                        max_lon_maiden,
                        _,
                    ) = maidenhead.maidenGrid(maidenhead_id)
                    # Define the polygon based on the bounding box
                    cell_polygon = Polygon(
                        [
                            [min_lon_maiden, min_lat_maiden],  # Bottom-left corner
                            [max_lon_maiden, min_lat_maiden],  # Bottom-right corner
                            [max_lon_maiden, max_lat_maiden],  # Top-right corner
                            [min_lon_maiden, max_lat_maiden],  # Top-left corner
                            [
                                min_lon_maiden,
                                min_lat_maiden,
                            ],  # Closing the polygon (same as the first point)
                        ]
                    )

                    cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)
                    maidenhead_feature = QgsFeature()
                    maidenhead_feature.setGeometry(cell_geometry)

                    (
                        center_lat,
                        center_lon,
                        cell_width,
                        cell_height,
                        cell_area,
                        cell_perimeter,
                    ) = graticule_dggs_metrics(cell_polygon)
                    maidenhead_feature.setAttributes(
                        [
                            maidenhead_id,
                            self.resolution,
                            center_lat,
                            center_lon,
                            cell_width,
                            cell_height,
                            cell_area,
                            cell_perimeter,
                        ]
                    )

                    sink.addFeature(maidenhead_feature, QgsFeatureSink.FastInsert)

                    # Update progress and feedback message
                    cell_count += 1
                    feedback.setProgress(int((cell_count / total_cells) * 100))

                    if feedback.isCanceled():
                        break
        else:
            # Calculate the cell indices corresponding to the extent bounds
            min_x = max(0, int((self.grid_extent.xMinimum() - base_lon) / lon_width))
            max_x = min(
                x_cells, int((self.grid_extent.xMaximum() - base_lon) / lon_width) + 1
            )
            min_y = max(0, int((self.grid_extent.yMinimum() - base_lat) / lat_width))
            max_y = min(
                y_cells, int((self.grid_extent.yMaximum() - base_lat) / lat_width) + 1
            )

            # Total cells to process, for progress feedback
            total_cells = (max_x - min_x) * (max_y - min_y)
            feedback.pushInfo(f"Total cells to be generated: {total_cells}.")
            cell_count = 0

            for i in range(min_x, max_x):
                for j in range(min_y, max_y):
                    cell_min_lon = base_lon + i * lon_width
                    cell_max_lon = cell_min_lon + lon_width
                    cell_min_lat = base_lat + j * lat_width
                    cell_max_lat = cell_min_lat + lat_width

                    cell_center_lat = (cell_min_lat + cell_max_lat) / 2
                    cell_center_lon = (cell_min_lon + cell_max_lon) / 2

                    maidenhead_id = maidenhead.toMaiden(
                        cell_center_lat, cell_center_lon, self.resolution
                    )
                    (
                        _,
                        _,
                        min_lat_maiden,
                        min_lon_maiden,
                        max_lat_maiden,
                        max_lon_maiden,
                        _,
                    ) = maidenhead.maidenGrid(maidenhead_id)

                    cell_polygon = Polygon(
                        [
                            [min_lon_maiden, min_lat_maiden],  # Bottom-left corner
                            [max_lon_maiden, min_lat_maiden],  # Bottom-right corner
                            [max_lon_maiden, max_lat_maiden],  # Top-right corner
                            [min_lon_maiden, max_lat_maiden],  # Top-left corner
                            [
                                min_lon_maiden,
                                min_lat_maiden,
                            ],  # Closing the polygon (same as the first point)
                        ]
                    )

                    cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)
                    maidenhead_feature = QgsFeature()
                    maidenhead_feature.setGeometry(cell_geometry)

                    (
                        center_lat,
                        center_lon,
                        cell_width,
                        cell_height,
                        cell_area,
                        cell_perimeter,
                    ) = graticule_dggs_metrics(cell_polygon)
                    maidenhead_feature.setAttributes(
                        [
                            maidenhead_id,
                            self.resolution,
                            center_lat,
                            center_lon,
                            cell_width,
                            cell_height,
                            cell_area,
                            cell_perimeter,
                        ]
                    )

                    sink.addFeature(maidenhead_feature, QgsFeatureSink.FastInsert)

                    # Update progress and feedback message
                    cell_count += 1
                    feedback.setProgress(int((cell_count / total_cells) * 100))

                    if feedback.isCanceled():
                        break

        feedback.pushInfo("Maidenhead DGGS generation completed.")
        if context.willLoadLayerOnCompletion(dest_id):
            lineColor = settings.maidenheadColor
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
            label.fieldName = "maidenhead"
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

        iface.mapCanvas().setExtent(layer.extent())
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
