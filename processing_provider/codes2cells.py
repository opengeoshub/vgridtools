# -*- coding: utf-8 -*-
"""
codes2cells.py
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
    QgsWkbTypes    
    )

from qgis.core import QgsApplication
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtCore import QCoreApplication,QVariant


from ..vgridlibrary.imgs import Imgs
from ..vgridlibrary.geocode.geocode2qgsfeature import *

class Codes2Cells(QgsProcessingFeatureBasedAlgorithm):
    """
    Algorithm to convert OLC/ OpenLocationCode/ Google Plus Code, MGRS, Geohash, GEOREF, S2, Vcode, Maidenhead, GARS to Gecode grid cells
    """
    INPUT = 'INPUT'
    CODE_FIELD = 'CODE_FIELD'
    GRID_TYPE = 'GRID_TYPE'
    GRID_OPTIONS = [
        'OLC', 'MGRS', 'Geohash', 'GEOREF', 'S2', 'Vcode', 'Maidenhead', 'GARS'
    ]
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
        return Codes2Cells()

    def name(self):
        return 'codes2cells'

    def icon(self):
        return QIcon(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'images/geocode_codes2cells.png'))
    
    def displayName(self):
        return self.tr('Codes to Cells', 'Codes to Cells')

    def group(self):
        return self.tr('Geocode', 'Geocode')

    def groupId(self):
        return 'geocode'

    def tags(self):
        return self.tr('OLC, OpenLocationCode, Google Plus Codes, MGRS, Geohash, GEOREF, S2, Vcode, Maidenhead, GARS').split(',')
    
    txt_en = 'Codes to Cells'
    txt_vi = 'Codes to Cells'
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

    def inputLayerTypes(self):
        return [QgsProcessing.TypeVectorPoint]

    def outputName(self):
        return self.tr('Output layer')
    
    def outputWkbType(self, input_wkb_type):
        return (QgsWkbTypes.Polygon)   
    
    def outputFields(self, input_fields):
        output_fields = QgsFields()
        output_fields.append(QgsField('code', QVariant.String))
        output_fields.append(QgsField('center_lat', QVariant.Double))
        output_fields.append(QgsField('center_lon', QVariant.Double))
        output_fields.append(QgsField('bbox_height', QVariant.String))
        output_fields.append(QgsField('bbox_width', QVariant.String))
        output_fields.append(QgsField('precision', QVariant.Int))

        return (output_fields)
        # return(input_fields)

    def supportInPlaceEdit(self, layer):
        return False

    def initParameters(self, config=None):   
        # Input point layer
        param = QgsProcessingParameterFeatureSource(
                self.INPUT,
                self.tr('Input point vector layer'),
                [QgsProcessing.TypeVectorPoint])
        self.addParameter(param)

        # Code field
        param = QgsProcessingParameterField(
            self.CODE_FIELD,  
            self.tr('Code field') ,
            type=QgsProcessingParameterField.String,
            parentLayerParameterName=self.INPUT
        )
        self.addParameter(param)

        # Grid Type
        param = QgsProcessingParameterEnum(
            self.GRID_TYPE,
            self.tr('Grid type'),
            options=self.GRID_OPTIONS,
            defaultValue=0  # Default to the first option (OLC)
        )
        self.addParameter(param)


    def prepareAlgorithm(self, parameters, context, feedback):
        source = self.parameterAsSource(parameters, self.INPUT, context)
        self.total_features = source.featureCount()
        self.num_bad = 0
        
        self.code_field = self.parameterAsString(parameters, self.CODE_FIELD, context)
        self.grid_type_index = self.parameterAsEnum(parameters, self.GRID_TYPE, context)
        self.grid_type_functions = {
            'olc': olc2qgsfeature,
            'mgrs': mgrs2qgsfeature,
            'geohash': geohash2qgsfeature,
            'georef': georef2qgsfeature,
            's2': s22qgsfeature,
            'vcode': vcode2qgsfeature,
            'maidenhead': maidenhead2qgsfeature,
            'gars': gars2qgsfeature
        }
        return True
    
    def processFeature(self, feature, context, feedback):
        try:
            code = feature[self.code_field]

            grid_type_key = self.GRID_OPTIONS[self.grid_type_index].lower()
            conversion_function = self.grid_type_functions.get(grid_type_key)
            # feedback.pushInfo(f"{grid_type_key}")
            if grid_type_key == 'mgrs':
                point = feature.geometry().asPoint()  # Returns a QgsPointXY object
                x, y = point.x(), point.y()  # Get the x and y coordinates
                
                # Call the mgrs2qgsfeature function with the coordinates
                cell_feature = mgrs2qgsfeature(code, y, x)  # Use y, x for lat, lon
                if cell_feature:
                    return [cell_feature]

            elif conversion_function:
                # Call the conversion function
                cell_feature = conversion_function(code)
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