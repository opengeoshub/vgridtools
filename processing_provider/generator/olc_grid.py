# -*- coding: utf-8 -*-
"""
olc_grid.py
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
from PyQt5.QtCore import QVariant
import os

from vgrid.dggs import olc
from vgrid.generator.olcgrid import olc_grid, olc_refine_cell
from vgrid.utils.geometry import graticule_dggs_metrics, graticule_dggs_to_geoseries
import geopandas as gpd

from ...utils.imgs import Imgs
from ...settings import settings
from shapely.geometry import Polygon, box


class OLCGrid(QgsProcessingAlgorithm):
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
        return OLCGrid()

    def name(self):
        return "grid_olc"

    def icon(self):
        return QIcon(
            os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "../images/generator/grid_olc.svg",
            )
        )

    def displayName(self):
        return self.tr("OLC", "OLC")

    def group(self):
        return self.tr("Generator", "Generator")

    def groupId(self):
        return "grid"

    def tags(self):
        return self.tr("OLC, grid, generator").split(",")

    txt_en = "OLC DGGS Generator"
    txt_vi = "OLC DGGS Generator"
    figure = "../images/tutorial/grid_olc.png"

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

        min_res, max_res, _ = settings.getResolution("OLC")
        param = QgsProcessingParameterNumber(
            self.RESOLUTION,
            self.tr(f"Resolution/ Code length [{min_res}..{max_res}]"),
            QgsProcessingParameterNumber.Integer,
            defaultValue=2,
            minValue=min_res,
            maxValue=max_res,
            optional=False,
        )
        self.addParameter(param)

        param = QgsProcessingParameterFeatureSink(self.OUTPUT, "OLC")
        self.addParameter(param)

    def prepareAlgorithm(self, parameters, context, feedback):
        self.resolution = self.parameterAsInt(parameters, self.RESOLUTION, context)

        if self.resolution not in [2, 4, 6, 8, 10, 11, 12, 13, 14, 15]:
            feedback.reportError(
                "Please select a resolution in [2, 4, 6, 8, 10..15] and try again."
            )
            return False

        # Get the extent parameter
        self.grid_extent = self.parameterAsExtent(parameters, self.EXTENT, context)

        if self.resolution > 4 and (
            self.grid_extent is None or self.grid_extent.isEmpty()
        ):
            feedback.reportError(
                "For performance reason, when resolutin/ code length is greater than 4, the grid extent must be set."
            )
            return False

        return True

    def outputFields(self):
        output_fields = QgsFields()
        output_fields.append(QgsField("olc", QVariant.String))
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

        if not sink:
            raise QgsProcessingException(self.invalidSinkError(parameters, self.OUTPUT))

        if self.grid_extent is None or self.grid_extent.isEmpty():
            extent_bbox = None
        else:
            extent_bbox = box(
                self.grid_extent.xMinimum(),
                self.grid_extent.yMinimum(),
                self.grid_extent.xMaximum(),
                self.grid_extent.yMaximum(),
            )
        if extent_bbox:
            # Generate grid within bounding box - implement directly
            min_lon, min_lat, max_lon, max_lat = extent_bbox.bounds
            bbox_poly = box(min_lon, min_lat, max_lon, max_lat)

            # Step 1: Generate base cells at the lowest resolution (e.g., resolution 2)
            base_resolution = 2
            base_gdf = olc_grid(base_resolution, verbose=False)

            # Step 2: Identify seed cells that intersect with the bounding box
            seed_cells = []
            for idx, base_cell in base_gdf.iterrows():
                base_cell_poly = base_cell["geometry"]
                if bbox_poly.intersects(base_cell_poly):
                    seed_cells.append(base_cell)

            refined_records = []

            # Step 3: Iterate over seed cells and refine to the output resolution
            for seed_cell in seed_cells:
                seed_cell_poly = seed_cell["geometry"]

                if (
                    seed_cell_poly.contains(bbox_poly)
                    and self.resolution == base_resolution
                ):
                    # Append the seed cell directly if fully contained and resolution matches
                    refined_records.append(seed_cell)
                else:
                    # Refine the seed cell to the output resolution and add it to the output
                    refined_records.extend(
                        olc_refine_cell(
                            seed_cell_poly.bounds,
                            base_resolution,
                            self.resolution,
                            bbox_poly,
                        )
                    )

            # Filter to target resolution and remove duplicates
            final_records = [
                record
                for record in refined_records
                if record["resolution"] == self.resolution
            ]

            # Remove duplicates based on OLC ID
            seen_olc_ids = set()
            unique_records = []
            for record in final_records:
                olc_id = record["olc"]
                if olc_id not in seen_olc_ids:
                    unique_records.append(record)
                    seen_olc_ids.add(olc_id)

            # Convert to QgsFeature directly
            total_features = len(unique_records)
            feedback.pushInfo(f"Processing {total_features} OLC grid cells...")

            for i, record in enumerate(unique_records):
                if feedback.isCanceled():
                    break

                progress = int((i / total_features) * 100)
                feedback.setProgress(progress)

                cell_polygon = record["geometry"]
                olc_id = record["olc"]
                cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)

                olc_feature = QgsFeature()
                olc_feature.setGeometry(cell_geometry)
                (
                    center_lat,
                    center_lon,
                    cell_width,
                    cell_height,
                    cell_area,
                    cell_perimeter,
                ) = graticule_dggs_metrics(cell_polygon)
                olc_feature.setAttributes(
                    [
                        olc_id,
                        self.resolution,
                        center_lat,
                        center_lon,
                        cell_width,
                        cell_height,
                        cell_area,
                        cell_perimeter,
                    ]
                )
                sink.addFeature(olc_feature, QgsFeatureSink.FastInsert)
        else:
            # Define the boundaries of the world
            sw_lat, sw_lng = -90, -180
            ne_lat, ne_lng = 90, 180

            # Get the precision step size
            area = olc.decode(olc.encode(sw_lat, sw_lng, self.resolution))
            lat_step = area.latitudeHi - area.latitudeLo
            lng_step = area.longitudeHi - area.longitudeLo

            # Calculate the total number of steps for progress tracking
            total_lat_steps = int((ne_lat - sw_lat) / lat_step)
            total_lng_steps = int((ne_lng - sw_lng) / lng_step)
            total_steps = total_lat_steps * total_lng_steps

            feedback.pushInfo(f"Processing {total_steps} global OLC grid cells...")

            current_step = 0
            lat = sw_lat
            while lat < ne_lat:
                lng = sw_lng
                while lng < ne_lng:
                    if feedback.isCanceled():
                        break

                    # Generate the Plus Code for the center of the cell
                    center_lat = lat + lat_step / 2
                    center_lon = lng + lng_step / 2
                    olc_id = olc.encode(center_lat, center_lon, self.resolution)
                    cell_polygon = Polygon(
                        [
                            [lng, lat],  # SW
                            [lng, lat + lat_step],  # NW
                            [lng + lng_step, lat + lat_step],  # NE
                            [lng + lng_step, lat],  # SE
                            [lng, lat],  # Close the polygon
                        ]
                    )

                    # Create QgsFeature directly
                    cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)
                    olc_feature = QgsFeature()
                    olc_feature.setGeometry(cell_geometry)

                    (
                        center_lat,
                        center_lon,
                        cell_width,
                        cell_height,
                        cell_area,
                        cell_perimeter,
                    ) = graticule_dggs_metrics(cell_polygon)

                    olc_feature.setAttributes(
                        [
                            olc_id,
                            self.resolution,
                            center_lat,
                            center_lon,
                            cell_width,
                            cell_height,
                            cell_area,
                            cell_perimeter,
                        ]
                    )
                    sink.addFeature(olc_feature, QgsFeatureSink.FastInsert)

                    lng += lng_step
                    current_step += 1

                    # Update QGIS progress
                    progress = int((current_step / total_steps) * 100)
                    feedback.setProgress(progress)
                lat += lat_step

        feedback.pushInfo("OLC DGGS generation completed.")
        if context.willLoadLayerOnCompletion(dest_id):
            lineColor = settings.olcColor
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
            label.fieldName = "olc"
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
