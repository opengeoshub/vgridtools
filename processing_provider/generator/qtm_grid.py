# -*- coding: utf-8 -*-
"""
qtm_grid.py
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
    QgsProject,
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
from vgrid.generator.settings import geodesic_dggs_metrics  
from shapely.geometry import box
from ...utils.imgs import Imgs

class QTMGrid(QgsProcessingAlgorithm):
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
        return QTMGrid()

    def name(self):
        return 'grid_qtm'

    def icon(self):
        return QIcon(os.path.join(os.path.dirname(os.path.dirname(__file__)), '../images/generator/grid_triangle.svg'))
    
    def displayName(self):
        return self.tr('QTM', 'QTM')

    def group(self):
        return self.tr('Generator', 'Generator')

    def groupId(self):
        return 'grid'

    def tags(self):
        return self.tr('DGGS, grid, QTM, generator').split(',')
    
    txt_en = 'QTM DGGS Generator'
    txt_vi = 'QTM DGGS Generator'
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
                    self.tr('Resolution [1..24]'),
                    QgsProcessingParameterNumber.Integer,
                    defaultValue=2,
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
        # Get the extent parameter
        self.grid_extent = self.parameterAsExtent(parameters, self.EXTENT, context)
        if self.resolution > 9 and (self.grid_extent is None or self.grid_extent.isEmpty()):
            feedback.reportError('For performance reason, when resolution is greater than 9, the grid extent must be set.')
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
        p90_n180, p90_n90, p90_p0, p90_p90, p90_p180 = (90.0, -180.0), (90.0, -90.0), (90.0, 0.0), (90.0, 90.0), (90.0, 180.0)
        p0_n180, p0_n90, p0_p0, p0_p90, p0_p180 = (0.0, -180.0), (0.0, -90.0), (0.0, 0.0), (0.0, 90.0), (0.0, 180.0)
        n90_n180, n90_n90, n90_p0, n90_p90, n90_p180 = (-90.0, -180.0), (-90.0, -90.0), (-90.0, 0.0), (-90.0, 90.0), (-90.0, 180.0)

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
            extent_bbox = box(self.grid_extent.xMinimum(), self.grid_extent.yMinimum(), 
                            self.grid_extent.xMaximum(), self.grid_extent.yMaximum())         
        
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
                        levelFacets[0].append(facet)                                         
                        if facet_geom.intersects(extent_bbox) and self.resolution == 1:
                            cell_geometry = QgsGeometry.fromWkt(facet_geom.wkt) 
                            qtm_feature = QgsFeature()
                            qtm_feature.setGeometry(cell_geometry)
                            qtm_id = QTMID[0][i]
                            num_edges = 3
                            center_lat, center_lon, avg_edge_len, cell_area = geodesic_dggs_metrics(facet_geom, num_edges)
                            qtm_feature.setAttributes([qtm_id,self.resolution,center_lat,center_lon,avg_edge_len,cell_area])
                            sink.addFeature(qtm_feature, QgsFeatureSink.FastInsert)      
                        if feedback.isCanceled():
                                break
                else:
                    for i, pf in enumerate(levelFacets[lvl - 1]):
                        subdivided_facets = qtm.divideFacet(pf)
                        for j, subfacet in enumerate(subdivided_facets):
                            subfacet_geom = qtm.constructGeometry(subfacet)
                            if subfacet_geom.intersects(extent_bbox):  # Only keep intersecting facets
                                cell_geometry = QgsGeometry.fromWkt(subfacet_geom.wkt)  
                                new_id = QTMID[lvl - 1][i] + str(j)
                                QTMID[lvl].append(new_id)
                                levelFacets[lvl].append(subfacet)
                                if lvl == self.resolution - 1:  # Only store final resolution
                                    qtm_feature = QgsFeature()
                                    qtm_feature.setGeometry(cell_geometry)
                                    qtm_id = new_id
                                    num_edges = 3
                                    center_lat, center_lon, avg_edge_len, cell_area = geodesic_dggs_metrics(subfacet_geom, num_edges)
                                    qtm_feature.setAttributes([qtm_id,self.resolution,center_lat,center_lon,avg_edge_len,cell_area])
                                    sink.addFeature(qtm_feature, QgsFeatureSink.FastInsert)   
                            if feedback.isCanceled():
                                break
                
        else:  # global scale            
            total_cells = 8*4**(self.resolution-1)                
            feedback.pushInfo(f"Total cells to be generated: {total_cells}.")
            processed_cells = 0  # Counter for progress tracking
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
                        if (self.resolution ==1):
                            qtm_id = QTMID[0][i]
                            num_edges = 3
                            center_lat, center_lon, avg_edge_len, cell_area = geodesic_dggs_metrics(facet_geom, num_edges)                       
                            cell_geometry = QgsGeometry.fromWkt(facet_geom.wkt) 
                            qtm_feature = QgsFeature()
                            qtm_feature.setGeometry(cell_geometry)
                            qtm_feature.setAttributes([qtm_id,self.resolution,center_lat,center_lon,avg_edge_len,cell_area])
                            sink.addFeature(qtm_feature, QgsFeatureSink.FastInsert)  
                            # Update progress
                            processed_cells += 1
                            feedback.setProgress(int(100 * processed_cells / total_cells)) 
                            if feedback.isCanceled():
                                break
                else:
                    for i, pf in enumerate(levelFacets[lvl - 1]):
                        subdivided_facets = qtm.divideFacet(pf)
                        for j, subfacet in enumerate(subdivided_facets):
                            new_id = QTMID[lvl - 1][i] + str(j)
                            QTMID[lvl].append(new_id)                    
                            levelFacets[lvl].append(subfacet)
                            if lvl == self.resolution -1:
                                subfacet_geom= qtm.constructGeometry(subfacet)
                                qtm_id = new_id
                                num_edges = 3
                                center_lat, center_lon, avg_edge_len, cell_area = geodesic_dggs_metrics(subfacet_geom, num_edges)
                            
                                cell_geometry = QgsGeometry.fromWkt(subfacet_geom.wkt) 
                                qtm_feature = QgsFeature()
                                qtm_feature.setGeometry(cell_geometry)
                                qtm_feature.setAttributes([qtm_id,self.resolution,center_lat,center_lon,avg_edge_len,cell_area])
                                sink.addFeature(qtm_feature, QgsFeatureSink.FastInsert)           
                                 # Update progress
                                processed_cells += 1
                                feedback.setProgress(int(100 * processed_cells / total_cells))

                            if feedback.isCanceled():
                                break
                
        feedback.pushInfo("QTM DGGS generation completed.")
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

        root = QgsProject.instance().layerTreeRoot()
        layer_node = root.findLayer(layer.id())
        if layer_node:
            layer_node.setCustomProperty("showFeatureCount", True)
        
        iface.mapCanvas().setExtent(layer.extent())
        iface.mapCanvas().refresh()
        
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