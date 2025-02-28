# -*- coding: utf-8 -*-
"""
grid_vgrid.py
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
import os
from ...vgridlibrary.utils import mercantile
from ...vgridlibrary.imgs import Imgs


class GridTilecode(QgsProcessingAlgorithm):
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
        return GridTilecode()

    def name(self):
        return 'grid_Tilecode'

    def icon(self):
        return QIcon(os.path.join(os.path.dirname(os.path.dirname(__file__)), '../images/grid_gzd.png'))
    
    def displayName(self):
        return self.tr('Tilecode', 'Tilecode')

    def group(self):
        return self.tr('Grid Generator', 'Grid Generator')

    def groupId(self):
        return 'grid'

    def tags(self):
        return self.tr('Vgrid, Tilecode, generator').split(',')
    
    txt_en = 'Tilecode Grid'
    txt_vi = 'Tilecode Grid'
    figure = '../images/tutorial/codes2cells.png'

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
                    self.tr('RESOLUTION (Zoom level)'),
                    QgsProcessingParameterNumber.Integer,
                    defaultValue=20,
                    minValue= 0,
                    maxValue= 24,
                    optional=False)
        self.addParameter(param)


        param = QgsProcessingParameterFeatureSink(
                self.OUTPUT,
                'Tilecode')
        self.addParameter(param)
                    
    def prepareAlgorithm(self, parameters, context, feedback):
        self.RESOLUTION = self.parameterAsInt(parameters, self.RESOLUTION, context)  
        if self.RESOLUTION < 0 or self.RESOLUTION > 24:
            feedback.reportError('RESOLUTION parameter must be in range [0,24]')
            return False
         
         # Get the extent parameter
        self.grid_extent = self.parameterAsExtent(parameters, self.EXTENT, context)
        # Ensure that when RESOLUTION > 4, the extent must be set
        if self.RESOLUTION > 10 and (self.grid_extent is None or self.grid_extent.isEmpty()):
            feedback.reportError('For performance reason, when RESOLUTION is greater than 10, the grid extent must be set.')
            return False
        
        return True
    
    def processAlgorithm(self, parameters, context, feedback):
        fields = QgsFields()
        fields.append(QgsField("Tilecode", QVariant.String))

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
        # Cover the entire world extent
            tiles = list(mercantile.tiles(-180.0,-85.05112878,180.0,85.05112878,self.RESOLUTION))
        else:
            # Use the specified grid extent
            xmin = self.grid_extent.xMinimum()
            ymin = self.grid_extent.yMinimum()
            xmax = self.grid_extent.xMaximum()
            ymax = self.grid_extent.yMaximum()
            tiles = list(mercantile.tiles(xmin, ymin, xmax, ymax, self.RESOLUTION))

        total_tiles = len(tiles)
        
        # Iterate over each tile to create features
        for index, tile in enumerate(tiles):
            # Get the tile's bounding box in geographic coordinates
            bounds = mercantile.bounds(tile)
            
            # Define the corner points of the tile polygon
            points = [
                QgsPointXY(bounds.west, bounds.south),
                QgsPointXY(bounds.east, bounds.south),
                QgsPointXY(bounds.east, bounds.north),
                QgsPointXY(bounds.west, bounds.north),
                QgsPointXY(bounds.west, bounds.south)  # Closing the polygon
            ]
            
            # Create a QgsGeometry polygon from the points
            polygon = QgsGeometry.fromPolygonXY([points])
            
            # Generate the 'Tilecode' attribute in the format "zZxXyY"
            Tilecode = f"z{tile.z}x{tile.x}y{tile.y}"
            
            # Create a new feature and set its geometry and attributes
            feature = QgsFeature(fields)
            feature.setGeometry(polygon)
            feature.setAttribute("Tilecode", Tilecode)
            
            # Add the feature to the output sink
            sink.addFeature(feature, QgsFeatureSink.FastInsert)
            
            if (index + 1) % 10000 == 0:
                message = f"Processed {index + 1}/{total_tiles} tiles"
                feedback.pushInfo(message)

            # Update progress
            feedback.setProgress(int(100 * (index + 1) / total_tiles))
            
            # Check if the process has been canceled
            if feedback.isCanceled():
                break

        if context.willLoadLayerOnCompletion(dest_id):
            lineColor = QColor('#FF0000')
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
        label.fieldName = 'Tilecode'
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