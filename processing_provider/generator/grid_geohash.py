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
    QgsProject,
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

from vgrid.utils import geohash
from ...utils.imgs import Imgs
from vgrid.generator.settings import graticule_dggs_metrics
from shapely.geometry import box
from vgrid.generator.geohashgrid import geohash_to_polygon


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
        return QIcon(os.path.join(os.path.dirname(os.path.dirname(__file__)), '../images/generator/grid_quad.svg'))

    def displayName(self):
        return self.tr('Geohash', 'Geohash')

    def group(self):
        return self.tr('DGGS Generator', 'DGGS Generator')

    def groupId(self):
        return 'grid'

    def tags(self):
        return self.tr('DGGS, grid, Geohash, generator').split(',')
    
    txt_en = 'Geohash Grid Generator'
    txt_vi = 'Geohash Grid Generator'
    figure = '../images/tutorial/grid_geohash.png'

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
                    self.tr('Resolution [1..10]'),
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
        self.resolution = self.parameterAsInt(parameters, self.RESOLUTION, context)  
        # Get the extent parameter
        self.grid_extent = self.parameterAsExtent(parameters, self.EXTENT, context)
        # Ensure that when resolution > 4, the extent must be set
        if self.resolution > 4 and (self.grid_extent is None or self.grid_extent.isEmpty()):
            feedback.reportError('For performance reason, when resolution is greater than 4, the grid extent must be set.')
            return False
        
        return True
    
    def outputFields(self):
        output_fields = QgsFields() 
        output_fields.append(QgsField("geohash", QVariant.String))
        output_fields.append(QgsField('resolution', QVariant.Int))
        output_fields.append(QgsField('center_lat', QVariant.Double))
        output_fields.append(QgsField('center_lon', QVariant.Double))
        output_fields.append(QgsField('cell_width', QVariant.Double))
        output_fields.append(QgsField('cell_height', QVariant.Double))
        output_fields.append(QgsField('cell_area', QVariant.Double))

        return output_fields
    
    def expand_geohash(self, gh, target_length, writer, fields, feedback):
        """Recursive function to expand geohashes to target RESOLUTION and write them."""
        if len(gh) == target_length:
            cell_polygon = geohash_to_polygon(gh)
            cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)
            geohash_feature = QgsFeature(fields)
            geohash_feature.setGeometry(cell_geometry)
            
            center_lat, center_lon, cell_width, cell_height, cell_area = graticule_dggs_metrics(cell_polygon)            
            geohash_feature.setAttributes([gh, self.resolution,center_lat, center_lon, cell_width, cell_height, cell_area])                    

            writer.addFeature(geohash_feature)
            return
        
        # Expand the geohash with all possible characters
        for char in "0123456789bcdefghjkmnpqrstuvwxyz":
            self.expand_geohash(gh + char, target_length, writer, fields, feedback)
            if feedback.isCanceled():
                return


    def expand_geohash_within_extent(self, gh, target_length, writer, fields, extent, feedback):
        cell_polygon = geohash_to_polygon(gh)
        extent_bbox = box(self.grid_extent.xMinimum(), self.grid_extent.yMinimum(), 
                            self.grid_extent.xMaximum(), self.grid_extent.yMaximum())       
        if not cell_polygon.intersects(extent_bbox):
            return
   
        if len(gh) == target_length:
            cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)
            geohash_feature = QgsFeature(fields)
            geohash_feature.setGeometry(cell_geometry)
            
            center_lat, center_lon, cell_width, cell_height, cell_area = graticule_dggs_metrics(cell_polygon)            
            geohash_feature.setAttributes([gh, self.resolution,center_lat, center_lon, cell_width, cell_height, cell_area])                    

            writer.addFeature(geohash_feature)
            return
        
        # If not at the target length, expand the geohash with all possible characters
        for char in "0123456789bcdefghjkmnpqrstuvwxyz":            
            self.expand_geohash_within_extent(gh + char, target_length, writer, fields, extent, feedback)
            if feedback.isCanceled():
                return

    def processAlgorithm(self, parameters, context, feedback):
        fields = self.outputFields()

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
       
        if  self.grid_extent is None or self.grid_extent.isEmpty():
            total_cells = 32 ** self.resolution
            feedback.pushInfo(f"Total cells to be generated: {total_cells}.")       
          
            for idx, gh in enumerate(initial_geohashes):               
                self.expand_geohash(gh, self.resolution, sink, fields,feedback)
                feedback.setProgress(int((idx / total_geohashes) * 100))
                if feedback.isCanceled():
                    break                
        else: 
            intersected_geohashes = []
            for gh in initial_geohashes:
                cell_polygon = geohash_to_polygon(gh)  
                extent_bbox = box(self.grid_extent.xMinimum(), self.grid_extent.yMinimum(), 
                                self.grid_extent.xMaximum(), self.grid_extent.yMaximum())       
                if cell_polygon.intersects(extent_bbox):
                    intersected_geohashes.append(gh)
            
            for idx, gh in enumerate(intersected_geohashes):
                feedback.setProgress(int((idx / total_geohashes) * 100))
                self.expand_geohash_within_extent(gh, self.resolution, sink, fields, self.grid_extent,feedback)
                if feedback.isCanceled():
                    break   
        
        feedback.pushInfo("Geohash grid generation completed.")            
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
        label.fieldName = 'geohash'
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