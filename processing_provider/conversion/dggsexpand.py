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
    DGGS_TYPE = 'DGGS_TYPE'
    RESOLUTION = 'RESOLUTION'
    OUTPUT = 'OUTPUT'

    DGGS_TYPES = ['H3']
    DGGS_RESOLUTION = {
        'H3': (0, 15, 10),
    }

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

        self.addParameter(QgsProcessingParameterNumber(
            self.RESOLUTION,
            "Resolution",
            QgsProcessingParameterNumber.Integer,
            10,
            minValue=0,
            maxValue=15
        ))

    def checkParameterValues(self, parameters, context):
        selected_index = self.parameterAsEnum(parameters, self.DGGS_TYPE, context)
        selected_dggs = self.DGGS_TYPES[selected_index]
        min_res, max_res, _ = self.DGGS_RESOLUTION[selected_dggs]
        res_value = self.parameterAsInt(parameters, self.RESOLUTION, context)

        if not (min_res <= res_value <= max_res):
            return (False, f"Resolution must be between {min_res} and {max_res} for {selected_dggs}.")
        return super().checkParameterValues(parameters, context)

    def prepareAlgorithm(self, parameters, context, feedback):
        self.resolution = self.parameterAsInt(parameters, self.RESOLUTION, context)
        self.DGGS_TYPE_index = self.parameterAsEnum(parameters, self.DGGS_TYPE, context)
        self.dggs_type = self.DGGS_TYPES[self.DGGS_TYPE_index].lower()

        self.DGGS_TYPE_functions = {
            'h3': h3expand 
        }

        return True

    def processAlgorithm(self, parameters, context, feedback):
        dggs_layer = self.parameterAsVectorLayer(parameters, self.INPUT, context)
        conversion_function = self.DGGS_TYPE_functions.get(self.dggs_type)

        if conversion_function is None:
            raise QgsProcessingException(f"No conversion function for DGGS type: {self.dggs_type}")

        feedback.pushInfo(f"Expanding {self.dggs_type.upper()} at resolution {self.resolution}")

        memory_layer = conversion_function(dggs_layer, self.resolution, feedback)

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
