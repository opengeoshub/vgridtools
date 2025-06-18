# -*- coding: utf-8 -*-
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
from vgrid.utils import s2
from vgrid.conversion.latlon2dggs import latlon2s2
from shapely.geometry import Point, Polygon, shape
from ...utils.imgs import Imgs
from collections import defaultdict, Counter    
from ...utils.binning.bin_helper import append_stats_value, get_default_stats_structure
from vgrid.utils.antimeridian import fix_polygon
 
class S2Bin(QgsProcessingAlgorithm):
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
        return S2Bin()

    def name(self):
        return 'bin_s2'

    def icon(self):
        return QIcon(os.path.join(os.path.dirname(os.path.dirname(__file__)), '../images/generator/grid_s2.svg'))
    
    def displayName(self):
        return self.tr('S2', 'S2')

    def group(self):
        return self.tr('Binning', 'Binning')

    def groupId(self):
        return 'binning'

    def tags(self):
        return self.tr('DGGS, S2, Binning').split(',')
    
    txt_en = 'S2 Binning'
    txt_vi = 'S2 Binning'
    figure = '../images/tutorial/bin_s2.png'

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
                    self.tr('Resolution [0..30]'),
                    QgsProcessingParameterNumber.Integer,
                    defaultValue=13,
                    minValue= 0,
                    maxValue= 30,
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
        return True

    def processAlgorithm(self, parameters, context, feedback):        
        s2_bins = defaultdict(lambda: defaultdict(get_default_stats_structure))
        s2_geometries = {}

        total_points = self.point_layer.featureCount()
        feedback.setProgress(0)  # Initial progress value

        # Process each point and update progress
        for i, point_feature in enumerate(self.point_layer.getFeatures()):
            try:
                point = point_feature.geometry().asPoint()
            except:
                feedback.pushInfo(f"Point feature {point_feature.id()} has invalid geometry and will be skipped")
                continue

            s2_token = latlon2s2(point.y(), point.x(), self.resolution)
            props = point_feature.attributes()
            fields = self.point_layer.fields()
            props_dict = {fields[i].name(): props[i] for i in range(len(fields))}

            append_stats_value(s2_bins, s2_token, props_dict, self.stats, self.numeric_field, self.category_field)

            # Update progress after each point is processed
            feedback.setProgress(int((i + 1) / total_points * 100))

      
        # Generate geometries and update progress
        total_s2_bins = len(s2_bins)
        for i, s2_token in enumerate(s2_bins.keys()):
            s2_id = s2.CellId.from_token(s2_token)
            s2_cell = s2.Cell(s2_id)
        
            vertices = [s2_cell.get_vertex(i) for i in range(4)]
            # Prepare vertices in (longitude, latitude) format for Shapely
            shapely_vertices = []
            for vertex in vertices:
                lat_lng = s2.LatLng.from_point(vertex)  # Convert Point to LatLng
                longitude = lat_lng.lng().degrees  # Access longitude in degrees
                latitude = lat_lng.lat().degrees   # Access latitude in degrees
                shapely_vertices.append((longitude, latitude))

            # Close the polygon by adding the first vertex again
            shapely_vertices.append(shapely_vertices[0])  # Closing the polygon
            # Create a Shapely Polygon
            cell_polygon = fix_polygon(Polygon(shapely_vertices)) # Fix antimeridian        
            # coords = [(lng, lat) for lat, lng in s2.cell_to_boundary(s2_token)]
            s2_geometries[s2_token] = cell_polygon

            # Update progress after each geometry is generated
            feedback.setProgress(int((i + 1) / total_s2_bins * 100))

        # Prepare output fields
        out_fields = QgsFields()
        out_fields.append(QgsField("s2", QVariant.String))

        all_categories = set()
        for bin_data in s2_bins.values():
            all_categories.update(bin_data.keys())

        for cat in sorted(all_categories):
            prefix = '' if not self.category_field else f"{cat}_"

            if self.stats == 'count':
                out_fields.append(QgsField(f"{prefix}count", QVariant.Int))
            elif self.stats in ['sum', 'mean', 'min', 'max', 'median', 'std', 'var', 'range']:
                out_fields.append(QgsField(f"{prefix}{self.stats}", QVariant.Double))
            elif self.stats in ['minority', 'majority']:
                out_fields.append(QgsField(f"{prefix}{self.stats}", QVariant.String))
            elif self.stats == 'variety':
                out_fields.append(QgsField(f"{prefix}variety", QVariant.Int))

        # Create the sink for the output
        (sink, dest_id) = self.parameterAsSink(parameters, self.OUTPUT, context, out_fields, QgsWkbTypes.Polygon, self.point_layer.sourceCrs())

        # Process each s2 bin and update progress
        total_s2_geometries = len(s2_geometries)
        for i, (s2_token, geom) in enumerate(s2_geometries.items()):
            props = {}
            for cat in sorted(all_categories):
                prefix = '' if not self.category_field else f"{cat}_"
                values = s2_bins[s2_token].get(cat, get_default_stats_structure())

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

            s2_feature = QgsFeature(out_fields)
            s2_feature.setGeometry(QgsGeometry.fromWkt(geom.wkt))
            s2_feature.setAttributes([props.get(f.name(), None) if f.name() != 's2' else s2_token for f in out_fields])
            sink.addFeature(s2_feature, QgsFeatureSink.FastInsert)

            # Update progress after each s2 bin is processed
            feedback.setProgress(int((i + 1) / total_s2_geometries * 100))

        return {self.OUTPUT: dest_id}
