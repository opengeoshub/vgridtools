# -*- coding: utf-8 -*-
"""
georefgen.py
***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 2 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************
"""

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
from qgis.PyQt.QtCore import QCoreApplication, Qt
from qgis.utils import iface
from qgis.core import QgsCoordinateTransform
from qgis.PyQt.QtCore import QVariant
import os

from vgrid.utils.constants import GEOREF_RESOLUTION_DEGREES
from ...utils.help_footer import social_links_footer
from ...utils.crs_helper import processing_extent_wgs84
from ...settings import settings
from ...utils.binning.bin_helper import apply_loaded_layer_name, set_output_layer_name
import numpy as np
from vgrid.utils.geometry import graticule_dggs_metrics
from vgrid.conversion.latlon2dggs import latlon2georef
from vgrid.conversion.dggs2geo import georef2geo


class GEOREFGen(QgsProcessingAlgorithm):
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
        return GEOREFGen()

    def name(self):
        return "georef_gen"

    def icon(self):
        return QIcon(
            os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "../images/generator/grid_quad.svg",
            )
        )

    def displayName(self):
        return self.tr("GEOREF", "GEOREF")

    def group(self):
        return self.tr("Generator", "Generator")

    def groupId(self):
        return "generator"

    def tags(self):
        return self.tr("GEOREF, DGGS, generator").split(",")

    txt_en = "GEOREF DGGS Generator"
    txt_vi = "GEOREF DGGS Generator"
    figure = "../images/tutorial/grid_georef.png"

    def shortHelpString(self):
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
            + social_links_footer()
            + """
                    </div>
                    """
        )
        return self.tr(self.txt_en, self.txt_vi) + footer

    def initAlgorithm(self, config=None):
        param = QgsProcessingParameterExtent(
            self.EXTENT, self.tr("Canvas extent"), optional=True
        )
        self.addParameter(param)

        min_res, max_res, _ = settings.getResolution("GEOREF")
        param = QgsProcessingParameterNumber(
            self.RESOLUTION,
            self.tr(f"RESOLUTION [{min_res}..{max_res}]"),
            QgsProcessingParameterNumber.Type.Integer,
            defaultValue=0,
            minValue=min_res,
            maxValue=max_res,
            optional=False,
        )
        self.addParameter(param)

        param = QgsProcessingParameterFeatureSink(self.OUTPUT, "GEOREF")
        self.addParameter(param)

    def prepareAlgorithm(self, parameters, context, feedback):
        self.resolution = self.parameterAsInt(parameters, self.RESOLUTION, context)
        if self.resolution < 0 or self.resolution > 10:
            feedback.reportError("Resolution must be in range [0..10]")
            return False

        # Get the extent parameter
        self.canvas_extent = self.parameterAsExtent(parameters, self.EXTENT, context)
        if self.resolution > 2 and (
            self.canvas_extent is None or self.canvas_extent.isEmpty()
        ):
            feedback.reportError(
                "For performance reason, when resolution is greater than 2, the canvas extent must be set."
            )
            return False

        return True

    def outputFields(self):
        output_fields = QgsFields()
        output_fields.append(QgsField("georef", QVariant.String))
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
        layer_name = f"GEOREF_{self.resolution}"
        set_output_layer_name(parameters, self.OUTPUT, "GEOREF", layer_name)
        # Get the output sink and its destination ID
        (sink, dest_id) = self.parameterAsSink(
            parameters,
            self.OUTPUT,
            context,
            fields,
            QgsWkbTypes.Type.Polygon,
            QgsCoordinateReferenceSystem("EPSG:4326"),
        )

        if sink is None:
            raise QgsProcessingException("Failed to create output sink")
        apply_loaded_layer_name(context, dest_id, "GEOREF", layer_name)

        resolution_degrees = GEOREF_RESOLUTION_DEGREES.get(self.resolution)

        min_lon, min_lat, max_lon, max_lat, _is_full_world = processing_extent_wgs84(
            self, parameters, self.EXTENT, context, feedback
        )

        longitudes = np.arange(min_lon, max_lon, resolution_degrees)
        latitudes = np.arange(min_lat, max_lat, resolution_degrees)

        # Total cells to process, for progress feedback
        total_cells = len(longitudes) * len(latitudes)
        cell_count = 0
        feedback.pushInfo(f"Total cells to be generated: {total_cells}.")
        for lon in longitudes:
            for lat in latitudes:
                if feedback.isCanceled():
                    break
                georef_id = latlon2georef(lat, lon, self.resolution)
                cell_polygon = georef2geo(georef_id)
                cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)
                georef_feature = QgsFeature()
                georef_feature.setGeometry(cell_geometry)
                (
                    center_lat,
                    center_lon,
                    cell_width,
                    cell_height,
                    cell_area,
                    cell_perimeter,
                ) = graticule_dggs_metrics(cell_polygon)
                georef_feature.setAttributes(
                    [
                        georef_id,
                        self.resolution,
                        center_lat,
                        center_lon,
                        cell_width,
                        cell_height,
                        cell_area,
                        cell_perimeter,
                    ]
                )
                sink.addFeature(georef_feature, QgsFeatureSink.Flag.FastInsert)
                # Update progress and feedback message
                cell_count += 1
                feedback.setProgress(int((cell_count / total_cells) * 100))

        feedback.pushInfo("GEOREF DGGS generation completed.")
        # Set styling if loading the layer
        if context.willLoadLayerOnCompletion(dest_id):
            lineColor = settings.georefColor
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
        sym.setBrushStyle(Qt.BrushStyle.NoBrush)
        sym.setStrokeColor(self.line_color)
        if settings.gridLabel:
            label = QgsPalLayerSettings()
            label.fieldName = "georef"
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
