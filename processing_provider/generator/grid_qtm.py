# -*- coding: utf-8 -*-
"""
grid_qtm.py
***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 2 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************
"""
#  Need to be checked and tested

__author__ = 'Thang Quach'
__date__ = '2024-11-20'
__copyright__ = '(L) 2024, Thang Quach'

from qgis.core import (
    QgsApplication,
    QgsFeatureSink,
    QgsProcessingLayerPostProcessorInterface,
    QgsProcessingParameterExtent,
    QgsProcessingParameterNumber,
    QgsProcessingException,
    QgsProcessingParameterFeatureSink,
    QgsProcessingAlgorithm,
    QgsFields,
    QgsField,
    QgsFeature,
    QgsGeometry,
    QgsWkbTypes,
    QgsCoordinateReferenceSystem,
    QgsVectorLayer,
    QgsPalLayerSettings, 
    QgsVectorLayerSimpleLabeling
)
from qgis.PyQt.QtGui import QIcon, QColor
from qgis.PyQt.QtCore import QCoreApplication,QSettings,Qt
from qgis.utils import iface
from PyQt5.QtCore import QVariant
import os, random
from vgrid.utils import qtm  
    
from ...utils.imgs import Imgs

from pyproj import Geod
geod = Geod(ellps="WGS84")
max_cells = 1_000_000
p90_n180, p90_n90, p90_p0, p90_p90, p90_p180 = (90.0, -180.0), (90.0, -90.0), (90.0, 0.0), (90.0, 90.0), (90.0, 180.0)
p0_n180, p0_n90, p0_p0, p0_p90, p0_p180 = (0.0, -180.0), (0.0, -90.0), (0.0, 0.0), (0.0, 90.0), (0.0, 180.0)
n90_n180, n90_n90, n90_p0, n90_p90, n90_p180 = (-90.0, -180.0), (-90.0, -90.0), (-90.0, 0.0), (-90.0, 90.0), (-90.0, 180.0)


