# -*- coding: utf-8 -*-
"""
tilecodegen.py          
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

from qgis.core import (
    QgsApplication,  # type: ignore
    QgsProject,
    QgsCoordinateTransform, 
    QgsFeatureSink,
    QgsProcessingLayerPostProcessorInterface,  # type: ignore
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
from PyQt5.QtCore import QVariant
import os, random
from ...utils.imgs import Imgs
from shapely.geometry import Polygon
from vgrid.dggs import mercantile
from vgrid.utils.geometry import graticule_dggs_metrics
from ...settings import settings
from vgrid.utils.io import validate_coordinate
from ...utils.latlon import epsg4326
    

class TilecodeGen(QgsProcessingAlgorithm):
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
        return TilecodeGen()

    def name(self):
        return "tilecode_gen"

    def icon(self):
        return QIcon(
            os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "../images/generator/grid_quad.svg",
            )
        )

    def displayName(self):
        return self.tr("Tilecode", "Tilecode")

    def group(self):
        return self.tr("Generator", "Generator")

    def groupId(self):
        return "generator"

    def tags(self):
        return self.tr("Tilecode, generator").split(",")

    txt_en = "Tilecode DGGS Generator"
    txt_vi = "Tilecode DGGS Generator"
    figure = "../images/tutorial/grid_tilecode.png"

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

        min_res, max_res, _ = settings.getResolution("Tilecode")
        param = QgsProcessingParameterNumber(
            self.RESOLUTION,
            self.tr(f"Resolution/ zoom level [{min_res}..{max_res}]"),
            QgsProcessingParameterNumber.Integer,
            defaultValue=1,
            minValue=min_res,
            maxValue=max_res,
            optional=False,
        )
        self.addParameter(param)

        param = QgsProcessingParameterFeatureSink(self.OUTPUT, "Tilecode")
        self.addParameter(param)

    def prepareAlgorithm(self, parameters, context, feedback):
        self.resolution = self.parameterAsInt(parameters, self.RESOLUTION, context)
        # Get the extent parameter
        self.canvas_extent = self.parameterAsExtent(parameters, self.EXTENT, context)
        if self.resolution > 9 and (
            self.canvas_extent is None or self.canvas_extent.isEmpty()
        ):
            feedback.reportError(
                "For performance reason, when resolution is greater than 9, the grid extent must be set."
            )
            return False

        return True

    def outputFields(self):
        output_fields = QgsFields()
        output_fields.append(QgsField("tilecode", QVariant.String))
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

        canvas_crs = QgsProject.instance().crs()    
        if self.canvas_extent is None or self.canvas_extent.isEmpty():
            # min_lon, min_lat, max_lon, max_lat =  -180.0, -85.05112878, 180.0, 85.05112878
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
                    trans_to_4326 = QgsCoordinateTransform(canvas_crs, epsg4326, QgsProject.instance())
                    self.canvas_extent   = trans_to_4326.transform(self.canvas_extent)              
                    min_lon, min_lat, max_lon, max_lat = (
                        self.canvas_extent.xMinimum(),  
                        self.canvas_extent.yMinimum(),
                        self.canvas_extent.xMaximum(),
                        self.canvas_extent.yMaximum(),
                    )     
            except Exception as e: 
                # min_lon, min_lat, max_lon, max_lat = -180.0, -85.05112878, 180.0, 85.05112878
                min_lon, min_lat, max_lon, max_lat = -180, -90, 180, 90

        min_lat, min_lon, max_lat, max_lon = validate_coordinate(min_lat, min_lon, max_lat, max_lon)

        tiles = list(mercantile.tiles(min_lon, min_lat, max_lon, max_lat, self.resolution))

        total_cells = len(tiles)
        feedback.pushInfo(f"Total cells to be generated: {total_cells}.")

        # Iterate over each tile to create features
        for idx, tile in enumerate(tiles):
            if feedback.isCanceled():
                break
            progress = int((idx / total_cells) * 100)
            feedback.setProgress(progress)
            # Get the tile's bounding box in geographic coordinates
            bounds = mercantile.bounds(tile)

            # Create a Shapely polygon
            cell_polygon = Polygon(
                [
                    (bounds.west, bounds.south),
                    (bounds.east, bounds.south),
                    (bounds.east, bounds.north),
                    (bounds.west, bounds.north),
                    (bounds.west, bounds.south),  # Closing the polygon
                ]
            )
            cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)
            tilecode_feature = QgsFeature()
            tilecode_feature.setGeometry(cell_geometry)

            tilecode_id = f"z{tile.z}x{tile.x}y{tile.y}"
            (
                center_lat,
                center_lon,
                cell_width,
                cell_height,
                cell_area,
                cell_perimeter,
            ) = graticule_dggs_metrics(cell_polygon)
            tilecode_feature.setAttributes(
                [
                    tilecode_id,
                    self.resolution,
                    center_lat,
                    center_lon,
                    cell_width,
                    cell_height,
                    cell_area,
                    cell_perimeter,
                ]
            )
            sink.addFeature(tilecode_feature, QgsFeatureSink.FastInsert)
           

        feedback.pushInfo("Tilecode DGGS generation completed.")
        if context.willLoadLayerOnCompletion(dest_id):
            lineColor = settings.tilecodeColor
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
            label.fieldName = "tilecode"
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

        #iface.mapCanvas().setExtent(layer.extent())
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
