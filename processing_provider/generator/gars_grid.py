# -*- coding: utf-8 -*-
"""
gars_grid.py
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
from ...utils.imgs import Imgs
import numpy as np
from vgrid.dggs.gars.garsgrid import GARSGrid as GARSGRID 
from shapely.geometry import Polygon
from vgrid.utils.geometry import graticule_dggs_metrics     
        
class GARSGrid(QgsProcessingAlgorithm):
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
        return GARSGrid()

    def name(self):
        return 'grid_gars'

    def icon(self):
        return QIcon(os.path.join(os.path.dirname(os.path.dirname(__file__)), '../images/generator/grid_quad.svg'))
    
    def displayName(self):
        return self.tr('GARS', 'GARS')

    def group(self):
        return self.tr('Generator', 'Generator')

    def groupId(self):
        return 'grid'

    def tags(self):
        return self.tr('DGGS, grid, GARS, generator').split(',')
    
    txt_en = 'GARS DGGS Generator'
    txt_vi = 'GARS DGGS Generator'
    figure = '../images/tutorial/grid_gars.png'

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
            self.tr('Resolution [1..4] (30, 15, 5, 1 minutes)'),
            defaultValue=1,  # Default to the first option (30 minutes)
             minValue= 0,
            maxValue=5,
            optional=False
        )
        self.addParameter(param)

        param = QgsProcessingParameterFeatureSink(
                self.OUTPUT,
                'GARS')
        self.addParameter(param)
                    
    def prepareAlgorithm(self, parameters, context, feedback):
        self.resolution = self.parameterAsInt(parameters, self.RESOLUTION, context)
        if self.resolution < 1 or self.resolution> 4:
            feedback.reportError('Resolution must be in range [1..4]')
            return False

        # Get the extent parameter
        self.grid_extent = self.parameterAsExtent(parameters, self.EXTENT, context)

        if self.resolution > 1 and (self.grid_extent is None or self.grid_extent.isEmpty()):
            feedback.reportError('For performance reason, when resolution is greater than 1, the grid extent must be set.')
            return False
        
        return True
    
    def outputFields(self):
        output_fields = QgsFields() 
        output_fields.append(QgsField("gars", QVariant.String))
        output_fields.append(QgsField('resolution', QVariant.Int))
        output_fields.append(QgsField('center_lat', QVariant.Double))
        output_fields.append(QgsField('center_lon', QVariant.Double))
        output_fields.append(QgsField('cell_width', QVariant.Double))
        output_fields.append(QgsField('cell_height', QVariant.Double))
        output_fields.append(QgsField('cell_area', QVariant.Double))
        output_fields.append(QgsField('cell_perimeter', QVariant.Double))
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
            QgsCoordinateReferenceSystem('EPSG:4326')
        )
         
        if sink is None:
            raise QgsProcessingException("Failed to create output sink")

        lon_min, lon_max = -180.0, 180.0
        lat_min, lat_max = -90.0, 90.0
        minutes_map = {
                1: 30,  # 30 minutes
                2: 15,  # 15 minutes
                3: 5,   # 5 minutes
                4: 1    # 1 minute
            }
        
        resolution_minutes = minutes_map[self.resolution]
        resolution_degrees = resolution_minutes / 60.0

        longitudes = np.arange(lon_min, lon_max, resolution_degrees)
        latitudes = np.arange(lat_min, lat_max, resolution_degrees)
            
        if self.grid_extent is None or self.grid_extent.isEmpty():          
            # Calculate total cells for progress reporting
            total_cells = len(longitudes) * len(latitudes)
            cell_count = 0

            feedback.pushInfo(f"Total cells to be generated: {total_cells}.")
            
            # Loop over longitudes and latitudes
            for lon in longitudes:
                for lat in latitudes:
                    cell_polygon = Polygon([
                        (lon, lat),
                        (lon + resolution_degrees, lat),
                        (lon + resolution_degrees, lat + resolution_degrees),
                        (lon, lat + resolution_degrees),
                        (lon, lat) ])
                    cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)
                    gars_feature = QgsFeature()
                    gars_feature.setGeometry(cell_geometry)
                    
                    center_lat, center_lon, cell_width, cell_height, cell_area,cell_perimeter = graticule_dggs_metrics(cell_polygon)
                    gars_id = str(GARSGRID.from_latlon(lat, lon, resolution_minutes))
                    gars_feature.setAttributes([gars_id, self.resolution,center_lat, center_lon, cell_width, cell_height, cell_area,cell_perimeter])                    
                    
                    sink.addFeature(gars_feature, QgsFeatureSink.FastInsert)         
                    # Update progress and feedback message
                    cell_count += 1
                    feedback.setProgress(int((cell_count / total_cells) * 100))
                    
                    if feedback.isCanceled():
                        break            
           
        else:
            # Calculate the cell indices corresponding to the extent bounds
            min_x = max(0, int((self.grid_extent.xMinimum() - lon_min) /  resolution_degrees))
            max_x = min(len(longitudes), int((self.grid_extent.xMaximum() - lon_min) / resolution_degrees) + 1)
            min_y = max(0, int((self.grid_extent.yMinimum() - lat_min) / resolution_degrees))
            max_y = min(len(latitudes), int((self.grid_extent.yMaximum() - lat_min) / resolution_degrees) + 1)

            # Total cells to process, for progress feedback
            total_cells = (max_x - min_x) * (max_y - min_y)
            cell_count = 0
            feedback.pushInfo(f"Total cells to be generated: {total_cells}.")
            
            # Prepare to process only the cells within the valid range (intersecting with extent)
            for i in range(min_x, max_x):
                for j in range(min_y, max_y):
                    lon = longitudes[i]
                    lat = latitudes[j]
                    cell_polygon = Polygon([
                        (lon, lat),
                        (lon + resolution_degrees, lat),
                        (lon + resolution_degrees, lat + resolution_degrees),
                        (lon, lat + resolution_degrees),
                        (lon, lat) ])
                   
                    cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)
                    gars_feature = QgsFeature()
                    gars_feature.setGeometry(cell_geometry)
                    
                    center_lat, center_lon, cell_width, cell_height, cell_area,cell_perimeter = graticule_dggs_metrics(cell_polygon)
                    gars_id = str(GARSGRID.from_latlon(lat, lon, resolution_minutes))
                    gars_feature.setAttributes([gars_id, self.resolution,center_lat, center_lon, cell_width, cell_height, cell_area,cell_perimeter])                    
                    
                    sink.addFeature(gars_feature, QgsFeatureSink.FastInsert)         
                    # Update progress and feedback message
                    cell_count += 1
                    feedback.setProgress(int((cell_count / total_cells) * 100))
                    
                    if feedback.isCanceled():
                        break       
        
        feedback.pushInfo("GARS DGGS generation completed.")            
        # Set styling if loading the layer
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
        label.fieldName = 'gars'
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