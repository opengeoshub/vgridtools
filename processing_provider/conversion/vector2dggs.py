# -*- coding: utf-8 -*-
"""
vector2dggs.py
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
    QgsProcessingFeatureBasedAlgorithm,
    QgsProcessingParameterEnum,
    QgsProcessingParameterNumber,
    QgsWkbTypes    
    )

from qgis.core import QgsApplication
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtCore import QCoreApplication,QVariant


from ...vgridlibrary.imgs import Imgs
from ...vgridlibrary.conversion.qgsfeature2dggs import *

class Vector2DGGS(QgsProcessingFeatureBasedAlgorithm):
    """
    convert Vector Layer to H3, S2, OLC, Geohash, GEOREF, MGRS, Tilecode, Maidenhead, GARS
    """
    INPUT = 'INPUT'
    DGGS_TYPE = 'DGGS_TYPE'
    RESOLUTION = 'RESOLUTION'
    DGGS_OPTIONS = [
        'H3', 'S2', 'OLC', 'Geohash', 'GEOREF','MGRS',  'Tilecode', 'Maidenhead', 'GARS'
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
        return Vector2DGGS()

    def name(self):
        return 'vector2dggs'

    def icon(self):
        return QIcon(os.path.join(os.path.dirname(os.path.dirname(__file__)), '../images/conversion_cellid2dggs.png'))
    
    def displayName(self):
        return self.tr('Vector to DGGS', 'Vector to DGGS')

    def group(self):
        return self.tr('Conversion', 'Conversion')

    def groupId(self):
        return 'conversion'

    def tags(self):
        return self.tr('S2, H3, OLC, OpenLocationCode, Google Plus Codes, MGRS, Geohash, GEOREF, Tilecode, Maidenhead, GARS').split(',')
    
    txt_en = 'Vector to DGGS'
    txt_vi = 'Vector to DGGS'
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
        return self.tr('Output DGGS')
    
    def outputWkbType(self, input_wkb_type):
        return (QgsWkbTypes.Polygon)   
    
    def outputFields(self, input_fields):
        output_fields = QgsFields()
        output_fields.append(QgsField('cell_id', QVariant.String))
        output_fields.append(QgsField('center_lat', QVariant.Double))
        output_fields.append(QgsField('center_lon', QVariant.Double))
        output_fields.append(QgsField('avg_edge_len', QVariant.Double))
        output_fields.append(QgsField('cell_area', QVariant.Double))
        output_fields.append(QgsField('resolution', QVariant.Int))

        return (output_fields)
        # return(input_fields)

    def supportInPlaceEdit(self, layer):
        return False

    def initParameters(self, config=None):   
        # Input vector layer
        param = QgsProcessingParameterFeatureSource(
                self.INPUT,
                self.tr('Input vector layer'),
                [QgsProcessing.TypeVector])
        self.addParameter(param)

        # DGGS Type
        param = QgsProcessingParameterEnum(
            self.DGGS_TYPE,
            self.tr('DGGS type'),
            options=self.DGGS_OPTIONS,
            defaultValue=0  # Default to the first option (OLC)
        )
        self.addParameter(param)

        param = QgsProcessingParameterNumber(
            self.RESOLUTION,  
            self.tr('Resolution'),  
            QgsProcessingParameterNumber.Integer,  # Specify the type correctly
            minValue=0
        )
        self.addParameter(param)

         
    def prepareAlgorithm(self, parameters, context, feedback):
        source = self.parameterAsSource(parameters, self.INPUT, context)
        self.RESOLUTION = self.parameterAsInt(parameters, self.RESOLUTION, context)

        self.total_features = source.featureCount()
        self.num_bad = 0
        
        self.DGGS_TYPE_index = self.parameterAsEnum(parameters, self.DGGS_TYPE, context)
        self.DGGS_TYPE_functions = {
            'h3': qgsfeature2h3,
            # 's2': s22qgsfeature,
            # 'olc': olc2qgsfeature,
            # 'mgrs': mgrs2qgsfeature,
            # 'geohash': geohash2qgsfeature,
            # 'georef': georef2qgsfeature,
            # 'Tilecode': tilecode2qgsfeature,
            # 'maidenhead': maidenhead2qgsfeature,
            # 'gars': gars2qgsfeature
        }
        return True
    
    def processFeature(self, feature, context, feedback):
        try:
            DGGS_TYPE_key = self.DGGS_OPTIONS[self.DGGS_TYPE_index].lower()
            conversion_function = self.DGGS_TYPE_functions.get(DGGS_TYPE_key)

            if conversion_function:
                geom = feature.geometry()

                if geom.isEmpty():
                    return []

                multi_features = []

                # Handle MultiPoint geometry
                if geom.wkbType() == QgsWkbTypes.MultiPoint:
                    for point in geom.asMultiPoint():
                        point_feature = QgsFeature(feature)  # Copy original feature
                        point_feature.setGeometry(QgsGeometry.fromPointXY(point))  # Set individual point geometry
                        cell_feature = conversion_function(point_feature, self.RESOLUTION)
                        if cell_feature:
                            multi_features.append(cell_feature)

                # Handle MultiLineString geometry
                elif geom.wkbType() == QgsWkbTypes.MultiLineString:
                    for linestring in geom.asMultiPolyline():
                        line_feature = QgsFeature(feature)
                        line_feature.setGeometry(QgsGeometry.fromPolylineXY(linestring))
                        cell_feature = conversion_function(line_feature, self.RESOLUTION)
                        if cell_feature:
                            multi_features.append(cell_feature)

                # Handle MultiPolygon geometry
                elif geom.wkbType() == QgsWkbTypes.MultiPolygon:
                    for polygon in geom.asMultiPolygon():
                        poly_feature = QgsFeature(feature)
                        poly_feature.setGeometry(QgsGeometry.fromPolygonXY(polygon))
                        cell_feature = conversion_function(poly_feature, self.RESOLUTION)
                        if cell_feature:
                            multi_features.append(cell_feature)

                # Handle single-part geometries: Point, LineString, Polygon
                else:
                    cell_feature = conversion_function(feature, self.RESOLUTION)
                    if cell_feature:
                        multi_features.append(cell_feature)

                return multi_features  # Return a list of converted features

        except Exception as e:
            self.num_bad += 1
            feedback.reportError(f"Error processing feature {feature.id()}: {str(e)}")

        return []


    def postProcessAlgorithm(self, context, feedback):
        if self.num_bad:
            feedback.pushInfo(self.tr("{} out of {} features had invalid parameters and were ignored.".format(self.num_bad, self.total_features)))
        return {}