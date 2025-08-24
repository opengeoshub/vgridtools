# -*- coding: utf-8 -*-
"""
dggs2qgsfeaure.py
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
from ...utils.conversion.dggs2qgsfeature import *

class CellID2DGGS(QgsProcessingFeatureBasedAlgorithm):
    """
    Algorithm to convert H3, S2, A5, rHEALPix,QTM, OLC/ OpenLocationCode/ Google Plus Code, Geohash, 
        GEOREF, MGRS, Tilecode, Quadkey, Maidenhead, GARS grid cells
    """
    INPUT = 'INPUT'
    CELL_ID = 'CELL_ID'
    DGGS_TYPE = 'DGGS_TYPE'
    DGGS_TYPES = ['H3', 'S2','A5','rHEALPix',
                  'DGGAL_GNOSIS', 'DGGAL_ISEA3H', 'DGGAL_ISEA9R', 'DGGAL_IVEA3H', 'DGGAL_IVEA9R', 'DGGAL_RTEA3H', 'DGGAL_RTEA9R',
                  'QTM', 'OLC', 'Geohash','GEOREF','MGRS', 'Tilecode','Quadkey', 'Maidenhead', 'GARS']
    
    if platform.system() == 'Windows':
        index = DGGS_TYPES.index('rHEALPix') + 1
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
        return QIcon(os.path.join(os.path.dirname(os.path.dirname(__file__)), '../images/generator/grid_hex.svg'))
    
    
    def displayName(self):
        return self.tr('Cell ID to DGGS', 'Cell ID to DGGS')

    def group(self):
        return self.tr('Conversion', 'Conversion')

    def groupId(self):
        return 'conversion'

    def tags(self):
        return self.tr('H3,S2,A5,rHEALPix,ISEA4T, ISEA3H, QTM,OLC,OpenLocationCode,Google Plus Code,Geohash,\
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
            defaultValue=0  
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
            'a5': a52qgsfeature,
            'rhealpix': rhealpix2qgsfeature,
            # 'ease': ease2qgsfeature, # prone to unexpected errors
            'dggal_gnosis': dggal_gnosis2qgsfeature,
            'dggal_isea3h': dggal_isea3h2qgsfeature,
            'dggal_isea9r': dggal_isea9r2qgsfeature,
            'dggal_ivea3h': dggal_ivea3h2qgsfeature,
            'dggal_ivea9r': dggal_ivea9r2qgsfeature,
            'dggal_rtea3h': dggal_rtea3h2qgsfeature,
            'dggal_rtea9r': dggal_rtea9r2qgsfeature,
            'qtm': qtm2qgsfeature,
            'olc': olc2qgsfeature,
            'geohash': geohash2qgsfeature,
            'georef': georef2qgsfeature,
            'mgrs': mgrs2qgsfeature,
            'tilecode': tilecode2qgsfeature,
            'quadkey': quadkey2qgsfeature,
            'maidenhead': maidenhead2qgsfeature,
            'gars': gars2qgsfeature
        }
        
        if platform.system() == 'Windows':
            self.DGGS_TYPE_functions['isea4t'] = isea4t2qgsfeature
            self.DGGS_TYPE_functions['isea3h'] = isea3h2qgsfeature

        return True
    

    def outputFields(self, input_fields): 
        output_fields = QgsFields()

        # Preserve all original input fields
        for field in input_fields:
            output_fields.append(field)

        # Function to generate a unique field name by adding a suffix if necessary
        def get_unique_name(base_name):
            existing_names = {field.name() for field in output_fields}
            if base_name not in existing_names:
                return base_name
            i = 1
            while f"{base_name}_{i}" in existing_names:
                i += 1
            return f"{base_name}_{i}"

        dggs_type = self.DGGS_TYPES[self.DGGS_TYPE_index].lower()

        # Fields to be added
        new_fields = [
            QgsField(get_unique_name(dggs_type), QVariant.String),
            QgsField(get_unique_name("resolution"), QVariant.Int),
            QgsField(get_unique_name("center_lat"), QVariant.Double),
            QgsField(get_unique_name("center_lon"), QVariant.Double),
            QgsField(get_unique_name("avg_edge_len" if dggs_type in ('h3', 's2', 'a5', 'rhealpix', 'isea4t', 'isea3h', 'dggal_gnosis', 
            'dggal_isea3h', 'dggal_isea9r', 'dggal_ivea3h', 'dggal_ivea9r', 'dggal_rtea3h', 'dggal_rtea9r','qtm') else "cell_width"), QVariant.Double),
            
            QgsField(get_unique_name("cell_height"), QVariant.Double) if dggs_type not in ('h3', 's2', 'a5', 'rhealpix', 'isea4t', 'isea3h', 
            'dggal_gnosis', 'dggal_isea3h', 'dggal_isea9r', 'dggal_ivea3h', 'dggal_ivea9r', 'dggal_rtea3h', 'dggal_rtea9r','qtm') else None,
            
            QgsField(get_unique_name("cell_area"), QVariant.Double),
            QgsField(get_unique_name("cell_perimeter"), QVariant.Double)
        ]

        # Append the fields to output_fields
        for field in new_fields:
            if field:
                output_fields.append(field)

        return output_fields

    
    def processFeature(self, feature, context, feedback):
        try:
            cell_id = feature[self.CELL_ID]
            DGGS_TYPE_key = self.DGGS_TYPES[self.DGGS_TYPE_index].lower()
            conversion_function = self.DGGS_TYPE_functions.get(DGGS_TYPE_key)
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