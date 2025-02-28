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
import os, sys
import subprocess
from PyQt5.QtWidgets import QMessageBox

import h3    
    
from ...vgridlibrary.imgs import Imgs

from shapely.geometry import Polygon,box
from pyproj import Geod
geod = Geod(ellps="WGS84")
max_cells = 10_000_000


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
        return QIcon(os.path.join(os.path.dirname(os.path.dirname(__file__)), '../images/grid_gzd.png'))
    
    def displayName(self):
        return self.tr('H3', 'H3')

    def group(self):
        return self.tr('Grid Generator', 'Grid Generator')

    def groupId(self):
        return 'grid'

    def tags(self):
        return self.tr('grid, H3, generator').split(',')
    
    txt_en = 'H3 Grid'
    txt_vi = 'H3 Grid'
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
                    self.tr('Resolution'),
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
        if self.resolution < 0 or self.resolution > 15:
            feedback.reportError('resolution parameter must be in range [0,15]')
            return False
         
         # Get the extent parameter
        self.grid_extent = self.parameterAsExtent(parameters, self.EXTENT, context)
        if self.resolution > 4 and (self.grid_extent is None or self.grid_extent.isEmpty()):
            feedback.reportError('For performance reason, when resolution is greater than 4, the grid extent must be set.')
            return False
        
        return True
    
    def fix_h3_antimeridian_cells(self, hex_boundary, threshold=-128):
        if any(lon < threshold for _, lon in hex_boundary):
            # Adjust all longitudes accordingly
            return [(lat, lon - 360 if lon > 0 else lon) for lat, lon in hex_boundary]
        return hex_boundary

    def processAlgorithm(self, parameters, context, feedback):        
        fields = QgsFields()
        fields.append(QgsField("h3", QVariant.String))
        
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
            extent_bbox = [
                [self.grid_extent.xMinimum(), self.grid_extent.yMinimum()],
                [self.grid_extent.xMaximum(), self.grid_extent.yMaximum()]
            ]        
        bbox = None
              
        if extent_bbox:
            minx, miny = extent_bbox[0]
            maxx, maxy = extent_bbox[1]
            # Create a Shapely box
            bbox = box(minx, miny, maxx, maxy)
            
            # if extent_bbox:           
            bbox_cells  = h3.geo_to_cells(bbox,self.resolution)

            total_cells = len(bbox_cells)           
                    
            feedback.pushInfo(f"Total cells to be generated: {total_cells}.")
            if total_cells > max_cells:
                feedback.reportError(f"For performance reason, the total cells must be lesser than {max_cells}. Please input an appropriate extent or resolution")
                return {self.OUTPUT: dest_id}
            
            for idx, bbox_buffer_cell in enumerate(bbox_cells):
                progress = int((idx / total_cells) * 100)
                feedback.setProgress(progress)
                # Get the boundary of the cell
                hex_boundary = h3.cell_to_boundary(bbox_buffer_cell)
                # Wrap and filter the boundary
                filtered_boundary = self.fix_h3_antimeridian_cells(hex_boundary)
                # Reverse lat/lon to lon/lat for GeoJSON compatibility
                reversed_boundary = [(lon, lat) for lat, lon in filtered_boundary]
                cell_wkt = Polygon(reversed_boundary).wkt            
                
                # Convert WKT to QgsGeometry
                cell_geometry = QgsGeometry.fromWkt(cell_wkt)

                if not cell_geometry.intersects(QgsGeometry.fromRect(self.grid_extent)):
                    continue
                                     
                feature = QgsFeature()
                feature.setGeometry(cell_geometry)
                feature.setAttributes([bbox_buffer_cell])
                sink.addFeature(feature, QgsFeatureSink.FastInsert)

                if idx % 10_000 == 0 and idx > 10_000:  # Log progress every 10_000 cells
                    feedback.pushInfo(f"Processed {idx} of {total_cells} cells...")

                if feedback.isCanceled():
                    break
        else:
            base_cells = h3.get_res0_cells()
            total_base_cells = len(base_cells)
            for idx, cell in enumerate(base_cells):
                progress = int((idx / total_base_cells) * 100)
                feedback.setProgress(progress) 
                feedback.pushInfo(f"Processed {idx} of {total_base_cells} base cells...")               
               
                child_cells = h3.cell_to_children(cell, self.resolution)                
                # Progress bar for child cells
                for child_cell in child_cells:
                    # Get the boundary of the cell
                    hex_boundary = h3.cell_to_boundary(child_cell)
                    # Wrap and filter the boundary
                    filtered_boundary = self.fix_h3_antimeridian_cells(hex_boundary)
                    # Reverse lat/lon to lon/lat for GeoJSON compatibility
                    reversed_boundary = [(lon, lat) for lat, lon in filtered_boundary]
                    cell_wkt = Polygon(reversed_boundary).wkt
                    cell_geometry = QgsGeometry.fromWkt(cell_wkt)
                
                    feature = QgsFeature()
                    feature.setGeometry(cell_geometry)
                    feature.setAttributes([child_cell])
                    sink.addFeature(feature, QgsFeatureSink.FastInsert)                    

                    if feedback.isCanceled():
                        break
                
        feedback.pushInfo("H3 grid generation completed.")
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
        label.fieldName = 's2_token'
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