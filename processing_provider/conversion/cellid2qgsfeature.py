# -*- coding: utf-8 -*-
"""
Code2Cell.py
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
    QgsProcessing,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterField,
    QgsProcessingFeatureBasedAlgorithm,
    QgsProcessingParameterEnum,
    QgsWkbTypes ,
    QgsCoordinateReferenceSystem
    )

from qgis.core import QgsApplication
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtCore import QCoreApplication,QVariant

import platform 

from ...utils.imgs import Imgs
from ...utils.conversion.cellid2qgsfeature import *

class CellID2DGGS(QgsProcessingFeatureBasedAlgorithm):
    """
    Algorithm to convert H3, S2, Rhealpix,EASE, QTM, OLC/ OpenLocationCode/ Google Plus Code, Geohash, 
        GEOREF, MGRS, Tilecode, Quadkey, Maidenhead, GARS grid cells
    """
    INPUT = 'INPUT'
    CELL_ID = 'CELL_ID'
    DGGS_TYPE = 'DGGS_TYPE'
    DGGS_TYPES = ['H3', 'S2','Rhealpix','EASE', 'QTM', 'OLC', 'Geohash', 
                  'GEOREF','MGRS', 'Tilecode','Quadkey', 'Maidenhead', 'GARS']
    
    if platform.system() == 'Windows':
        index = DGGS_TYPES.index('Rhealpix') + 1
        DGGS_TYPES[index:index] = ['ISEA4T', 'ISEA3H']
        
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
        return CellID2DGGS()

    def name(self):
        return 'cellid2dggs'

    def icon(self):
        return QIcon(os.path.join(os.path.dirname(os.path.dirname(__file__)), '../images/conversion/cellid2dggs.png'))
    
    
    def displayName(self):
        return self.tr('Cell ID to DGGS', 'Cell ID to DGGS')

    def group(self):
        return self.tr('Conversion', 'Conversion')

    def groupId(self):
        return 'conversion'

    def tags(self):
        return self.tr('H3,S2,Rhealpix,ISEA4T, ISEA3H, EASE,QTM,OLC,OpenLocationCode,Google Plus Code,Geohash,\
                        GEOREF,MGRS,Tilecode,Quadkey,Maidenhead,GARS').split(',')
    
    txt_en = 'Cell ID to DGGS'
    txt_vi = 'Cell ID to DGGS'
    figure = '../images/tutorial/cellid2dggs.png'

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

    def inputLayerTypes(self):
        return [QgsProcessing.TypeVector]

    def outputName(self):
        return self.tr('CellID2DGGS')
    
    def outputCrs(self, input_crs):
        return QgsCoordinateReferenceSystem("EPSG:4326")

    def outputWkbType(self, input_wkb_type):
        return (QgsWkbTypes.Polygon)   
    
    def outputFields(self, input_fields):
        output_fields = QgsFields()

        # Preserve all original input fields
        for field in input_fields:
            output_fields.append(field)

        # Append H3-related fields
        output_fields.append(QgsField('cell_id', QVariant.String))
        output_fields.append(QgsField('resolution', QVariant.Int))
        output_fields.append(QgsField('center_lat', QVariant.Double))
        output_fields.append(QgsField('center_lon', QVariant.Double))
        output_fields.append(QgsField('avg_edge_len', QVariant.Double))
        output_fields.append(QgsField('cell_area', QVariant.Double))

        return output_fields

    def supportInPlaceEdit(self, layer):
        return False

    def initParameters(self, config=None):   
        # Input layer
        param = QgsProcessingParameterFeatureSource(
                self.INPUT,
                self.tr('Input layer'),
                [QgsProcessing.TypeVector])
        self.addParameter(param)

        # Cell ID
        param = QgsProcessingParameterField(
            self.CELL_ID,  
            self.tr('Cell ID field') ,
            type=QgsProcessingParameterField.String,
            parentLayerParameterName=self.INPUT
        )
        self.addParameter(param)

        # DGGS Type
        param = QgsProcessingParameterEnum(
            self.DGGS_TYPE,
            self.tr('DGGS type'),
            options=self.DGGS_TYPES,
            defaultValue=0  # Default to the first option (H3)
        )
        self.addParameter(param)


    def prepareAlgorithm(self, parameters, context, feedback):
        source = self.parameterAsSource(parameters, self.INPUT, context)
        self.total_features = source.featureCount()
        self.num_bad = 0
        
        self.CELL_ID = self.parameterAsString(parameters, self.CELL_ID, context)
        self.DGGS_TYPE_index = self.parameterAsEnum(parameters, self.DGGS_TYPE, context)
        self.DGGS_TYPE_functions = {
            'h3': h32qgsfeature,
            's2': s22qgsfeature,
            'rhealpix': rhealpix2qgsfeature,
            # 'ease': ease2qgsfeature,
            'qtm': qtm2qgsfeature,
            'olc': olc2qgsfeature,
            'geohash': geohash2qgsfeature,
            'georef': georef2qgsfeature,
            'mgrs': mgrs2qgsfeature,
            'tilecode': tilecode2qgsfeature,
            'maidenhead': maidenhead2qgsfeature,
            'gars': gars2qgsfeature
        }
        
        if platform.system() == 'Windows':
            self.DGGS_TYPE_functions['isea4t'] = isea4t2qgsfeature
            self.DGGS_TYPE_functions['isea3h'] = isea3h2qgsfeature

        return True
    
    def processFeature(self, feature, context, feedback):
        try:
            cell_id = feature[self.CELL_ID]

            DGGS_TYPE_key = self.DGGS_TYPES[self.DGGS_TYPE_index].lower()
            conversion_function = self.DGGS_TYPE_functions.get(DGGS_TYPE_key)
            # feedback.pushInfo(f"{DGGS_TYPE_key}")
            if DGGS_TYPE_key == 'mgrs':
                point = feature.geometry().asPoint()  # Returns a QgsPointXY object
                x, y = point.x(), point.y()  # Get the x and y coordinates
                
                # Call the mgrs2qgsfeature function with the coordinates
                cell_feature = mgrs2qgsfeature(cell_id, y, x)  # Use y, x for lat, lon
                if cell_feature:
                    return [cell_feature]

            elif conversion_function:
                # Call the conversion function
                cell_feature = conversion_function(feature,cell_id)
                if cell_feature:
                    return [cell_feature]
            
        except Exception as e:
            self.num_bad += 1
            feedback.reportError(f"Error processing feature {feature.id()}: {str(e)}")        
        
        return []

    def postProcessAlgorithm(self, context, feedback):
        if self.num_bad:
            feedback.pushInfo(self.tr("{} out of {} features had invalid parameters and were ignored.".format(self.num_bad, self.total_features)))
        return {}