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

# from vgrid.processing_provider.Vect_Antipodal import Antipodal
# from vgrid.processing_provider.Vect_Reversed_X import Reversed_X
# from vgrid.processing_provider.Vect_Reversed_Y import Reversed_Y
# from vgrid.processing_provider.Vect_Swap_XY import Swap_XY

# from vgrid.processing_provider.Vect_Wedge import Wedge
# from vgrid.processing_provider.Vect_SpiralWedge import SpiralWedge


# from vgrid.processing_provider.Vect_SplitPolygon import SplitPolygon


# from vgrid.processing_provider.Vect_Skeleton import Skeleton
# from vgrid.processing_provider.Vect_Isolation import Isolation
# from vgrid.processing_provider.Vect_DirectionalMerge import DirectionalMerge
# from vgrid.processing_provider.Vect_Lec import Lec
# from vgrid.processing_provider.Vect_Mic import Mic
# from vgrid.processing_provider.Vect_ClosestFarthest import ClosestFarthest

# from vgrid.processing_provider.Att_FontConvert import FontConvert

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
        # self.addAlgorithm(Antipodal())

        # self.addAlgorithm(Reversed_X())
        # self.addAlgorithm(Reversed_Y())
        # self.addAlgorithm(Swap_XY())

        # self.addAlgorithm(Wedge())
        # self.addAlgorithm(SpiralWedge())

        # self.addAlgorithm(SplitPolygon())

        # self.addAlgorithm(Skeleton())
        # self.addAlgorithm(Isolation())
        # self.addAlgorithm(DirectionalMerge())
        # self.addAlgorithm(Lec())
        # self.addAlgorithm(Mic())
        # self.addAlgorithm(ClosestFarthest())  

        # self.addAlgorithm(FontConvert())
        pass

    def id(self):
        return 'vgrid'

    def name(self):
        return self.tr('vgrid Tools')

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