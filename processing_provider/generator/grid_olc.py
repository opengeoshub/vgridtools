# -*- coding: utf-8 -*-
"""
grid_olc.py
***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 2 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************
"""
__author__ = 'Thang Quach'
__date__ = '2024-11-20'
__copyright__ = '(L) 2024, Thang Quach'

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
    QgsVectorLayerSimpleLabeling
)

from qgis.PyQt.QtGui import QIcon, QColor
from qgis.PyQt.QtCore import QCoreApplication,QSettings,Qt
from qgis.utils import iface
from PyQt5.QtCore import QVariant
import os, random

from vgrid.utils import olc
from vgrid.generator.olcgrid import generate_grid, refine_cell
from vgrid.generator.settings import graticule_dggs_metrics
from ...utils.imgs import Imgs
from shapely.geometry import Polygon,box


class GridOLC(QgsProcessingAlgorithm):
    EXTENT = 'EXTENT'
    RESOLUTION = 'RESOLUTION'
    OUTPUT = 'OUTPUT'
    
    LOC = QgsApplication.locale()[:2]

    def translate(self, string):
        return QCoreApplication.translate('Processing', string)

    def tr(self, *string):
        # Translate to Vietnamese: arg[0] - English (translate), arg[1] - Vietnamese
        if self.LOC == 'vi':
            if len(string) == 2:
                return string[1]
            else:
                return self.translate(string[0])
        else:
            return self.translate(string[0])
    
    def createInstance(self):
        return GridOLC()

    def name(self):
        return 'grid_olc'

    def icon(self):
        return QIcon(os.path.join(os.path.dirname(os.path.dirname(__file__)), '../images/grid_gzd.png'))
    
    def displayName(self):
        return self.tr('OLC', 'OLC')

    def group(self):
        return self.tr('DGGS Generator', 'DGGS Generator')

    def groupId(self):
        return 'grid'

    def tags(self):
        return self.tr('OLC, grid, generator').split(',')
    
    txt_en = 'OLC Grid'
    txt_vi = 'OLC Grid'
    figure = '../images/tutorial/grid_olc.png'

    def shortHelpString(self):
        social_BW = Imgs().social_BW
        footer = '''<div align="center">
                      <img src="'''+ os.path.join(os.path.dirname(os.path.dirname(__file__)), self.figure) +'''">
                    </div>
                    <div align="right">
                      <p align="right">
                      <b>'''+self.tr('Author: Thang Quach', 'Author: Thang Quach')+'''</b>
                      </p>'''+ social_BW + '''
                    </div>
                    '''
        return self.tr(self.txt_en, self.txt_vi) + footer    
    

    def initAlgorithm(self, config=None):
        param = QgsProcessingParameterExtent(self.EXTENT,
                                             self.tr('Grid extent'),
                                             optional=True
                                            )
        self.addParameter(param)

        param = QgsProcessingParameterNumber(
                    self.RESOLUTION,
                    self.tr('Resolution/ Code length in [2, 4, 6, 8, 10, 11..15]'),
                    QgsProcessingParameterNumber.Integer,
                    defaultValue=2,
                    minValue= 2,
                    maxValue= 15,
                    optional=False)
        self.addParameter(param)

        param = QgsProcessingParameterFeatureSink(
                self.OUTPUT,
                'OLC')
        self.addParameter(param)
    
    def prepareAlgorithm(self, parameters, context, feedback):
        self.resolution = self.parameterAsInt(parameters, self.RESOLUTION, context)  
        
        if self.resolution not in [2, 4, 6, 8, 10, 11, 12, 13, 14, 15]:
            feedback.reportError('Please select a resolution in [2, 4, 6, 8, 10..15] and try again.')
            return False

        # Get the extent parameter
        self.grid_extent = self.parameterAsExtent(parameters, self.EXTENT, context)

        if self.resolution > 6 and (self.grid_extent is None or self.grid_extent.isEmpty()):
            feedback.reportError('For performance reason, when resolutin/ code length is greater than 6, the grid extent must be set.')
            return False
        
        return True

    def processAlgorithm(self, parameters, context, feedback):
        fields = QgsFields()
        fields.append(QgsField("olc", QVariant.String))
        fields.append(QgsField("resolution", QVariant.Int)) 
        fields.append(QgsField("center_lat", QVariant.Double))
        fields.append(QgsField("center_lon", QVariant.Double)) 
        fields.append(QgsField("cell_width", QVariant.Double))
        fields.append(QgsField("cell_height", QVariant.Double)) 
        fields.append(QgsField("cell_area", QVariant.Double)) 

        # Get the output sink and its destination ID
        (sink, dest_id) = self.parameterAsSink(parameters, self.OUTPUT, context,
                                                fields, QgsWkbTypes.Polygon,
                                                QgsCoordinateReferenceSystem('EPSG:4326'))

        if not sink:
            raise QgsProcessingException(self.invalidSinkError(parameters, self.OUTPUT))

        if self.grid_extent is None or self.grid_extent.isEmpty():
            extent_bbox = None
        else:
            extent_bbox = [
                [self.grid_extent.xMinimum(), self.grid_extent.yMinimum()],
                [self.grid_extent.xMaximum(), self.grid_extent.yMaximum()]
            ]        

        if extent_bbox: 
            min_lon, min_lat = extent_bbox[0]
            max_lon, max_lat = extent_bbox[1]           
            bbox_poly = box(min_lon, min_lat, max_lon, max_lat)
            # Step 1: Generate base cells at the lowest resolution (e.g., resolution 2)
            base_resolution = 2
            base_cells = generate_grid(base_resolution)

            # Step 2: Identify seed cells that intersect with the bounding box
            seed_cells = []
            for base_cell in base_cells["features"]:
                base_cell_poly = Polygon(base_cell["geometry"]["coordinates"][0])
                if bbox_poly.intersects(base_cell_poly):
                    seed_cells.append(base_cell)

            refined_features = []

            # Step 3: Iterate over seed cells and refine to the output resolution
            for seed_cell in seed_cells:
                seed_cell_poly = Polygon(seed_cell["geometry"]["coordinates"][0])

                if seed_cell_poly.contains(bbox_poly) and self.resolution == base_resolution:
                    # Append the seed cell directly if fully contained and resolution matches
                    refined_features.append(seed_cell)
                else:
                    # Refine the seed cell to the output resolution and add it to the output
                    refined_features.extend(
                        refine_cell(seed_cell_poly.bounds, base_resolution, self.resolution, bbox_poly)
                    )
                if feedback.isCanceled():
                    break
                
            resolution_features = [
                feature for feature in refined_features if feature["properties"]["resolution"] == self.resolution
            ]

            final_features = []
            seen_olc_ids = set()  # Reset the set for final feature filtering

            for feature in resolution_features:
                olc_id = feature["properties"]["olc"]
                if olc_id not in seen_olc_ids:  # Check if OLC code is already in the set
                    final_features.append(feature)
                    seen_olc_ids.add(olc_id)
                if feedback.isCanceled():
                    break

            # Convert final_features to QgsFeature
            for feature in final_features:
                cell_polygon = Polygon(feature["geometry"]["coordinates"][0])
                olc_id = feature["properties"]["olc"]
                cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)
                
                olc_feature = QgsFeature()
                olc_feature.setGeometry(cell_geometry)
                center_lat, center_lon, cell_width, cell_height, cell_area = graticule_dggs_metrics(cell_polygon)                     
                olc_feature.setAttributes([olc_id,self.resolution,center_lat,center_lon,cell_width, cell_height,cell_area])
                sink.addFeature(olc_feature, QgsFeatureSink.FastInsert) 
                # sink.addFeature(qgs_feature, QgsFeatureSink.FastInsert)
                if feedback.isCanceled():
                    break

        feedback.pushInfo("OLC grid generation completed.")
        
        if context.willLoadLayerOnCompletion(dest_id):
            lineColor = QColor.fromRgb(random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
            fontColor = QColor('#000000')
            context.layerToLoadOnCompletionDetails(dest_id).setPostProcessor(StylePostProcessor.create(lineColor, fontColor))
            
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
        label.fieldName = 'olc'
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
    def create(line_color, font_color) -> 'StylePostProcessor':
        """
        Returns a new instance of the post processor, keeping a reference to the sip
        wrapper so that sip doesn't get confused with the Python subclass and call
        the base wrapper implementation instead... ahhh sip, you wonderful piece of sip
        """
        StylePostProcessor.instance = StylePostProcessor(line_color, font_color)
        return StylePostProcessor.instance