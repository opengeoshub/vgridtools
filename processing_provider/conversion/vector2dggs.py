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

import platform
from ...vgridlibrary.imgs import Imgs
from ...vgridlibrary.conversion.qgsfeature2dggs import *

class Vector2DGGS(QgsProcessingFeatureBasedAlgorithm):
    """
    convert Vector Layer to H3, S2, Rhealpix, ISEA4T, ISEA3H, EASE, QTM, OLC, Geohash, GEOREF, MGRS, Tilecode, Maidenhead, GARS
    """
    INPUT = 'INPUT'
    DGGS_TYPE = 'DGGS_TYPE'
    RESOLUTION = 'RESOLUTION'
    DGGS_TYPES = [
        'H3', 'S2','Rhealpix','EASE', 'QTM', 'OLC', 'Geohash', 
        'GEOREF','MGRS', 'Tilecode','Quadkey', 'Maidenhead', 'GARS'
    ]
    DGGS_RESOLUTION = {
        'H3': (0, 15, 10),
        'S2': (0, 30, 16),
        'Rhealpix': (1, 15,11),      
        'EASE':(0,6,4),
        'QTM':(1,24,18),
        'OLC': (2, 15, 10),
        'Geohash': (1, 30, 15),
        'GEOREF': (0, 10, 6),
        'MGRS': (0, 5, 4),
        'Tilecode': (0, 29, 15),
        'Quadkey': (0, 29, 15),
        'Maidenhead': (1, 4, 3),
        'GARS': (1, 30, 1)
    }
    if platform.system() == 'Windows':
        index = DGGS_TYPES.index('Rhealpix') + 1
        DGGS_TYPES[index:index] = ['ISEA4T', 'ISEA3H']

        DGGS_RESOLUTION.update({
            'ISEA4T': (0, 39, 18),
            'ISEA3H': (0, 40, 20),
        })

    
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
        return QIcon(os.path.join(os.path.dirname(os.path.dirname(__file__)), '../images/conversion/vector2dggs.png'))
    
    def displayName(self):
        return self.tr('Vector to DGGS', 'Vector to DGGS')

    def group(self):
        return self.tr('Conversion', 'Conversion')

    def groupId(self):
        return 'conversion'

    def tags(self):
        return self.tr('S2, H3, Rhealpix, ISEA4T, ISEA3H, EASE, OLC, OpenLocationCode, Google Plus Codes, MGRS, Geohash, GEOREF, Tilecode, Maidenhead, GARS').split(',')
    
    txt_en = 'Vector to DGGS'
    txt_vi = 'Vector to DGGS'
    figure = '../images/tutorial/vector2dggs.png'

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
        return self.tr('Vector2DGGS')
    
    def outputWkbType(self, input_wkb_type):
        return (QgsWkbTypes.Polygon)   
    
    def outputFields(self, input_fields):
        output_fields = QgsFields()

        # Preserve all original input fields
        for field in input_fields:
            output_fields.append(field)

        # Append DGGS fields
        output_fields.append(QgsField("cell_id", QVariant.String))
        output_fields.append(QgsField('resolution', QVariant.Int))
        output_fields.append(QgsField('center_lat', QVariant.Double))
        output_fields.append(QgsField('center_lon', QVariant.Double))
        output_fields.append(QgsField('avg_edge_len', QVariant.Double))
        output_fields.append(QgsField('cell_area', QVariant.Double))

        return output_fields


    def supportInPlaceEdit(self, layer):
        return False

    def initParameters(self, config=None):   
        # Input vector layer
        self.addParameter(QgsProcessingParameterFeatureSource(
                self.INPUT,
                self.tr('Input vector layer'),
                [QgsProcessing.TypeVector]))

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
            maxValue=40
        ))


    def checkParameterValues(self, parameters, context):
        """Dynamically update resolution limits before execution"""
        selected_index = self.parameterAsEnum(parameters, self.DGGS_TYPE, context)
        selected_dggs = self.DGGS_TYPES[selected_index]

        min_res, max_res, _ = self.DGGS_RESOLUTION[selected_dggs]
        res_value = self.parameterAsInt(parameters, self.RESOLUTION, context)

        if not (min_res <= res_value <= max_res):
            return (False, f"Resolution must be between {min_res} and {max_res} for {selected_dggs}.")

        if (selected_dggs == 'OLC'):
            if res_value not in (2,4,6,8,10,11,12,13,14,15):
                return (False, f"Resolution must be in [2,4,6,8,10,11,12,13,14,15] for {selected_dggs}.")
        elif (selected_dggs == 'GARS'):
            if res_value not in (30,15,5,1):
                return (False, f"Resolution must be in [30,15,5,1] minutes for {selected_dggs}.")
        
        return super().checkParameterValues(parameters, context)
    
    def prepareAlgorithm(self, parameters, context, feedback):       
        
        source = self.parameterAsSource(parameters, self.INPUT, context)
        self.RESOLUTION = self.parameterAsInt(parameters, self.RESOLUTION, context)

        self.total_features = source.featureCount()
        self.num_bad = 0
        
        self.DGGS_TYPE_index = self.parameterAsEnum(parameters, self.DGGS_TYPE, context)
        self.DGGS_TYPE_functions = {
            'h3': qgsfeature2h3,
            's2': qgsfeature2s2,
            'rhealpix': qgsfeature2rhealpix,
            'ease': qgsfeature2ease,
            'qtm': qgsfeature2qtm,
            'tilecode': qgsfeature2tilecode
            # 'mgrs': mgrs2qgsfeature,
            # 'geohash': geohash2qgsfeature,
            # 'georef': georef2qgsfeature,
            # 'maidenhead': maidenhead2qgsfeature,
            # 'gars': gars2qgsfeature
        }
        if platform.system() == 'Windows':
            self.DGGS_TYPE_functions['isea4t'] = qgsfeature2isea4t
            self.DGGS_TYPE_functions['isea3h'] = qgsfeature2isea3h

        return True


    def processFeature(self, feature, context, feedback):
        try:
            self.dggs_type = self.DGGS_TYPES[self.DGGS_TYPE_index].lower()
            conversion_function = self.DGGS_TYPE_functions.get(self.dggs_type)

            if conversion_function is None:
                return []

            geom = feature.geometry()
            if geom.isEmpty():
                return []

            cell_polygons = []
            multi_cell_polygons = []

            # Handle MultiPoint geometry
            if geom.wkbType() == QgsWkbTypes.MultiPoint:
                for point in geom.asMultiPoint():
                    point_feature = QgsFeature(feature)  # Copy original feature
                    point_feature.setGeometry(QgsGeometry.fromPointXY(point))  # Set individual point geometry
                    cell_polygons = conversion_function(point_feature, self.RESOLUTION)
                    multi_cell_polygons.extend(cell_polygons)          

                return multi_cell_polygons
            
                    
            # Handle MultiLineString geometry
            elif geom.wkbType() == QgsWkbTypes.MultiLineString:
                for line in geom.asMultiPolyline():
                    line_feature = QgsFeature(feature)
                    line_feature.setGeometry(QgsGeometry.fromPolylineXY(line))
                    cell_polygons = conversion_function(line_feature, self.RESOLUTION)
                    multi_cell_polygons.extend(cell_polygons)                
           
                return multi_cell_polygons
            
            # Handle MultiPolygon geometry
            elif geom.wkbType() == QgsWkbTypes.MultiPolygon:
                for polygon in geom.asMultiPolygon():
                    polygon_feature = QgsFeature(feature)
                    polygon_feature.setGeometry(QgsGeometry.fromPolygonXY(polygon))
                    cell_polygons = conversion_function(polygon_feature, self.RESOLUTION)
                    multi_cell_polygons.extend(cell_polygons)                
           
                return multi_cell_polygons
            
            # Handle Single Geometries
            else:
                cell_polygons = conversion_function(feature, self.RESOLUTION)
                return cell_polygons
                        
        except Exception as e:
            feedback.reportError(f"Error processing feature {feature.id()}: {str(e)}")
            return []


    def postProcessAlgorithm(self, context, feedback):
        if self.num_bad:
            feedback.pushInfo(self.tr("{} out of {} features had invalid parameters and were ignored.".format(self.num_bad, self.total_features)))
        return {}