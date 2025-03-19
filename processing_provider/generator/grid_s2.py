# -*- coding: utf-8 -*-
"""
grid_vgrid.py
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
    QgsPointXY, 
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
import os
from vgrid.utils import s2 
from ...utils.imgs import Imgs
from vgrid.utils.antimeridian import fix_polygon
from shapely.geometry import Polygon
import random
from vgrid.generator.settings import max_cells,geodesic_dggs_metrics

class GridS2(QgsProcessingAlgorithm):
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
        return GridS2()

    def name(self):
        return 'grid_s2'

    def icon(self):
        return QIcon(os.path.join(os.path.dirname(os.path.dirname(__file__)), '../images/generator/grid_s2.svg'))
    
    def displayName(self):
        return self.tr('S2', 'S2')

    def group(self):
        return self.tr('DGGS Generator', 'DGGS Generator')

    def groupId(self):
        return 'grid'

    def tags(self):
        return self.tr('DGGS, grid, S2, generator').split(',')
    
    txt_en = 'S2 Grid Generator'
    txt_vi = 'S2 Grid Generator'
    figure = '../images/tutorial/grid_s2.png'

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
                    self.tr('Resolution [0..30]'),
                    QgsProcessingParameterNumber.Integer,
                    defaultValue=1,
                    minValue= 0,
                    maxValue= 30,
                    optional=False)
        self.addParameter(param)


        param = QgsProcessingParameterFeatureSink(
                self.OUTPUT,
                'S2')
        self.addParameter(param)
                    
    def prepareAlgorithm(self, parameters, context, feedback):
        self.resolution = self.parameterAsInt(parameters, self.RESOLUTION, context)  
        # Get the extent parameter
        self.grid_extent = self.parameterAsExtent(parameters, self.EXTENT, context)
        if self.resolution > 8 and (self.grid_extent is None or self.grid_extent.isEmpty()):
            feedback.reportError('For performance reason, when resolution is greater than 8, the grid extent must be set.')
            return False
        
        return True
    
    def processAlgorithm(self, parameters, context, feedback):
        fields = QgsFields()
        fields.append(QgsField("s2", QVariant.String))   # S2 token
        fields.append(QgsField("resolution", QVariant.Int)) 
        fields.append(QgsField("center_lat", QVariant.Double)) # Centroid latitude
        fields.append(QgsField("center_lon", QVariant.Double)) # Centroid longitude
        fields.append(QgsField("avg_edge_len", QVariant.Double)) # Average edge length
        fields.append(QgsField("cell_area", QVariant.Double))  # Area in square meters

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
        
        region = None
        if extent_bbox:
            region = s2.LatLngRect.from_point_pair(
                s2.LatLng.from_degrees(extent_bbox[0][1], extent_bbox[0][0]),
                s2.LatLng.from_degrees(extent_bbox[1][1], extent_bbox[1][0])
            )

        covering = s2.RegionCoverer()
        covering.min_level = self.resolution
        covering.max_level = self.resolution
        # covering.max_cells = 10_000

        # Get covering for the specified region or all regions
        cells = covering.get_covering(region) if region else covering.get_covering(s2.LatLngRect.full())
        total_cells = len(cells)
        
        feedback.pushInfo(f"Total cells to be generated: {total_cells}.")
        # if total_cells > max_cells:
        #     feedback.reportError(f"For performance reason, it must be lesser than {max_cells}. Please input an appropriate extent or RESOLUTION")
        #     return {self.OUTPUT: dest_id}
        
        for idx, s2_cell_id in enumerate(cells):
            progress = int((idx / total_cells) * 100)
            feedback.setProgress(progress)

            cell = s2.Cell(s2_cell_id)
            s2_token = s2.CellId.to_token(s2_cell_id)
            vertices = []
            for i in range(4):  # S2 cells are quads
                vertex = cell.get_vertex(i)
                latlng = s2.LatLng.from_point(vertex)
                vertices.append([latlng.lng().degrees, latlng.lat().degrees])
            vertices.append(vertices[0])  # Close the ring

            cell_polygon = fix_polygon(Polygon(vertices))
            cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)
            
            # Filter cells by extent if it exists
            if extent_bbox:
                if not cell_geometry.intersects(QgsGeometry.fromRect(self.grid_extent)):
                    continue
            
            s2_feature = QgsFeature()
            s2_feature.setGeometry(cell_geometry)
            
            num_edges = 4
            center_lat, center_lon, avg_edge_len, cell_area = geodesic_dggs_metrics(cell_polygon, num_edges)
            s2_feature.setAttributes([s2_token, self.resolution,center_lat, center_lon, avg_edge_len, cell_area])                    
            sink.addFeature(s2_feature, QgsFeatureSink.FastInsert)                    

            if feedback.isCanceled():
                break
            
        feedback.pushInfo("S2 grid generation completed.")
        if context.willLoadLayerOnCompletion(dest_id):
            # lineColor = QColor('#FF0000')
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
        label.fieldName = 's2'
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