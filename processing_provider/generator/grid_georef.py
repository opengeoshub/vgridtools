# -*- coding: utf-8 -*-
"""
grid_georef.py
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
import os, random

from vgrid.utils import georef
from ...utils.imgs import Imgs


class GridGeoref(QgsProcessingAlgorithm):
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
        return GridGeoref()

    def name(self):
        return 'grid_georef'

    def icon(self):
        return QIcon(os.path.join(os.path.dirname(os.path.dirname(__file__)), '../images/grid_gzd.png'))
    
    def displayName(self):
        return self.tr('Georef', 'Georef')

    def group(self):
        return self.tr('DGGS Generator', 'DGGS Generator')

    def groupId(self):
        return 'grid'

    def tags(self):
        return self.tr('Georef, grid, generator').split(',')
    
    txt_en = 'Georef Grid'
    txt_vi = 'Georef Grid'
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
                    self.tr('RESOLUTION'),
                    QgsProcessingParameterNumber.Integer,
                    defaultValue=1,
                    minValue= 0,
                    maxValue=5,
                    optional=False)
        self.addParameter(param)

        param = QgsProcessingParameterFeatureSink(
                self.OUTPUT,
                'Georef')
        self.addParameter(param)
                    
    def prepareAlgorithm(self, parameters, context, feedback):
        self.RESOLUTION = self.parameterAsInt(parameters, self.RESOLUTION, context)  
        if self.RESOLUTION < 0 or self.RESOLUTION>5:
            feedback.reportError('Density parameter must be in range [0,5]')
            return False
         
         # Get the extent parameter
        self.grid_extent = self.parameterAsExtent(parameters, self.EXTENT, context)
        # Ensure that when RESOLUTION > 3, the extent must be set
        if self.RESOLUTION > 2 and (self.grid_extent is None or self.grid_extent.isEmpty()):
            feedback.reportError('For performance reason, when RESOLUTION is greater than 2, the grid extent must be set.')
            return False
        
        return True
    
    def georef_to_bbox(self, gh):
        """Convert georef to bounding box coordinates."""
        lat, lon = georef.decode(gh)
        lat_err, lon_err = georef.decode_exactly(gh)[2:]
        bbox = {
            'w': max(lon - lon_err, -180),
            'e': min(lon + lon_err, 180),
            's': max(lat - lat_err, -85.051129),
            'n': min(lat + lat_err, 85.051129)
        }
        return bbox

    def georef_to_polygon(self, gh):
        """Convert georef to a QGIS QgsGeometry Polygon."""
        bbox = self.georef_to_bbox(gh)

        # Create a list of QgsPointXY from the bounding box coordinates
        qgis_points = [
            QgsPointXY(bbox['w'], bbox['s']),
            QgsPointXY(bbox['w'], bbox['n']),
            QgsPointXY(bbox['e'], bbox['n']),
            QgsPointXY(bbox['e'], bbox['s']),
            QgsPointXY(bbox['w'], bbox['s']),
        ]

        # Create and return a QGIS QgsGeometry Polygon from the points
        return QgsGeometry.fromPolygonXY([qgis_points])

    def expand_georef(self, gh, target_length, writer, fields, feedback):
        """Recursive function to expand georefes to target RESOLUTION and write them."""
        if len(gh) == target_length:
            polygon = self.georef_to_polygon(gh)
            feature = QgsFeature(fields)
            feature.setAttribute("georef", gh)
            feature.setGeometry(polygon)
            writer.addFeature(feature)
            return
        
        # Expand the georef with all possible characters
        for char in "0123456789bcdefghjkmnpqrstuvwxyz":
            if feedback.isCanceled():
                return
            self.expand_georef(gh + char, target_length, writer, fields, feedback)

    def expand_georef_within_extent(self, gh, target_length, writer, fields, extent, feedback):
        """Recursive function to expand georefes to target RESOLUTION and write them within the specified extent."""
        
        # Get the georef as a QgsGeometry polygon
        polygon = self.georef_to_polygon(gh)

        # Check if the polygon's bounding box intersects with the extent
        if not polygon.boundingBox().intersects(extent):
            # If the bounding box does not intersect the extent, exit early (no need to expand)
            return
        
        # If we reach the target length, we can write the feature
        if len(gh) == target_length:
            feature = QgsFeature(fields)
            feature.setAttribute("georef", gh)
            feature.setGeometry(polygon)
            writer.addFeature(feature)
            return
        
        # If not at the target length, expand the georef with all possible characters
        for char in "0123456789bcdefghjkmnpqrstuvwxyz":
            if feedback.isCanceled():
                return
            
            # Recursively expand the georef with the next character
            self.expand_georef_within_extent(gh + char, target_length, writer, fields, extent, feedback)

    def processAlgorithm(self, parameters, context, feedback):
        fields = QgsFields()
        fields.append(QgsField("georef", QVariant.String))

        # Get the output sink and its destination ID (this handles both file and temporary layers)
        (sink, dest_id) = self.parameterAsSink(parameters, self.OUTPUT, context, 
                                                fields, QgsWkbTypes.Polygon, 
                                                QgsCoordinateReferenceSystem('EPSG:4326'))

        if sink is None:
            raise QgsProcessingException("Failed to create output sink")
        
        # Initial georefes covering the world at the lowest RESOLUTION
        initial_georefes = ["b", "c", "f", "g", "u", "v", "y", "z", 
                            "8", "9", "d", "e", "s", "t", "w", "x", 
                            "0", "1", "2", "3", "p", "q", "r", "k", 
                            "m", "n", "h", "j", "4", "5", "6", "7"]

        # Expand each initial georef to the target RESOLUTION
        total_georefes = len(initial_georefes)
        feedback.pushInfo(f"Expanding initial georefes to RESOLUTION {self.RESOLUTION}")
       
        if  self.grid_extent is None or self.grid_extent.isEmpty():
            for idx, gh in enumerate(initial_georefes):
                if feedback.isCanceled():
                    break
                
                feedback.setProgress(int((idx / total_georefes) * 100))
                feedback.pushInfo(f"Processing georef prefix: {gh}")

                self.expand_georef(gh, self.RESOLUTION, sink, fields,feedback)
        else: 
            filtered_georefes = []
            for gh in initial_georefes:
                georef_polygon = self.georef_to_polygon(gh)  # Already a QgsGeometry now
                if georef_polygon.boundingBox().intersects(self.grid_extent):
                    filtered_georefes.append(gh)
            initial_georefes = filtered_georefes  # Replace with only intersecting georefes
            for idx, gh in enumerate(initial_georefes):
                if feedback.isCanceled():
                    break
                
                feedback.setProgress(int((idx / total_georefes) * 100))
                feedback.pushInfo(f"Processing georef prefix: {gh}")

                self.expand_georef_within_extent(gh, self.RESOLUTION, sink, fields, self.grid_extent,feedback)

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
        label.fieldName = 'georef'
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