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
    QgsProcessingParameterFeatureSink,
    QgsProcessingAlgorithm,
    QgsProcessingException,
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
import os,math
from ...vgridlibrary.conversion import mgrs
from ...vgridlibrary.imgs import Imgs


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
        return self.tr('Grid Generator', 'Grid Generator')

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
        # Define fields
        fields = QgsFields()
        fields.append(QgsField("MGRS", QVariant.String))

        # Create output sink
        (sink, dest_id) = self.parameterAsSink(
            parameters, self.OUTPUT,
            context, fields, QgsWkbTypes.Polygon, QgsCoordinateReferenceSystem("EPSG:4326")
        )
        
        if sink is None:
            raise QgsProcessingException("Failed to create output sink")        

        if self.grid_extent is None or self.grid_extent.isEmpty():
            lat_min, lat_max = -80, 84.0  # MGRS is valid between these latitudes
            lon_min, lon_max = -180.0, 180.0
        else:
            lon_min = self.grid_extent.xMinimum()
            lat_min = self.grid_extent.yMinimum()
            lon_max = self.grid_extent.xMaximum()
            lat_max = self.grid_extent.yMaximum()

        feedback.pushInfo(f"Generating MGRS grid at RESOLUTION {self.RESOLUTION}.")

        # Define the grid zone bounds and step sizes
        bands = "CDEFGHJKLMNPQRSTUVWX"
        # bands = "C"
        lat = -80
        for band in bands:
            feedback.pushInfo(f"Processing band {band}")
            height = 8 if band != 'X' else 12
            lon = -180
            while lon < 180:
                # Loop through GZDs
                gzd = f"{(int((lon + 180) / 6) + 1):02d}{band}"
                create_mgrs_grids(lon, lat, 6, height, gzd, self.RESOLUTION, sink, feedback)
                lon += 6
            lat += height

        feedback.pushInfo("MGRS grid generation completed.")

        # Apply styling (optional)
        if context.willLoadLayerOnCompletion(dest_id):
            lineColor = QColor('#FF0000')  # Red lines
            fontColor = QColor('#000000')  # Black font
            context.layerToLoadOnCompletionDetails(dest_id).setPostProcessor(
                StylePostProcessor.create(lineColor, fontColor)
            )

        return {self.OUTPUT: dest_id}

def km_to_lon_degree(km, lat):
    """Convert a distance in kilometers to degrees of longitude at a given latitude."""
    return km / (111.32 * math.cos(math.radians(lat)))

def create_mgrs_grids(lon_start, lat_start, lon_width, lat_height, gzd, RESOLUTION, sink, feedback):
    """Create MGRS grids at the specified RESOLUTION."""
    if RESOLUTION == 0:
        # RESOLUTION 0 means 100 km x 100 km squares (100,000 meters)
        lon_step_km = 100  # 100 km step in longitude
        lat_step_km = 100  # 100 km step in latitude

        # Convert lon_step_km and lat_step_km to degrees of longitude and latitude
        lon_step_deg = km_to_lon_degree(lon_step_km, lat_start)  # Convert to degrees at the current latitude
        lat_step_deg = lat_step_km / 111.32  # Convert km to degrees for latitude (constant)

    else:
        # Calculate the step size for higher RESOLUTION
        step = 10 ** (5 - RESOLUTION)  # Step size in meters
        lon_step_deg = km_to_lon_degree(step / 1000, lat_start)  # Convert meters to degrees
        lat_step_deg = step / 111.32  # Convert meters to degrees for latitude

    # Add logging to check the calculated steps
    feedback.pushInfo(f"Lon step (in degrees): {lon_step_deg}, Lat step (in degrees): {lat_step_deg}")

    # Iterate over the grid to create each polygon
    for i in range(int(lon_width / lon_step_deg)):
        for j in range(int(lat_height / lat_step_deg)):
            lon_min = lon_start + i * lon_step_deg
            lon_max = lon_min + lon_step_deg
            lat_min = lat_start + j * lat_step_deg
            lat_max = lat_min + lat_step_deg

            # Create a MGRS code for each grid square
            mgrs_code = f"{gzd}{i:02d}{j:02d}"
            add_polygon_to_sink(lon_min, lat_min, lon_max, lat_max, mgrs_code, sink, feedback)

def add_polygon_to_sink(lon_min, lat_min, lon_max, lat_max, mgrs_code, sink, feedback):
    """Add a polygon representing the MGRS grid cell to the sink."""
    try:
        # Define the coordinates of the polygon
        polygon = QgsGeometry.fromPolygonXY([[QgsPointXY(lon_min, lat_min),
                                              QgsPointXY(lon_max, lat_min),
                                              QgsPointXY(lon_max, lat_max),
                                              QgsPointXY(lon_min, lat_max),
                                              QgsPointXY(lon_min, lat_min)]])
        # Create a feature and add the polygon geometry
        feature = QgsFeature()
        feature.setGeometry(polygon)
        feature.setAttributes([mgrs_code])  # Set the MGRS code as an attribute
        sink.addFeature(feature, QgsFeatureSink.FastInsert)
        feedback.pushInfo(f"Added MGRS cell: {mgrs_code}")
    except Exception as e:
        feedback.pushWarning(f"Error adding MGRS cell {mgrs_code}: {e}")


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