class GridQTM(QgsProcessingAlgorithm):
    EXTENT = 'EXTENT'
    RESOLUTION = 'RESOLUTION'
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
        return GridQTM()

    def name(self):
        return 'grid_qtm'

    def icon(self):
        return QIcon(os.path.join(os.path.dirname(os.path.dirname(__file__)), '../images/generator/grid_qtm.png'))
    
    def displayName(self):
        return self.tr('QTM', 'QTM')

    def group(self):
        return self.tr('DGGS Generator', 'DGGS Generator')

    def groupId(self):
        return 'grid'

    def tags(self):
        return self.tr('DGGS, grid, QTM, generator').split(',')
    
    txt_en = 'QTM Grid Generator'
    txt_vi = 'QTM Grid Generator'
    figure = '../images/tutorial/grid_qtm.png'

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
        param = QgsProcessingParameterExtent(self.EXTENT,
                                             self.tr('Grid extent'),
                                             optional=True
                                            )
        self.addParameter(param)

        param = QgsProcessingParameterNumber(
                    self.RESOLUTION,
                    self.tr('Resolution'),
                    QgsProcessingParameterNumber.Integer,
                    defaultValue=1,
                    minValue= 1,
                    maxValue= 24,
                    optional=False)
        self.addParameter(param)


        param = QgsProcessingParameterFeatureSink(
                self.OUTPUT,
                'QTM')
        self.addParameter(param)
                    
    def prepareAlgorithm(self, parameters, context, feedback):
        self.resolution = self.parameterAsInt(parameters, self.RESOLUTION, context)  
        if self.resolution < 1 or self.resolution > 24:
            feedback.reportError('resolution parameter must be in range [1,24]')
            return False
         
         # Get the extent parameter
        self.grid_extent = self.parameterAsExtent(parameters, self.EXTENT, context)
        if self.resolution > 8 and (self.grid_extent is None or self.grid_extent.isEmpty()):
            feedback.reportError('For performance reason, when resolution is greater than 8, the grid extent must be set.')
            return False
        
        return True    

    def outputFields(self):
        output_fields = QgsFields() 

        # Append DGGS fields
        output_fields.append(QgsField("qtm", QVariant.String))
        output_fields.append(QgsField('resolution', QVariant.Int))
        output_fields.append(QgsField('center_lat', QVariant.Double))
        output_fields.append(QgsField('center_lon', QVariant.Double))
        output_fields.append(QgsField('avg_edge_len', QVariant.Double))
        output_fields.append(QgsField('cell_area', QVariant.Double))

        return output_fields


    def processAlgorithm(self, parameters, context, feedback):        
        fields = self.outputFields()
        
        # Output layer initialization
        (sink, dest_id) = self.parameterAsSink(
            parameters,
            self.OUTPUT,
            context,
            fields,
            QgsWkbTypes.Polygon,
            QgsCoordinateReferenceSystem('EPSG:4326')
        )

        if not sink:
            raise QgsProcessingException(self.invalidSinkError(parameters, self.OUTPUT))

        if self.grid_extent is None or self.grid_extent.isEmpty():
            extent_bbox = None
        else:
            extent_bbox = [
                [self.grid_extent.xMinimum(), self.grid_extent.yMinimum()],
                [self.grid_extent.xMaximum(), self.grid_extent.yMaximum()]
            ]        
        
        QTMID = {}
        levelFacets = {}
        if extent_bbox:    
            for lvl in range(self.resolution):
                levelFacets[lvl] = []
                QTMID[lvl] = []

                if lvl == 0:
                    initial_facets = [
                        [p0_n180, p0_n90, p90_n90, p90_n180, p0_n180, True],
                        [p0_n90, p0_p0, p90_p0, p90_n90, p0_n90, True],
                        [p0_p0, p0_p90, p90_p90, p90_p0, p0_p0, True],
                        [p0_p90, p0_p180, p90_p180, p90_p90, p0_p90, True],
                        [n90_n180, n90_n90, p0_n90, p0_n180, n90_n180, False],
                        [n90_n90, n90_p0, p0_p0, p0_n90, n90_n90, False],
                        [n90_p0, n90_p90, p0_p90, p0_p0, n90_p0, False],
                        [n90_p90, n90_p180, p0_p180, p0_p90, n90_p90, False],
                    ]

                    for i, facet in enumerate(initial_facets):
                        QTMID[0].append(str(i + 1))
                        facet_geom = qtm.constructGeometry(facet)
                        cell_centroid = facet_geom.centroid
                        center_lat =  round(cell_centroid.y, 7)
                        center_lon = round(cell_centroid.x, 7)
                        cell_area = round(abs(geod.geometry_area_perimeter(facet_geom)[0]),2)
                        cell_perimeter = abs(geod.geometry_area_perimeter(facet_geom)[1])
                        avg_edge_len = round(cell_perimeter / 3,2)
                        cell_geometry = QgsGeometry.fromWkt(facet_geom.wkt)       

                        levelFacets[0].append(facet)                                         
                        if cell_geometry.intersects(QgsGeometry.fromRect(self.grid_extent)) and self.resolution == 1:
                            feature = QgsFeature()
                            feature.setGeometry(cell_geometry)
                            feature.setAttributes([QTMID[0][i],self.resolution,center_lat,center_lon,avg_edge_len,cell_area])
                            sink.addFeature(feature, QgsFeatureSink.FastInsert)      
                else:
                    for i, pf in enumerate(levelFacets[lvl - 1]):
                        subdivided_facets = qtm.divideFacet(pf)
                        for j, subfacet in enumerate(subdivided_facets):
                            subfacet_geom = qtm.constructGeometry(subfacet)
                            cell_geometry = QgsGeometry.fromWkt(subfacet_geom.wkt)    
                            if cell_geometry.intersects(QgsGeometry.fromRect(self.grid_extent)):  # Only keep intersecting facets
                                new_id = QTMID[lvl - 1][i] + str(j)
                                QTMID[lvl].append(new_id)
                                levelFacets[lvl].append(subfacet)
                                if lvl == self.resolution - 1:  # Only store final resolution
                                    cell_centroid = subfacet_geom.centroid
                                    center_lat =  round(cell_centroid.y, 7)
                                    center_lon = round(cell_centroid.x, 7)
                                    cell_area = round(abs(geod.geometry_area_perimeter(subfacet_geom)[0]),2)
                                    cell_perimeter = abs(geod.geometry_area_perimeter(subfacet_geom)[1])
                                    avg_edge_len = round(cell_perimeter / 3,2)
                                    
                                       
                                    feature = QgsFeature()
                                    feature.setGeometry(cell_geometry)
                                    feature.setAttributes([new_id,self.resolution,center_lat,center_lon,avg_edge_len,cell_area])
                                    sink.addFeature(feature, QgsFeatureSink.FastInsert)   
        else:
            for lvl in range(self.resolution):
                levelFacets[lvl] = []
                QTMID[lvl] = []

                if lvl == 0:
                    initial_facets = [
                        [p0_n180, p0_n90, p90_n90, p90_n180, p0_n180, True],
                        [p0_n90, p0_p0, p90_p0, p90_n90, p0_n90, True],
                        [p0_p0, p0_p90, p90_p90, p90_p0, p0_p0, True],
                        [p0_p90, p0_p180, p90_p180, p90_p90, p0_p90, True],
                        [n90_n180, n90_n90, p0_n90, p0_n180, n90_n180, False],
                        [n90_n90, n90_p0, p0_p0, p0_n90, n90_n90, False],
                        [n90_p0, n90_p90, p0_p90, p0_p0, n90_p0, False],
                        [n90_p90, n90_p180, p0_p180, p0_p90, n90_p90, False],
                    ]

                    for i, facet in enumerate(initial_facets):
                        facet_geom = qtm.constructGeometry(facet)
                        QTMID[0].append(str(i + 1))
                        levelFacets[0].append(facet)
                        
                        cell_centroid = facet_geom.centroid
                        center_lat =  round(cell_centroid.y, 7)
                        center_lon = round(cell_centroid.x, 7)
                        cell_area = round(abs(geod.geometry_area_perimeter(facet_geom)[0]),2)
                        cell_perimeter = abs(geod.geometry_area_perimeter(facet_geom)[1])
                        avg_edge_len = round(cell_perimeter / 3,2)                         

                        cell_geometry = QgsGeometry.fromWkt(facet_geom.wkt)                        
                        
                        feature = QgsFeature()
                        feature.setGeometry(cell_geometry)
                        feature.setAttributes([QTMID[0][i],self.resolution,center_lat,center_lon,avg_edge_len,cell_area])
                        sink.addFeature(feature, QgsFeatureSink.FastInsert)               
                else:
                    for i, pf in enumerate(levelFacets[lvl - 1]):
                        subdivided_facets = qtm.divideFacet(pf)
                        for j, subfacet in enumerate(subdivided_facets):
                            new_id = QTMID[lvl - 1][i] + str(j)
                            QTMID[lvl].append(new_id)                    
                            levelFacets[lvl].append(subfacet)
                            if lvl == self.resolution -1:
                                subfacet_geom= qtm.constructGeometry(subfacet)
                                cell_centroid = subfacet_geom.centroid
                                center_lat =  round(cell_centroid.y, 7)
                                center_lon = round(cell_centroid.x, 7)
                                cell_area = round(abs(geod.geometry_area_perimeter(subfacet_geom)[0]),2)
                                cell_perimeter = abs(geod.geometry_area_perimeter(subfacet_geom)[1])
                                avg_edge_len = round(cell_perimeter / 3,2)                
                               
                                cell_geometry = QgsGeometry.fromWkt(subfacet_geom.wkt)                        
                                feature = QgsFeature()
                                feature.setGeometry(cell_geometry)
                                feature.setAttributes([new_id,self.resolution,center_lat,center_lon,avg_edge_len,cell_area])
                                sink.addFeature(feature, QgsFeatureSink.FastInsert)                                        
                                    
                            if feedback.isCanceled():
                                break
                
        feedback.pushInfo("QTM grid generation completed.")
        if context.willLoadLayerOnCompletion(dest_id):
            lineColor = QColor.fromRgb(random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
            fontColor = QColor('#000000')
            context.layerToLoadOnCompletionDetails(dest_id).setPostProcessor(StylePostProcessor.create(lineColor, fontColor))
        
        return {self.OUTPUT: dest_id}


class StylePostProcessor(QgsProcessingLayerPostProcessorInterface):
    instance = None
    line_color = None
    font_color = None

    def __init__(self, line_color, font_color):
        self.line_color = line_color
        self.font_color = font_color
        super().__init__()

    def postProcessLayer(self, layer, context, feedback):

        if not isinstance(layer, QgsVectorLayer):
            return
        sym = layer.renderer().symbol().symbolLayer(0)
        sym.setBrushStyle(Qt.NoBrush)
        sym.setStrokeColor(self.line_color)
        label = QgsPalLayerSettings()
        label.fieldName = 'qtm'
        format = label.format()
        format.setColor(self.font_color)
        format.setSize(8)
        label.setFormat(format)
        labeling = QgsVectorLayerSimpleLabeling(label)
        layer.setLabeling(labeling)
        layer.setLabelsEnabled(True)
        iface.layerTreeView().refreshLayerSymbology(layer.id())

    # Hack to work around sip bug!
    @staticmethod
    def create(line_color, font_color) -> 'StylePostProcessor':
        """
        Returns a new instance of the post processor, keeping a reference to the sip
        wrapper so that sip doesn't get confused with the Python subclass and call
        the base wrapper implementation instead... ahhh sip, you wonderful piece of sip
        """
        StylePostProcessor.instance = StylePostProcessor(line_color, font_color)
        return StylePostProcessor.instance