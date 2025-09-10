# -*- coding: utf-8 -*-
"""
mgrs_grid.py
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
    QgsProcessingParameterString,
    QgsProcessingParameterNumber,
    QgsProcessingParameterFeatureSink,
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsFields,
    QgsField,
    QgsFeature,
    QgsGeometry,
    QgsWkbTypes,
    QgsCoordinateReferenceSystem,
    QgsVectorLayer,
    QgsPalLayerSettings,
    QgsVectorLayerSimpleLabeling,
    QgsCoordinateTransform,
    QgsProject,
)

from qgis.PyQt.QtGui import QIcon, QColor
from qgis.PyQt.QtCore import QCoreApplication, QSettings, Qt
from qgis.core import QgsApplication
from qgis.utils import iface
from PyQt5.QtCore import QVariant
import os, random
from vgrid.dggs import mgrs
from ...utils.imgs import Imgs
from ...settings import settings
from vgrid.generator.mgrsgrid import is_valid_gzd
import json
from shapely.geometry import shape, Polygon
from shapely.wkt import loads
import numpy as np
from vgrid.utils.geometry import graticule_dggs_metrics


class MGRSGrid(QgsProcessingAlgorithm):
    GZD = "GZD"
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
        return MGRSGrid()

    def name(self):
        return "grid_mgrs"

    def icon(self):
        return QIcon(
            os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "../images/generator/grid_quad.svg",
            )
        )

    def displayName(self):
        return self.tr("MGRS", "MGRS")

    def group(self):
        return self.tr("Generator", "Generator")

    def groupId(self):
        return "grid"

    def tags(self):
        return self.tr("DGGS, grid, MGRS, generator").split(",")

    txt_en = "MGRS DGGS Generator"
    txt_vi = "MGRS DGGS Generator"
    figure = "../images/tutorial/grid_mgrs.png"

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
        # GZD
        param = QgsProcessingParameterString(
            self.GZD, self.tr("GZD"), defaultValue="48P", optional=False
        )
        self.addParameter(param)

        min_res, max_res, _ = settings.getResolution("MGRS")
        param = QgsProcessingParameterNumber(
            self.RESOLUTION,
            self.tr(f"Resolution [{min_res}..{max_res}]"),
            QgsProcessingParameterNumber.Integer,
            defaultValue=0,
            minValue=min_res,
            maxValue=max_res,
            optional=False,
        )
        self.addParameter(param)

        param = QgsProcessingParameterFeatureSink(self.OUTPUT, "MGRS")
        self.addParameter(param)

    def prepareAlgorithm(self, parameters, context, feedback):
        self.resolution = self.parameterAsInt(parameters, self.RESOLUTION, context)
        self.gzd = self.parameterAsString(parameters, self.GZD, context).upper()
        if self.resolution > 2:
            feedback.reportError(
                "For performance reason, resolution must be smaller than 2 (1000 x 1000 km cell size)"
            )
            return False

        if not is_valid_gzd(self.gzd):
            feedback.reportError("Please input a valid GZD")
            return False

        return True

    def outputFields(self):
        output_fields = QgsFields()
        output_fields.append(QgsField("mgrs", QVariant.String))
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

        cell_size = 100_000 // (10**self.resolution)
        north_bands = "NPQRSTUVWX"
        south_bands = "MLKJHGFEDC"
        band_distance = 111_132 * 8
        gzd_band = self.gzd[2]

        if gzd_band >= "N":  # North Hemesphere
            epsg_code = int("326" + self.gzd[:2])
            min_x, min_y, max_x, max_y = 100000, 0, 900000, 9500000  # for the North
            north_band_idx = north_bands.index(gzd_band)
            max_y = band_distance * (north_band_idx + 1)
            if gzd_band == "X":
                max_y += band_distance  # band X = 12 deggrees instead of 8 degrees

        else:  # South Hemesphere
            epsg_code = int("327" + self.gzd[:2])
            min_x, min_y, max_x, max_y = 100000, 0, 900000, 10000000  # for the South
            south_band_idx = south_bands.index(gzd_band)
            max_y = band_distance * (south_band_idx + 1)

        utm_crs = QgsCoordinateReferenceSystem(epsg_code)
        wgs84_crs = QgsCoordinateReferenceSystem(4326)  # WGS84

        transform_context = QgsProject.instance().transformContext()
        transformer = QgsCoordinateTransform(utm_crs, wgs84_crs, transform_context)
        gzd_json_path = os.path.join(os.path.dirname(__file__), "gzd.geojson")
        with open(gzd_json_path, "r") as f:
            gzd_data = json.load(f)

        gzd_features = gzd_data["features"]
        gzd_feature = [
            feature
            for feature in gzd_features
            if feature["properties"].get("gzd") == self.gzd
        ][0]
        gzd_geom = shape(gzd_feature["geometry"])

        x_coords = np.arange(min_x, max_x, cell_size)
        y_coords = np.arange(min_y, max_y, cell_size)
        total_cells = len(x_coords) * len(y_coords)
        feedback.pushInfo(f"Total cells to be processed: {total_cells}.")

        current_step = 0  # Track current step
        for x in x_coords:
            for y in y_coords:
                current_step += 1
                progress = int((current_step / total_cells) * 100)
                feedback.setProgress(progress)

                cell_polygon_utm = Polygon(
                    [
                        (x, y),
                        (x + cell_size, y),
                        (x + cell_size, y + cell_size),
                        (x, y + cell_size),
                        (x, y),  # Close the polygon
                    ]
                )
                cell_geometry_utm = QgsGeometry.fromWkt(cell_polygon_utm.wkt)
                cell_geometry_utm.transform(transformer)
                cell_polygon = loads(cell_geometry_utm.asWkt())

                if cell_polygon.intersects(gzd_geom):
                    centroid_lat, centroid_lon = (
                        cell_polygon.centroid.y,
                        cell_polygon.centroid.x,
                    )
                    mgrs_id = mgrs.toMgrs(centroid_lat, centroid_lon, self.resolution)
                    cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)

                    mgrs_feature = QgsFeature()
                    mgrs_feature.setGeometry(cell_geometry)
                    (
                        center_lat,
                        center_lon,
                        cell_width,
                        cell_height,
                        cell_area,
                        cell_perimeter,
                    ) = graticule_dggs_metrics(cell_polygon)
                    mgrs_feature.setAttributes(
                        [
                            mgrs_id,
                            self.resolution,
                            center_lat,
                            center_lon,
                            cell_width,
                            cell_height,
                            cell_area,
                            cell_perimeter,
                        ]
                    )
                    if not gzd_geom.contains(cell_polygon):
                        intersected_polygon = cell_polygon.intersection(gzd_geom)
                        if intersected_polygon:
                            intersected_centroid_lat, intersected_centroid_lon = (
                                intersected_polygon.centroid.y,
                                intersected_polygon.centroid.x,
                            )
                            interescted_mgrs_id = mgrs.toMgrs(
                                intersected_centroid_lat,
                                intersected_centroid_lon,
                                self.resolution,
                            )
                            (
                                center_lat,
                                center_lon,
                                cell_width,
                                cell_height,
                                cell_area,
                                cell_perimeter,
                            ) = graticule_dggs_metrics(intersected_polygon)
                            cell_geometry = QgsGeometry.fromWkt(intersected_polygon.wkt)
                            mgrs_feature.setGeometry(cell_geometry)
                            mgrs_feature.setAttributes(
                                [
                                    interescted_mgrs_id,
                                    self.resolution,
                                    center_lat,
                                    center_lon,
                                    cell_width,
                                    cell_height,
                                    cell_area,
                                    cell_perimeter,
                                ]
                            )

                    sink.addFeature(mgrs_feature, QgsFeatureSink.FastInsert)

                if feedback.isCanceled():
                    break

        feedback.pushInfo("MGRS DGGS generation completed.")
        # Apply styling (optional)
        if context.willLoadLayerOnCompletion(dest_id):
            lineColor = QColor.fromRgb(
                random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)
            )
            fontColor = QColor("#000000")  # Black font
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
        label = QgsPalLayerSettings()
        label.fieldName = "mgrs"
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
