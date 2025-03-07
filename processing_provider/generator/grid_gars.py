# -*- coding: utf-8 -*-
"""
grid_gars.py
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
    QgsProcessingParameterEnum,
    QgsProcessingException,
    QgsProcessingParameterFeatureSink,
    QgsProcessingAlgorithm,
    QgsFields,
    QgsField,
    QgsPointXY, 
    QgsFeature,
    QgsGeometry,
    QgsRectangle,
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
import numpy as np
from vgrid.utils.gars.garsgrid import GARSGrid  
from ...utils.imgs import Imgs


class GridGARS(QgsProcessingAlgorithm):
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
        return GridGARS()

    def name(self):
        return 'grid_gars'

    def icon(self):
        return QIcon(os.path.join(os.path.dirname(os.path.dirname(__file__)), '../images/grid_gzd.png'))
    
    def displayName(self):
        return self.tr('GARS', 'GARS')

    def group(self):
        return self.tr('DGGS Generator', 'DGGS Generator')

    def groupId(self):
        return 'grid'

    def tags(self):
        return self.tr('DGGS, grid, GARS, generator').split(',')
    
    txt_en = 'GARS Grid Generator'
    txt_vi = 'GARS Grid Generator'
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

        param = QgsProcessingParameterEnum(
            self.RESOLUTION,
            self.tr('RESOLUTION'),
            [self.tr('30 minutes'), self.tr('15 minutes'),self.tr('5 minutes'),self.tr('1 minute')],
            defaultValue=0,  # Default to the first option (30 minutes)
            optional=False
        )
        self.addParameter(param)


        param = QgsProcessingParameterFeatureSink(
                self.OUTPUT,
                'GARS')
        self.addParameter(param)
                    
    def prepareAlgorithm(self, parameters, context, feedback):
        RESOLUTION_index = self.parameterAsEnum(parameters, self.RESOLUTION, context)
        RESOLUTION_values = [30,15,5,1]
        self.RESOLUTION = RESOLUTION_values[RESOLUTION_index]
        if self.RESOLUTION not in  [30,15,5,1]:
            feedback.reportError('RESOLUTION parameter must be in [30,15,5,1] minutes')
            return False

        # Get the extent parameter
        self.grid_extent = self.parameterAsExtent(parameters, self.EXTENT, context)
        # Ensure that when RESOLUTION > 4, the extent must be set
        if self.RESOLUTION < 30 and (self.grid_extent is None or self.grid_extent.isEmpty()):
            feedback.reportError('For performance reason, when RESOLUTION is smaller than 30 minutes, the grid extent must be set.')
            return False
        
        return True
    
    def garsgrid(self, RESOLUTION, feedback):
        # Define bounds for the whole planet
        lon_min, lon_max = -180.0, 180.0
        lat_min, lat_max = -90.0, 90.0
        
        # Set resolution in degrees based on RESOLUTION in minutes
        if RESOLUTION in [30,15,5,1]:
            res = RESOLUTION/ 60.0
        # if RESOLUTION == 1:
        #     res = 1 / 60.0  # 1 minute in degrees
        # elif RESOLUTION == 5:
        #     res = 5 / 60.0  # 5 minutes in degrees
        # elif RESOLUTION == 15:
        #     res = 15 / 60.0  # 15 minutes in degrees
        # elif RESOLUTION == 30:
        #     res = 30 / 60.0  # 30 minutes in degrees
        else:
            raise ValueError("Unsupported RESOLUTION. Choose from 1, 5, 15, or 30 minutes.")
        
        gars_grid = []

        # Use numpy to generate ranges with floating-point steps based on resolution
        longitudes = np.arange(lon_min, lon_max, res)
        latitudes = np.arange(lat_min, lat_max, res)

        # Calculate total cells for progress reporting
        total_cells = len(longitudes) * len(latitudes)
        cell_count = 0

        feedback.pushInfo(f"Total cells to be generated: {total_cells}.")
        
        if total_cells > 1000000:
            feedback.reportError("For performance reason, it must be lesser than 1000000. Please input an appropriate extent or RESOLUTION")
            return None

        # Loop over longitudes and latitudes
        for lon in longitudes:
            for lat in latitudes:
                # Define vertices of the polygon for each GARS cell
                vertices = [
                    QgsPointXY(lon, lat),
                    QgsPointXY(lon + res, lat),
                    QgsPointXY(lon + res, lat + res),
                    QgsPointXY(lon, lat + res),
                    QgsPointXY(lon, lat)  # Close the polygon
                ]
                
                # Create QgsGeometry polygon
                polygon = QgsGeometry.fromPolygonXY([vertices])
                
                # Generate GARS code (assuming GARSGrid class with a `from_latlon` method)
                gars_code = GARSGrid.from_latlon(lat, lon, res * 60)  # Convert res to minutes for GARS
                
                # Append the QgsGeometry polygon and its GARS code
                gars_grid.append({'geometry': polygon, 'gars': str(gars_code)})

                # Update progress
                cell_count += 1
                progress = int((cell_count / total_cells) * 100)
                feedback.setProgress(progress)
                
                # Optionally log progress every 10000 cells
                if cell_count % 10000 == 0:
                    feedback.pushInfo(f"Processed {cell_count}/{total_cells} cells ")

                if feedback.isCanceled():
                    feedback.pushInfo("Process canceled by user.")
                    return []  # Cancel if the user stops the process

        return gars_grid

    def garsgrid_with_extent(self, RESOLUTION, extent, feedback):
        # Define bounds for the whole planet
        lon_min, lon_max = -180.0, 180.0
        lat_min, lat_max = -90.0, 90.0
        
        # Set resolution in degrees based on RESOLUTION in minutes
        if RESOLUTION in [30,15,5,1]:
            res = RESOLUTION/ 60.0
        # if RESOLUTION == 1:
        #     res = 0.5 / 60.0  # 1 minute in degrees
        # elif RESOLUTION == 5:
        #     res = 5 / 60.0  # 5 minutes in degrees
        # elif RESOLUTION == 15:
        #     res = 15 / 60.0  # 15 minutes in degrees
        # elif RESOLUTION == 30:
        #     res = 30 / 60.0  # 30 minutes in degrees
        else:
            raise ValueError("Unsupported RESOLUTION. Choose from 1, 5, 15, or 30 minutes.")
        
        gars_grid = []

        # Use numpy to generate ranges with floating-point steps based on resolution
        longitudes = np.arange(lon_min, lon_max, res)
        latitudes = np.arange(lat_min, lat_max, res)

        # Calculate the cell indices corresponding to the extent bounds
        min_x = max(0, int((extent.xMinimum() - lon_min) / res))
        max_x = min(len(longitudes), int((extent.xMaximum() - lon_min) / res) + 1)
        min_y = max(0, int((extent.yMinimum() - lat_min) / res))
        max_y = min(len(latitudes), int((extent.yMaximum() - lat_min) / res) + 1)

        # Total cells to process, for progress feedback
        total_cells = (max_x - min_x) * (max_y - min_y)
        cell_count = 0
        feedback.pushInfo(f"Total cells to be generated: {total_cells}.")
        
        if total_cells > 1000000:
            feedback.reportError("For performance reason, it must be lesser than 1000,000. Please input an appropriate extent or RESOLUTION")
            return None

        # Prepare to process only the cells within the valid range (intersecting with extent)
        for i in range(min_x, max_x):
            for j in range(min_y, max_y):
                lon = longitudes[i]
                lat = latitudes[j]

                # Define vertices of the polygon for each GARS cell
                vertices = [
                    QgsPointXY(lon, lat),
                    QgsPointXY(lon + res, lat),
                    QgsPointXY(lon + res, lat + res),
                    QgsPointXY(lon, lat + res),
                    QgsPointXY(lon, lat)  # Close the polygon
                ]
                
                # Create QgsGeometry polygon
                polygon = QgsGeometry.fromPolygonXY([vertices])
                
                # Generate GARS code (assuming GARSGrid class with a `from_latlon` method)
                gars_code = GARSGrid.from_latlon(lat, lon, res * 60)  # Convert res to minutes for GARS
                
                # Create a feature
                feature = QgsFeature()

                # Add 'gars' attribute to the feature (if not already defined)
                feature.setFields(QgsFields([QgsField('gars', QVariant.String)]))  # Define the 'gars' attribute
                
                # Set the geometry of the feature
                feature.setGeometry(polygon)
                
                # Set the 'gars' attribute (set the value of 'gars' for this feature)
                feature.setAttribute('gars', str(gars_code))  # Store GARS code as attribute

                # Add the feature to the output list
                gars_grid.append(feature)

                # Update progress
                cell_count += 1
                progress = int((cell_count / total_cells) * 100)
                feedback.setProgress(progress)
                
                # Optionally log progress every 1000 cells
                if cell_count % 1000 == 0:
                    feedback.pushInfo(f"Processed {cell_count}/{total_cells} cells")

                # Stop if process is canceled
                if feedback.isCanceled():
                    feedback.pushInfo("Process canceled by user.")
                    return []  # Cancel if the user stops the process

        return gars_grid

    def processAlgorithm(self, parameters, context, feedback):
        fields = QgsFields()
        fields.append(QgsField("gars", QVariant.String))

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
            grid_cells = self.garsgrid(self.RESOLUTION,feedback)
            if grid_cells:
                for entry in grid_cells:
                    # Create a QgsFeature object
                    feature = QgsFeature()
                    
                    # Set the feature's geometry (from the dictionary)
                    feature.setGeometry(entry['geometry'])
                    
                    # Set the feature's attributes (in this case, just the 'gars' attribute)
                    feature.setAttributes([entry['gars']])
                    
                    # Add the feature to the sink (use FastInsert for faster insertion)
                    sink.addFeature(feature, QgsFeatureSink.FastInsert)

        else:
            grid_cells = self.garsgrid_with_extent(self.RESOLUTION, self.grid_extent, feedback)
            if (grid_cells):
                for feature in grid_cells:
                    # Create a QgsFeature object
                    feature_object = QgsFeature()
                    
                    # Set the feature's geometry (from the feature returned by garsgrid_with_extent)
                    feature_object.setGeometry(feature.geometry())
                    
                    # Set the feature's attributes (in this case, just the 'gars' attribute)
                    feature_object.setAttributes([feature['gars']])
                    
                    # Add the feature to the sink (use FastInsert for faster insertion)
                    sink.addFeature(feature_object, QgsFeatureSink.FastInsert)
            

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