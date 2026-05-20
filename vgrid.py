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

import webbrowser
import os
from qgis.core import QgsApplication, QgsExpression
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtCore import Qt, QTimer, QCoreApplication
import processing
from qgis.PyQt.QtWidgets import (
    QAction,
    QMenu,
    QWidgetAction,
    QCheckBox,
    QMessageBox,
)
from qgis.core import (
    QgsCoordinateTransform,
    QgsRectangle,
    QgsPoint,
    QgsPointXY,
    QgsGeometry,
    QgsWkbTypes,
    QgsProject,
)
from qgis.gui import QgsRubberBand

from .vgrid_provider import VgridProvider
from .expressions import *
from .settings import SettingsWidget, settings
from .latlon2dggs import LatLon2DGGSWidget
from .dggsclient import DGGSClientWidget
from .dggsjson2geojson import DGGSJSON2GeoJSONWidget
from .utils import tr
from .utils.dggs_viz_menu import setup_dggs_visualization_menus
from .dggsgrid.h3grid import H3Grid
from .dggsgrid.a5grid import A5Grid
from .dggsgrid.s2grid import S2Grid
from .dggsgrid.rhealpixgrid import RhealpixGrid
from .dggsgrid.isea4tgrid import ISEA4TGrid
from .dggsgrid.isea3hgrid import ISEA3HGrid
from .dggsgrid.easegrid import EASEGrid
from .dggsgrid.dggal_gnosisgrid import DGGALGnosisGrid
from .dggsgrid.dggal_isea3hgrid import DGGALISEA3HGrid
from .dggsgrid.dggal_isea4rgrid import DGGALISEA4RGrid
from .dggsgrid.dggal_isea7hgrid import DGGALISEA7HGrid
from .dggsgrid.dggal_isea7h_z7grid import DGGALISEA7H_Z7Grid
from .dggsgrid.dggal_isea9rgrid import DGGALISEA9RGrid
from .dggsgrid.dggal_ivea3hgrid import DGGALIVEA3HGrid
from .dggsgrid.dggal_ivea4rgrid import DGGALIVEA4RGrid
from .dggsgrid.dggal_ivea7hgrid import DGGALIVEA7HGrid
from .dggsgrid.dggal_ivea7h_z7grid import DGGALIVEA7H_Z7Grid
from .dggsgrid.dggal_ivea9rgrid import DGGALIVEA9RGrid
from .dggsgrid.dggal_rtea3hgrid import DGGALRTEA3HGrid
from .dggsgrid.dggal_rtea4rgrid import DGGALRTEA4RGrid
from .dggsgrid.dggal_rtea7hgrid import DGGALRTEA7HGrid
from .dggsgrid.dggal_rtea7h_z7grid import DGGALRTEA7H_Z7Grid
from .dggsgrid.dggal_rtea9rgrid import DGGALRTEA9RGrid
from .dggsgrid.dggal_healpixgrid import DGGALHEALPixGrid
from .dggsgrid.dggal_rhealpixgrid import DGGALRHEALPixGrid

# from .dggsgrid.qtmgrid import QTMGrid
from .dggsgrid.olcgrid import OLCGrid
from .dggsgrid.geohasgrid import GeohashGrid
from .dggsgrid.georefgrid import GEOREFGrid
from .dggsgrid.tilecodegrid import TilecodeGrid
from .dggsgrid.maidenheadgrid import MaidenheadGrid
from .dggsgrid.garsgrid import GARSGrid
from .dggsgrid.digipingrid import DIGIPINGrid
from math import log2

exprs = (
    latlon2h3,
    latlon2s2,
    latlon2a5,
    latlon2rhealpix,
    latlon2isea4t,
    latlon2isea3h,
    latlon2dggal,
    latlon2qtm,
    latlon2olc,
    latlon2geohash,
    latlon2georef,
    latlon2mgrs,
    latlon2tilecode,
    latlon2quadkey,
    latlon2maidenhead,
    latlon2gars,
    latlon2digipin  
)


