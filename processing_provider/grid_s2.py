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
from ..vgridlibrary.geocode.s2 import CellId, LatLng, LatLngRect,Cell
from ..vgridlibrary.imgs import Imgs


class GridS2(QgsProcessingAlgorithm):
    EXTENT = 'EXTENT'
    PRECISION = 'PRECISION'
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
        return GridS2()

    def name(self):
        return 'grid_s2'

    def icon(self):
        return QIcon(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'images/grid_gzd.png'))
    
    def displayName(self):
        return self.tr('S2', 'S2')

    def group(self):
        return self.tr('Grid Generator', 'Grid Generator')

    def groupId(self):
        return 'grid'

    def tags(self):
        return self.tr('grid, S2, generator').split(',')
    
    txt_en = 'S2 Grid'
    txt_vi = 'S2 Grid'
    figure = 'images/tutorial/codes2cells.png'

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
                    self.PRECISION,
                    self.tr('Precision'),
                    QgsProcessingParameterNumber.Integer,
                    defaultValue=1,
                    minValue= 0,
                    maxValue= 30,
                    optional=False)
        self.addParameter(param)


        param = QgsProcessingParameterFeatureSink(
                self.OUTPUT,
                's2')
        self.addParameter(param)
                    
    def prepareAlgorithm(self, parameters, context, feedback):
        self.precision = self.parameterAsInt(parameters, self.PRECISION, context)  
        if self.precision < 0 or self.precision > 30:
            feedback.reportError('Precision parameter must be in range [0,30]')
            return False
         
         # Get the extent parameter
        self.grid_extent = self.parameterAsExtent(parameters, self.EXTENT, context)
        # Ensure that when precision > 4, the extent must be set
        if self.precision > 10 and (self.grid_extent is None or self.grid_extent.isEmpty()):
            feedback.reportError('For performance reason, when precision is greater than 10, the grid extent must be set.')
            return False
        
        return True
    
    def processAlgorithm(self, parameters, context, feedback):
        fields = QgsFields()
        fields.append(QgsField("s2", QVariant.String))

        # Create the output sink (vector layer)
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

        # Get the grid extent or the entire world if not defined
        if self.grid_extent is None or self.grid_extent.isEmpty():
            # Define the entire world extent using LatLngRect
            south_west = LatLng.from_degrees(-90, -180)
            north_east = LatLng.from_degrees(90, 180)
            bounds = LatLngRect(south_west, north_east)
        else:
            xmin = self.grid_extent.xMinimum()
            ymin = self.grid_extent.yMinimum()
            xmax = self.grid_extent.xMaximum()
            ymax = self.grid_extent.yMaximum()
            
            # Create LatLng objects for bounds (SW and NE corners)
            south_west = LatLng.from_degrees(ymin, xmin)
            north_east = LatLng.from_degrees(ymax, xmax)
            
            # Create LatLngRect from corners
            bounds = LatLngRect(south_west, north_east)

        # Get S2 cell ID at the given precision (resolution level)
        s2_level = self.precision  # Precision corresponds to the S2 cell level (0-30)
        cell_ids = []

        # Iterate over the bounding box and generate S2 cells
        for lat in range(int(bounds.lat_lo().degrees), int(bounds.lat_hi().degrees) + 1):
            for lng in range(int(bounds.lng_lo().degrees), int(bounds.lng_hi().degrees) + 1):
                # Generate a LatLng from the coordinates
                lat_lng = LatLng.from_degrees(lat, lng)
                
                # Create an S2 cell ID at the given precision
                cell_id = CellId.from_lat_lng(lat_lng)
                cell_id = cell_id.parent(s2_level) 
                
                cell_ids.append(cell_id)

        total_cells = len(cell_ids)

        # Iterate over the generated S2 cells and create features
        for index, cell_id in enumerate(cell_ids):
            # Convert CellId to S2Cell
            s2cell = Cell(cell_id)

            # Get the LatLngRect for the cell using the S2Cell's getRectBound method
            cell_rect = s2cell.get_rect_bound()

            # Define the corner points of the cell polygon
            points = [
                QgsPointXY(cell_rect.lat_lo().degrees, cell_rect.lng_lo().degrees),
                QgsPointXY(cell_rect.lat_lo().degrees, cell_rect.lng_hi().degrees),
                QgsPointXY(cell_rect.lat_hi().degrees, cell_rect.lng_hi().degrees),
                QgsPointXY(cell_rect.lat_hi().degrees, cell_rect.lng_lo().degrees),
                QgsPointXY(cell_rect.lat_lo().degrees, cell_rect.lng_lo().degrees)  # Closing the polygon
            ]
            
            # Create a QgsGeometry polygon from the points
            polygon = QgsGeometry.fromPolygonXY([points])
            
            # Generate the 's2' attribute for the S2 cell (e.g., "s2x123456")
            s2_code = f"{cell_id.id()}"

            # Create a new feature and set its geometry and attributes
            feature = QgsFeature(fields)
            feature.setGeometry(polygon)
            feature.setAttribute("s2", s2_code)

            # Add the feature to the output sink
            sink.addFeature(feature, QgsFeatureSink.FastInsert)

            # Push progress information every 1000 cells
            if (index + 1) % 1000 == 0:
                message = f"Processed {index + 1}/{total_cells}"
                feedback.pushInfo(message)

            # Check if the process has been canceled
            if feedback.isCanceled():
                break


        # Apply style to the layer if loaded on completion
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
        label.fieldName = 's2'
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