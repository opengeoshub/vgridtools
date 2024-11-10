# -*- coding: utf-8 -*-
"""
codes2cells.py
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
                       QgsProcessingAlgorithm,
                       QgsProcessingParameterExtent,
                       QgsProcessingParameterVectorDestination)
from qgis.core import QgsApplication
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtCore import QCoreApplication,QVariant
import os
from ..vgridlibrary.imgs import Imgs

class GridGeohash(QgsProcessingAlgorithm):
    EXTENT = 'EXTENT'
    PRECISION = 'PRECISION'
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
        return GridGeohash()

    def name(self):
        return 'grid_geohash'

    def icon(self):
        return QIcon(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'images/grid_gzd.png'))
    
    def displayName(self):
        return self.tr('Geohash Grid Generator', 'Geohash Grid Generator')

    def group(self):
        return self.tr('Grid', 'Grid')

    def groupId(self):
        return 'grid'

    def tags(self):
        return self.tr('Geohash, grid').split(',')
    
    txt_en = 'Geohash Grid Generator'
    txt_vi = 'Geohash Grid Generator'
    figure = 'images/tutorial/codes2cells.png'

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
        self.addParameter(QgsProcessingParameterExtent(self.EXTENT,
                                                       self.tr('Grid extent')))

        # options_param = QgsProcessingParameterString(self.OPTIONS,
        #                                              self.tr('Additional creation options'),
        #                                              defaultValue='',
        #                                              optional=True)
        # options_param.setFlags(options_param.flags() | QgsProcessingParameterDefinition.Flag.FlagAdvanced)
        # self.addParameter(options_param)

        self.addParameter(QgsProcessingParameterVectorDestination(self.OUTPUT,
                                                                  self.tr('Output Geohash')))