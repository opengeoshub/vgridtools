# -*- coding: utf-8 -*-
"""
latlong2codes.py
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

from becagis.becagislibrary.imgs import Imgs


class latlong2codes(QgsProcessingFeatureBasedAlgorithm):
    """
    Algorithm to covert OLC/ OpenLocationCode/ Google Plus Code, MGRS, Geohash, GEOREF, S2, Vcode, Maidenhead, GARS to Gecode grid cells
    """
    INPUT = 'INPUT'
    PRECISION = 'PRECISION'
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
        return latlong2codes()

    def name(self):
        return 'latlong2codes'

    def icon(self):
        return QIcon(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'images/geocode_latlong2codes.png'))
    
    def displayName(self):
        return self.tr('Codes to Cells', 'Codes to Cells')

    def group(self):
        return self.tr('Geocode', 'Geocode')

    def groupId(self):
        return 'geocode'

    def tags(self):
        return self.tr('OLC, OpenLocationCode, Google Plus Codes, MGRS, Geohash, GEOREF, S2, Vcode, Maidenhead, GARS').split(',')
    
    txt_en = 'latlong2codes'
    txt_vi = 'latlong2codes'
    figure = 'images/tutorial/geocode_latlong2codes.png'

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
            # parentLayerParameterName: self.INPUT,
            self.tr('Code field') ,
            parentLayerParameterName=self.INPUT
        )
        self.addParameter(param)

        # Precision
        param = QgsProcessingParameterNumber(
            self.PRECISION,
            self.tr('Precision'),
            QgsProcessingParameterNumber.Integer,
            defaultValue=1,
            minValue= 0,
            optional=False)
        param.setIsDynamic(True)
        param.setDynamicPropertyDefinition(QgsPropertyDefinition(
            self.PRECISION,
            self.tr('Precision'),
            QgsPropertyDefinition.Integer))
        param.setDynamicLayerParameterName(self.INPUT)
        self.addParameter(param)

    def prepareAlgorithm(self, parameters, context, feedback):
        self.precision = self.parameterAsDouble(parameters, self.PRECISION, context)  
        if self.precision < 0:
            feedback.reportError('Precision must be at least 0')
            return False
        self.precision_dyn = QgsProcessingParameters.isDynamic(parameters, self.PRECISION)
        if self.precision_dyn:
            self.precision_dyn_property = parameters[self.PRECISION]
     
        source = self.parameterAsSource(parameters, self.INPUT, context)
        
        self.total_features = source.featureCount()
        self.num_bad = 0
        return True
    
    def processFeature(self, feature, context, feedback):         
        # return [feature]
        try:
            # Generate skeleton
            geom = feature.geometry()           
            attrs = feature.attributes()
            cell_geoms = geom
            # feedback.pushInfo(cell_geoms.geometry().asWkt())
            cell_features = []
            for cell in cell_geoms:
                cell_geom = cell.geometry()
                # feedback.pushInfo(ske.geometry().asWkt())
                cell_feature = QgsFeature()                
                cell_feature.setAttributes(attrs)         
                cell_feature.setGeometry(cell_geom) 
                cell_features.append(cell_feature)
                
            return cell_features        
        
        except Exception as e:
            self.num_bad += 1
            feedback.reportError(f"Error processing feature {feature.id()}: {str(e)}")
            return []


    def postProcessAlgorithm(self, context, feedback):
        if self.num_bad:
            feedback.pushInfo(self.tr("{} out of {} features had invalid parameters and were ignored.".format(self.num_bad, self.total_features)))
        return {}