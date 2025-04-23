# -*- coding: utf-8 -*-
"""
grid_h3.py
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

import h3    
    
from ...utils.imgs import Imgs
from vgrid.generator.h3grid import fix_h3_antimeridian_cells
from shapely.geometry import Polygon,box
from vgrid.generator.settings import geodesic_dggs_metrics


class GridH3(QgsProcessingAlgorithm):
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
        return GridH3()

    def name(self):
        return 'grid_h3'

    def icon(self):
        return QIcon(os.path.join(os.path.dirname(os.path.dirname(__file__)), '../images/generator/grid_h3.svg'))
    
    def displayName(self):
        return self.tr('H3', 'H3')

    def group(self):
        return self.tr('Generator', 'Generator')

    def groupId(self):
        return 'grid'

    def tags(self):
        return self.tr('DGGS, grid, H3, generator').split(',')
    
    txt_en = 'H3 DGGS Generator'
    txt_vi = 'H3 DGGS Generator'
    figure = '../images/tutorial/grid_h3.png'

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
                    self.tr('Resolution [0.15]'),
                    QgsProcessingParameterNumber.Integer,
                    defaultValue=1,
                    minValue= 0,
                    maxValue= 15,
                    optional=False)
        self.addParameter(param)


        param = QgsProcessingParameterFeatureSink(
                self.OUTPUT,
                'H3')
        self.addParameter(param)
                    
    def prepareAlgorithm(self, parameters, context, feedback):
        self.resolution = self.parameterAsInt(parameters, self.RESOLUTION, context)         
        self.grid_extent = self.parameterAsExtent(parameters, self.EXTENT, context)
        if self.resolution > 4 and (self.grid_extent is None or self.grid_extent.isEmpty()):
            feedback.reportError('For performance reason, when resolution is greater than 4, the grid extent must be set.')
            return False
        
        return True
    
    def outputFields(self):
        output_fields = QgsFields() 
        output_fields.append(QgsField("h3", QVariant.String))
        output_fields.append(QgsField('resolution', QVariant.Int))
        output_fields.append(QgsField('center_lat', QVariant.Double))
        output_fields.append(QgsField('center_lon', QVariant.Double))
        output_fields.append(QgsField('avg_edge_len', QVariant.Double))
        output_fields.append(QgsField('cell_area', QVariant.Double))

        return output_fields

    def processAlgorithm(self, parameters, context, feedback):        
        fields = self.outputFields()
        # Output layer initialization
        (sink, dest_id) = self.parameterAsSink(
            parameters,
            self.OUTPUT,
            context,
            fields,
            QgsWkbTypes.Polygon,
            QgsCoordinateReferenceSystem('EPSG:4326')
        )

        if not sink:
            raise QgsProcessingException(self.invalidSinkError(parameters, self.OUTPUT))

        if self.grid_extent is None or self.grid_extent.isEmpty():
            extent_bbox = None
        else:        
            extent_bbox = box(self.grid_extent.xMinimum(), self.grid_extent.yMinimum(), 
                            self.grid_extent.xMaximum(), self.grid_extent.yMaximum())  
              
        if extent_bbox:                
            bbox_cells  = h3.geo_to_cells(extent_bbox,self.resolution)
            total_cells = len(bbox_cells)           
                    
            feedback.pushInfo(f"Total cells to be generated: {total_cells}.")
            for idx, bbox_cell in enumerate(bbox_cells):
                progress = int((idx / total_cells) * 100)
                feedback.setProgress(progress)

                hex_boundary = h3.cell_to_boundary(bbox_cell)
                filtered_boundary = fix_h3_antimeridian_cells(hex_boundary)
                reversed_boundary = [(lon, lat) for lat, lon in filtered_boundary]
                cell_polygon = Polygon(reversed_boundary)
                cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)

                if not cell_geometry.intersects(QgsGeometry.fromRect(self.grid_extent)):
                    continue
                                     
                h3_feature = QgsFeature()
                h3_feature.setGeometry(cell_geometry)
                
                num_edges = 6
                if (h3.is_pentagon(bbox_cell)):
                    num_edges = 5                
                center_lat, center_lon, avg_edge_len, cell_area = geodesic_dggs_metrics(cell_polygon, num_edges)
                h3_feature.setAttributes([bbox_cell, self.resolution, center_lat, center_lon, avg_edge_len, cell_area])                    
                sink.addFeature(h3_feature, QgsFeatureSink.FastInsert)                    

                if feedback.isCanceled():
                    break
        else:
            base_cells = h3.get_res0_cells()
            total_base_cells = len(base_cells)
            total_cells = h3.get_num_cells(self.resolution)
            feedback.pushInfo(f"Total cells to be generated: {total_cells}.")
            for idx, cell in enumerate(base_cells):
                progress = int((idx / total_base_cells) * 100)
                feedback.setProgress(progress) 
               
                child_cells = h3.cell_to_children(cell, self.resolution)                
                # Progress bar for child cells
                for child_cell in child_cells:
                    # Get the boundary of the cell
                    hex_boundary = h3.cell_to_boundary(child_cell)
                    # Wrap and filter the boundary
                    filtered_boundary = fix_h3_antimeridian_cells(hex_boundary)
                    # Reverse lat/lon to lon/lat for GeoJSON compatibility
                    reversed_boundary = [(lon, lat) for lat, lon in filtered_boundary]
                    cell_polygon = Polygon(reversed_boundary) 
                    cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)
                
                    h3_feature = QgsFeature()
                    h3_feature.setGeometry(cell_geometry)
                    
                    num_edges = 6
                    if (h3.is_pentagon(child_cell)):
                        num_edges = 5 
                    
                    center_lat, center_lon, avg_edge_len, cell_area = geodesic_dggs_metrics(cell_polygon, num_edges)
                    h3_feature.setAttributes([child_cell, self.resolution, center_lat, center_lon, avg_edge_len, cell_area])                    
                    sink.addFeature(h3_feature, QgsFeatureSink.FastInsert)                    

                    if feedback.isCanceled():
                        break
                
        feedback.pushInfo("H3 DGGS generation completed.")
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
        label.fieldName = 'h3'
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