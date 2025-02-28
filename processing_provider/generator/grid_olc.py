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

from ...vgridlibrary.conversion import olc
from ...vgridlibrary.imgs import Imgs


class GridOLC(QgsProcessingAlgorithm):
    EXTENT = 'EXTENT'
    CODELENGTH = 'CODELENGTH'
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
        return self.tr('Grid Generator', 'Grid Generator')

    def groupId(self):
        return 'grid'

    def tags(self):
        return self.tr('OLC, grid, generator').split(',')
    
    txt_en = 'OLC Grid'
    txt_vi = 'OLC Grid'
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
                    self.CODELENGTH,
                    self.tr('OLC length'),
                    QgsProcessingParameterNumber.Integer,
                    defaultValue=2,
                    minValue= 2,
                    maxValue=15,
                    optional=False)
        self.addParameter(param)

        param = QgsProcessingParameterFeatureSink(
                self.OUTPUT,
                'OLC')
        self.addParameter(param)
                    
    def prepareAlgorithm(self, parameters, context, feedback):
        self.codelength = self.parameterAsInt(parameters, self.CODELENGTH, context)  
        
        if self.codelength < 2 or self.codelength > 15:
            feedback.reportError('Code length parameter must be in range [10,15]')
            return False
         
         # Get the extent parameter
        self.grid_extent = self.parameterAsExtent(parameters, self.EXTENT, context)

        if self.codelength > 11 and (self.grid_extent is None or self.grid_extent.isEmpty()):
            feedback.reportError('For performance reason, when Code length is greater than 11, the grid extent must be set.')
            return False
        
        return True
    
    def generate_all_olcs(self, length):
        """Generate all OLC codes of a given length including the '+' sign."""
        olc_chars = '23456789CFGHJMPQRVWX'
        
        if length < 2:
            raise ValueError("OLC length should be at least 2.")

        # The '+' sign appears after the first 6 characters for a full OLC code
        # If the length is greater than 6, insert the '+' at the appropriate place
        base_length = 6  # The first part of the OLC code before the '+'
        finer_length = length - base_length  # The finer part after the '+'

        # Handle base length (first part) separately from finer length (second part)
        def olc_generator(prefix, depth, insert_plus=False):
            if depth == length:
                yield prefix
            elif depth == base_length and finer_length > 0:
                # Insert the '+' after the base part
                if insert_plus:
                    yield from olc_generator(prefix + '+', depth + 1, insert_plus=False)
                else:
                    for char in olc_chars:
                        yield from olc_generator(prefix + char, depth + 1, insert_plus=True)
            else:
                for char in olc_chars:
                    yield from olc_generator(prefix + char, depth + 1, insert_plus)

        return olc_generator("", 0, insert_plus=False)

    def create_polygon_for_olc(self, olc_code):
        """Create a QgsGeometry Polygon for a given OLC code."""
        decoded = olc.decode(olc_code)
        
        # Define coordinates from the OLC bounding box (Longitude/Latitude)
        coordinates = [
            QgsPointXY(decoded.longitudeLo, decoded.latitudeLo),
            QgsPointXY(decoded.longitudeLo, decoded.latitudeHi),
            QgsPointXY(decoded.longitudeHi, decoded.latitudeHi),
            QgsPointXY(decoded.longitudeHi, decoded.latitudeLo),
            QgsPointXY(decoded.longitudeLo, decoded.latitudeLo)  # Closing the polygon
        ]
        
        # Create the QgsGeometry from the polygon
        polygon = QgsGeometry.fromPolygonXY([coordinates])
        
        return polygon


    def is_within_bounding_box(self, decoded, bbox):
        """Check if the OLC's bounding box is within the specified bounding box."""
        return (decoded.longitudeLo < bbox[2] and decoded.longitudeHi > bbox[0] and
                decoded.latitudeLo < bbox[3] and decoded.latitudeHi > bbox[1])


    def processAlgorithm(self, parameters, context, feedback):
        fields = QgsFields()
        fields.append(QgsField("olc", QVariant.String))

        # Get the output sink and its destination ID
        (sink, dest_id) = self.parameterAsSink(parameters, self.OUTPUT, context,
                                                fields, QgsWkbTypes.Polygon,
                                                QgsCoordinateReferenceSystem('EPSG:4326'))

        if sink is None:
            raise QgsProcessingException("Failed to create output sink")

        total_codes = 20 ** self.codelength  # Total number of possible codes of the given length
        feedback.pushInfo(f"Generating OLC grid of length {self.codelength}")

        # Iterate through the generated OLC codes
        for idx, olc_code in enumerate(self.generate_all_olcs(self.codelength)):
            if feedback.isCanceled():
                break
            feedback.pushInfo (olc_code)
            # # Decode the OLC code to get the bounding box
            # decoded = olc.decode(olc_code)

            # if self.grid_extent is None or self.grid_extent.isEmpty() or self.is_within_bounding_box(decoded, self.grid_extent):
            #     polygon = self.create_polygon_for_olc(olc_code)  # Get QgsGeometry polygon
            #     feature = QgsFeature(fields)
            #     feature.setAttribute("olc", olc_code)
            #     feature.setGeometry(polygon)  # Directly set the QgsGeometry
            #     sink.addFeature(feature)

            # # Set progress for feedback
            # progress = (idx / total_codes) * 100
            # feedback.setProgress(int(progress))

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