# -*- coding: utf-8 -*-
"""
DGGRIDgen.py
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
    QgsProcessingParameterEnum,
    QgsProcessingParameterBoolean,
)
from qgis.PyQt.QtGui import QIcon, QColor
from qgis.PyQt.QtCore import QCoreApplication, Qt
from qgis.utils import iface
from qgis.PyQt.QtCore import QVariant
from qgis.core import QgsCoordinateTransform
import os
from ...settings import settings

from ...utils.imgs import Imgs
from ...utils.latlon import epsg4326
from vgrid.utils.io import convert_to_output_format, create_dggrid_instance
from vgrid.utils.io import validate_dggrid_type, validate_dggrid_resolution
from vgrid.utils.constants import OUTPUT_FORMATS, STRUCTURED_FORMATS, DGGRID_TYPES
from vgrid.utils.io import validate_coordinate
from dggrid4py.dggrid_runner import output_address_types


class DGGRIDGen(QgsProcessingAlgorithm):
    EXTENT = "EXTENT"
    DGGS_TYPE = "DGGS_TYPE"
    RESOLUTION = "RESOLUTION"
    OUTPUT_ADDRESS_TYPE = "OUTPUT_ADDRESS_TYPE"
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
        return DGGRIDGen()

    def name(self):
        return "DGGRID_gen"

    def icon(self):
        return QIcon(
            os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "../images/generator/grid_DGGRID.png",
            )
        )

    def displayName(self):
        return self.tr("DGGRID", "DGGRID")

    def group(self):
        return self.tr("Generator", "Generator")

    def groupId(self):
        return "generator"

    def tags(self):
        return self.tr("DGGS, DGGRID, generator").split(",")

    txt_en = "DGGRID Generator"
    txt_vi = "DGGRID Generator"
    figure = "../images/tutorial/grid_dggrid.png"

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

        param = QgsProcessingParameterEnum(
            self.DGGS_TYPE,
            self.tr("DGGS Type"),
            options=[key for key in DGGRID_TYPES.keys()],
            defaultValue="ISEA3H",
        )
        self.addParameter(param)

        param = QgsProcessingParameterNumber(
            self.RESOLUTION,
            self.tr("Resolution"),
            QgsProcessingParameterNumber.Integer,
            defaultValue=1,
            minValue=0,
            maxValue=33,
            optional=False,
        )
        self.addParameter(param)

        param = QgsProcessingParameterEnum(
            self.OUTPUT_ADDRESS_TYPE,
            self.tr("Output Address Type"),
            options=list(output_address_types),
            optional=True,
        )
        self.addParameter(param)

        param = QgsProcessingParameterBoolean(
            self.SPLIT_ANTIMERIDIAN,
            self.tr("Split at Antimeridian"),
            defaultValue=False,
        )
        self.addParameter(param)

        param = QgsProcessingParameterFeatureSink(self.OUTPUT, self.tr("DGGRID"))
        self.addParameter(param)

    def prepareAlgorithm(self, parameters, context, feedback):
        dggs_type_index = self.parameterAsEnum(parameters, self.DGGS_TYPE, context)
        self.dggs_type = validate_dggrid_type(list(DGGRID_TYPES.keys())[dggs_type_index])
        self.resolution = self.parameterAsInt(parameters, self.RESOLUTION, context)
        output_address_type_index = self.parameterAsEnum(
            parameters, self.OUTPUT_ADDRESS_TYPE, context
        )
        if output_address_type_index >= 0:
            self.output_address_type = output_address_types[output_address_type_index]
        else:
            self.output_address_type = None
        self.canvas_extent = self.parameterAsExtent(parameters, self.EXTENT, context)
        self.split_antimeridian = self.parameterAsBoolean(
            parameters, self.SPLIT_ANTIMERIDIAN, context
        )

        # Validate resolution for the selected DGGS type
        self.resolution = validate_dggrid_resolution(self.dggs_type, self.resolution)

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
        output_fields.append(QgsField(f"dggrid_{self.dggs_type}", QVariant.String))
        output_fields.append(QgsField("resolution", QVariant.Int))
        output_fields.append(QgsField("center_lat", QVariant.Double))
        output_fields.append(QgsField("center_lon", QVariant.Double))
        output_fields.append(QgsField("avg_edge_len", QVariant.Double))
        output_fields.append(QgsField("cell_area", QVariant.Double))
        output_fields.append(QgsField("cell_perimeter", QVariant.Double))
        return output_fields

    def _zone_to_output_id(self, dggrs, zone):
        # Keep behavior compatible with existing output while allowing
        # numeric sequence IDs when requested and supported.
        if self.output_address_type == "SEQNUM" and hasattr(dggrs, "getZoneID"):
            return str(dggrs.getZoneID(zone))
        return dggrs.getZoneTextID(zone)

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

        if sink is None:
            raise QgsProcessingException("Failed to create output sink")

        canvas_crs = QgsProject.instance().crs()
        if self.canvas_extent is not None and not self.canvas_extent.isEmpty():
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
                min_lon, min_lat, max_lon, max_lat = -180, -90, 180, 90
        else:
            min_lon, min_lat, max_lon, max_lat = -180, -90, 180, 90

        min_lat, min_lon, max_lat, max_lon = validate_coordinate(
            min_lat, min_lon, max_lat, max_lon
        )
        dggrid_instance = create_dggrid_instance()
       
        if self.canvas_extent is not None and not self.canvas_extent.isEmpty():
            bounding_box = self.canvas_extent
        else:
            bounding_box = None

        kwargs = {
            "split_dateline": self.split_antimeridian,
            "output_address_type": self.output_address_type,
        }
        dggrid_gdf = dggrid_instance.grid_cell_polygons_for_extent(
                self.dggs_type,
                self.resolution,
                clip_geom=bounding_box,
                **kwargs,
            )

        # Apply antimeridian fixing if requested
        if self.split_antimeridian:
            dggrid_gdf = dggrid_gdf.dissolve(by="global_id")

        # feedback.pushInfo(f"{self.dggs_type} DGGRID generation completed.")
        # if context.willLoadLayerOnCompletion(dest_id):
        #     lineColor = settings.DGGRID_isea3hColor
        #     fontColor = QColor("#000000")
        #     field_name = f"dggrid_{self.dggs_type}"
        #     context.layerToLoadOnCompletionDetails(dest_id).setPostProcessor(
        #         StylePostProcessor.create(lineColor, fontColor, field_name)
        #     )

        return {self.OUTPUT: dest_id}


class StylePostProcessor(QgsProcessingLayerPostProcessorInterface):
    instance = None
    line_color = None
    font_color = None
    field_name = None

    def __init__(self, line_color, font_color, field_name):
        self.line_color = line_color
        self.font_color = font_color
        self.field_name = field_name
        super().__init__()

    def postProcessLayer(self, layer, context, feedback):
        if not isinstance(layer, QgsVectorLayer):
            return
        sym = layer.renderer().symbol().symbolLayer(0)
        sym.setBrushStyle(Qt.BrushStyle.NoBrush)
        sym.setStrokeColor(self.line_color)

        if settings.gridLabel:
            label = QgsPalLayerSettings()
            label.fieldName = self.field_name
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
    def create(line_color, font_color, field_name) -> "StylePostProcessor":
        """
        Returns a new instance of the post processor, keeping a reference to the sip
        wrapper so that sip doesn't get confused with the Python subclass and call
        the base wrapper implementation instead... ahhh sip, you wonderful piece of sip
        """
        StylePostProcessor.instance = StylePostProcessor(
            line_color, font_color, field_name
        )
        return StylePostProcessor.instance
