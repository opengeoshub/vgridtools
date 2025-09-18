# -*- coding: utf-8 -*-
"""
isea4tgen.py
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
    QgsCoordinateTransform,
    QgsFeatureSink,
    QgsProcessingLayerPostProcessorInterface,
    QgsProcessingParameterExtent,
    QgsProcessingParameterNumber,
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
import os, platform

if platform.system() == "Windows":
    from vgrid.dggs.eaggr.eaggr import Eaggr
    from vgrid.dggs.eaggr.shapes.dggs_cell import DggsCell
    from vgrid.dggs.eaggr.enums.shape_string_format import ShapeStringFormat
    from vgrid.dggs.eaggr.enums.model import Model
    from vgrid.generator.isea4tgrid import (
        get_isea4t_children_cells,
        get_isea4t_children_cells_within_bbox,
    )
    from vgrid.utils.constants import ISEA4T_BASE_CELLS
    from vgrid.conversion.dggs2geo import isea4t2geo
    isea4t_dggs = Eaggr(Model.ISEA4T)

from ...utils.imgs import Imgs
from shapely.geometry import box
from ...settings import settings
from vgrid.utils.constants import ISEA4T_RES_ACCURACY_DICT
from vgrid.utils.geometry import geodesic_dggs_metrics
from vgrid.utils.io import validate_coordinate
from ...utils.latlon import epsg4326


class ISEA4TGen(QgsProcessingAlgorithm):
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
        return ISEA4TGen()

    def name(self):
        return "isea4t_gen"

    def icon(self):
        return QIcon(
            os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "../images/generator/grid_triangle.svg",
            )
        )

    def displayName(self):
        return self.tr("ISEA4T", "ISEA4T")

    def group(self):
        return self.tr("Generator", "Generator")

    def groupId(self):
        return "generator"

    def tags(self):
        return self.tr("DGGS, ISEA4T, generator").split(",")      

    txt_en = "ISEA4T DGGS Generator"
    txt_vi = "ISEA4T DGGS Generator"
    figure = "../images/tutorial/grid_isea4t.png"

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

        min_res, max_res, _ = settings.getResolution("ISEA4T")
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

        param = QgsProcessingParameterFeatureSink(self.OUTPUT, "ISEA4T")
        self.addParameter(param)

    def prepareAlgorithm(self, parameters, context, feedback):
        self.resolution = self.parameterAsInt(parameters, self.RESOLUTION, context)
        self.canvas_extent = self.parameterAsExtent(parameters, self.EXTENT, context)
        if self.resolution > 8 and (
            self.canvas_extent is None or self.canvas_extent.isEmpty()
        ):
            feedback.reportError(
                "For performance reason, when resolution is greater than 8, the canvas extent must be set."
            )
            return False

        return True

    def outputFields(self):
        output_fields = QgsFields()
        output_fields.append(QgsField("isea4t", QVariant.String))
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

        canvas_crs = QgsProject.instance().crs()

        if self.canvas_extent is None or self.canvas_extent.isEmpty():
            extent_bbox = None
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
                    transformed_extent = trans_to_4326.transform(self.canvas_extent)              
                    min_lon, min_lat, max_lon, max_lat = (
                        transformed_extent.xMinimum(),
                        transformed_extent.yMinimum(),
                        transformed_extent.xMaximum(),
                        transformed_extent.yMaximum(),
                    )     
            except Exception as e: 
                min_lon, min_lat, max_lon, max_lat = -180, -90, 180, 90

            min_lat, min_lon, max_lat, max_lon = validate_coordinate(min_lat, min_lon, max_lat, max_lon)
            extent_bbox = box(min_lon, min_lat, max_lon, max_lat)

        if platform.system() == "Windows":
            if extent_bbox:
                accuracy = ISEA4T_RES_ACCURACY_DICT.get(self.resolution)
                extent_bbox_wkt = extent_bbox.wkt  # Create a bounding box polygon
                shapes = isea4t_dggs.convert_shape_string_to_dggs_shapes(
                    extent_bbox_wkt, ShapeStringFormat.WKT, accuracy
                )
                shape = shapes[0]
                bbox_cells = shape.get_shape().get_outer_ring().get_cells()
                bounding_cell = isea4t_dggs.get_bounding_dggs_cell(bbox_cells)
                bounding_children = get_isea4t_children_cells_within_bbox(
                    bounding_cell.get_cell_id(), extent_bbox, self.resolution
                )
                total_bounding_children = len(bounding_children)
                feedback.pushInfo(
                    f"Total cells to be generated: {total_bounding_children}."
                )

                for idx, child in enumerate(bounding_children):
                    progress = int((idx / total_bounding_children) * 100)
                    feedback.setProgress(progress)

                    isea4t_cell = DggsCell(child)
                    isea4t_id = isea4t_cell.get_cell_id()
                    cell_polygon = isea4t2geo(isea4t_id)
                    cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)
                    isea4t_feature = QgsFeature()
                    isea4t_feature.setGeometry(cell_geometry)

                    num_edges = 3
                    center_lat, center_lon, avg_edge_len, cell_area, cell_perimeter = (
                        geodesic_dggs_metrics(cell_polygon, num_edges)
                    )
                    isea4t_feature.setAttributes(
                        [
                            isea4t_id,
                            self.resolution,
                            center_lat,
                            center_lon,
                            avg_edge_len,
                            cell_area,
                            cell_perimeter,
                        ]
                    )
                    sink.addFeature(isea4t_feature, QgsFeatureSink.FastInsert)

                    if feedback.isCanceled():
                        break
            else:
                total_cells = 20 * (4**self.resolution)
                feedback.pushInfo(f"Total cells to be generated: {total_cells}.")

                children = get_isea4t_children_cells(ISEA4T_BASE_CELLS, self.resolution)
                for idx, child in enumerate(children):
                    progress = int((idx / total_cells) * 100)
                    feedback.setProgress(progress)

                    isea4t_cell = DggsCell(child)
                    isea4t_id = isea4t_cell.get_cell_id()
                    cell_polygon = isea4t2geo(isea4t_id)                   
                    cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)
                    isea4t_feature = QgsFeature()
                    isea4t_feature.setGeometry(cell_geometry)

                    num_edges = 3
                    center_lat, center_lon, avg_edge_len, cell_area, cell_perimeter = (
                        geodesic_dggs_metrics(cell_polygon, num_edges)
                    )
                    isea4t_feature.setAttributes(
                        [
                            isea4t_id,
                            self.resolution,
                            center_lat,
                            center_lon,
                            avg_edge_len,
                            cell_area,
                            cell_perimeter,
                        ]
                    )
                    sink.addFeature(isea4t_feature, QgsFeatureSink.FastInsert)

                    if feedback.isCanceled():
                        break

            feedback.pushInfo("ISEA4T DGGS generation completed.")
            if context.willLoadLayerOnCompletion(dest_id):
                lineColor = settings.isea4tColor
                fontColor = QColor("#000000")
                context.layerToLoadOnCompletionDetails(dest_id).setPostProcessor(
                    StylePostProcessor.create(lineColor, fontColor)
                )

            return {self.OUTPUT: dest_id}
        else:
            return {}


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
            label.fieldName = "isea4t"
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
