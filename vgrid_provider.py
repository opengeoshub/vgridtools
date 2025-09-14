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
"""

__author__ = "Thang Quach"
__date__ = "2024-11-20"
__copyright__ = "(L) 2024 by Thang Quach"

# This will get replaced with a git SHA1 when you do a git archive

__revision__ = "$Format:%H$"
import os
from qgis.core import QgsProcessingProvider
from qgis.PyQt.QtGui import QIcon

from .processing_provider.conversion.dggs2qgsfeature import CellID2DGGS
from .processing_provider.conversion.qgsfeature2dggs import Vector2DGGS
from .processing_provider.conversion.raster2dggs import Raster2DGGS
from .processing_provider.conversion.dggsexpand import DGGSExpand
from .processing_provider.conversion.dggscompact import DGGSCompact

from .processing_provider.resampling.dggsresample import DGGSResample

from .processing_provider.binning.h3_bin import H3Bin
from .processing_provider.binning.s2_bin import S2Bin
from .processing_provider.binning.a5_bin import A5Bin
from .processing_provider.binning.rhealpix_bin import rHEALPixBin
from .processing_provider.binning.isea4t_bin import ISEA4TBin
from .processing_provider.binning.dggal_bin import DGGALBin

from .processing_provider.binning.qtm_bin import QTMBin

from .processing_provider.binning.olc_bin import OLCBin
from .processing_provider.binning.geohash_bin import GeohashBin
from .processing_provider.binning.tilecode_bin import TilecodeBin
from .processing_provider.binning.quadkey_bin import QuadkeyBin

from .processing_provider.binning.polygon_bin import PolygonBin


from .processing_provider.generator.h3_grid import H3Grid
from .processing_provider.generator.s2_grid import S2Grid
from .processing_provider.generator.a5_grid import A5Grid
from .processing_provider.generator.rhealpix_grid import rHEALPixGrid
from .processing_provider.generator.isea4t_grid import ISEA4TGrid

from .processing_provider.generator.qtm_grid import QTMGrid

from .processing_provider.generator.olc_grid import OLCGrid
from .processing_provider.generator.geohash_grid import GeohashGrid
from .processing_provider.generator.georef_grid import GEOREFGrid
from .processing_provider.generator.dggal_grid import DGGALGrid
from .processing_provider.generator.mgrs_grid import MGRSGrid
from .processing_provider.generator.gzd_grid import GZDGrid
from .processing_provider.generator.tilecode_grid import TilecodeGrid
from .processing_provider.generator.quadkey_grid import QuadkeyGrid
from .processing_provider.generator.maidenhead_grid import MaidenheadGrid
from .processing_provider.generator.gars_grid import GARSGrid


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
        # Conversion algorithms
        self.addAlgorithm(CellID2DGGS())
        self.addAlgorithm(Vector2DGGS())
        self.addAlgorithm(DGGSCompact())
        self.addAlgorithm(DGGSExpand())
        self.addAlgorithm(Raster2DGGS())
        
        # Resampling algorithms
        self.addAlgorithm(DGGSResample())
        
        # Binning algorithms
        self.addAlgorithm(H3Bin())
        self.addAlgorithm(S2Bin())
        self.addAlgorithm(A5Bin())
        self.addAlgorithm(rHEALPixBin())
        self.addAlgorithm(ISEA4TBin())
        self.addAlgorithm(DGGALBin())

        self.addAlgorithm(QTMBin())

        self.addAlgorithm(OLCBin())
        self.addAlgorithm(GeohashBin())
        self.addAlgorithm(TilecodeBin())
        self.addAlgorithm(QuadkeyBin())

        self.addAlgorithm(PolygonBin())

        # Generator algorithms
        self.addAlgorithm(H3Grid())
        self.addAlgorithm(S2Grid())
        self.addAlgorithm(A5Grid())
        self.addAlgorithm(rHEALPixGrid())
        self.addAlgorithm(ISEA4TGrid())
        self.addAlgorithm(QTMGrid())

        self.addAlgorithm(OLCGrid())
        self.addAlgorithm(GeohashGrid())
        # self.addAlgorithm(GEOREFGrid())
        self.addAlgorithm(DGGALGrid())
        ################################
        self.addAlgorithm(MGRSGrid())
        self.addAlgorithm(GZDGrid())
        ################################
        self.addAlgorithm(TilecodeGrid())
        self.addAlgorithm(QuadkeyGrid())
        self.addAlgorithm(MaidenheadGrid())
        self.addAlgorithm(GARSGrid())        

    def id(self):
        return "vgrid"

    def name(self):
        return self.tr("DGGS Vgrid")

    def icon(self):
        return QIcon(os.path.dirname(__file__) + "./images/vgrid.svg")

    def longName(self):
        return self.name()
