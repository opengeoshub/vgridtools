# -*- coding: utf-8 -*-
"""
grid_gzd.py
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

import os, random

from qgis.PyQt.QtCore import QCoreApplication,QVariant,Qt
from qgis.PyQt.QtGui import QIcon, QColor
from qgis.utils import iface

from qgis.core import (
    QgsApplication,
    QgsProject,
    QgsCoordinateReferenceSystem,
    QgsProcessingAlgorithm,
    QgsProcessingParameterBoolean,
    QgsProcessingLayerPostProcessorInterface,
    QgsProcessingParameterFeatureSink,
    QgsFields, QgsField, QgsFeature, 
    QgsWkbTypes, QgsRectangle, 
    QgsGeometry, QgsVectorLayer, 
    QgsPalLayerSettings, QgsVectorLayerSimpleLabeling)

from ...utils.imgs import Imgs

bands = ['C','D','E','F','G','H','J','K','L','M','N','P','Q','R','S','T','U','V','W','X']
epsg4326 = QgsCoordinateReferenceSystem('EPSG:4326')

class GridGZD(QgsProcessingAlgorithm):
    POLAR = 'POLAR'
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
        return GridGZD()

    def name(self):
        return 'grid_gzd'

    def icon(self):
        return QIcon(os.path.join(os.path.dirname(os.path.dirname(__file__)), '../images/generator/grid_quad.svg'))
    
    def displayName(self):
        return self.tr('MGRS GZD', 'MGRS GZD')

    def group(self):
        return self.tr('Generator', 'Generator')

    def groupId(self):
        return 'grid'

    def tags(self):
        return self.tr('DGGS, MGRS Grid Zone Designator, gzd, generator').split(',')
    
    txt_en = 'MGRS GZD Geneartor'
    txt_vi = 'MGRS GZD Generator'
    figure = '../images/tutorial/grid_mgrs.png'

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
        self.addParameter(
            QgsProcessingParameterBoolean (
                self.POLAR,
                'Include polar regions',
                True,
                optional=False)
        )
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT,
                'MGRS GZD')
        )

    def processAlgorithm(self, parameters, context, feedback):
        polar = self.parameterAsBoolean(parameters, self.POLAR, context)

        f = QgsFields()
        f.append(QgsField("gzd", QVariant.String))

        (sink, dest_id) = self.parameterAsSink(
            parameters, self.OUTPUT,
            context, f, QgsWkbTypes.Polygon, epsg4326)
        if polar:
            self.exportPolygon(sink, -180, -90, 180, 10, 'A')
            self.exportPolygon(sink, 0, -90, 180, 10, 'B')
        lat = -80
        for b in bands:
            if b == 'X':
                height = 12
                lon = -180
                for i in range(1, 31):
                    gzd = '{:02d}{}'.format(i, b)
                    width = 6
                    self.exportPolygon(sink, lon, lat, width, height, gzd)
                    lon += width
                self.exportPolygon(sink, lon, lat, 9, height, '31X')
                lon += 9
                self.exportPolygon(sink, lon, lat, 12, height, '33X')
                lon += 12
                self.exportPolygon(sink, lon, lat, 12, height, '35X')
                lon += 12
                self.exportPolygon(sink, lon, lat, 9, height, '37X')
                lon += 9
                for i in range(38, 61):
                    gzd = '{:02d}{}'.format(i, b)
                    width = 6
                    self.exportPolygon(sink, lon, lat, width, height, gzd)
                    lon += width
            else:
                height = 8
                lon = -180
                for i in range(1, 61):
                    gzd = '{:02d}{}'.format(i, b)
                    if b == 'V' and i == 31:
                        width = 3
                    elif b == 'V' and i == 32:
                        width = 9
                    else:
                        width = 6
                    self.exportPolygon(sink, lon, lat, width, height, gzd)
                    lon += width
            lat += height

        if polar:
            self.exportPolygon(sink, -180, 84, 180, 6, 'Y')
            self.exportPolygon(sink, 0, 84, 180, 6, 'Z')

        feedback.pushInfo("GZD generation completed.")
        # Apply styling (optional)
        if context.willLoadLayerOnCompletion(dest_id):
            lineColor = QColor.fromRgb(random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
            fontColor = QColor('#000000')  # Black font
            context.layerToLoadOnCompletionDetails(dest_id).setPostProcessor(
                StylePostProcessor.create(lineColor, fontColor)
            )

        return {self.OUTPUT: dest_id}


    def exportPolygon(self, sink, lon, lat, width, height, gzd):
        rect = QgsRectangle(lon, lat, lon+width, lat+height)
        f = QgsFeature()
        f.setGeometry(QgsGeometry.fromRect(rect))
        f.setAttributes([gzd])
        sink.addFeature(f)

    
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
        label.fieldName = 'gzd'
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
