# -*- coding: utf-8 -*-
"""
grid_geohash.py
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

from ...vgridlibrary.conversion import geohash
from ...vgridlibrary.imgs import Imgs


class GridGeohash(QgsProcessingAlgorithm):
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
        return GridGeohash()

    def name(self):
        return 'grid_geohash'

    def icon(self):
        return QIcon(os.path.join(os.path.dirname(os.path.dirname(__file__)), '../images/grid_gzd.png'))
    
    def displayName(self):
        return self.tr('Geohash', 'Geohash')

    def group(self):
        return self.tr('Grid Generator', 'Grid Generator')

    def groupId(self):
        return 'grid'

    def tags(self):
        return self.tr('Geohash, grid, generator').split(',')
    
    txt_en = 'Geohash Grid'
    txt_vi = 'Geohash Grid'
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
                    minValue= 1,
                    maxValue=10,
                    optional=False)
        self.addParameter(param)

        param = QgsProcessingParameterFeatureSink(
                self.OUTPUT,
                'Geohash')
        self.addParameter(param)
                    
    def prepareAlgorithm(self, parameters, context, feedback):
        self.RESOLUTION = self.parameterAsInt(parameters, self.RESOLUTION, context)  
        if self.RESOLUTION < 1 or self.RESOLUTION>10:
            feedback.reportError('RESOLUTION parameter must be in range [1,10]')
            return False
         
         # Get the extent parameter
        self.grid_extent = self.parameterAsExtent(parameters, self.EXTENT, context)
        # Ensure that when RESOLUTION > 4, the extent must be set
        if self.RESOLUTION > 4 and (self.grid_extent is None or self.grid_extent.isEmpty()):
            feedback.reportError('For performance reason, when RESOLUTION is greater than 4, the grid extent must be set.')
            return False
        
        return True
    
    def geohash_to_bbox(self, gh):
        """Convert geohash to bounding box coordinates."""
        lat, lon = geohash.decode(gh)
        lat_err, lon_err = geohash.decode_exactly(gh)[2:]
        bbox = {
            'w': max(lon - lon_err, -180),
            'e': min(lon + lon_err, 180),
            's': max(lat - lat_err, -85.051129),
            'n': min(lat + lat_err, 85.051129)
        }
        return bbox

    def geohash_to_polygon(self, gh):
        """Convert geohash to a QGIS QgsGeometry Polygon."""
        bbox = self.geohash_to_bbox(gh)

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

    def expand_geohash(self, gh, target_length, writer, fields, feedback):
        """Recursive function to expand geohashes to target RESOLUTION and write them."""
        if len(gh) == target_length:
            polygon = self.geohash_to_polygon(gh)
            feature = QgsFeature(fields)
            feature.setAttribute("geohash", gh)
            feature.setGeometry(polygon)
            writer.addFeature(feature)
            return
        
        # Expand the geohash with all possible characters
        for char in "0123456789bcdefghjkmnpqrstuvwxyz":
            if feedback.isCanceled():
                return
            self.expand_geohash(gh + char, target_length, writer, fields, feedback)

    def expand_geohash_within_extent(self, gh, target_length, writer, fields, extent, feedback):
        """Recursive function to expand geohashes to target RESOLUTION and write them within the specified extent."""
        
        # Get the geohash as a QgsGeometry polygon
        polygon = self.geohash_to_polygon(gh)

        # Check if the polygon's bounding box intersects with the extent
        if not polygon.boundingBox().intersects(extent):
            # If the bounding box does not intersect the extent, exit early (no need to expand)
            return
        
        # If we reach the target length, we can write the feature
        if len(gh) == target_length:
            feature = QgsFeature(fields)
            feature.setAttribute("geohash", gh)
            feature.setGeometry(polygon)
            writer.addFeature(feature)
            return
        
        # If not at the target length, expand the geohash with all possible characters
        for char in "0123456789bcdefghjkmnpqrstuvwxyz":
            if feedback.isCanceled():
                return
            
            # Recursively expand the geohash with the next character
            self.expand_geohash_within_extent(gh + char, target_length, writer, fields, extent, feedback)

    def processAlgorithm(self, parameters, context, feedback):
        fields = QgsFields()
        fields.append(QgsField("geohash", QVariant.String))

        # Get the output sink and its destination ID (this handles both file and temporary layers)
        (sink, dest_id) = self.parameterAsSink(parameters, self.OUTPUT, context, 
                                                fields, QgsWkbTypes.Polygon, 
                                                QgsCoordinateReferenceSystem('EPSG:4326'))

        if sink is None:
            raise QgsProcessingException("Failed to create output sink")
        
        # Initial geohashes covering the world at the lowest RESOLUTION
        initial_geohashes = ["b", "c", "f", "g", "u", "v", "y", "z", 
                            "8", "9", "d", "e", "s", "t", "w", "x", 
                            "0", "1", "2", "3", "p", "q", "r", "k", 
                            "m", "n", "h", "j", "4", "5", "6", "7"]

        # Expand each initial geohash to the target RESOLUTION
        total_geohashes = len(initial_geohashes)
        feedback.pushInfo(f"Expanding initial geohashes to RESOLUTION {self.RESOLUTION}")
       
        if  self.grid_extent is None or self.grid_extent.isEmpty():
            for idx, gh in enumerate(initial_geohashes):
                if feedback.isCanceled():
                    break
                
                feedback.setProgress(int((idx / total_geohashes) * 100))
                feedback.pushInfo(f"Processing geohash prefix: {gh}")

                self.expand_geohash(gh, self.RESOLUTION, sink, fields,feedback)
        else: 
            filtered_geohashes = []
            for gh in initial_geohashes:
                geohash_polygon = self.geohash_to_polygon(gh)  # Already a QgsGeometry now
                if geohash_polygon.boundingBox().intersects(self.grid_extent):
                    filtered_geohashes.append(gh)
            initial_geohashes = filtered_geohashes  # Replace with only intersecting geohashes
            for idx, gh in enumerate(initial_geohashes):
                if feedback.isCanceled():
                    break
                
                feedback.setProgress(int((idx / total_geohashes) * 100))
                feedback.pushInfo(f"Processing geohash prefix: {gh}")

                self.expand_geohash_within_extent(gh, self.RESOLUTION, sink, fields, self.grid_extent,feedback)

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
        label.fieldName = 'geohash'
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