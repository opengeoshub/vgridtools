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
    QgsFeature,  QgsWkbTypes, QgsPropertyDefinition)

from qgis.core import (
    QgsProcessing,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterField,
    QgsProcessingParameters,
    QgsProcessingFeatureBasedAlgorithm,
    QgsProcessingParameterNumber
    )

from qgis.core import QgsApplication
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtCore import QCoreApplication

from ..vgridlibrary.imgs import Imgs
from ..vgridlibrary.geocode.geocode2qgsfeature import olc2qgsfeature

class Codes2Cells(QgsProcessingFeatureBasedAlgorithm):
    """
    Algorithm to covert OLC/ OpenLocationCode/ Google Plus Code, MGRS, Geohash, GEOREF, S2, Vcode, Maidenhead, GARS to Gecode grid cells
    """
    INPUT = 'INPUT'
    CODEFIELD = 'CODEFIELD'

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
    figure = 'images/tutorial/geocode_codes2cells.png'

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
        # return (QgsWkbTypes.Point)   
    
    def outputFields(self, input_fields):
        return(input_fields)

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
            self.CODEFIELD,  
            self.tr('Code field') ,
            parentLayerParameterName=self.INPUT
        )
        self.addParameter(param)


    def prepareAlgorithm(self, parameters, context, feedback):
        source = self.parameterAsSource(parameters, self.INPUT, context)
        self.total_features = source.featureCount()
        self.num_bad = 0

        self.code_field = self.parameterAsString(parameters, self.CODEFIELD, context)
        return True
    
    def processFeature(self, feature, context, feedback):         
        try:
            # Retrieve the OLC code from the feature's attribute
            # olc_code = '7P28QMFQ+R26'

            olc_code = feature[self.code_field]
            # Generate a new feature using the OLC code
            cell_feature = olc2qgsfeature(olc_code)
            
            if cell_feature:
                # Optionally, copy over attributes from the original feature
                cell_feature.setAttributes(feature.attributes())
                # Return the feature in a list
                return [cell_feature]
            
        except Exception as e:
            # Increment the error count and log the error
            self.num_bad += 1
            feedback.reportError(f"Error processing feature {feature.id()}: {str(e)}")
        
        # Return an empty list if no feature was created or an error occurred
        return []


    def postProcessAlgorithm(self, context, feedback):
        if self.num_bad:
            feedback.pushInfo(self.tr("{} out of {} features had invalid parameters and were ignored.".format(self.num_bad, self.total_features)))
        return {}