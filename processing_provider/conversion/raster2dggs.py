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
from vgrid.stats.s2stats import s2_metrics
from vgrid.stats.rhealpixstats import rhealpix_metrics
from vgrid.stats.isea4tstats import isea4t_metrics

from vgrid.stats.qtmstats import qtm_metrics
from vgrid.stats.olcstats import olc_metrics
from vgrid.stats.geohashstats import geohash_metrics
from vgrid.stats.tilecodestats import tilecode_metrics
from vgrid.stats.quadkeystats import quadkey_metrics


class Raster2DGGS(QgsProcessingAlgorithm):
    """
    convert Raster Layer to H3, S2, rHEALPix, ISEA4T, QTM, OLC, Geohash, Tilecode
    """
    INPUT = 'INPUT'
    DGGS_TYPE = 'DGGS_TYPE'
    RESOLUTION = 'RESOLUTION'
    OUTPUT = 'OUTPUT'
    
    DGGS_TYPES = [
        'H3', 'S2','rHEALPix','QTM', 'OLC', 'Geohash', 
        'Tilecode','Quadkey']
    DGGS_RESOLUTION = {
        'H3': (-1, 15, 10),
        'S2': (-1, 30, 16),
        'rHEALPix': (-1, 15,11),      
        'QTM':(-1,24,12),
        'OLC': (-1, 13, 10),
        'Geohash': (-1, 10, 9),
        'Tilecode': (-1, 26, 15),
        'Quadkey': (-1, 26, 15)        
    }
    if platform.system() == 'Windows':
        index = DGGS_TYPES.index('rHEALPix') + 1
        DGGS_TYPES[index:index] = ['ISEA4T']

        DGGS_RESOLUTION.update({
            'ISEA4T': (0, 23, 18)
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
        return self.tr('raster, S2, H3, rHEALPix, ISEA4T, EASE, OLC, OpenLocationCode, Google Plus Codes, MGRS, Geohash, GEOREF, Tilecode, Maidenhead, GARS').split(',')
    
    txt_en = 'Raster to DGGS'
    txt_vi = 'Raster to DGGS'
    figure = '../images/tutorial/raster2dggs.png'

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
            "Resolution (leave -1 for automatic)",
            QgsProcessingParameterNumber.Integer,
            -1,
            minValue=-1,
            maxValue=40
        ))

        
        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT,
            self.tr('Raster2DGGS'),
            QgsProcessing.TypeVectorPolygon
    ))

    def get_nearest_resolution(self, dggs_type, pixel_size):        
        if dggs_type == 'h3':
            resolutions = range(16)
            get_area = lambda res: h3.average_hexagon_area(res, unit='m^2')
        elif dggs_type == 's2':
            resolutions = range(25)
            get_area = lambda res: s2_metrics(res)[2]  # avg_area
        elif dggs_type == 'rhealpix':
            resolutions = range(16)
            get_area = lambda res: rhealpix_metrics(res)[2]  # avg_area
        elif dggs_type == 'isea4t':
            isea4t_dggs = Eaggr(Model.ISEA4T) 
            resolutions = range(24)
            get_area = lambda res: isea4t_metrics(isea4t_dggs, res)[2]  # avg_area
        elif dggs_type == 'qtm':
            resolutions = range(2,25)
            get_area = lambda res: qtm_metrics(res)[2]  # avg_area
        elif dggs_type == 'olc':
            resolutions = [2, 4, 6, 8, 10, 11, 12]
            get_area = lambda res: olc_metrics(res)[2]  # avg_area
        elif dggs_type == 'geohash':
            resolutions = range(1,11)
            get_area = lambda res: geohash_metrics(res)[2]  # avg_area
        elif dggs_type == 'tilecode':
            resolutions = range(27)
            get_area = lambda res: tilecode_metrics(res)[2]  # avg_area
        elif dggs_type == 'quadkey':
            resolutions = range(27)
            get_area = lambda res: quadkey_metrics(res)[2]  # avg_area
            
        else:
            raise ValueError(f"Unsupported DGGS type: {dggs_type}")

        nearest_res = None
        min_diff = float('inf')
        for res in resolutions:
            area = get_area(res)
            diff = abs(area - pixel_size)
            if diff < min_diff:
                min_diff = diff
                nearest_res = res

        return nearest_res


    def prepareAlgorithm(self, parameters, context, feedback):       
        self.resolution = self.parameterAsInt(parameters, self.RESOLUTION, context) 
        self.DGGS_TYPE_index = self.parameterAsEnum(parameters, self.DGGS_TYPE, context)
        self.dggs_type = self.DGGS_TYPES[self.DGGS_TYPE_index].lower()

        raster_layer = self.parameterAsRasterLayer(parameters, self.INPUT, context)
        crs = raster_layer.crs()

        # Only accept geographic CRS (e.g., EPSG:4326)
        if not crs.isGeographic():
            feedback.reportError("Only rasters with geographic CRS (e.g., EPSG:4326) are supported.")
            return False
        
        # Get pixel size of raster layer (in map units)
        pixel_size_x = raster_layer.rasterUnitsPerPixelX()
        pixel_size_y = raster_layer.rasterUnitsPerPixelY()
        pixel_size = abs(pixel_size_x * pixel_size_y)
        feedback.pushInfo(f"pixel_size: {pixel_size}")

        user_res = self.parameterAsInt(parameters, self.RESOLUTION, context)
        if user_res >= 0:
            self.resolution = user_res
        else:
            self.resolution = self.get_nearest_resolution(self.dggs_type, pixel_size)
            feedback.pushInfo(f"Automatic resolution set to {self.resolution} based on raster pixel size")
        
        if self.dggs_type == 'qtm' and self.resolution in (0,1):
            feedback.pushInfo("Resolution <=1 is not supported for QTM. Automatically changed to resolution 2.")
            self.resolution = 2

        if self.dggs_type == 'olc' and self.resolution not in [-1, 2, 4, 6, 8, 10, 11, 12]:
            feedback.reportError("Invalid Resolution (OLC code length). It must be in [2, 4, 6, 8, 10, 11, 12].")
            return False

        if self.dggs_type == 'geohash' and self.resolution == 0:
            feedback.pushInfo("Resolution 0 is not supported for Geohash. Automatically changed to resolution 1.")
            self.resolution = 1
            
        self.DGGS_TYPE_functions = {
            'h3': raster2h3,
            's2': raster2s2,
            'rhealpix': raster2rhealpix,            
            'qtm': raster2qtm,
            'olc': raster2olc,
            'geohash': raster2geohash, 
            'tilecode': raster2tilecode,
            'quadkey': raster2quadkey
        }
        if platform.system() == 'Windows':
            self.DGGS_TYPE_functions['isea4t'] = raster2isea4t 
        return True


    def processAlgorithm(self, parameters, context, feedback):
        raster_layer = self.parameterAsRasterLayer(parameters, self.INPUT, context)
        self.dggs_type = self.DGGS_TYPES[self.DGGS_TYPE_index].lower()
        conversion_function = self.DGGS_TYPE_functions.get(self.dggs_type)

        if conversion_function is None:
            return {}

        feedback.pushInfo(f"Processing raster: {raster_layer.name()} at resolution: {self.resolution}")

        # conversion_function returns a memory layer (QgsVectorLayer)
        memory_layer = conversion_function(raster_layer, self.resolution,feedback)
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