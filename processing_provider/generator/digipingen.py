# -*- coding: utf-8 -*-
"""
digipingrid.py
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
    QgsFeatureSink,  # type: ignore
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
from PyQt5.QtCore import QVariant
from qgis.core import QgsCoordinateTransform
import os

from shapely.geometry import Polygon
from vgrid.conversion.latlon2dggs import latlon2digipin
from vgrid.conversion.dggs2geo.digipin2geo import digipin2geo
from vgrid.utils.io import validate_digipin_coordinate
from vgrid.dggs.digipin import BOUNDS
from vgrid.utils.geometry import graticule_dggs_metrics

from ...utils.imgs import Imgs
from ...settings import settings
from ...utils.latlon import epsg4326
from vgrid.utils.constants import DGGS_TYPES


class DIGIPINGen(QgsProcessingAlgorithm):
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
        return DIGIPINGen()

    def name(self):
        return "digipin_grid"

    def icon(self):
        return QIcon(
            os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "../images/generator/grid_quad.svg",
            )
        )

    def displayName(self):
        return self.tr("DIGIPIN", "DIGIPIN")

    def group(self):
        return self.tr("Generator", "Generator")

    def groupId(self):
        return "generator"

    def tags(self):
        return self.tr("DGGS, grid, DIGIPIN, generator").split(",")

    txt_en = "DIGIPIN DGGS Grid Generator"
    txt_vi = "DIGIPIN DGGS Grid Generator"
    figure = "../images/tutorial/grid_digipin.png"

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
            self.EXTENT, self.tr("Canvas extent"), optional=True
        )
        self.addParameter(param)

        min_res = DGGS_TYPES['digipin']["min_res"]
        max_res = DGGS_TYPES['digipin']["max_res"]
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

        param = QgsProcessingParameterFeatureSink(self.OUTPUT, "DIGIPIN")
        self.addParameter(param)

    def prepareAlgorithm(self, parameters, context, feedback):
        self.resolution = self.parameterAsInt(parameters, self.RESOLUTION, context)
        self.canvas_extent = self.parameterAsExtent(parameters, self.EXTENT, context)
        if self.resolution > 4 and (
            self.canvas_extent is None or self.canvas_extent.isEmpty()
        ):
            feedback.reportError(
                "For performance reason, when resolution is greater than 4, the canvas extent must be set."
            )
            return False

        return True

    def outputFields(self):
        output_fields = QgsFields()
        output_fields.append(QgsField("digipin", QVariant.String))
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
            # Use full DIGIPIN bounds if no extent specified
            min_lat, min_lon, max_lat, max_lon = (
                BOUNDS['minLat'], BOUNDS['minLon'], BOUNDS['maxLat'], BOUNDS['maxLon']
            )
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
                    transformed_extent = trans_to_4326.transform(self.canvas_extent)
                    min_lon, min_lat, max_lon, max_lat = (
                        transformed_extent.xMinimum(),
                        transformed_extent.yMinimum(),
                        transformed_extent.xMaximum(),
                        transformed_extent.yMaximum(),
                    )
            except Exception:
                min_lat, min_lon, max_lat, max_lon = (
                    BOUNDS['minLat'], BOUNDS['minLon'], BOUNDS['maxLat'], BOUNDS['maxLon']
                )

            # Validate and constrain to DIGIPIN bounds (India region)
            min_lat, min_lon, max_lat, max_lon = validate_digipin_coordinate(
                min_lat, min_lon, max_lat, max_lon
            )            

        # Calculate sampling density based on resolution
        # Each level divides the cell by 4 (2x2 grid)
        base_width = 9.0  # degrees at resolution 1
        factor = 0.25 ** (self.resolution - 1)  # each level divides by 4
        sample_width = base_width * factor
        
        seen_cells = set()
        total_cells = 0
        
        # Estimate total cells for progress tracking
        lon_range = max_lon - min_lon
        lat_range = max_lat - min_lat
        estimated_cells = int((lon_range / sample_width) * (lat_range / sample_width))
        feedback.pushInfo(f"Estimated cells to be generated: {estimated_cells}.")
        
        # Sample points across the bounding box
        lon = min_lon
        cell_count = 0
        while lon <= max_lon:
            lat = min_lat
            while lat <= max_lat:
                if feedback.isCanceled():
                    break
                    
                try:
                    # Get DIGIPIN code for this point at the specified resolution
                    digipin_id = latlon2digipin(lat, lon, self.resolution)
                    
                    if digipin_id == 'Out of Bound':
                        lat += sample_width
                        continue
                    
                    if digipin_id in seen_cells:
                        lat += sample_width
                        continue
                    
                    seen_cells.add(digipin_id)
                    
                    # Get the bounds for this DIGIPIN cell
                    cell_polygon = digipin2geo(digipin_id)
                    
                    if isinstance(cell_polygon, str):  # Error like 'Invalid DIGIPIN'
                        lat += sample_width
                        continue
                    
                    # Convert to QgsGeometry
                    cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)
                    
                    # Calculate cell metrics
                    center_lat, center_lon, cell_width, cell_height, cell_area, cell_perimeter = (
                        graticule_dggs_metrics(cell_polygon)
                    )
                    
                    # Create QgsFeature
                    digipin_feature = QgsFeature()
                    digipin_feature.setGeometry(cell_geometry)
                    digipin_feature.setAttributes([
                        digipin_id,
                        self.resolution,
                        center_lat,
                        center_lon,
                        cell_width,
                        cell_height,
                        cell_area,
                        cell_perimeter,
                    ])
                    
                    sink.addFeature(digipin_feature, QgsFeatureSink.FastInsert)
                    cell_count += 1
                    
                    # Update progress
                    if cell_count % 100 == 0:
                        progress = int((cell_count / estimated_cells) * 100) if estimated_cells > 0 else 0
                        feedback.setProgress(progress)
                    
                except Exception:
                    # Skip cells with errors
                    pass
                
                lat += sample_width
            lon += sample_width

        feedback.pushInfo(f"DIGIPIN DGGS generation completed. Generated {cell_count} cells.")

        if context.willLoadLayerOnCompletion(dest_id):
            lineColor = settings.digipinColor if hasattr(settings, 'digipinColor') else QColor("#FF0000")
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
            label.fieldName = "digipin"
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
