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

__author__ = "Thang Quach"
__date__ = "2024-11-20"
__copyright__ = "(L) 2024, Thang Quach"

import os

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
    QgsCoordinateTransform,
)
from qgis.PyQt.QtGui import QIcon, QColor
from qgis.PyQt.QtCore import QCoreApplication, Qt, QVariant
from qgis.utils import iface
from dggrid4py import DGGRIDv8
from vgrid.utils.io import (
    validate_dggrid_type,
    validate_dggrid_resolution,
    validate_coordinate,
    is_full_world_bbox,
)
from vgrid.utils.geometry import dggrid_num_edges

from ...utils.dggrid_instance import (
    DGGRID_TYPES_NO_ANTIMERIDIAN,
    build_dggrid_options,
    generate_grid_qgis,
    get_plugin_dggrid_instance,
)
from vgrid.utils.constants import DGGRID_TYPES
from vgrid.utils.geometry import geodesic_dggs_metrics

from ...settings import settings
from ...utils.help_footer import social_links_footer
from ...utils.latlon import epsg4326

# Must match DGGRIDv8 (not deprecated dggrid_runner.output_address_types v7 list).
_DGGS_TYPE_OPTIONS = list(DGGRID_TYPES.keys())
_OUTPUT_ADDRESS_TYPE_OPTIONS = list(DGGRIDv8.output_address_types)
_DEFAULT_DGGS_TYPE = "ISEA3H"
_DEFAULT_OUTPUT_ADDRESS_TYPE = "SEQNUM"


def _option_index(options, name, fallback=0):
    try:
        return options.index(name)
    except ValueError:
        return fallback


