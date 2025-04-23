# -*- coding: utf-8 -*-

"""
/***************************************************************************
 vgrid DGGS
                                 A QGIS plugin
 based on Vgrid and following lftools project structure https://github.com/LEOXINGU/lftools
                              -------------------
        Date                 : 2024-11-20
        copyright            : (L) 2024 by Thang Quach
        email                : quachdongthang@gmail.com
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""

__author__ = 'Thang Quach'
__date__ = '2024-11-20'
__copyright__ = '(L) 2024 by Thang Quach'

# This will get replaced with a git SHA1 when you do a git archive

__revision__ = '$Format:%H$'
import os
from qgis.core import QgsProcessingProvider
from qgis.PyQt.QtGui import QIcon

from .processing_provider.conversion.dggs2qgsfeature import CellID2DGGS
from .processing_provider.conversion.qgsfeature2dggs import Vector2DGGS
from .processing_provider.conversion.raster2dggs import Raster2DGGS


from .processing_provider.binning.bin_h3 import BinH3
from .processing_provider.binning.bin_s2 import BinS2
from .processing_provider.binning.bin_rhealpix import BinrHEALPix
from .processing_provider.binning.bin_isea4t import BinISEA4T
from .processing_provider.binning.bin_qtm import BinQTM
from .processing_provider.binning.bin_polygon import BinPolygon


from .processing_provider.generator.grid_h3 import GridH3
from .processing_provider.generator.grid_s2 import GridS2
from .processing_provider.generator.grid_rhealpix import GridrHEALPix
from .processing_provider.generator.grid_isea4t import GridISEA4T

from .processing_provider.generator.grid_qtm import GridQTM

from .processing_provider.generator.grid_olc import GridOLC
from .processing_provider.generator.grid_geohash import GridGeohash
from .processing_provider.generator.grid_georef import GridGEOREF
from .processing_provider.generator.grid_mgrs import GridMGRS
from .processing_provider.generator.grid_gzd import GridGZD
from .processing_provider.generator.grid_tilecode import GridTilecode
from .processing_provider.generator.grid_quadkey import GridQuadkey
from .processing_provider.generator.grid_maidenhead import GridMaidenhead
from .processing_provider.generator.grid_gars import GridGARS


import pathlib,sys

class VgridProvider(QgsProcessingProvider):

    def __init__(self):
        """
        Default constructor.
        """
        QgsProcessingProvider.__init__(self)
     

    def unload(self):
        """
        Unloads the provider. Any tear-down steps required by the provider
        should be implemented here.
        """
        pass

    def loadAlgorithms(self):
        self.addAlgorithm(CellID2DGGS())
        self.addAlgorithm(Vector2DGGS())
        self.addAlgorithm(Raster2DGGS())
        
        self.addAlgorithm(BinH3())
        self.addAlgorithm(BinS2())
        self.addAlgorithm(BinrHEALPix())
        self.addAlgorithm(BinISEA4T())
        self.addAlgorithm(BinQTM())
        self.addAlgorithm(BinPolygon())


        self.addAlgorithm(GridH3())
        self.addAlgorithm(GridS2())
        self.addAlgorithm(GridrHEALPix())
        self.addAlgorithm(GridISEA4T())
        self.addAlgorithm(GridQTM())

        self.addAlgorithm(GridOLC())
        self.addAlgorithm(GridGeohash())
        # self.addAlgorithm(GridGEOREF())
        self.addAlgorithm(GridMGRS())
        self.addAlgorithm(GridGZD())
        self.addAlgorithm(GridTilecode())
        self.addAlgorithm(GridQuadkey())
        self.addAlgorithm(GridMaidenhead())
        self.addAlgorithm(GridGARS())


    def id(self):
        return 'vgrid'

    def name(self):
        return self.tr('DGGS Vgrid')

    def icon(self):
        return QIcon(os.path.dirname(__file__) + './images/vgrid.svg')

    def longName(self):      
        return self.name()