# -*- coding: utf-8 -*-
"""
expanddggs.py
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
import platform

from qgis.core import (
    QgsProcessing,
    QgsProcessingParameterVectorLayer,
    QgsProcessingParameterField,
    QgsProcessingParameterEnum,
    QgsProcessingParameterNumber,
    QgsProcessingFeatureBasedAlgorithm,
    QgsProcessingException,
    QgsWkbTypes,
    QgsApplication,
    QgsVectorLayer,
    QgsFeatureSink
)

from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtCore import QCoreApplication

from ...utils.imgs import Imgs
from ...utils.conversion.dggsexpand import * 

class DGGSExpand(QgsProcessingFeatureBasedAlgorithm):
    INPUT = 'INPUT'
    DGGS_FIELD = 'DGGS_FIELD'
    DGGS_TYPE = 'DGGS_TYPE'
    RESOLUTION = 'RESOLUTION'
    OUTPUT = 'OUTPUT'

    DGGS_TYPES = ['H3','S2', 'rHEALPix', 'ISEA4T', 'ISEA3H', 'QTM']
    

    LOC = QgsApplication.locale()[:2]

    def translate(self, string):
        return QCoreApplication.translate('Processing', string)

    def tr(self, *string):
        if self.LOC == 'vi':
            return string[1] if len(string) == 2 else self.translate(string[0])
        return self.translate(string[0])

    def name(self):
        return 'dggsexpand'

    def displayName(self):
        return self.tr('DGGS Expand', 'DGGS Expand')

    def group(self):
        return self.tr('Conversion', 'Conversion')

    def groupId(self):
        return 'conversion'

    def icon(self):
        return QIcon(os.path.join(os.path.dirname(os.path.dirname(__file__)), '../images/conversion/dggsexpand.png'))

    def tags(self):
        return self.tr('H3, DGGS, Hexagon, Spatial Grid').split(',')

    txt_en = 'DGGS Expand'
    txt_vi = 'DGGS Expand'
    figure = '../images/tutorial/dggsexpand.png'

    def shortHelpString(self):
        social_BW = Imgs().social_BW
        footer = f'''<div align="center">
                      <img src="{os.path.join(os.path.dirname(os.path.dirname(__file__)), self.figure)}">
                    </div>
                    <div align="right">
                      <p><b>{self.tr('Author: Thang Quach', 'Author: Thang Quach')}</b></p>
                      {social_BW}
                    </div>'''
        return self.tr(self.txt_en, self.txt_vi) + footer

    def inputLayerTypes(self):
        return [QgsProcessing.TypeVectorPolygon]

    def outputName(self):
        return self.tr('DGGS_expanded')

    def outputWkbType(self, input_wkb_type):
        return QgsWkbTypes.Polygon

    def supportInPlaceEdit(self, layer):
        return False

    def createInstance(self):
        return DGGSExpand()

    def initParameters(self, config=None):
        self.addParameter(QgsProcessingParameterVectorLayer(
            self.INPUT,
            self.tr('Input DGGS layer'),
            [QgsProcessing.TypeVectorPolygon]
        ))

        self.addParameter(QgsProcessingParameterEnum(
            self.DGGS_TYPE,
            "DGGS Type",
            options=self.DGGS_TYPES,
            defaultValue=0
        ))

        self.addParameter(
            QgsProcessingParameterField(
                self.DGGS_FIELD,
                "DGGS_ID field",
                parentLayerParameterName=self.INPUT,
                type=QgsProcessingParameterField.String
            )
        )
        
        self.addParameter(QgsProcessingParameterNumber(
            self.RESOLUTION,
            "Resolution",
            QgsProcessingParameterNumber.Integer,
            10,
            minValue=0,
            maxValue=40
        ))

    def prepareAlgorithm(self, parameters, context, feedback):
        selected_index = self.parameterAsEnum(parameters, self.DGGS_TYPE, context)
        self.resolution = self.parameterAsInt(parameters, self.RESOLUTION, context)
                      
        self.DGGS_TYPE_index = self.parameterAsEnum(parameters, self.DGGS_TYPE, context)
        self.dggs_type = self.DGGS_TYPES[self.DGGS_TYPE_index].lower()
        self.dggs_field = self.parameterAsString(parameters, self.DGGS_FIELD, context)

        self.DGGS_TYPE_functions = {
            'h3': h3expand,
            's2': s2expand,
            'rhealpix': rhealpixexpand,
            'isea4t': isea4texpand,
            'isea3h': isea3hexpand,
            'qtm': qtmexpand
        }

        return True

    def processAlgorithm(self, parameters, context, feedback):
        dggs_layer = self.parameterAsVectorLayer(parameters, self.INPUT, context)
        conversion_function = self.DGGS_TYPE_functions.get(self.dggs_type)

        if conversion_function is None:
            raise QgsProcessingException(f"No conversion function for DGGS type: {self.dggs_type}")

        feedback.pushInfo(f"Expanding {self.dggs_type.upper()} at resolution {self.resolution}")

        memory_layer = conversion_function(dggs_layer, self.resolution, self.dggs_field, feedback)

        if not isinstance(memory_layer, QgsVectorLayer) or not memory_layer.isValid():
            raise QgsProcessingException("Invalid output layer returned from conversion function.")

        (sink, sink_id) = self.parameterAsSink(
            parameters,
            self.OUTPUT,
            context,
            memory_layer.fields(),
            memory_layer.wkbType(),
            memory_layer.crs()
        )

        for feature in memory_layer.getFeatures():
            sink.addFeature(feature, QgsFeatureSink.FastInsert)

        return {self.OUTPUT: sink_id}
