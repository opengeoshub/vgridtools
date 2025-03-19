# -*- coding: utf-8 -*-
"""
grid_h3.py
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

from vgrid.conversion.dggs2geojson import rhealpix_cell_to_polygon
from vgrid.utils.rhealpixdggs.dggs import RHEALPixDGGS
from ...utils.imgs import Imgs
from shapely.geometry import Polygon,box
from pyproj import Geod
from vgrid.generator.settings import geodesic_dggs_metrics
rhealpix_dggs = RHEALPixDGGS()


class GridRhealpix(QgsProcessingAlgorithm):
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
        return GridRhealpix()

    def name(self):
        return 'grid_rhealpix'

    def icon(self):
        return QIcon(os.path.join(os.path.dirname(os.path.dirname(__file__)),  '../images/grid_gzd.png'))
    
    def displayName(self):
        return self.tr('Rhealpix', 'Rhealpix')

    def group(self):
        return self.tr('DGGS Generator', 'DGGS Generator')

    def groupId(self):
        return 'grid'

    def tags(self):
        return self.tr('DGGS, grid, Rhealpix, generator').split(',')
    
    txt_en = 'Rhealpix Grid Generator'
    txt_vi = 'Rhealpix Grid Generator'
    figure = '../images/tutorial/grid_rhealpix.png'

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
                    self.tr('Resolution [0..15]'),
                    QgsProcessingParameterNumber.Integer,
                    defaultValue=1,
                    minValue= 0,
                    maxValue= 15,
                    optional=False)
        self.addParameter(param)


        param = QgsProcessingParameterFeatureSink(
                self.OUTPUT,
                'Rhealpix')
        self.addParameter(param)
                    
    def prepareAlgorithm(self, parameters, context, feedback):
        self.resolution = self.parameterAsInt(parameters, self.RESOLUTION, context)  
        self.grid_extent = self.parameterAsExtent(parameters, self.EXTENT, context)
        if self.resolution > 5 and (self.grid_extent is None or self.grid_extent.isEmpty()):
            feedback.reportError('For performance reason, when resolution is greater than 4, the grid extent must be set.')
            return False
        
        return True
    
    def processAlgorithm(self, parameters, context, feedback):        
        fields = QgsFields()
        fields.append(QgsField("rhealpix", QVariant.String))   # S2 token
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
              
        if extent_bbox:
            minx, miny = extent_bbox[0]
            maxx, maxy = extent_bbox[1]
            # Create a Shapely box
            bbox_polygon = box(minx, miny, maxx, maxy)
            bbox_center_lon = bbox_polygon.centroid.x
            bbox_center_lat = bbox_polygon.centroid.y
            seed_point = (bbox_center_lon, bbox_center_lat)

            seed_cell = rhealpix_dggs.cell_from_point(self.resolution, seed_point, plane=False)
            seed_cell_id = str(seed_cell)  # Unique identifier for the current cell
            seed_cell_polygon = rhealpix_cell_to_polygon(seed_cell)

            if seed_cell_polygon.contains(bbox_polygon):             
                num_edges = 4
                if seed_cell.ellipsoidal_shape() == 'dart':
                    num_edges = 3
                
                seed_cell_geometry = QgsGeometry.fromWkt(seed_cell_polygon.wkt)
            
                rhealpix_feature = QgsFeature()
                rhealpix_feature.setGeometry(seed_cell_geometry) 
                
                center_lat, center_lon, avg_edge_len, cell_area = geodesic_dggs_metrics(cell_polygon, num_edges)
                rhealpix_feature.setAttributes([seed_cell_id, self.resolution,center_lat, center_lon, avg_edge_len, cell_area])                    
                sink.addFeature(rhealpix_feature, QgsFeatureSink.FastInsert)                    

            else:
                # Initialize sets and queue
                covered_cells = set()  # Cells that have been processed (by their unique ID)
                queue = [seed_cell]  # Queue for BFS exploration
                while queue:
                    current_cell = queue.pop()
                    current_cell_id = str(current_cell)  # Unique identifier for the current cell

                    if current_cell_id in covered_cells:
                        continue
                    # Add current cell to the covered set
                    covered_cells.add(current_cell_id)
                    # Convert current cell to polygon
                    cell_polygon = rhealpix_cell_to_polygon(current_cell)
                    # Skip cells that do not intersect the bounding box
                    if not cell_polygon.intersects(bbox_polygon):
                        continue
                    # Get neighbors and add to queue
                    neighbors = current_cell.neighbors(plane=False)
                    for _, neighbor in neighbors.items():
                        neighbor_id = str(neighbor)  # Unique identifier for the neighbor
                        if neighbor_id not in covered_cells:
                            queue.append(neighbor)
                    if feedback.isCanceled():
                        break

                for idx, cover_cell in enumerate(covered_cells):
                    progress = int((idx / len(covered_cells)) * 100)
                    feedback.setProgress(progress)
                    
                    rhealpix_uids = (cover_cell[0],) + tuple(map(int, cover_cell[1:]))
                    cell = rhealpix_dggs.cell(rhealpix_uids)    
                    cell_polygon = rhealpix_cell_to_polygon(cell)          
                    if cell_polygon.intersects(bbox_polygon):
                        cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)            
                        rhealpix_feature = QgsFeature()
                        rhealpix_feature.setGeometry(cell_geometry) 
                        
                        cell_id = str(cover_cell)      
                        num_edges = 4
                        if seed_cell.ellipsoidal_shape() == 'dart':
                            num_edges = 3
                        
                        center_lat, center_lon, avg_edge_len, cell_area = geodesic_dggs_metrics(cell_polygon, num_edges)
                        rhealpix_feature.setAttributes([cell_id, self.resolution,center_lat, center_lon, avg_edge_len, cell_area])                    
                        sink.addFeature(rhealpix_feature, QgsFeatureSink.FastInsert) 
                        
                    if feedback.isCanceled():
                        break
       
        else:
            total_cells = rhealpix_dggs.num_cells(self.resolution)
            feedback.pushInfo(f"Total cells to be generated: {total_cells}.")
            rhealpix_grid = rhealpix_dggs.grid(self.resolution)
            for idx, cell in enumerate(rhealpix_grid):
                progress = int((idx / total_cells) * 100)
                feedback.setProgress(progress)            
                cell_polygon = rhealpix_cell_to_polygon(cell)
                cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)
            
                rhealpix_feature = QgsFeature()
                rhealpix_feature.setGeometry(cell_geometry)                
                
                rhealpix_id = str(cell)
                num_edges = 4
                if cell.ellipsoidal_shape() == 'dart':
                    num_edges = 3
                center_lat, center_lon, avg_edge_len, cell_area = geodesic_dggs_metrics(cell_polygon, num_edges)
                rhealpix_feature.setAttributes([rhealpix_id, self.resolution,center_lat, center_lon, avg_edge_len, cell_area])                    
                sink.addFeature(rhealpix_feature, QgsFeatureSink.FastInsert)                    
                if feedback.isCanceled():
                    break
                
        feedback.pushInfo("Rhealpix grid generation completed.")
        
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
        label.fieldName = 'rhealpix'
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