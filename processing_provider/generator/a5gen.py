# -*- coding: utf-8 -*-
"""
a5gen.py
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
from qgis.PyQt.QtGui import QIcon, QColor
from qgis.PyQt.QtCore import QCoreApplication, Qt
from qgis.utils import iface
from PyQt5.QtCore import QVariant
import os
from ...utils.imgs import Imgs
from vgrid.utils.geometry import geodesic_dggs_metrics
from vgrid.conversion.dggs2geo.a52geo import a52geo
from vgrid.conversion.latlon2dggs import latlon2a5
from ...settings import settings
from vgrid.utils.io import validate_coordinate
from qgis.core import QgsCoordinateTransform
from ...utils.latlon import epsg4326
from vgrid.utils.antimeridian import fix_polygon


class A5Gen(QgsProcessingAlgorithm):
    EXTENT = "EXTENT"
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
        return A5Gen()

    def name(self):
        return "a5_gen"

    def icon(self):
        return QIcon(
            os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "../images/generator/grid_a5.svg",
            )
        )

    def displayName(self):
        return self.tr("A5", "A5")

    def group(self):
        return self.tr("Generator", "Generator")

    def groupId(self):
        return "generator"

    def tags(self):
        return self.tr("DGGS, A5, generator").split(",")

    txt_en = "A5 DGGS Generator"
    txt_vi = "A5 DGGS Generator"
    figure = "../images/tutorial/grid_a5.png"

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
        min_res, max_res, _ = settings.getResolution("A5")
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
            self.SPLIT_ANTIMERIDIAN,
            self.tr("Split at Antimeridian"),
            defaultValue=False,
        )
        self.addParameter(param)

        param = QgsProcessingParameterFeatureSink(self.OUTPUT, "A5")
        self.addParameter(param)

    def prepareAlgorithm(self, parameters, context, feedback):
        self.resolution = self.parameterAsInt(parameters, self.RESOLUTION, context)
        # Get the extent parameter
        self.canvas_extent = self.parameterAsExtent(parameters, self.EXTENT, context)
        self.split_antimeridian = self.parameterAsBoolean(
            parameters, self.SPLIT_ANTIMERIDIAN, context
        )
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
        output_fields.append(QgsField("a5", QVariant.String))
        output_fields.append(QgsField("resolution", QVariant.Int))
        output_fields.append(QgsField("center_lat", QVariant.Double))
        output_fields.append(QgsField("center_lon", QVariant.Double))
        output_fields.append(QgsField("avg_edge_len", QVariant.Double))
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
        # Calculate longitude and latitude width based on resolution
        if self.resolution == 0:
            lon_width = 35
            lat_width = 35
        elif self.resolution == 1:
            lon_width = 18
            lat_width = 18
        elif self.resolution == 2:
            lon_width = 10
            lat_width = 10
        elif self.resolution == 3:
            lon_width = 5
            lat_width = 5
        elif self.resolution > 3:
            base_width = 5  # at resolution 3
            factor = 0.5 ** (self.resolution - 3)
            lon_width = base_width * factor
            lat_width = base_width * factor

        # Generate longitude and latitude arrays
        longitudes = []
        latitudes = []

        lon = min_lon
        while lon < max_lon:
            longitudes.append(lon)
            lon += lon_width

        lat = min_lat
        while lat < max_lat:
            latitudes.append(lat)
            lat += lat_width

        seen_a5_hex = set()  # Track unique A5 hex codes
        total_cells = len(longitudes) * len(latitudes)
        feedback.pushInfo(f"Total grid points to process: {total_cells}.")

        cell_count = 0

        # Generate features for each grid cell
        for i, lon in enumerate(longitudes):
            for j, lat in enumerate(latitudes):
                if feedback.isCanceled():
                    break

                progress = int(((i * len(latitudes) + j) / total_cells) * 100)
                feedback.setProgress(progress)

                min_lon = lon
                min_lat = lat
                max_lon = lon + lon_width
                max_lat = lat + lat_width

                # Calculate centroid
                centroid_lat = (min_lat + max_lat) / 2
                centroid_lon = (min_lon + max_lon) / 2

                try:
                    # Convert centroid to A5 cell ID using direct A5 functions
                    a5_hex = latlon2a5(centroid_lat, centroid_lon, self.resolution)
                    cell_polygon = a52geo(a5_hex)

                    if cell_polygon is not None:
                        # Only add if this A5 hex code hasn't been seen before
                        if a5_hex not in seen_a5_hex:
                            seen_a5_hex.add(a5_hex)
                            # Apply antimeridian fix if requested
                            if self.split_antimeridian:
                                cell_polygon = fix_polygon(cell_polygon)
                            cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)
                            a5_feature = QgsFeature()
                            a5_feature.setGeometry(cell_geometry)

                            num_edges = 5
                            (
                                center_lat,
                                center_lon,
                                avg_edge_len,
                                cell_area,
                                cell_perimeter,
                            ) = geodesic_dggs_metrics(cell_polygon, num_edges)
                            a5_feature.setAttributes(
                                [
                                    a5_hex,
                                    self.resolution,
                                    center_lat,
                                    center_lon,
                                    avg_edge_len,
                                    cell_area,
                                    cell_perimeter,
                                ]
                            )
                            sink.addFeature(a5_feature, QgsFeatureSink.FastInsert)
                            cell_count += 1

                except Exception:
                    # Skip cells that can't be processed
                    continue

            if feedback.isCanceled():
                break

        feedback.pushInfo(
            f"A5 DGGS generation completed. Generated {cell_count} unique cells."
        )
        if context.willLoadLayerOnCompletion(dest_id):
            lineColor = settings.a5Color
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
            label.fieldName = "a5"
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
