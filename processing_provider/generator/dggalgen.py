# -*- coding: utf-8 -*-
"""
dggalgen.py
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
from PyQt5.QtCore import QVariant
from qgis.core import QgsCoordinateTransform
import os
from ...settings import settings
from dggal import *

# Initialize dggal application
app = Application(appGlobals=globals())
pydggal_setup(app)

from ...utils.imgs import Imgs
from ...utils.latlon import epsg4326
from vgrid.utils.geometry import geodesic_dggs_metrics, dggal_to_geo
from vgrid.utils.constants import DGGAL_TYPES
from vgrid.utils.io import validate_dggal_resolution
from vgrid.utils.io import validate_coordinate
from vgrid.utils.antimeridian import fix_polygon


class DGGALGen(QgsProcessingAlgorithm):
    EXTENT = "EXTENT"
    DGGS_TYPE = "DGGS_TYPE"
    RESOLUTION = "RESOLUTION"
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
        return DGGALGen()

    def name(self):
        return "dggal_gen"

    def icon(self):
        return QIcon(
            os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "../images/generator/grid_dggal.svg",
            )
        )

    def displayName(self):
        return self.tr("DGGAL", "DGGAL")

    def group(self):
        return self.tr("Generator", "Generator")

    def groupId(self):
        return "generator"

    def tags(self):
        return self.tr("DGGS, DGGAL, generator").split(",")

    txt_en = "DGGAL Generator"
    txt_vi = "DGGAL Generator"
    figure = "../images/tutorial/grid_dggal.png"

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
            options=[key for key in DGGAL_TYPES.keys()],
            defaultValue="gnosis",
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

        param = QgsProcessingParameterBoolean(
            self.SPLIT_ANTIMERIDIAN,
            self.tr("Split at Antimeridian"),
            defaultValue=False,
        )
        self.addParameter(param)

        param = QgsProcessingParameterFeatureSink(self.OUTPUT, self.tr("DGGAL"))
        self.addParameter(param)

    def prepareAlgorithm(self, parameters, context, feedback):
        dggs_type_index = self.parameterAsEnum(parameters, self.DGGS_TYPE, context)
        self.dggs_type = list(DGGAL_TYPES.keys())[dggs_type_index]
        self.resolution = self.parameterAsInt(parameters, self.RESOLUTION, context)
        self.canvas_extent = self.parameterAsExtent(parameters, self.EXTENT, context)
        self.split_antimeridian = self.parameterAsBoolean(
            parameters, self.SPLIT_ANTIMERIDIAN, context
        )

        # Validate resolution for the selected DGGS type
        self.resolution = validate_dggal_resolution(self.dggs_type, self.resolution)

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
        output_fields.append(QgsField(f"dggal_{self.dggs_type}", QVariant.String))
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

        dggs_class_name = DGGAL_TYPES[self.dggs_type]["class_name"]
        dggrs = globals()[dggs_class_name]()

        if not sink:
            raise QgsProcessingException(self.invalidSinkError(parameters, self.OUTPUT))
        canvas_crs = QgsProject.instance().crs()

        if self.canvas_extent is None or self.canvas_extent.isEmpty():
            min_lon, min_lat, max_lon, max_lat = -180, -90, 180, 90  # Whole world
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
                min_lon, min_lat, max_lon, max_lat = -180, -90, 180, 90

        min_lat, min_lon, max_lat, max_lon = validate_coordinate(
            min_lat, min_lon, max_lat, max_lon
        )
        ll = GeoPoint(min_lat, min_lon)
        ur = GeoPoint(max_lat, max_lon)
        geo_extent = GeoExtent(ll, ur)

        zones = dggrs.listZones(self.resolution, geo_extent)

        total_cells = len(zones)
        feedback.pushInfo(f"Total cells to be generated: {total_cells}.")
        for idx, zone in enumerate(zones):
            progress = int((idx / total_cells) * 100)
            feedback.setProgress(progress)
            zone_id = dggrs.getZoneTextID(zone)
            num_edges = dggrs.countZoneEdges(zone)
            cell_resolution = dggrs.getZoneLevel(zone)
            # Convert zone to geometry using dggal2geo
            cell_polygon = dggal_to_geo(self.dggs_type, zone_id)
            # Apply antimeridian fix if requested
            if self.split_antimeridian:
                cell_polygon = fix_polygon(cell_polygon)
            cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)
            # Only check intersection if we have a valid extent
            if self.canvas_extent and not self.canvas_extent.isEmpty():
                if not cell_geometry.intersects(
                    QgsGeometry.fromRect(self.canvas_extent)
                ):
                    continue
            dggal_feature = QgsFeature()
            dggal_feature.setGeometry(cell_geometry)
            center_lat, center_lon, avg_edge_len, cell_area, cell_perimeter = (
                geodesic_dggs_metrics(cell_polygon, num_edges)
            )
            dggal_feature.setAttributes(
                [
                    zone_id,
                    cell_resolution,
                    center_lat,
                    center_lon,
                    avg_edge_len,
                    cell_area,
                    cell_perimeter,
                ]
            )
            sink.addFeature(dggal_feature, QgsFeatureSink.FastInsert)

            if feedback.isCanceled():
                break

        feedback.pushInfo(f"{self.dggs_type} DGGS generation completed.")
        if context.willLoadLayerOnCompletion(dest_id):
            lineColor = settings.dggal_gnosisColor
            fontColor = QColor("#000000")
            field_name = f"dggal_{self.dggs_type}"
            context.layerToLoadOnCompletionDetails(dest_id).setPostProcessor(
                StylePostProcessor.create(lineColor, fontColor, field_name)
            )

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
        sym.setBrushStyle(Qt.NoBrush)
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