class DGGRIDGen(QgsProcessingAlgorithm):
    EXTENT = "EXTENT"
    DGGS_TYPE = "DGGS_TYPE"
    RESOLUTION = "RESOLUTION"
    OUTPUT_ADDRESS_TYPE = "OUTPUT_ADDRESS_TYPE"
    SPLIT_ANTIMERIDIAN = "SPLIT_ANTIMERIDIAN"
    AGGREGATE = "AGGREGATE"
    DENSIFICATION = "DENSIFICATION"
    OUTPUT = "OUTPUT"

    LOC = QgsApplication.locale()[:2]

    def translate(self, string):
        return QCoreApplication.translate("Processing", string)

    def tr(self, *string):
        if self.LOC == "vi":
            if len(string) == 2:
                return string[1]
            return self.translate(string[0])
        return self.translate(string[0])

    def createInstance(self):
        return DGGRIDGen()

    def name(self):
        return "DGGRID_gen"

    def icon(self):
        return QIcon(
            os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "../images/generator/grid_dggrid.svg",
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
        settings.readSettings()

        self.addParameter(
            QgsProcessingParameterExtent(
                self.EXTENT, self.tr("Canvas extent"), optional=True
            )
        )

        self.addParameter(
            QgsProcessingParameterEnum(
                self.DGGS_TYPE,
                self.tr("DGGS Type"),
                options=_DGGS_TYPE_OPTIONS,
                defaultValue=_option_index(_DGGS_TYPE_OPTIONS, _DEFAULT_DGGS_TYPE),
            )
        )

        self.addParameter(
            QgsProcessingParameterNumber(
                self.RESOLUTION,
                self.tr("Resolution"),
                QgsProcessingParameterNumber.Integer,
                defaultValue=1,
                minValue=0,
                maxValue=35,
                optional=False,
            )
        )

        self.addParameter(
            QgsProcessingParameterEnum(
                self.OUTPUT_ADDRESS_TYPE,
                self.tr("Output Address Type"),
                options=_OUTPUT_ADDRESS_TYPE_OPTIONS,
                defaultValue=_option_index(
                    _OUTPUT_ADDRESS_TYPE_OPTIONS, _DEFAULT_OUTPUT_ADDRESS_TYPE
                ),
            )
        )

        self.addParameter(
            QgsProcessingParameterBoolean(
                self.SPLIT_ANTIMERIDIAN,
                self.tr("Split at Antimeridian"),
                defaultValue=False,
            )
        )

        self.addParameter(
            QgsProcessingParameterBoolean(
                self.AGGREGATE,
                self.tr("Aggregate split cells"),
                defaultValue=False,
            )
        )

        self.addParameter(
            QgsProcessingParameterNumber(
                self.DENSIFICATION,
                self.tr("Densification"),
                QgsProcessingParameterNumber.Integer,
                defaultValue=settings.dggridDensificationSpinBox,
                minValue=1,
                optional=False,
            )
        )

        self.addParameter(
            QgsProcessingParameterFeatureSink(self.OUTPUT, self.tr("DGGRID"))
        )

    def _enum_choice(self, parameters, param_name, context, options, default_name):
        index = self.parameterAsEnum(parameters, param_name, context)
        if index < 0 or index >= len(options):
            index = _option_index(options, default_name)
        return options[index]

    def prepareAlgorithm(self, parameters, context, feedback):
        self.dggs_type = validate_dggrid_type(
            self._enum_choice(
                parameters,
                self.DGGS_TYPE,
                context,
                _DGGS_TYPE_OPTIONS,
                _DEFAULT_DGGS_TYPE,
            )
        )
        self.id_field = f"dggrid_{self.dggs_type.lower()}"
        self.resolution = self.parameterAsInt(parameters, self.RESOLUTION, context)
        self.output_address_type = self._enum_choice(
            parameters,
            self.OUTPUT_ADDRESS_TYPE,
            context,
            _OUTPUT_ADDRESS_TYPE_OPTIONS,
            _DEFAULT_OUTPUT_ADDRESS_TYPE,
        )
        self.canvas_extent = self.parameterAsExtent(parameters, self.EXTENT, context)
        self.split_antimeridian = self.parameterAsBoolean(
            parameters, self.SPLIT_ANTIMERIDIAN, context
        )
        self.aggregate = self.parameterAsBoolean(parameters, self.AGGREGATE, context)
        self.densification = self.parameterAsInt(
            parameters, self.DENSIFICATION, context
        )
        self.dggrid_options = build_dggrid_options(self.densification)

        self.resolution = validate_dggrid_resolution(self.dggs_type, self.resolution)

        if self.resolution > 4 and (
            self.canvas_extent is None or self.canvas_extent.isEmpty()
        ):
            feedback.reportError(
                "For performance reason, when resolution is greater than 4, "
                "the canvas extent must be set."
            )
            return False

        if self.dggs_type in DGGRID_TYPES_NO_ANTIMERIDIAN:
            if self.split_antimeridian:
                feedback.reportError(
                    f"Split at Antimeridian is not supported for {self.dggs_type} due to the current DGGRIDv8 bugs. "
                    "Disable Split at Antimeridian or choose another DGGS type."
                )
                return False
            if self.aggregate:
                feedback.reportWarning(
                    f"Aggregate is ignored for {self.dggs_type} "
                    "(antimeridian splitting is not available for this type)."
                )
                self.aggregate = False
        elif self.aggregate and not self.split_antimeridian:
            feedback.reportWarning(
                "Aggregate split cellsSplit at Antimeridian; Aggregate will be ignored."
            )
            self.aggregate = False

        return True

    def outputFields(self):
        output_fields = QgsFields()
        output_fields.append(QgsField(self.id_field, QVariant.String))
        output_fields.append(QgsField("resolution", QVariant.Int))
        output_fields.append(QgsField("center_lat", QVariant.Double))
        output_fields.append(QgsField("center_lon", QVariant.Double))
        output_fields.append(QgsField("avg_edge_len", QVariant.Double))
        output_fields.append(QgsField("cell_area", QVariant.Double))
        output_fields.append(QgsField("cell_perimeter", QVariant.Double))
        return output_fields

    def processAlgorithm(self, parameters, context, feedback):
        fields = self.outputFields()
        sink, dest_id = self.parameterAsSink(
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
        bbox = None

        if self.canvas_extent is not None and not self.canvas_extent.isEmpty():
            try:
                min_lon = self.canvas_extent.xMinimum()
                min_lat = self.canvas_extent.yMinimum()
                max_lon = self.canvas_extent.xMaximum()
                max_lat = self.canvas_extent.yMaximum()
                if epsg4326 != canvas_crs:
                    trans_to_4326 = QgsCoordinateTransform(
                        canvas_crs, epsg4326, QgsProject.instance()
                    )
                    transformed_extent = trans_to_4326.transform(self.canvas_extent)
                    min_lon = transformed_extent.xMinimum()
                    min_lat = transformed_extent.yMinimum()
                    max_lon = transformed_extent.xMaximum()
                    max_lat = transformed_extent.yMaximum()
            except Exception:
                min_lon, min_lat, max_lon, max_lat = -180, -90, 180, 90

            min_lon, min_lat, max_lon, max_lat = validate_coordinate(
                min_lon, min_lat, max_lon, max_lat
            )
            bbox = [min_lon, min_lat, max_lon, max_lat]
            if is_full_world_bbox(bbox):
                bbox = None

        feedback.pushInfo(
            f"Generating DGGRID {self.dggs_type} cells at resolution {self.resolution} "
            f"(output address type: {self.output_address_type})."
        )
        dggrid_instance = get_plugin_dggrid_instance(feedback=feedback)
        dggrid_gdf = generate_grid_qgis(
            dggrid_instance,
            self.dggs_type,
            self.resolution,
            bbox,
            output_address_type=self.output_address_type,
            split_antimeridian=self.split_antimeridian,
            aggregate=self.aggregate,
            options=self.dggrid_options,
        )

        if dggrid_gdf is None or dggrid_gdf.empty:
            feedback.pushInfo("No DGGRID cells generated for the given parameters.")
            return {self.OUTPUT: dest_id}

        if "global_id" in dggrid_gdf.columns:
            dggrid_gdf = dggrid_gdf.rename(columns={"global_id": self.id_field})
        elif self.id_field not in dggrid_gdf.columns and "name" in dggrid_gdf.columns:
            dggrid_gdf = dggrid_gdf.rename(columns={"name": self.id_field})

        total_cells = len(dggrid_gdf)
        feedback.pushInfo(f"Total cells to be generated: {total_cells}.")
        num_edges = dggrid_num_edges(self.dggs_type)

        for idx, row in dggrid_gdf.iterrows():
            if feedback.isCanceled():
                break

            progress = int((idx / total_cells) * 100) if total_cells else 100
            feedback.setProgress(progress)

            cell_polygon = row.geometry
            if cell_polygon is None or cell_polygon.is_empty:
                continue

            cell_id = row.get(self.id_field)
            if cell_id is None:
                continue

            center_lat, center_lon, avg_edge_len, cell_area, cell_perimeter = (
                geodesic_dggs_metrics(cell_polygon, num_edges)
            )

            feature = QgsFeature()
            feature.setGeometry(QgsGeometry.fromWkt(cell_polygon.wkt))
            feature.setAttributes(
                [
                    str(cell_id),
                    self.resolution,
                    center_lat,
                    center_lon,
                    avg_edge_len,
                    cell_area,
                    cell_perimeter,
                ]
            )
            sink.addFeature(feature, QgsFeatureSink.FastInsert)

        feedback.pushInfo(f"{self.dggs_type} DGGRID generation completed.")

        if context.willLoadLayerOnCompletion(dest_id):
            line_color = settings.isea3hColor
            font_color = QColor("#000000")
            context.layerToLoadOnCompletionDetails(dest_id).setPostProcessor(
                StylePostProcessor.create(line_color, font_color, self.id_field)
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

        iface.mapCanvas().refresh()

    @staticmethod
    def create(line_color, font_color, field_name) -> "StylePostProcessor":
        StylePostProcessor.instance = StylePostProcessor(
            line_color, font_color, field_name
        )
        return StylePostProcessor.instance
