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
from .processing_provider.binning.digipin_bin import DigipinBin


from .processing_provider.generator.h3gen import H3Gen
from .processing_provider.generator.s2gen import S2Gen
from .processing_provider.generator.a5gen import A5Gen
from .processing_provider.generator.rhealpixgen import rHEALPixGen
from .processing_provider.generator.isea4tgen import ISEA4TGen
from .processing_provider.generator.dggalgen import DGGALGen

from .processing_provider.generator.qtmgen import QTMGen

from .processing_provider.generator.olcgen import OLCGen
from .processing_provider.generator.geohashgen import GeohashGen
from .processing_provider.generator.mgrsgen import MGRSGen
from .processing_provider.generator.gzdgen import GZDGen
from .processing_provider.generator.tilecodegen import TilecodeGen
from .processing_provider.generator.quadkeygen import QuadkeyGen
from .processing_provider.generator.maidenheadgen import MaidenheadGen
from .processing_provider.generator.garsgen import GARSGen
from .processing_provider.generator.georefgen import GEOREFGen
from .processing_provider.generator.digipingen import DIGIPINGen

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
        self.addAlgorithm(DigipinBin())

        # Generator algorithms
        self.addAlgorithm(H3Gen())
        self.addAlgorithm(S2Gen())
        self.addAlgorithm(A5Gen())
        self.addAlgorithm(rHEALPixGen())
        self.addAlgorithm(ISEA4TGen())
        self.addAlgorithm(QTMGen())

        self.addAlgorithm(OLCGen())
        self.addAlgorithm(GeohashGen())
        self.addAlgorithm(GEOREFGen())
        self.addAlgorithm(DGGALGen())
        ################################
        self.addAlgorithm(MGRSGen())
        self.addAlgorithm(GZDGen())
        ################################
        self.addAlgorithm(TilecodeGen())
        self.addAlgorithm(QuadkeyGen())
        self.addAlgorithm(MaidenheadGen())
        self.addAlgorithm(GARSGen())
        self.addAlgorithm(DIGIPINGen())
    def id(self):
        return "vgrid"

    def name(self):
        return self.tr("DGGS Vgrid")

    def icon(self):
        return QIcon(os.path.dirname(__file__) + "./images/vgrid.svg")

    def longName(self):
        return self.name()
