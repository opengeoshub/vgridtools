# -*- coding: utf-8 -*-
"""
bin_qtm.py
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
import os, statistics
from vgrid.utils import qtm
from shapely.geometry import Point, Polygon, shape
from ...utils.imgs import Imgs
from collections import defaultdict, Counter    
from ...utils.binning.bin_helper import append_stats_value, get_default_stats_structure

class QTMBin(QgsProcessingAlgorithm):
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
        return QTMBin()

    def name(self):
        return 'bin_qtm'

    def icon(self):
        return QIcon(os.path.join(os.path.dirname(os.path.dirname(__file__)), '../images/generator/grid_triangle.svg'))
    
    def displayName(self):
        return self.tr('QTM', 'QTM')

    def group(self):
        return self.tr('Binning', 'Binning')

    def groupId(self):
        return 'binning'

    def tags(self):
        return self.tr('DGGS, qtm, Binning').split(',')
    
    txt_en = 'QTM Binning'
    txt_vi = 'QTM Binning'
    figure = '../images/tutorial/bin_qtm.png'

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
                    self.tr('Resolution [1..24]'),
                    QgsProcessingParameterNumber.Integer,
                    defaultValue=14,
                    minValue= 1,
                    maxValue= 24,
                    optional=False)
        )

        self.addParameter(QgsProcessingParameterVectorDestination(self.OUTPUT, 'DGGS_binning'))

                   
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
        qtm_bins = defaultdict(lambda: defaultdict(get_default_stats_structure))
        qtm_geometries = {}

        total_points = sum(1 for _ in self.point_layer.getFeatures())
        feedback.setProgress(0)  # Initial progress value

        # Process each point and update progress
        for i, point_feature in enumerate(self.point_layer.getFeatures()):
            point = point_feature.geometry().asPoint()
            qtm_id = qtm.latlon_to_qtm_id(point.y(), point.x(), self.resolution)
            props = point_feature.attributes()
            fields = self.point_layer.fields()
            props_dict = {fields[i].name(): props[i] for i in range(len(fields))}

            append_stats_value(qtm_bins, qtm_id, props_dict, self.stats, self.numeric_field, self.category_field)

            # Update progress after each point is processed
            feedback.setProgress(int((i + 1) / total_points * 100))

        # Provide progress feedback for the categories
        for cat, values in qtm_bins[next(iter(qtm_bins))].items():
            feedback.pushInfo(str(cat))

        # Generate geometries and update progress
        total_qtm_bins = len(qtm_bins)
        for i, qtm_id in enumerate(qtm_bins.keys()):
            facet = qtm.qtm_id_to_facet(qtm_id)
            cell_polygon = qtm.constructGeometry(facet)  
            qtm_geometries[qtm_id] = cell_polygon

            # Update progress after each geometry is generated
            feedback.setProgress(int((i + 1) / total_qtm_bins * 100))

        # Prepare output fields
        out_fields = QgsFields()
        out_fields.append(QgsField("qtm", QVariant.String))

        all_categories = set()
        for bin_data in qtm_bins.values():
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

        # Process each qtm bin and update progress
        total_qtm_geometries = len(qtm_geometries)
        for i, (qtm_id, geom) in enumerate(qtm_geometries.items()):
            props = {}
            for cat in sorted(all_categories):
                prefix = '' if not self.category_field else f"{cat}_"
                values = qtm_bins[qtm_id].get(cat, get_default_stats_structure())

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

            qtm_feature = QgsFeature(out_fields)
            qtm_feature.setGeometry(QgsGeometry.fromWkt(geom.wkt))
            qtm_feature.setAttributes([props.get(f.name(), None) if f.name() != 'qtm' else qtm_id for f in out_fields])
            sink.addFeature(qtm_feature, QgsFeatureSink.FastInsert)

            # Update progress after each qtm bin is processed
            feedback.setProgress(int((i + 1) / total_qtm_geometries * 100))

        return {self.OUTPUT: dest_id}
