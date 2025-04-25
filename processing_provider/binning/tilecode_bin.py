# -*- coding: utf-8 -*-
"""
bin_tilecode.py
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

from qgis.core import (
    QgsApplication,
    QgsFeatureSink,  
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterField,
    QgsProcessingParameterNumber,
    QgsFields,
    QgsField,
    QgsFeature,
    QgsGeometry,
    QgsWkbTypes,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterField,
    QgsProcessingParameterVectorDestination,
    QgsProcessingParameterEnum,
    QgsProcessingException
)
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtCore import QCoreApplication,QSettings,Qt
from PyQt5.QtCore import QVariant
import os,re, statistics
from shapely.geometry import  Polygon
from ...utils.imgs import Imgs
from collections import defaultdict, Counter    
from ...utils.binning.bin_helper import append_stats_value, get_default_stats_structure
from vgrid.utils import mercantile
from vgrid.conversion.latlon2dggs import latlon2tilecode

class TilecodeBin(QgsProcessingAlgorithm):
    INPUT = 'INPUT'
    CATEGORY_FIELD = 'CATEGORY_FIELD'
    NUMERIC_FIELD = 'NUMERIC_FIELD'
    STATS = 'STATS'
    RESOLUTION = 'RESOLUTION'
    OUTPUT = 'OUTPUT'

    STATISTICS = [
        'count', 'sum', 'min', 'max',
        'mean', 'median', 'std', 'var', 'range',
        'minority', 'majority', 'variety'
    ]
   
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
        return TilecodeBin()

    def name(self):
        return 'bin_tilecode'

    def icon(self):
        return QIcon(os.path.join(os.path.dirname(os.path.dirname(__file__)), '../images/generator/grid_quad.svg'))
    
    def displayName(self):
        return self.tr('Tilecode', 'Tilecode')

    def group(self):
        return self.tr('Binning', 'Binning')

    def groupId(self):
        return 'binning'

    def tags(self):
        return self.tr('DGGS, Tilecode, Binning').split(',')
    
    txt_en = 'Tilecode Binning'
    txt_vi = 'Tilecode Binning'
    figure = '../images/tutorial/bin_tilecode.png'

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

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.INPUT,
                'Input point layer',
                [QgsProcessing.TypeVectorPoint]  # Ensures only point geometries are selectable
            )
        )
        
        self.addParameter(QgsProcessingParameterEnum(
            self.STATS,
            "Statistic to compute",
            options=self.STATISTICS,
            defaultValue=0
        )) 

        self.addParameter(
            QgsProcessingParameterField(
                self.NUMERIC_FIELD,
                "Numeric field (for statistics other than 'count')",
                parentLayerParameterName=self.INPUT,
                optional=True,
                type=QgsProcessingParameterField.Numeric  # 🔥 This limits to numeric fields only
            )
        )
        self.addParameter(
            QgsProcessingParameterField(
                self.CATEGORY_FIELD, 
                'Category field', 
                optional=True, 
            parentLayerParameterName=self.INPUT
            )
        )

        self.addParameter(QgsProcessingParameterNumber(
            self.RESOLUTION,
            self.tr('Resolution [0..29]'),
            QgsProcessingParameterNumber.Integer,
            defaultValue=15,
            minValue= 0,
            maxValue= 29,
            optional=False) 
        )

        self.addParameter(QgsProcessingParameterVectorDestination(self.OUTPUT, 'Output'))

                   
    def prepareAlgorithm(self, parameters, context, feedback):
        self.point_layer = self.parameterAsSource(parameters, self.INPUT, context)
        self.stats_index = self.parameterAsEnum(parameters, self.STATS, context)
        self.stats = self.STATISTICS[self.stats_index]
        self.resolution = self.parameterAsInt(parameters, self.RESOLUTION, context)         
        self.numeric_field = self.parameterAsString(parameters, self.NUMERIC_FIELD, context)
        self.category_field = self.parameterAsString(parameters, self.CATEGORY_FIELD, context)

        if self.stats != 'count' and not self.numeric_field:  
            raise QgsProcessingException("A numeric field is required for statistics other than 'count'.")

        for point_feature in self.point_layer.getFeatures():
            geom = point_feature.geometry()
            if geom.isMultipart():
                raise QgsProcessingException("The input layer must contain only single-part point geometries.")
            if geom.type() != QgsWkbTypes.PointGeometry:
                raise QgsProcessingException("The input layer must contain only point geometries.")

        return True

    def processAlgorithm(self, parameters, context, feedback):        
        tilecode_bins = defaultdict(lambda: defaultdict(get_default_stats_structure))
        tilecode_geometries = {}

        total_points = sum(1 for _ in self.point_layer.getFeatures())
        feedback.setProgress(0)  # Initial progress value

        # Process each point and update progress
        for i, point_feature in enumerate(self.point_layer.getFeatures()):
            point = point_feature.geometry().asPoint()
            tilecode_id = latlon2tilecode(point.y(), point.x(), self.resolution)
            props = point_feature.attributes()
            fields = self.point_layer.fields()
            props_dict = {fields[i].name(): props[i] for i in range(len(fields))}

            append_stats_value(tilecode_bins, tilecode_id, props_dict, self.stats, self.numeric_field, self.category_field)

            # Update progress after each point is processed
            feedback.setProgress(int((i + 1) / total_points * 100))

        # Provide progress feedback for the categories
        for cat, values in tilecode_bins[next(iter(tilecode_bins))].items():
            feedback.pushInfo(str(cat))

        # Generate geometries and update progress
        total_tilecode_bins = len(tilecode_bins)
        for i, tilecode_id in enumerate(tilecode_bins.keys()):
            match = re.match(r'z(\d+)x(\d+)y(\d+)', tilecode_id)    
            # Convert matched groups to integers
            z = int(match.group(1))
            x = int(match.group(2))
            y = int(match.group(3))
            bounds = mercantile.bounds(x, y, z)    
            min_lat, min_lon = bounds.south, bounds.west
            max_lat, max_lon = bounds.north, bounds.east
            cell_polygon = Polygon([
                [min_lon, min_lat],  # Bottom-left corner
                [max_lon, min_lat],  # Bottom-right corner
                [max_lon, max_lat],  # Top-right corner
                [min_lon, max_lat],  # Top-left corner
                [min_lon, min_lat]   # Closing the polygon (same as the first point)
            ])

            tilecode_geometries[tilecode_id] = cell_polygon

            # Update progress after each geometry is generated
            feedback.setProgress(int((i + 1) / total_tilecode_bins * 100))

        # Prepare output fields
        out_fields = QgsFields()
        out_fields.append(QgsField("tilecode", QVariant.String))

        all_categories = set()
        for bin_data in tilecode_bins.values():
            all_categories.update(bin_data.keys())

        for cat in sorted(all_categories):
            prefix = '' if not self.category_field else f"{cat}_"

            if self.stats == 'count':
                out_fields.append(QgsField(f"{prefix}count", QVariant.Double))
            elif self.stats in ['sum', 'mean', 'min', 'max', 'median', 'std', 'var', 'range']:
                out_fields.append(QgsField(f"{prefix}{self.stats}", QVariant.Double))
            elif self.stats in ['minority', 'majority']:
                out_fields.append(QgsField(f"{prefix}{self.stats}", QVariant.String))
            elif self.stats == 'variety':
                out_fields.append(QgsField(f"{prefix}variety", QVariant.Int))

        # Create the sink for the output
        (sink, dest_id) = self.parameterAsSink(parameters, self.OUTPUT, context, out_fields, QgsWkbTypes.Polygon, self.point_layer.sourceCrs())

        # Process each tilecode bin and update progress
        total_tilecode_geometries = len(tilecode_geometries)
        for i, (tilecode_id, geom) in enumerate(tilecode_geometries.items()):
            props = {}
            for cat in sorted(all_categories):
                prefix = '' if not self.category_field else f"{cat}_"
                values = tilecode_bins[tilecode_id].get(cat, get_default_stats_structure())

                if self.stats == 'count':
                    props[f'{prefix}count'] = values['count']
                elif self.stats == 'sum':
                    props[f'{prefix}sum'] = sum(values['sum']) if values['sum'] else None
                elif self.stats == 'min':
                    props[f'{prefix}min'] = min(values['min']) if values['min'] else None
                elif self.stats == 'max':
                    props[f'{prefix}max'] = max(values['max']) if values['max'] else None
                elif self.stats == 'mean':
                    props[f'{prefix}mean'] = statistics.mean(values['mean']) if values['mean'] else None
                elif self.stats == 'median':
                    props[f'{prefix}median'] = statistics.median(values['median']) if values['median'] else None
                elif self.stats == 'std':
                    props[f'{prefix}std'] = statistics.stdev(values['std']) if len(values['std']) > 1 else 0
                elif self.stats == 'var':
                    props[f'{prefix}var'] = statistics.variance(values['var']) if len(values['var']) > 1 else 0
                elif self.stats == 'range':
                    props[f'{prefix}range'] = max(values['range']) - min(values['range']) if values['range'] else 0
                elif self.stats == 'minority':
                    freq = Counter(values['values'])
                    props[f'{prefix}minority'] = min(freq.items(), key=lambda x: x[1])[0] if freq else None
                elif self.stats == 'majority':
                    freq = Counter(values['values'])
                    props[f'{prefix}majority'] = max(freq.items(), key=lambda x: x[1])[0] if freq else None
                elif self.stats == 'variety':
                    props[f'{prefix}variety'] = len(set(values['values']))

            tilecode_feature = QgsFeature(out_fields)
            tilecode_feature.setGeometry(QgsGeometry.fromWkt(geom.wkt))
            tilecode_feature.setAttributes([props.get(f.name(), None) if f.name() != 'tilecode' else tilecode_id for f in out_fields])
            sink.addFeature(tilecode_feature, QgsFeatureSink.FastInsert)

            # Update progress after each tilecode bin is processed
            feedback.setProgress(int((i + 1) / total_tilecode_geometries * 100))

        return {self.OUTPUT: dest_id}
