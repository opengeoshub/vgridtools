# -*- coding: utf-8 -*-
"""
grid_maidenhead.py
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

__author__ = 'Thang Quach'
__date__ = '2024-11-20'
__copyright__ = '(L) 2024, Thang Quach'

from qgis.core import (
    QgsApplication,
    QgsFeatureSink,
    QgsProcessingLayerPostProcessorInterface,
    QgsProcessingParameterExtent,
    QgsProcessingParameterNumber,
    QgsProcessingException,
    QgsProcessingParameterFeatureSink,
    QgsProcessingAlgorithm,
    QgsFields,
    QgsField,
    QgsPointXY, 
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

from vgrid.utils import maidenhead
from ...utils.imgs import Imgs


class GridMaidenhead(QgsProcessingAlgorithm):
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
        return GridMaidenhead()

    def name(self):
        return 'grid_maidenhead'

    def icon(self):
        return QIcon(os.path.join(os.path.dirname(os.path.dirname(__file__)), '../images/grid_gzd.png'))
    
    def displayName(self):
        return self.tr('Maidenhead', 'Maidenhead')

    def group(self):
        return self.tr('DGGS Generator', 'DGGS Generator')

    def groupId(self):
        return 'grid'

    def tags(self):
        return self.tr('DGGS, grid, Maidenhead, generator').split(',')
    
    txt_en = 'Maidenhead Grid Generator'
    txt_vi = 'Maidenhead Grid'
    figure = '../images/tutorial/grid_maidenhead.png'

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
                    self.tr('RESOLUTION'),
                    QgsProcessingParameterNumber.Integer,
                    defaultValue=1,
                    minValue= 1,
                    maxValue=4,
                    optional=False)
        self.addParameter(param)

        param = QgsProcessingParameterFeatureSink(
                self.OUTPUT,
                'Maidenhead')
        self.addParameter(param)
                    
    def prepareAlgorithm(self, parameters, context, feedback):
        self.RESOLUTION = self.parameterAsInt(parameters, self.RESOLUTION, context)  
        if self.RESOLUTION < 1 or self.RESOLUTION> 4:
            feedback.reportError('RESOLUTION parameter must be in range [1,4]')
            return False
         
         # Get the extent parameter
        self.grid_extent = self.parameterAsExtent(parameters, self.EXTENT, context)
        # Ensure that when RESOLUTION > 4, the extent must be set
        if self.RESOLUTION > 3 and (self.grid_extent is None or self.grid_extent.isEmpty()):
            feedback.reportError('For performance reason, when RESOLUTION is greater than 3, the grid extent must be set.')
            return False
        
        return True
    
    def maidenheadgrid(self, RESOLUTION, feedback):
        grid_params = {
            1: (18, 18, 20, 10),
            2: (180, 180, 2, 1),
            3: (1800, 1800, 0.2, 0.1),
            4: (18000, 18000, 0.02, 0.01)
        }
        
        if RESOLUTION not in grid_params:
            raise ValueError("Unsupported RESOLUTION")

        x_cells, y_cells, lon_width, lat_width = grid_params[RESOLUTION]
        base_lat, base_lon = -90, -180
        total_cells = x_cells * y_cells
        features = []

        cell_count = 0  # Counter to track progress
        for i in range(x_cells):
            for j in range(y_cells):
                min_lon = base_lon + i * lon_width
                max_lon = min_lon + lon_width
                min_lat = base_lat + j * lat_width
                max_lat = min_lat + lat_width
                center_lat = (min_lat + max_lat) / 2
                center_lon = (min_lon + max_lon) / 2
                
                maidenhead_code = maidenhead.toMaiden(center_lat, center_lon, RESOLUTION)
                vertices = [
                    QgsPointXY(min_lon, min_lat),
                    QgsPointXY(max_lon, min_lat),
                    QgsPointXY(max_lon, max_lat),
                    QgsPointXY(min_lon, max_lat),
                    QgsPointXY(min_lon, min_lat)
                ]
                polygon = QgsGeometry.fromPolygonXY([vertices])
                
                feature = QgsFeature()
                feature.setGeometry(polygon)
                feature.setAttributes([maidenhead_code])
                features.append(feature)
                
                # Update progress and feedback message
                cell_count += 1
                feedback.setProgress(int((cell_count / total_cells) * 100))
                if cell_count % 10000 == 0:  # Every 10,000 cells,
                    feedback.pushInfo(f"Processed {cell_count}/{total_cells} cells")
                
                if feedback.isCanceled():
                    return []  # Cancel if the user stops the process

        return features


    def maidenheadgrid_with_extent(self, RESOLUTION, extent, feedback):
        # Define grid parameters based on RESOLUTION level
        grid_params = {
            1: (18, 18, 20, 10),
            2: (180, 180, 2, 1),
            3: (1800, 1800, 0.2, 0.1),
            4: (18000, 18000, 0.02, 0.01)
        }
        
        if RESOLUTION not in grid_params:
            raise ValueError("Unsupported RESOLUTION")

        x_cells, y_cells, lon_width, lat_width = grid_params[RESOLUTION]
        base_lat, base_lon = -90, -180
        features = []

        # Calculate the cell indices corresponding to the extent bounds
        min_x = max(0, int((extent.xMinimum() - base_lon) / lon_width))
        max_x = min(x_cells, int((extent.xMaximum() - base_lon) / lon_width) + 1)
        min_y = max(0, int((extent.yMinimum() - base_lat) / lat_width))
        max_y = min(y_cells, int((extent.yMaximum() - base_lat) / lat_width) + 1)

        # Total cells to process, for progress feedback
        total_cells = (max_x - min_x) * (max_y - min_y)
        cell_count = 0

        for i in range(min_x, max_x):
            for j in range(min_y, max_y):
                min_lon = base_lon + i * lon_width
                max_lon = min_lon + lon_width
                min_lat = base_lat + j * lat_width
                max_lat = min_lat + lat_width
                center_lat = (min_lat + max_lat) / 2
                center_lon = (min_lon + max_lon) / 2

                # Get Maidenhead code
                maidenhead_code = maidenhead.toMaiden(center_lat, center_lon, RESOLUTION)
                
                # Define polygon vertices in clockwise order
                vertices = [
                    QgsPointXY(min_lon, min_lat),
                    QgsPointXY(max_lon, min_lat),
                    QgsPointXY(max_lon, max_lat),
                    QgsPointXY(min_lon, max_lat),
                    QgsPointXY(min_lon, min_lat)  # Closing the polygon
                ]
                
                # Create the polygon geometry
                polygon = QgsGeometry.fromPolygonXY([vertices])
                
                # Create a new feature and set the maidenhead attribute
                feature = QgsFeature()
                feature.setGeometry(polygon)
                feature.setAttributes([maidenhead_code])
                features.append(feature)
                
                # Update progress
                cell_count += 1
                feedback.setProgress(int((cell_count / total_cells) * 100))
                if cell_count % 1000 == 0:  # Every 10,000 cells,
                    feedback.pushInfo(f"Processed {cell_count}/{total_cells} cells")
                
                if feedback.isCanceled():
                    return []  # Cancel if the user stops the process

        return features

    def processAlgorithm(self, parameters, context, feedback):
        fields = QgsFields()
        fields.append(QgsField("maidenhead", QVariant.String))

        # Get the output sink and its destination ID
        (sink, dest_id) = self.parameterAsSink(
            parameters, 
            self.OUTPUT, 
            context, 
            fields, 
            QgsWkbTypes.Polygon, 
            QgsCoordinateReferenceSystem('EPSG:4326')
        )

        if sink is None:
            raise QgsProcessingException("Failed to create output sink")

        if self.grid_extent is None or self.grid_extent.isEmpty():
            grid_cells = self.maidenheadgrid(self.RESOLUTION,feedback)
        else:
            grid_cells = self.maidenheadgrid_with_extent(self.RESOLUTION, self.grid_extent, feedback)
        
        # Add each feature to the output sink
        for feature in grid_cells:
            sink.addFeature(feature, QgsFeatureSink.FastInsert)


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
        label.fieldName = 'maidenhead'
        format = label.format()
        format.setColor(self.font_color)
        format.setSize(8)
        label.setFormat(format)
        labeling = QgsVectorLayerSimpleLabeling(label)
        layer.setLabeling(labeling)
        layer.setLabelsEnabled(True)
        iface.layerTreeView().refreshLayerSymbology(layer.id())

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