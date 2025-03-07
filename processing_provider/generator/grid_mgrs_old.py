# -*- coding: utf-8 -*-
"""
grid_mgrs.py
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
    QgsCoordinateTransform,
    QgsRectangle,
    QgsFields,
    QgsField,
    QgsPointXY, 
    QgsPoint,
    QgsPolygon,
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
from vgrid.utils import mgrs
from ...utils.imgs import Imgs


class GridMGRS(QgsProcessingAlgorithm):
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
        return GridMGRS()

    def name(self):
        return 'grid_mgrs'

    def icon(self):
        return QIcon(os.path.join(os.path.dirname(os.path.dirname(__file__)), '../images/grid_gzd.png'))
    
    def displayName(self):
        return self.tr('MGRS', 'MGRS')

    def group(self):
        return self.tr('DGGS Generator', 'DGGS Generator')

    def groupId(self):
        return 'grid'

    def tags(self):
        return self.tr('grid, MGRS, generator').split(',')
    
    txt_en = 'MGRS Grid'
    txt_vi = 'MGRS Grid'
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
                    defaultValue=0,
                    minValue= 0,
                    maxValue= 5,
                    optional=False)
        self.addParameter(param)


        param = QgsProcessingParameterFeatureSink(
                self.OUTPUT,
                'MGRS')
        self.addParameter(param)
                    
    def prepareAlgorithm(self, parameters, context, feedback):
        self.RESOLUTION = self.parameterAsInt(parameters, self.RESOLUTION, context)  
        if self.RESOLUTION < 0 or self.RESOLUTION > 5:
            feedback.reportError('RESOLUTION parameter must be in range [0,5]')
            return False
         
         # Get the extent parameter
        self.grid_extent = self.parameterAsExtent(parameters, self.EXTENT, context)
        # Ensure that when RESOLUTION > 4, the extent must be set
        if self.RESOLUTION > 3 and (self.grid_extent is None or self.grid_extent.isEmpty()):
            feedback.reportError('For performance reason, when RESOLUTION is greater than 3, the grid extent must be set.')
            return False
        
        return True
    
    def processAlgorithm(self, parameters, context, feedback):
        fields = QgsFields()
        fields.append(QgsField("mgrs", QVariant.String))

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
        

        if self.grid_extent is None or self.grid_extent.isEmpty():
            lat_min, lat_max = -79.99999, 84.0  # MGRS is valid between these latitudes
            lon_min, lon_max = -180.0, 180.0
        else:
            lon_min = self.grid_extent.xMinimum()
            lat_min = self.grid_extent.yMinimum()
            lon_max = self.grid_extent.xMaximum()
            lat_max = self.grid_extent.yMaximum()

        step = 1
        if self.RESOLUTION == 0:
            step = 1    # 100 km grid cell
        if self.RESOLUTION == 1:
            step = 0.1    # 10 km grid cell
        elif self.RESOLUTION == 2:
            step = 0.01   # 1 km grid cell
        elif self.RESOLUTION == 3:
            step = 0.001  # 100 m grid cell
        elif self.RESOLUTION == 4:
            step = 0.0001 # 10 m grid cell
        elif self.RESOLUTION == 5:
            step = 0.00001 # 1 m grid cell
        else:
            step = 1 
    

        total_cells = int(((lat_max - lat_min) / step) * ((lon_max - lon_min) / step)) 
        processed_cells = 0


        lat = lat_min
        while lat <= lat_max:
            lon = lon_min
            while lon <= lon_max:
                # Convert lat/lon to MGRS code at the desired RESOLUTION
                mgrs_code = mgrs.toMgrs(lat, lon, self.RESOLUTION)

                # Get the MGRS cell polygon (a tuple of (lon, lat) coordinates for the corners of the MGRS cell)
                origin_lat, origin_lon, min_lat, min_lon, max_lat, max_lon, RESOLUTION = mgrs.mgrscell(mgrs_code)

                # Create the coordinates for the polygon (using the corners)
                vertices = [
                    QgsPointXY(min_lon, min_lat),
                    QgsPointXY(max_lon, min_lat),
                    QgsPointXY(max_lon, max_lat),
                    QgsPointXY(min_lon, max_lat),
                    QgsPointXY(min_lon, min_lat)
                ]
                polygon = QgsGeometry.fromPolygonXY([vertices])

                # Create a QgsFeature and set the geometry
                feature = QgsFeature()
                feature.setGeometry(polygon)

                # Optionally, add attributes to the feature
                feature.setAttributes([mgrs_code])

                # Add the feature to the sink (using FastInsert for efficiency)
                sink.addFeature(feature, QgsFeatureSink.FastInsert)

                processed_cells += 1
                # Optionally, show progress info
                if processed_cells % 10000 == 0:  # Log every 100 processed cells
                    feedback.pushInfo(f"Processed {processed_cells}/{total_cells} cells")
                
                progress_percentage = (processed_cells / total_cells) * 100
                feedback.setProgress(int(progress_percentage))  # Update progress bar

                if feedback.isCanceled():
                    break
                lon += step
            lat += step
      
        # Apply styling if layer is loaded on completion
        if context.willLoadLayerOnCompletion(dest_id):
            lineColor = QColor.fromRgb(random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
            fontColor = QColor('#000000')
            context.layerToLoadOnCompletionDetails(dest_id).setPostProcessor(
                StylePostProcessor.create(lineColor, fontColor)
            )
        
        feedback.pushInfo("Processing complete.")
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
        label.fieldName = 'mgrs'
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