# -*- coding: utf-8 -*-
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
    QgsProcessingParameterBoolean,
    QgsWkbTypes    
    )

from qgis.core import QgsApplication
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtCore import QCoreApplication,QVariant

import platform
from ...utils.imgs import Imgs
from ...utils.conversion.qgsfeature2dggs import *
from .dggs_settings import settings, DGGSettingsDialog

class Vector2DGGS(QgsProcessingFeatureBasedAlgorithm):
    """
    convert Vector Layer to H3, S2, rHEALPix, ISEA4T, ISEA3H, QTM, OLC, Geohash, GEOREF, MGRS, Tilecode, Maidenhead, GARS
    """
    INPUT = 'INPUT'
    DGGS_TYPE = 'DGGS_TYPE'
    RESOLUTION = 'RESOLUTION'
    COMPACT = 'COMPACT'
    PREDICATE = 'PREDICATE'
    PREDICATES = ['intersects', 'within', 'centroid_within','largest_overlap']
    DGGS_TYPES = [
        'H3', 'S2','rHEALPix','QTM', 'OLC', 'Geohash', 
        # 'GEOREF',
        # 'MGRS',
         'Tilecode','Quadkey']
    
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
        return self.tr('vector, S2, H3, rHEALPix, ISEA4T, ISEA3H, EASE, OLC, OpenLocationCode, Google Plus Codes, MGRS, Geohash, GEOREF, Tilecode, Maidenhead, GARS').split(',')
    
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

        # Get default resolution from settings
        default_dggs = self.DGGS_TYPES[0]
        _, _, default_res = settings.getResolution(default_dggs)

        self.addParameter(QgsProcessingParameterNumber(
            self.RESOLUTION,
            "Resolution",
            QgsProcessingParameterNumber.Integer,
            default_res,
            minValue=0,
            maxValue=40
        ))
        
        self.addParameter(QgsProcessingParameterEnum(
            self.PREDICATE,
            "Spatial predicate",
            options=self.PREDICATES,
            defaultValue=0
        ))

        self.addParameter(QgsProcessingParameterBoolean(
            self.COMPACT,
            "Compact",
            defaultValue=False  
        ))


    def checkParameterValues(self, parameters, context):
        """Dynamically update resolution limits before execution"""
        selected_dggs_index = self.parameterAsEnum(parameters, self.DGGS_TYPE, context)
        selected_dggs = self.DGGS_TYPES[selected_dggs_index]

        min_res, max_res, _ = settings.getResolution(selected_dggs)
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
            QgsField(get_unique_name("avg_edge_len" if dggs_type in ('h3', 's2', 'rhealpix', 'isea4t', 'isea3h', 'ease', 'qtm') else "cell_width"), QVariant.Double),
            QgsField(get_unique_name("cell_height"), QVariant.Double) if dggs_type not in ('h3', 's2', 'rhealpix', 'isea4t', 'isea3h', 'ease', 'qtm') else None,
            QgsField(get_unique_name("cell_area"), QVariant.Double)
        ]

        # Append the fields to output_fields
        for field in new_fields:
            if field:
                output_fields.append(field)

        return output_fields

    def prepareAlgorithm(self, parameters, context, feedback):       
        source = self.parameterAsSource(parameters, self.INPUT, context)
        # Check CRS
        crs = source.sourceCrs() if hasattr(source, 'sourceCrs') else None
        if crs is not None and not crs.isGeographic():
            feedback.reportError('Input layer CRS must be a geographic coordinate system (degrees).')
            return False
     
        self.resolution = self.parameterAsInt(parameters, self.RESOLUTION, context)
        self.compact  = self.parameterAsBool(parameters, self.COMPACT, context)
        self.predicate = self.parameterAsEnum(parameters, self.PREDICATE, context)

        self.total_features = source.featureCount()
        self.num_bad = 0
        
        self.DGGS_TYPE_index = self.parameterAsEnum(parameters, self.DGGS_TYPE, context)
        self.DGGS_TYPE_functions = {
            'h3': qgsfeature2h3,
            's2': qgsfeature2s2,
            'rhealpix': qgsfeature2rhealpix,
            # 'ease': qgsfeature2ease,
            'qtm': qgsfeature2qtm,
            'olc': qgsfeature2olc,
            'geohash': qgsfeature2geohash, # Need to check polyline/ polygon2geohash
            # 'georef': qgsfeature2georef,   
            'tilecode': qgsfeature2tilecode,
            'quadkey': qgsfeature2quadkey
        }
        if platform.system() == 'Windows':
            self.DGGS_TYPE_functions['isea4t'] = qgsfeature2isea4t # Need to check polyline/ polygon2isea4t --> QGIS crashed
            self.DGGS_TYPE_functions['isea3h'] = qgsfeature2isea3h # Need to check polyline/ polygon2isea3h --> QGIS crashed

        return True

    def processFeature(self, feature, context, feedback):
        try:     
            self.dggs_type = self.DGGS_TYPES[self.DGGS_TYPE_index].lower()
            conversion_function = self.DGGS_TYPE_functions.get(self.dggs_type)

            if conversion_function is None:
                return []

            feature_geom = feature.geometry()

            cell_polygons = []
            multi_cell_polygons = []

            # Handle MultiPoint geometry
            if feature_geom.wkbType() == QgsWkbTypes.MultiPoint:
                for point in feature_geom.asMultiPoint():
                    point_feature = QgsFeature(feature)  # Copy original feature
                    point_feature.setGeometry(QgsGeometry.fromPointXY(point))  # Set individual point geometry
                    cell_polygons = conversion_function(point_feature, self.resolution, self.predicate,self.compact, feedback)
                    multi_cell_polygons.extend(cell_polygons)          
                return multi_cell_polygons
            
                    
            # Handle MultiLineString geometry
            elif feature_geom.wkbType() == QgsWkbTypes.MultiLineString:
                for line in feature_geom.asMultiPolyline():
                    line_feature = QgsFeature(feature)
                    line_feature.setGeometry(QgsGeometry.fromPolylineXY(line))
                    cell_polygons = conversion_function(line_feature, self.resolution,self.predicate, self.compact,feedback)
                    multi_cell_polygons.extend(cell_polygons)
                return multi_cell_polygons
            
            # Handle MultiPolygon geometry
            elif feature_geom.wkbType() == QgsWkbTypes.MultiPolygon:
                for polygon in feature_geom.asMultiPolygon():
                    polygon_feature = QgsFeature(feature)
                    polygon_feature.setGeometry(QgsGeometry.fromPolygonXY(polygon))
                    cell_polygons = conversion_function(polygon_feature, self.resolution,self.predicate, self.compact, feedback)
                    multi_cell_polygons.extend(cell_polygons)                
                return multi_cell_polygons
            
            else: # Single part features
                return conversion_function(feature, self.resolution,self.predicate, self.compact, feedback)
            
        except Exception as e:
            self.num_bad += 1
            feedback.reportError(f"Error processing feature {feature.id()}: {str(e)}")   

    def postProcessAlgorithm(self, context, feedback):
        if self.num_bad:
            feedback.pushInfo(self.tr("{} out of {} features had invalid parameters and were ignored.".format(self.num_bad, self.total_features)))
        return {}