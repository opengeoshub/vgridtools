# -*- coding: utf-8 -*-
"""
raster2dggs.py
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

import os

from qgis.core import (
    QgsProcessingParameterRasterLayer,
    QgsProcessingParameterFeatureSink,
    QgsFeatureSink,
    QgsProcessingAlgorithm,
    QgsProcessingParameterEnum,
    QgsProcessingParameterNumber,
    QgsWkbTypes,
    QgsProcessing,
    QgsProcessingException
    )

from qgis.core import QgsApplication
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtCore import QCoreApplication,QVariant

import platform
from ...utils.imgs import Imgs
from ...utils.conversion.raster2dggs import *

class Raster2DGGS(QgsProcessingAlgorithm):
    """
    convert Raster Layer to H3, S2, Rhealpix, ISEA4T, ISEA3H, EASE, QTM, OLC, Geohash, GEOREF, MGRS, Tilecode, Maidenhead, GARS
    """
    INPUT = 'INPUT'
    DGGS_TYPE = 'DGGS_TYPE'
    RESOLUTION = 'RESOLUTION'
    OUTPUT = 'OUTPUT'
    
    DGGS_TYPES = [
        'H3', 'S2','Rhealpix','EASE', 'QTM', 'OLC', 'Geohash', 
        # 'GEOREF',
        'MGRS', 'Tilecode','Quadkey']
    DGGS_RESOLUTION = {
        'H3': (0, 15, 10),
        'S2': (0, 30, 16),
        'Rhealpix': (1, 15,11),      
        'EASE':(0,6,4),
        'QTM':(1,24,12),
        'OLC': (2, 15, 10),
        'Geohash': (1, 30, 15),
        # 'GEOREF': (0, 10, 6),
        'MGRS': (0, 5, 4),
        'Tilecode': (0, 29, 15),
        'Quadkey': (0, 29, 15)        
    }
    if platform.system() == 'Windows':
        index = DGGS_TYPES.index('Rhealpix') + 1
        DGGS_TYPES[index:index] = ['ISEA4T', 'ISEA3H']

        DGGS_RESOLUTION.update({
            'ISEA4T': (0, 39, 18),
            'ISEA3H': (0, 40, 20),
        })

      

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
        return Raster2DGGS()

    def name(self):
        return 'raster2dggs'

    def icon(self):
        return QIcon(os.path.join(os.path.dirname(os.path.dirname(__file__)), '../images/conversion/raster2dggs.png'))
    
    def displayName(self):
        return self.tr('Raster to DGGS', 'Raster to DGGS')

    def group(self):
        return self.tr('Conversion', 'Conversion')

    def groupId(self):
        return 'conversion'

    def tags(self):
        return self.tr('raster, S2, H3, Rhealpix, ISEA4T, ISEA3H, EASE, OLC, OpenLocationCode, Google Plus Codes, MGRS, Geohash, GEOREF, Tilecode, Maidenhead, GARS').split(',')
    
    txt_en = 'Raster to DGGS'
    txt_vi = 'Raster to DGGS'
    figure = '../images/tutorial/vector2dggs.png'

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

    
    def outputName(self):
        return self.tr('Raster2DGGS')
    
    
    def initAlgorithm(self, config=None):   
        # Input raster layer
        self.addParameter(QgsProcessingParameterRasterLayer(self.INPUT, "Input raster"))


        self.addParameter(QgsProcessingParameterEnum(
            self.DGGS_TYPE,
            "DGGS Type",
            options=self.DGGS_TYPES,
            defaultValue=0
        ))

        self.addParameter(QgsProcessingParameterNumber(
            self.RESOLUTION,
            "Resolution",
            QgsProcessingParameterNumber.Integer,
            10,
            minValue=0,
            maxValue=40
        ))
        
        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT,
            self.tr('Raster2DGGS'),
            QgsProcessing.TypeVectorPolygon
    ))

    def checkParameterValues(self, parameters, context):
        """Dynamically update resolution limits before execution"""
        selected_index = self.parameterAsEnum(parameters, self.DGGS_TYPE, context)
        selected_dggs = self.DGGS_TYPES[selected_index]

        min_res, max_res, _ = self.DGGS_RESOLUTION[selected_dggs]
        res_value = self.parameterAsInt(parameters, self.RESOLUTION, context)

        if not (min_res <= res_value <= max_res):
            return (False, f"Resolution must be between {min_res} and {max_res} for {selected_dggs}.")

        if (selected_dggs == 'OLC'):
            if res_value not in (2,4,6,8,10,11,12,13,14,15):
                return (False, f"Resolution must be in [2,4,6,8,10,11,12,13,14,15] for {selected_dggs}.")
        elif (selected_dggs == 'GARS'):
            if res_value not in (30,15,5,1):
                return (False, f"Resolution must be in [30,15,5,1] minutes for {selected_dggs}.")
        
        return super().checkParameterValues(parameters, context)
    
    def get_nearest_h3_resolution(self,pixel_size):
        # H3 resolutions are discrete levels, so we need to pick the best one
        h3_resolutions = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]

        # Approximate mapping between pixel size and H3 resolution
        # (This is an example. You can adjust based on your use case.)
        if pixel_size < 100:
            return h3_resolutions[14]
        elif pixel_size < 500:
            return h3_resolutions[12]
        elif pixel_size < 1000:
            return h3_resolutions[10]
        elif pixel_size < 5000:
            return h3_resolutions[8]
        else:
            return h3_resolutions[6]

    def prepareAlgorithm(self, parameters, context, feedback):       
        self.resolution = self.parameterAsInt(parameters, self.RESOLUTION, context) 
        self.DGGS_TYPE_index = self.parameterAsEnum(parameters, self.DGGS_TYPE, context)
        raster_layer = self.parameterAsRasterLayer(parameters, self.INPUT, context)
        crs = raster_layer.crs()

        # Only accept geographic CRS (e.g., EPSG:4326)
        if not crs.isGeographic():
            feedback.reportError("Only rasters with geographic CRS (e.g., EPSG:4326) are supported.")
            return False
         # Get pixel size of raster layer (in map units)
        pixel_size_x = raster_layer.rasterUnitsPerPixelX()
        pixel_size_y = raster_layer.rasterUnitsPerPixelY()

        # Calculate the pixel size (we take the average of the X and Y directions)
        pixel_size = (pixel_size_x + pixel_size_y) / 2

        # Dynamically set the H3 resolution based on pixel size
        self.resolution = self.get_nearest_h3_resolution(pixel_size)
        feedback.pushInfo(f"Dynamic resolution set to {self.resolution} based on raster pixel size")

        self.DGGS_TYPE_functions = {
            'h3': raster2h3,
            # 's2': raster2s2,
            # 'rhealpix': raster2rhealpix,
            # 'qtm': raster2qtm,
            # 'olc': raster2olc,
            # 'geohash': raster2geohash, # Need to check polyline/ polygon2geohash
            # 'tilecode': raster2tilecode,
            # 'quadkey': raster2quadkey
        }
        # if platform.system() == 'Windows':
        #     self.DGGS_TYPE_functions['isea4t'] = raster2isea4t # Need to check polyline/ polygon2isea4t --> QGIS crashed
        #     self.DGGS_TYPE_functions['isea3h'] = raster2isea3h # Need to check polyline/ polygon2isea3h --> QGIS crashed

        return True


    def processAlgorithm(self, parameters, context, feedback):
        raster_layer = self.parameterAsRasterLayer(parameters, self.INPUT, context)
        self.dggs_type = self.DGGS_TYPES[self.DGGS_TYPE_index].lower()
        conversion_function = self.DGGS_TYPE_functions.get(self.dggs_type)

        if conversion_function is None:
            return {}

        feedback.pushInfo(f"Processing raster: {raster_layer.name()} at resolution: {self.resolution}")

        # conversion_function returns a memory layer (QgsVectorLayer)
        memory_layer = conversion_function(raster_layer, self.resolution)
        # memory_layer = conversion_function(raster_layer)

        if not isinstance(memory_layer, QgsVectorLayer) or not memory_layer.isValid():
            raise QgsProcessingException("Invalid output layer returned from conversion function.")

        # Create output sink with the same fields and CRS
        (sink, sink_id) = self.parameterAsSink(
            parameters,
            self.OUTPUT,
            context,
            memory_layer.fields(),
            memory_layer.wkbType(),
            memory_layer.crs()
        )

        # Copy features
        for feature in memory_layer.getFeatures():
            sink.addFeature(feature, QgsFeatureSink.FastInsert)

        return {self.OUTPUT: sink_id}