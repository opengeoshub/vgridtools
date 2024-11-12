# -*- coding: utf-8 -*-

"""
/***************************************************************************
 vgrid
                                 A QGIS plugin
 GeoPorocessing Tools based on lftools https://github.com/LEOXINGU/lftools
                              -------------------
        Date                : 2024-11-20
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

from .processing_provider.codes2cells import Codes2Cells
from .processing_provider.grid_geohash import GridGeohash
from .processing_provider.grid_georef import GridGeoref
from .processing_provider.grid_olc import GridOLC
from .processing_provider.grid_maidenhead import GridMaidenhead
from .processing_provider.grid_gars import GridGARS
from .processing_provider.grid_vcode import GridVcode
from .processing_provider.grid_s2 import GridS2
from .processing_provider.grid_mgrs import GridMGRS


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
        self.addAlgorithm(Codes2Cells())
        # self.addAlgorithm(GridOLC())
        self.addAlgorithm(GridGeohash())
        self.addAlgorithm(GridMaidenhead())
        self.addAlgorithm(GridGARS())
        self.addAlgorithm(GridVcode())
        self.addAlgorithm(GridS2())
        self.addAlgorithm(GridMGRS())


    def id(self):
        return 'vgrid'

    def name(self):
        return self.tr('Vgrid Tools')

    def icon(self):
        return QIcon(os.path.dirname(__file__) + '/images/vgrid.svg')

    def longName(self):
        """
        Returns the a longer version of the provider name, which can include
        extra details such as version numbers. E.g. "Lastools LIDAR tools
        (version 2.2.1)". This string should be localised. The default
        implementation returns the same string as name().
        """
        return self.name()