class VgridTools(object):
    latlon2DGGSDialog = None
    dggsClientDialog = None
    dggsJson2GeoJsonDialog = None

    def __init__(
        self,
        iface,
    ):
        self.provider = None
        self.plugin_dir = os.path.dirname(__file__)
        self.iface = iface
        self.canvas = iface.mapCanvas()
        self.provider = VgridProvider()

        self.h3grid = H3Grid(self, self.canvas, self.iface)
        self.a5grid = A5Grid(self, self.canvas, self.iface)
        self.s2grid = S2Grid(self, self.canvas, self.iface)
        self.rhealpixgrid = RhealpixGrid(self, self.canvas, self.iface)
        self.isea4tgrid = ISEA4TGrid(self, self.canvas, self.iface)
        self.isea3hgrid = ISEA3HGrid(self, self.canvas, self.iface)
        self.easegrid = EASEGrid(self, self.canvas, self.iface)
        self.dggal_gnosisgrid = DGGALGnosisGrid(self, self.canvas, self.iface)
        self.dggal_isea3hgrid = DGGALISEA3HGrid(self, self.canvas, self.iface)
        self.dggal_isea4rgrid = DGGALISEA4RGrid(self, self.canvas, self.iface)
        self.dggal_isea7hgrid = DGGALISEA7HGrid(self, self.canvas, self.iface)
        self.dggal_isea7h_z7grid = DGGALISEA7H_Z7Grid(self, self.canvas, self.iface)
        self.dggal_isea9rgrid = DGGALISEA9RGrid(self, self.canvas, self.iface)
        self.dggal_ivea3hgrid = DGGALIVEA3HGrid(self, self.canvas, self.iface)
        self.dggal_ivea4rgrid = DGGALIVEA4RGrid(self, self.canvas, self.iface)
        self.dggal_ivea7hgrid = DGGALIVEA7HGrid(self, self.canvas, self.iface)
        self.dggal_ivea7h_z7grid = DGGALIVEA7H_Z7Grid(self, self.canvas, self.iface)
        self.dggal_ivea9rgrid = DGGALIVEA9RGrid(self, self.canvas, self.iface)
        self.dggal_rtea3hgrid = DGGALRTEA3HGrid(self, self.canvas, self.iface)
        self.dggal_rtea4rgrid = DGGALRTEA4RGrid(self, self.canvas, self.iface)
        self.dggal_rtea7hgrid = DGGALRTEA7HGrid(self, self.canvas, self.iface)
        self.dggal_rtea7h_z7grid = DGGALRTEA7H_Z7Grid(self, self.canvas, self.iface)
        self.dggal_rtea9rgrid = DGGALRTEA9RGrid(self, self.canvas, self.iface)
        self.dggal_rhealpixgrid = DGGALRHEALPixGrid(self, self.canvas, self.iface)
        self.dggal_healpixgrid = DGGALHEALPixGrid(self, self.canvas, self.iface)
        # self.qtmgrid = QTMGrid(self, self.canvas, self.iface)
        self.olcgrid = OLCGrid(self, self.canvas, self.iface)
        self.geohashgrid = GeohashGrid(self, self.canvas, self.iface)
        self.georefgrid = GEOREFGrid(self, self.canvas, self.iface)
        self.tilecodegrid = TilecodeGrid(self, self.canvas, self.iface)
        self.maidenheadgrid = MaidenheadGrid(self, self.canvas, self.iface)
        self.garsgrid = GARSGrid(self, self.canvas, self.iface)
        self.digipingrid = DIGIPINGrid(self, self.canvas, self.iface)

        self.Vgrid_menu = None
        self.toolbar = self.iface.addToolBar(tr("Vgrid Toolbar"))
        self.toolbar.setObjectName("VgridToolbar")
        self.toolbar.setToolTip(tr("Vgrid Toolbar"))

        self.crossRb = QgsRubberBand(self.canvas, QgsWkbTypes.LineGeometry)
        self.crossRb.setColor(Qt.GlobalColor.red)

        self.iface.mapCanvas().scaleChanged.connect(self.displayZoomLevel)

    def displayZoomLevel(self):
        """Display the current zoom level in the status bar"""

        scale = self.iface.mapCanvas().scale()
        # Convert the scale to the equivalent zoom level
        # (This is accurate enough for at least 2 decimal places)
        zoom = 29.1402 - log2(scale)
        if settings.zoomLevel:
            self.iface.mainWindow().statusBar().showMessage(
                "Zoom Level: {:.2f}".format(zoom)
            )

    def initProcessing(self):
        """Init Processing provider for QGIS >= 3.8."""
        self.provider = VgridProvider()
        QgsApplication.processingRegistry().addProvider(self.provider)

    def initGui(self):
        self.initProcessing()
        for expr in exprs:
            if not QgsExpression.isFunctionName(expr.name()):
                QgsExpression.registerFunction(expr)

        # Create Vgrid menu
        self.Vgrid_menu = QMenu(QCoreApplication.translate("Vgrid", "Vgrid"))
        self.iface.mainWindow().menuBar().insertMenu(
            self.iface.firstRightStandardMenu().menuAction(), self.Vgrid_menu
        )

        setup_dggs_visualization_menus(self)

        # Create DGGS Client action
        dggs_client_icon = QIcon(
            os.path.dirname(__file__) + "/images/dggsclient/ogc.png"
        )
        self.dggsClientAction = QAction(
            dggs_client_icon, tr("DGGS Client"), self.iface.mainWindow()
        )
        self.dggsClientAction.setObjectName("dggsClient")
        self.dggsClientAction.setToolTip(tr("DGGS Client"))
        self.dggsClientAction.triggered.connect(self.showDGGSClient)
        self.Vgrid_menu.addAction(self.dggsClientAction)

        # Create Lat Lon to DGGS action
        latlon2dggs_icon = QIcon(os.path.dirname(__file__) + "/images/vgrid.svg")
        self.latlon2dggsAction = QAction(
            latlon2dggs_icon, tr("Lat Lon to DGGS"), self.iface.mainWindow()
        )
        self.latlon2dggsAction.setObjectName("latlon2dggs")
        self.latlon2dggsAction.setToolTip(tr("Convert coordinates to DGGS"))
        self.latlon2dggsAction.triggered.connect(self.latlon2DGGS)
        self.Vgrid_menu.addAction(self.latlon2dggsAction)

        # Create Conversion submenu
        self.conversion_menu = QMenu("Conversion")
        conversion_icon = QIcon(
            os.path.dirname(__file__) + "/images/conversion/conversion.svg"
        )
        self.Vgrid_add_submenu2(self.conversion_menu, conversion_icon)

        # Create Generator submenu
        self.generator_menu = QMenu("Generator")
        generator_icon = QIcon(
            os.path.dirname(__file__) + "/images/generator/generator.svg"
        )
        self.Vgrid_add_submenu2(self.generator_menu, generator_icon)

        # Create Binning submenu
        self.binning_menu = QMenu("Binning")
        binning_icon = QIcon(os.path.dirname(__file__) + "/images/binning/binning.svg")
        self.Vgrid_add_submenu2(self.binning_menu, binning_icon)

        # Create Utils submenu
        self.utils_menu = QMenu("Utils")
        utils_icon = QIcon(os.path.dirname(__file__) + "/images/utils/utils.png")
        self.Vgrid_add_submenu2(self.utils_menu, utils_icon)

        # Add Binning actions
        # H3 Bin
        icon = QIcon(os.path.dirname(__file__) + "/images/generator/grid_h3.svg")
        self.h3BinAction = QAction(icon, tr("H3 Bin"), self.iface.mainWindow())
        self.h3BinAction.setObjectName("h3Bin")
        self.h3BinAction.setToolTip(tr("H3 Binning"))
        self.h3BinAction.triggered.connect(self.runH3Bin)
        self.binning_menu.addAction(self.h3BinAction)

        # S2 Bin
        icon = QIcon(os.path.dirname(__file__) + "/images/generator/grid_s2.svg")
        self.s2BinAction = QAction(icon, tr("S2 Bin"), self.iface.mainWindow())
        self.s2BinAction.setObjectName("s2Bin")
        self.s2BinAction.setToolTip(tr("S2 Binning"))
        self.s2BinAction.triggered.connect(self.runS2Bin)
        self.binning_menu.addAction(self.s2BinAction)

        # A5 Bin
        icon = QIcon(os.path.dirname(__file__) + "/images/generator/grid_a5.svg")
        self.a5BinAction = QAction(icon, tr("A5 Bin"), self.iface.mainWindow())
        self.a5BinAction.setObjectName("a5Bin")
        self.a5BinAction.setToolTip(tr("A5 Binning"))
        self.a5BinAction.triggered.connect(self.runA5Bin)
        self.binning_menu.addAction(self.a5BinAction)

        # rHEALPix Bin
        icon = QIcon(os.path.dirname(__file__) + "/images/generator/grid_rhealpix.svg")
        self.rhealpixBinAction = QAction(
            icon, tr("rHEALPix Bin"), self.iface.mainWindow()
        )
        self.rhealpixBinAction.setObjectName("rhealpixBin")
        self.rhealpixBinAction.setToolTip(tr("rHEALPix Binning"))
        self.rhealpixBinAction.triggered.connect(self.runRhealpixBin)
        self.binning_menu.addAction(self.rhealpixBinAction)

        # ISEA4T Bin
        icon = QIcon(os.path.dirname(__file__) + "/images/generator/grid_triangle.svg")
        self.isea4tBinAction = QAction(icon, tr("ISEA4T Bin"), self.iface.mainWindow())
        self.isea4tBinAction.setObjectName("isea4tBin")
        self.isea4tBinAction.setToolTip(tr("ISEA4T Binning"))
        self.isea4tBinAction.triggered.connect(self.runISEA4TBin)
        self.binning_menu.addAction(self.isea4tBinAction)

        # DGGAL Bin
        icon = QIcon(os.path.dirname(__file__) + "/images/generator/grid_dggal.svg")
        self.dggalBinAction = QAction(icon, tr("DGGAL Bin"), self.iface.mainWindow())
        self.dggalBinAction.setObjectName("dggalBin")
        self.dggalBinAction.setToolTip(tr("DGGAL Binning"))
        self.dggalBinAction.triggered.connect(self.runDGGALBin)
        self.binning_menu.addAction(self.dggalBinAction)

        # DGGRID Bin
        # icon = QIcon(os.path.dirname(__file__) + "/images/generator/grid_dggrid.svg")
        # self.dggridBinAction = QAction(icon, tr("DGGRID Bin"), self.iface.mainWindow())
        # self.dggridBinAction.setObjectName("dggridBin")
        # self.dggridBinAction.setToolTip(tr("DGGRID Binning"))
        # self.dggridBinAction.triggered.connect(self.runDGGRIDBin)
        # self.binning_menu.addAction(self.dggridBinAction)

        # OLC Bin
        icon = QIcon(os.path.dirname(__file__) + "/images/generator/grid_olc.svg")
        self.olcBinAction = QAction(icon, tr("OLC Bin"), self.iface.mainWindow())
        self.olcBinAction.setObjectName("olcBin")
        self.olcBinAction.setToolTip(tr("OLC Binning"))
        self.olcBinAction.triggered.connect(self.runOLCBin)
        self.binning_menu.addAction(self.olcBinAction)

        # Geohash Bin
        icon = QIcon(os.path.dirname(__file__) + "/images/generator/grid_quad.svg")
        self.geohashBinAction = QAction(
            icon, tr("Geohash Bin"), self.iface.mainWindow()
        )
        self.geohashBinAction.setObjectName("geohashBin")
        self.geohashBinAction.setToolTip(tr("Geohash Binning"))
        self.geohashBinAction.triggered.connect(self.runGeohashBin)
        self.binning_menu.addAction(self.geohashBinAction)

        # Tilecode Bin
        icon = QIcon(os.path.dirname(__file__) + "/images/generator/grid_quad.svg")
        self.tilecodeBinAction = QAction(
            icon, tr("Tilecode Bin"), self.iface.mainWindow()
        )
        self.tilecodeBinAction.setObjectName("tilecodeBin")
        self.tilecodeBinAction.setToolTip(tr("Tilecode Binning"))
        self.tilecodeBinAction.triggered.connect(self.runTilecodeBin)
        self.binning_menu.addAction(self.tilecodeBinAction)

        # Quadkey Bin
        icon = QIcon(os.path.dirname(__file__) + "/images/generator/grid_quad.svg")
        self.quadkeyBinAction = QAction(
            icon, tr("Quadkey Bin"), self.iface.mainWindow()
        )
        self.quadkeyBinAction.setObjectName("quadkeyBin")
        self.quadkeyBinAction.setToolTip(tr("Quadkey Binning"))
        self.quadkeyBinAction.triggered.connect(self.runQuadkeyBin)
        self.binning_menu.addAction(self.quadkeyBinAction)

        # Add Conversion actions
        # Cell ID to DGGS
        icon = QIcon(os.path.dirname(__file__) + "/images/conversion/cellid2dggs.svg")
        self.cellId2DGGSAction = QAction(
            icon, tr("Cell ID to DGGS"), self.iface.mainWindow()
        )
        self.cellId2DGGSAction.setObjectName("cellId2DGGS")
        self.cellId2DGGSAction.setToolTip(tr("Cell ID to DGGS"))
        self.cellId2DGGSAction.triggered.connect(self.runCellId2DGGS)
        self.conversion_menu.addAction(self.cellId2DGGSAction)

        # Vector to DGGS
        icon = QIcon(os.path.dirname(__file__) + "/images/conversion/vector2dggs.png")
        self.vector2DGGSAction = QAction(
            icon, tr("Vector to DGGS"), self.iface.mainWindow()
        )
        self.vector2DGGSAction.setObjectName("vector2DGGS")
        self.vector2DGGSAction.setToolTip(tr("Vector to DGGS"))
        self.vector2DGGSAction.triggered.connect(self.runVector2DGGS)
        self.conversion_menu.addAction(self.vector2DGGSAction)

        # DGGS Compact
        icon = QIcon(os.path.dirname(__file__) + "/images/conversion/dggscompact.png")
        self.dggsCompactAction = QAction(
            icon, tr("DGGS Compact"), self.iface.mainWindow()
        )
        self.dggsCompactAction.setObjectName("dggsCompact")
        self.dggsCompactAction.setToolTip(tr("DGGS Compact"))
        self.dggsCompactAction.triggered.connect(self.runDGGSCompact)
        self.conversion_menu.addAction(self.dggsCompactAction)

        # DGGS Expand
        icon = QIcon(os.path.dirname(__file__) + "/images/conversion/dggsexpand.png")
        self.dggsExpandAction = QAction(
            icon, tr("DGGS Expand"), self.iface.mainWindow()
        )
        self.dggsExpandAction.setObjectName("dggsExpand")
        self.dggsExpandAction.setToolTip(tr("DGGS Expand"))
        self.dggsExpandAction.triggered.connect(self.runDGGSExpand)
        self.conversion_menu.addAction(self.dggsExpandAction)

        # DGGS Resample
        icon = QIcon(
            os.path.dirname(__file__) + "/images/conversion/dggsresample.svg"
        )
        self.dggsResampleAction = QAction(
            icon, tr("DGGS Resample"), self.iface.mainWindow()
        )
        self.dggsResampleAction.setObjectName("dggsResample")
        self.dggsResampleAction.setToolTip(tr("DGGS Resample"))
        self.dggsResampleAction.triggered.connect(self.runDGGSResample)
        self.conversion_menu.addAction(self.dggsResampleAction)

        # Raster to DGGS
        icon = QIcon(os.path.dirname(__file__) + "/images/conversion/raster2dggs.png")
        self.raster2DGGSAction = QAction(
            icon, tr("Raster to DGGS"), self.iface.mainWindow()
        )
        self.raster2DGGSAction.setObjectName("raster2DGGS")
        self.raster2DGGSAction.setToolTip(tr("Raster to DGGS"))
        self.raster2DGGSAction.triggered.connect(self.runRaster2DGGS)
        self.conversion_menu.addAction(self.raster2DGGSAction)

        # Add Utils actions
        # Split at Antimeridian action
        icon = QIcon(os.path.dirname(__file__) + "/images/utils/antimeridian.svg")
        self.splitAntimeridianAction = QAction(
            icon, tr("Split at Antimeridian"), self.iface.mainWindow()
        )
        self.splitAntimeridianAction.setObjectName("splitAntimeridian")
        self.splitAntimeridianAction.setToolTip(tr("Split at Antimeridian"))
        self.splitAntimeridianAction.triggered.connect(self.runSplitAtAntimeridian)
        self.utils_menu.addAction(self.splitAntimeridianAction)
        
        # Shift at Antimeridian action
        icon = QIcon(os.path.dirname(__file__) + "/images/utils/shift_antimeridian.png")
        self.shiftAntimeridianAction = QAction(
            icon, tr("Shift at Antimeridian"), self.iface.mainWindow()
        )
        self.shiftAntimeridianAction.setObjectName("shiftAntimeridian")
        self.shiftAntimeridianAction.setToolTip(tr("Shift at Antimeridian"))
        self.shiftAntimeridianAction.triggered.connect(self.runShiftAtAntimeridian)
        self.utils_menu.addAction(self.shiftAntimeridianAction)
        
        # DGGS-JSON to GeoJSON action
        dggs_json_icon = QIcon(os.path.dirname(__file__) + "/images/conversion/conversion.svg")
        self.dggsJson2GeoJsonAction = QAction(
            dggs_json_icon, tr("DGGS-JSON to GeoJSON"), self.iface.mainWindow()
        )
        self.dggsJson2GeoJsonAction.setObjectName("dggsJson2GeoJson")
        self.dggsJson2GeoJsonAction.setToolTip(tr("Convert DGGS-JSON to GeoJSON"))
        self.dggsJson2GeoJsonAction.triggered.connect(self.showDGGSJSON2GeoJSON)
        self.utils_menu.addAction(self.dggsJson2GeoJsonAction)

        dggrid_utils_icon = QIcon(
            os.path.dirname(__file__) + "/images/generator/grid_dggrid.svg"
        )
        self.createDGGRIDInstanceAction = QAction(
            dggrid_utils_icon, tr("Create DGGRID Instance"), self.iface.mainWindow()
        )
        self.createDGGRIDInstanceAction.setObjectName("createDGGRIDInstance")
        self.createDGGRIDInstanceAction.setToolTip(
            tr("Initialize the shared DGGRID instance (Generator and DGGRID Viz)")
        )
        self.createDGGRIDInstanceAction.triggered.connect(self.createDGGRIDInstance)
        self.utils_menu.addAction(self.createDGGRIDInstanceAction)

        self.clearDGGRIDCachesAction = QAction(
            dggrid_utils_icon, tr("Clear DGGRID Caches"), self.iface.mainWindow()
        )
        self.clearDGGRIDCachesAction.setObjectName("clearDGGRIDCaches")
        self.clearDGGRIDCachesAction.setToolTip(
            tr("Delete temp_* and metafile_* files in the dggrid folder")
        )
        self.clearDGGRIDCachesAction.triggered.connect(self.clearDGGRIDCaches)
        self.utils_menu.addAction(self.clearDGGRIDCachesAction)

        # Add Generator actions
        # H3 Generator
        icon = QIcon(os.path.dirname(__file__) + "/images/generator/grid_h3.svg")
        self.h3GenAction = QAction(icon, tr("H3"), self.iface.mainWindow())
        self.h3GenAction.setObjectName("h3Gen")
        self.h3GenAction.setToolTip(tr("H3 Generator"))
        self.h3GenAction.triggered.connect(self.runH3Gen)
        self.generator_menu.addAction(self.h3GenAction)

        # S2 Generator
        icon = QIcon(os.path.dirname(__file__) + "/images/generator/grid_s2.svg")
        self.s2GenAction = QAction(icon, tr("S2"), self.iface.mainWindow())
        self.s2GenAction.setObjectName("s2Gen")
        self.s2GenAction.setToolTip(tr("S2 Generator"))
        self.s2GenAction.triggered.connect(self.runS2Gen)
        self.generator_menu.addAction(self.s2GenAction)

        # A5 Generator
        icon = QIcon(os.path.dirname(__file__) + "/images/generator/grid_a5.svg")
        self.a5GenAction = QAction(icon, tr("A5"), self.iface.mainWindow())
        self.a5GenAction.setObjectName("a5Gen")
        self.a5GenAction.setToolTip(tr("A5 Generator"))
        self.a5GenAction.triggered.connect(self.runA5Gen)
        self.generator_menu.addAction(self.a5GenAction)

        # rHEALPix Generator
        icon = QIcon(os.path.dirname(__file__) + "/images/generator/grid_rhealpix.svg")
        self.rhealpixGenAction = QAction(icon, tr("rHEALPix"), self.iface.mainWindow())
        self.rhealpixGenAction.setObjectName("rhealpixGen")
        self.rhealpixGenAction.setToolTip(tr("rHEALPix Generator"))
        self.rhealpixGenAction.triggered.connect(self.runRhealpixGen)
        self.generator_menu.addAction(self.rhealpixGenAction)

        # ISEA4T Generator
        icon = QIcon(os.path.dirname(__file__) + "/images/generator/grid_triangle.svg")
        self.isea4tGenAction = QAction(icon, tr("ISEA4T"), self.iface.mainWindow())
        self.isea4tGenAction.setObjectName("isea4tGen")
        self.isea4tGenAction.setToolTip(tr("ISEA4T Generator"))
        self.isea4tGenAction.triggered.connect(self.runISEA4TGen)
        self.generator_menu.addAction(self.isea4tGenAction)

        # DGGAL Generator
        icon = QIcon(os.path.dirname(__file__) + "/images/generator/grid_dggal.svg")
        self.dggalGenAction = QAction(icon, tr("DGGAL"), self.iface.mainWindow())
        self.dggalGenAction.setObjectName("dggalGen")
        self.dggalGenAction.setToolTip(tr("DGGAL Generator"))
        self.dggalGenAction.triggered.connect(self.runDGGALGen)
        self.generator_menu.addAction(self.dggalGenAction)

        # DGGRID Generator
        icon = QIcon(os.path.dirname(__file__) + "/images/generator/grid_dggrid.svg")
        self.dggridGenAction = QAction(icon, tr("DGGRID"), self.iface.mainWindow())
        self.dggridGenAction.setObjectName("dggridGen")
        self.dggridGenAction.setToolTip(tr("DGGRID Generator"))
        self.dggridGenAction.triggered.connect(self.runDGGRIDGen)
        self.generator_menu.addAction(self.dggridGenAction)

        # QTM Generator
        icon = QIcon(os.path.dirname(__file__) + "/images/generator/grid_triangle.svg")
        self.qtmGenAction = QAction(icon, tr("QTM"), self.iface.mainWindow())
        self.qtmGenAction.setObjectName("qtmGen")
        self.qtmGenAction.setToolTip(tr("QTM Generator"))
        self.qtmGenAction.triggered.connect(self.runQTMGen)
        self.generator_menu.addAction(self.qtmGenAction)

        # OLC Generator
        icon = QIcon(os.path.dirname(__file__) + "/images/generator/grid_olc.svg")
        self.olcGenAction = QAction(icon, tr("OLC"), self.iface.mainWindow())
        self.olcGenAction.setObjectName("olcGen")
        self.olcGenAction.setToolTip(tr("OLC Generator"))
        self.olcGenAction.triggered.connect(self.runOLCGen)
        self.generator_menu.addAction(self.olcGenAction)

        # Geohash Generator
        icon = QIcon(os.path.dirname(__file__) + "/images/generator/grid_quad.svg")
        self.geohashGenAction = QAction(icon, tr("Geohash"), self.iface.mainWindow())
        self.geohashGenAction.setObjectName("geohashGen")
        self.geohashGenAction.setToolTip(tr("Geohash Generator"))
        self.geohashGenAction.triggered.connect(self.runGeohashGen)
        self.generator_menu.addAction(self.geohashGenAction)

        # GEOREF Generator
        icon = QIcon(os.path.dirname(__file__) + "/images/generator/grid_quad.svg")
        self.georefGenAction = QAction(icon, tr("GEOREF"), self.iface.mainWindow())
        self.georefGenAction.setObjectName("georefGen")
        self.georefGenAction.setToolTip(tr("GEOREF Generator"))
        self.georefGenAction.triggered.connect(self.runGEOREFGen)
        self.generator_menu.addAction(self.georefGenAction)

        # MGRS Generator
        icon = QIcon(os.path.dirname(__file__) + "/images/generator/grid_mgrs.svg")
        self.mgrsGenAction = QAction(icon, tr("MGRS"), self.iface.mainWindow())
        self.mgrsGenAction.setObjectName("mgrsGen")
        self.mgrsGenAction.setToolTip(tr("MGRS Generator"))
        self.mgrsGenAction.triggered.connect(self.runMGRSGen)
        self.generator_menu.addAction(self.mgrsGenAction)

        # GZD Generator
        icon = QIcon(os.path.dirname(__file__) + "/images/generator/grid_quad.svg")
        self.gzdGenAction = QAction(icon, tr("GZD"), self.iface.mainWindow())
        self.gzdGenAction.setObjectName("gzdGen")
        self.gzdGenAction.setToolTip(tr("GZD Generator"))
        self.gzdGenAction.triggered.connect(self.runGZDGen)
        self.generator_menu.addAction(self.gzdGenAction)

        # Tilecode Generator
        icon = QIcon(os.path.dirname(__file__) + "/images/generator/grid_quad.svg")
        self.tilecodeGenAction = QAction(icon, tr("Tilecode"), self.iface.mainWindow())
        self.tilecodeGenAction.setObjectName("tilecodeGen")
        self.tilecodeGenAction.setToolTip(tr("Tilecode Generator"))
        self.tilecodeGenAction.triggered.connect(self.runTilecodeGen)
        self.generator_menu.addAction(self.tilecodeGenAction)

        # Quadkey Generator
        icon = QIcon(os.path.dirname(__file__) + "/images/generator/grid_quad.svg")
        self.quadkeyGenAction = QAction(icon, tr("Quadkey"), self.iface.mainWindow())
        self.quadkeyGenAction.setObjectName("quadkeyGen")
        self.quadkeyGenAction.setToolTip(tr("Quadkey Generator"))
        self.quadkeyGenAction.triggered.connect(self.runQuadkeyGen)
        self.generator_menu.addAction(self.quadkeyGenAction)

        # Maidenhead Generator
        icon = QIcon(os.path.dirname(__file__) + "/images/generator/grid_quad.svg")
        self.maidenheadGenAction = QAction(
            icon, tr("Maidenhead"), self.iface.mainWindow()
        )
        self.maidenheadGenAction.setObjectName("maidenheadGen")
        self.maidenheadGenAction.setToolTip(tr("Maidenhead Generator"))
        self.maidenheadGenAction.triggered.connect(self.runMaidenheadGen)
        self.generator_menu.addAction(self.maidenheadGenAction)

        # GARS Generator
        icon = QIcon(os.path.dirname(__file__) + "/images/generator/grid_quad.svg")
        self.garsGenAction = QAction(icon, tr("GARS"), self.iface.mainWindow())
        self.garsGenAction.setObjectName("garsGen")
        self.garsGenAction.setToolTip(tr("GARS Generator"))
        self.garsGenAction.triggered.connect(self.runGARSGen)
        self.generator_menu.addAction(self.garsGenAction)

        

        # Add Latlon2DGGS action
        icon = QIcon(os.path.dirname(__file__) + "/images/vgrid.svg")
        self.latlon2DGGSAction = QAction(
            icon, tr("Lat Lon to DGGS"), self.iface.mainWindow()
        )
        self.latlon2DGGSAction.setObjectName("latlon2dggs")
        self.latlon2DGGSAction.setToolTip(tr("Lat Lon to DGGS"))
        self.latlon2DGGSAction.triggered.connect(self.latlon2DGGS)
        self.toolbar.addAction(self.latlon2DGGSAction)

        # Add Interface for settings
        self.settingsDialog = SettingsWidget(self, self.iface, self.iface.mainWindow())
        settings_icon = QIcon(os.path.dirname(__file__) + "/images/settings.svg")
        self.settingsAction = QAction(
            settings_icon, tr("Settings"), self.iface.mainWindow()
        )
        self.settingsAction.setObjectName("settings")
        self.settingsAction.setToolTip(tr("Vgrid Settings"))
        self.settingsAction.triggered.connect(self.settings)
        self.toolbar.addAction(self.settingsAction)

        # Add Settings action to main menu
        self.settingsMenuAction = QAction(
            settings_icon, tr("Settings"), self.iface.mainWindow()
        )
        self.settingsMenuAction.setObjectName("settingsMenu")
        self.settingsMenuAction.setToolTip(tr("Vgrid Settings"))
        self.settingsMenuAction.triggered.connect(self.settings)
        self.Vgrid_menu.addAction(self.settingsMenuAction)

        # Add Vgrid Home action
        home_icon = QIcon(os.path.dirname(__file__) + "/images/vgrid.svg")
        self.vgridHomeAction = QAction(
            home_icon, tr("Vgrid Home"), self.iface.mainWindow()
        )
        self.vgridHomeAction.setObjectName("vgridHome")
        self.vgridHomeAction.setToolTip(tr("Open Vgrid Home website"))
        self.vgridHomeAction.triggered.connect(self.VgridHome)
        self.Vgrid_menu.addAction(self.vgridHomeAction)

    def unload(self):
        for expr in exprs:
            if QgsExpression.isFunctionName(expr.name()):
                QgsExpression.unregisterFunction(expr.name())

        if self.Vgrid_menu is not None:
            self.iface.mainWindow().menuBar().removeAction(self.Vgrid_menu.menuAction())

        if  self.latlon2DGGSAction:
            self.iface.removeToolBarIcon(self.latlon2DGGSAction)
        if  self.settingsAction:
            self.iface.removeToolBarIcon(self.settingsAction)
        if  self.toolbar:
            self.iface.mainWindow().removeToolBar(self.toolbar)
            self.toolbar = None

        if self.latlon2DGGSDialog:
            self.latlon2DGGSDialog.removeMarker()
            self.iface.removeDockWidget(self.latlon2DGGSDialog)
            self.latlon2DGGSDialog = None

        if self.dggsClientDialog:
            self.dggsClientDialog.close()
            self.dggsClientDialog = None

        if self.dggsJson2GeoJsonDialog:
            self.dggsJson2GeoJsonDialog.close()
            self.dggsJson2GeoJsonDialog = None

        # Cleanup H3 grid rubber bands and signals
        if self.h3grid:
            self.h3grid.cleanup()
        if hasattr(self, "a5grid") and self.a5grid:
            self.a5grid.cleanup()
        if hasattr(self, "s2grid") and self.s2grid:
            self.s2grid.cleanup()
        if hasattr(self, "rhealpixgrid") and self.rhealpixgrid:
            self.rhealpixgrid.cleanup()
        if hasattr(self, "isea4tgrid") and self.isea4tgrid:
            self.isea4tgrid.cleanup()
        if hasattr(self, "isea3hgrid") and self.isea3hgrid:
            self.isea3hgrid.cleanup()
        if hasattr(self, "easegrid") and self.easegrid:
            self.easegrid.cleanup()
        if hasattr(self, "dggal_gnosisgrid") and self.dggal_gnosisgrid:
            self.dggal_gnosisgrid.cleanup()
        if hasattr(self, "dggal_isea3hgrid") and self.dggal_isea3hgrid:
            self.dggal_isea3hgrid.cleanup()
        if hasattr(self, "dggal_isea4rgrid") and self.dggal_isea4rgrid:
            self.dggal_isea4rgrid.cleanup()
        if hasattr(self, "dggal_isea7hgrid") and self.dggal_isea7hgrid:
            self.dggal_isea7hgrid.cleanup()
        if hasattr(self, "dggal_isea7h_z7grid") and self.dggal_isea7h_z7grid:
            self.dggal_isea7h_z7grid.cleanup()
        if hasattr(self, "dggal_isea9rgrid") and self.dggal_isea9rgrid:
            self.dggal_isea9rgrid.cleanup()
        if hasattr(self, "dggal_ivea3hgrid") and self.dggal_ivea3hgrid:
            self.dggal_ivea3hgrid.cleanup()
        if hasattr(self, "dggal_ivea4rgrid") and self.dggal_ivea4rgrid:
            self.dggal_ivea4rgrid.cleanup()
        if hasattr(self, "dggal_ivea7hgrid") and self.dggal_ivea7hgrid:
            self.dggal_ivea7hgrid.cleanup()
        if hasattr(self, "dggal_ivea7h_z7grid") and self.dggal_ivea7h_z7grid:
            self.dggal_ivea7h_z7grid.cleanup()
        if hasattr(self, "dggal_ivea9rgrid") and self.dggal_ivea9rgrid:
            self.dggal_ivea9rgrid.cleanup()
        if hasattr(self, "dggal_rtea3hgrid") and self.dggal_rtea3hgrid:
            self.dggal_rtea3hgrid.cleanup()
        if hasattr(self, "dggal_rtea4rgrid") and self.dggal_rtea4rgrid:
            self.dggal_rtea4rgrid.cleanup()
        if hasattr(self, "dggal_rtea7hgrid") and self.dggal_rtea7hgrid:
            self.dggal_rtea7hgrid.cleanup()
        if hasattr(self, "dggal_rtea7h_z7grid") and self.dggal_rtea7h_z7grid:
            self.dggal_rtea7h_z7grid.cleanup()
        if hasattr(self, "dggal_rtea9rgrid") and self.dggal_rtea9rgrid:
            self.dggal_rtea9rgrid.cleanup()
        if hasattr(self, "dggal_rhealpixgrid") and self.dggal_rhealpixgrid:
            self.dggal_rhealpixgrid.cleanup()
        if hasattr(self, "dggal_healpixgrid") and self.dggal_healpixgrid:
            self.dggal_healpixgrid.cleanup()
        # if hasattr(self, "qtmgrid") and self.qtmgrid:
        #     self.qtmgrid.cleanup()
        if hasattr(self, "olcgrid") and self.olcgrid:
            self.olcgrid.cleanup()
        if hasattr(self, "geohashgrid") and self.geohashgrid:
            self.geohashgrid.cleanup()
        if hasattr(self, "georefgrid") and self.georefgrid:
            self.georefgrid.cleanup()
        if hasattr(self, "tilecodegrid") and self.tilecodegrid:
            self.tilecodegrid.cleanup()
        if hasattr(self, "maidenheadgrid") and self.maidenheadgrid:
            self.maidenheadgrid.cleanup()
        if hasattr(self, "garsgrid") and self.garsgrid:
            self.garsgrid.cleanup()
        if hasattr(self, "digipingrid") and self.digipingrid:
            self.digipingrid.cleanup()
        if getattr(self, "dggrid_grids", None):
            for dggrid_grid in self.dggrid_grids.values():
                try:
                    dggrid_grid.cleanup()
                except Exception:
                    pass
        from .utils.dggrid_instance import reset_plugin_dggrid_instance

        reset_plugin_dggrid_instance()

        self.settingsDialog = None
        QgsApplication.processingRegistry().removeProvider(self.provider)

    def latlon2DGGS(self):
        """Display the Convert Coordinate Tool Dialog box."""
        if self.latlon2DGGSDialog is None:
            self.latlon2DGGSDialog = LatLon2DGGSWidget(
                self, self.settingsDialog, self.iface, self.iface.mainWindow()
            )
            self.latlon2DGGSDialog.setFloating(True)
            self.iface.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.latlon2DGGSDialog)
        self.latlon2DGGSDialog.show()

    def showDGGSClient(self):
        """Display the DGGS Client Dialog box."""
        if self.dggsClientDialog is None:
            self.dggsClientDialog = DGGSClientWidget(
                self, self.settingsDialog, self.iface, self.iface.mainWindow()
            )

        self.dggsClientDialog.show()

    def settings(self):
        """Show the settings dialog box"""
        self.settingsDialog.show()

    def settingsChanged(self):
        # Settings may have changed so we need to make sure the zoomToDialog window is configured properly
        if self.latlon2DGGSDialog is not None:
            self.latlon2DGGSDialog.configure()

    def zoomTo(self, src_crs, lat, lon):
        canvas_crs = self.canvas.mapSettings().destinationCrs()
        transform = QgsCoordinateTransform(src_crs, canvas_crs, QgsProject.instance())
        x, y = transform.transform(float(lon), float(lat))

        rect = QgsRectangle(x, y, x, y)
        self.canvas.setExtent(rect)

        pt = QgsPointXY(x, y)
        self.highlight(pt)
        self.canvas.refresh()
        return pt

    def highlight(self, point):
        currExt = self.canvas.extent()

        leftPt = QgsPoint(currExt.xMinimum(), point.y())
        rightPt = QgsPoint(currExt.xMaximum(), point.y())

        topPt = QgsPoint(point.x(), currExt.yMaximum())
        bottomPt = QgsPoint(point.x(), currExt.yMinimum())

        horizLine = QgsGeometry.fromPolyline([leftPt, rightPt])
        vertLine = QgsGeometry.fromPolyline([topPt, bottomPt])

        self.crossRb.reset(QgsWkbTypes.LineGeometry)
        self.crossRb.setWidth(settings.markerWidth)
        self.crossRb.setColor(settings.markerColor)
        self.crossRb.addGeometry(horizLine, None)
        self.crossRb.addGeometry(vertLine, None)

        QTimer.singleShot(700, self.resetRubberbands)

    def resetRubberbands(self):
        self.crossRb.reset()

    def Vgrid_add_submenu(self, submenu):
        if self.Vgrid_menu is not None:
            self.Vgrid_menu.addMenu(submenu)
        else:
            self.iface.addPluginToMenu("&Vgrid", submenu.menuAction())

    def Vgrid_add_submenu2(self, submenu, icon):
        if self.Vgrid_menu is not None:
            submenu.setIcon(QIcon(icon))
            self.Vgrid_menu.addMenu(submenu)
        else:
            self.iface.addPluginToMenu("&Vgrid", submenu.menuAction())

    def Vgrid_add_submenu3(self, submenu, icon):
        if self.dggs_menu is not None:
            submenu.setIcon(QIcon(icon))
            self.dggs_menu.addMenu(submenu)
        else:
            self.iface.addPluginToMenu("&DGGS", submenu.menuAction())

    def runH3Bin(self):
        """Run H3 Binning algorithm"""
        processing.execAlgorithmDialog("vgrid:bin_h3", {})

    def runS2Bin(self):
        """Run S2 Binning algorithm"""
        processing.execAlgorithmDialog("vgrid:bin_s2", {})

    def runA5Bin(self):
        """Run A5 Binning algorithm"""
        processing.execAlgorithmDialog("vgrid:bin_a5", {})

    def runRhealpixBin(self):
        """Run rHEALPix Binning algorithm"""
        processing.execAlgorithmDialog("vgrid:bin_rhealpix", {})

    def runISEA4TBin(self):
        """Run ISEA4T Binning algorithm"""
        processing.execAlgorithmDialog("vgrid:bin_isea4t", {})

    def runDGGALBin(self):
        """Run DGGAL Binning algorithm"""
        processing.execAlgorithmDialog("vgrid:bin_dggal", {})

    def runOLCBin(self):
        """Run OLC Binning algorithm"""
        processing.execAlgorithmDialog("vgrid:bin_olc", {})

    def runGeohashBin(self):
        """Run Geohash Binning algorithm"""
        processing.execAlgorithmDialog("vgrid:bin_geohash", {})

    def runTilecodeBin(self):
        """Run Tilecode Binning algorithm"""
        processing.execAlgorithmDialog("vgrid:bin_tilecode", {})

    def runQuadkeyBin(self):
        """Run Quadkey Binning algorithm"""
        processing.execAlgorithmDialog("vgrid:bin_quadkey", {})

    def runCellId2DGGS(self):
        """Run Cell ID to DGGS algorithm"""
        processing.execAlgorithmDialog("vgrid:cellid2dggs", {})

    def runVector2DGGS(self):
        """Run Vector to DGGS algorithm"""
        processing.execAlgorithmDialog("vgrid:vector2dggs", {})

    def runDGGSCompact(self):
        """Run DGGS Compact algorithm"""
        processing.execAlgorithmDialog("vgrid:dggscompact", {})

    def runDGGSExpand(self):
        """Run DGGS Expand algorithm"""
        processing.execAlgorithmDialog("vgrid:dggsexpand", {})

    def runRaster2DGGS(self):
        """Run Raster to DGGS algorithm"""
        processing.execAlgorithmDialog("vgrid:raster2dggs", {})

    def runH3Gen(self):
        """Run H3 Gen algorithm"""
        processing.execAlgorithmDialog("vgrid:h3_gen", {})

    def runS2Gen(self):
        """Run S2 Gen algorithm"""
        processing.execAlgorithmDialog("vgrid:s2_gen", {})

    def runA5Gen(self):
        """Run A5 Gen algorithm"""
        processing.execAlgorithmDialog("vgrid:a5_gen", {})

    def runRhealpixGen(self):
        """Run rHEALPix Gen algorithm"""
        processing.execAlgorithmDialog("vgrid:rhealpix_gen", {})

    def runISEA4TGen(self):
        """Run ISEA4T Gen algorithm"""
        processing.execAlgorithmDialog("vgrid:isea4t_gen", {})

    def runQTMGen(self):
        """Run QTM Gen algorithm"""
        processing.execAlgorithmDialog("vgrid:qtm_gen", {})

    def runOLCGen(self):
        """Run OLC Gen algorithm"""
        processing.execAlgorithmDialog("vgrid:olc_gen", {})

    def runGEOREFGen(self):
        """Run GEOREF Gen algorithm"""
        processing.execAlgorithmDialog("vgrid:georef_gen", {})

    def runGeohashGen(self):
        """Run Geohash Gen algorithm"""
        processing.execAlgorithmDialog("vgrid:geohash_gen", {})

    def runDGGALGen(self):
        """Run DGGAL Gen algorithm"""
        processing.execAlgorithmDialog("vgrid:dggal_gen", {})

    def runDGGRIDGen(self):
        """Run DGGRID Gen algorithm"""
        processing.execAlgorithmDialog("vgrid:DGGRID_gen", {})

    def runMGRSGen(self):
        """Run MGRS Gen algorithm"""
        processing.execAlgorithmDialog("vgrid:mgrs_gen", {})

    def runGZDGen(self):
        """Run GZD Gen algorithm"""
        processing.execAlgorithmDialog("vgrid:gzd_gen", {})

    def runTilecodeGen(self):
        """Run Tilecode Gen algorithm"""
        processing.execAlgorithmDialog("vgrid:tilecode_gen", {})

    def runQuadkeyGen(self):
        """Run Quadkey Gen algorithm"""
        processing.execAlgorithmDialog("vgrid:quadkey_gen", {})

    def runMaidenheadGen(self):
        """Run Maidenhead Gen algorithm"""
        processing.execAlgorithmDialog("vgrid:maidenhead_gen", {})

    def runGARSGen(self):
        """Run GARS Gen algorithm"""
        processing.execAlgorithmDialog("vgrid:gars_gen", {})

    def runDGGSResample(self):
        """Run DGGS Resample algorithm"""
        processing.execAlgorithmDialog("vgrid:dggsresample", {})

    def runSplitAtAntimeridian(self):
        """Run Split at Antimeridian algorithm"""
        processing.execAlgorithmDialog("vgrid:splitantimeridian", {})

    def runShiftAtAntimeridian(self):
        """Run Shift at Antimeridian algorithm"""
        processing.execAlgorithmDialog("vgrid:shiftantimeridian", {})

    def showDGGSJSON2GeoJSON(self):
        """Display the DGGS-JSON to GeoJSON Dialog box."""
        if self.dggsJson2GeoJsonDialog is None:
            self.dggsJson2GeoJsonDialog = DGGSJSON2GeoJSONWidget(
                self, self.settingsDialog, self.iface, self.iface.mainWindow()
            )

        self.dggsJson2GeoJsonDialog.show()

    def createDGGRIDInstance(self):
        """Initialize the shared DGGRID instance used by Generator and DGGRID Viz."""
        from .utils.dggrid_instance import dggrid_work_dir, get_plugin_dggrid_instance

        try:
            get_plugin_dggrid_instance(force_new=True)
            QMessageBox.information(
                self.iface.mainWindow(),
                tr("Vgrid"),
                tr(
                    "DGGRID instance is ready.\n\nWorking directory:\n{0}"
                ).format(dggrid_work_dir()),
            )
        except Exception as exc:
            QMessageBox.critical(
                self.iface.mainWindow(),
                tr("Vgrid"),
                tr("Failed to create DGGRID instance:\n\n{0}").format(exc),
            )

    def clearDGGRIDCaches(self):
        """Remove all *.txt files from the plugin dggrid folder."""
        from .utils.dggrid_instance import (
            clear_dggrid_cache_files,
            reset_plugin_dggrid_instance,
        )

        reset_plugin_dggrid_instance()
        removed, errors = clear_dggrid_cache_files()
        if errors:
            detail = "\n".join(f"{name}: {err}" for name, err in errors[:10])
            QMessageBox.warning(
                self.iface.mainWindow(),
                tr("Vgrid"),
                tr("Removed {0} file(s). Some files could not be deleted:\n\n{1}").format(
                    len(removed), detail
                ),
            )
        else:
            QMessageBox.information(
                self.iface.mainWindow(),
                tr("Vgrid"),
                tr("Removed {0} DGGRID cache file(s).").format(len(removed)),
            )

    def VgridHome(self):
        webbrowser.open("https://vgridhome.gishub.vn")
