# -*- coding: utf-8 -*-
"""
dggsresample.py
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
from ...utils.resampling.dggsresample import * 

class DGGSResample(QgsProcessingFeatureBasedAlgorithm):
    INPUT = 'INPUT'
    DGGS_FIELD = 'DGGS_FIELD'
    RESAMPLE_FIELD = 'RESAMPLE_FIELD'
    DGGSTYPE_FROM = 'DGGSTYPE_FROM'
    DGGSTYPE_TO = 'DGGSTYPE_TO'
    RESOLUTION = 'RESOLUTION'
    OUTPUT = 'OUTPUT'

    DGGS_TYPES = ['H3','S2', 'A5', 'rHEALPix','QTM',
                  'OLC','Geohash','Tilecode','Quadkey']
    
    if platform.system() == 'Windows':
        index = DGGS_TYPES.index('rHEALPix') + 1
        DGGS_TYPES[index:index] = ['ISEA4T']

    LOC = QgsApplication.locale()[:2]

    def translate(self, string):
        return QCoreApplication.translate('Processing', string)

    def tr(self, *string):
        if self.LOC == 'vi':
            return string[1] if len(string) == 2 else self.translate(string[0])
        return self.translate(string[0])

    def name(self):
        return 'dggsresample'

    def displayName(self):
        return self.tr('DGGS Resample', 'DGGS Resample')

    def group(self):
        return self.tr('Resampling', 'Resampling')

    def groupId(self):
        return 'resampling'

    def icon(self):
        return QIcon(os.path.join(os.path.dirname(os.path.dirname(__file__)), '../images/resampling/dggsresample.svg'))

    def tags(self):
        return self.tr('DGGS, resample, H3,S2, A5, rHEALPix, ISEA4T, QTM,OLC,Geohash,Tilecode,Quadkey').split(',')

    txt_en = 'DGGS Resample'
    txt_vi = 'DGGS Resample'
    figure = '../images/tutorial/dggsresample.png'

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
        return self.tr('DGGS_resampled')

    def outputWkbType(self, input_wkb_type):
        return QgsWkbTypes.Polygon

    def supportInPlaceEdit(self, layer):
        return False

    def createInstance(self):
        return DGGSResample()

    def initParameters(self, config=None):
        self.addParameter(QgsProcessingParameterVectorLayer(
            self.INPUT,
            self.tr('Input DGGS'),
            [QgsProcessing.TypeVectorPolygon]
        ))

        self.addParameter(QgsProcessingParameterEnum(
            self.DGGSTYPE_FROM,
            self.tr("Input DGGS type"),
            options=self.DGGS_TYPES,
            defaultValue=0
        ))
        
        self.addParameter(
            QgsProcessingParameterField(
                self.DGGS_FIELD,
                self.tr("Input DGGS ID field"),
                parentLayerParameterName=self.INPUT,
                type=QgsProcessingParameterField.String
            )
        )
        
        self.addParameter(
            QgsProcessingParameterField(
                self.RESAMPLE_FIELD,
                self.tr("Input resample field"),
                parentLayerParameterName=self.INPUT,
                type=QgsProcessingParameterField.Numeric,
                optional=True,
                defaultValue=None
            )
        )
        
        self.addParameter(QgsProcessingParameterEnum(
            self.DGGSTYPE_TO,
            self.tr("Output DGGS type"),
            options=self.DGGS_TYPES,
            defaultValue=1
        ))

        self.addParameter(QgsProcessingParameterNumber(
            self.RESOLUTION,
            self.tr("Output resolution (leave -1 for automatic)"),
            QgsProcessingParameterNumber.Integer,
            -1,
            minValue=-1,
            maxValue=40
        ))


    def prepareAlgorithm(self, parameters, context, feedback):
        self.DGGSTYPE_FROM_index = self.parameterAsEnum(parameters, self.DGGSTYPE_FROM, context)
        self.DGGSTYPE_TO_index = self.parameterAsEnum(parameters, self.DGGSTYPE_TO, context)
        self.dggstype_from = self.DGGS_TYPES[self.DGGSTYPE_FROM_index].lower()
        self.dggstype_to = self.DGGS_TYPES[self.DGGSTYPE_TO_index].lower()
        
        if (self.dggstype_from == self.dggstype_to):
            feedback.reportError("Input DGGS Type must be different with Output DGGS Type.")
            return False

        self.dggs_field = self.parameterAsString(parameters, self.DGGS_FIELD, context)
        self.resample_field = self.parameterAsString(parameters, self.RESAMPLE_FIELD, context)
        self.resolution = self.parameterAsInt(parameters, self.RESOLUTION, context)                
        return True

    def processAlgorithm(self, parameters, context, feedback):
        dggs_layer = self.parameterAsVectorLayer(parameters, self.INPUT, context)
        feedback.pushInfo(f"Resampling from {self.dggstype_from.title()} to {self.dggstype_to.title()}")
        memory_layer = resample(dggs_layer, self.dggstype_from, self.dggstype_to, self.resolution, self.dggs_field, self.resample_field, feedback)

        if not isinstance(memory_layer, QgsVectorLayer) or not memory_layer.isValid():
            raise QgsProcessingException("Invalid output layer returned from resampling function.")

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