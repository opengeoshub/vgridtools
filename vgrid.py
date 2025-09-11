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
from qgis.PyQt.QtGui import QIcon, QColor
from qgis.PyQt.QtCore import Qt, QTimer, QUrl, QTranslator, QCoreApplication
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import (
    QAction,
    QMenu,
    QWidgetAction,
    QCheckBox,
    QApplication,
    QToolButton,
)
from qgis.core import (
    Qgis,
    QgsCoordinateTransform,
    QgsVectorLayer,
    QgsRectangle,
    QgsPoint,
    QgsPointXY,
    QgsGeometry,
    QgsWkbTypes,
    QgsProject,
    QgsApplication,
    QgsSettings,
)
from qgis.gui import QgsRubberBand

from .vgrid_provider import VgridProvider
from .expressions import *
from .settings import SettingsWidget, settings
from .latlon2dggs import LatLon2DGGSWidget
from .utils import tr
from .dggsgrid.h3grid import H3Grid
from .dggsgrid.a5grid import A5Grid
from .dggsgrid.s2grid import S2Grid
from .dggsgrid.rhealpixgrid import RhealpixGrid
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
)


class VgridTools(object):
    latlon2DGGSDialog = None

    def __init__(
        self,
        iface,
    ):
        self.provider = None
        self.plugin_dir = os.path.dirname(__file__)
        self.iface = iface
        self.canvas = iface.mapCanvas()
        
        self.h3grid = H3Grid(self, self.canvas, self.iface)
        self.a5grid = A5Grid(self, self.canvas, self.iface)
        self.s2grid = S2Grid(self, self.canvas, self.iface)
        self.rhealpixgrid = RhealpixGrid(self, self.canvas, self.iface)
        
        self.Vgrid_menu = None
        self.toolbar = self.iface.addToolBar(tr("Vgrid Toolbar"))
        self.toolbar.setObjectName("VgridToolbar")
        self.toolbar.setToolTip(tr("Vgrid Toolbar"))

        self.crossRb = QgsRubberBand(self.canvas, QgsWkbTypes.LineGeometry)
        self.crossRb.setColor(Qt.red)


        self.iface.mapCanvas().scaleChanged.connect(self.displayZoomLevel)

    def displayZoomLevel(self):
        """Display the current zoom level in the status bar"""

        scale = self.iface.mapCanvas().scale()

        # Convert the scale to the equivalent zoom level
        # (This is accurate enough for at least 2 decimal places)
        zoom = 29.1402 - log2(scale)
        if settings.zoomLevel:
            self.iface.mainWindow().statusBar().showMessage(
                "Vgrid zoom Level {:.2f}".format(zoom)
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

        # Create Vgrid DGGS submenu
        self.dggs_menu = QMenu("DGGS")
        icon = QIcon(os.path.dirname(__file__) + "/images/generator/grid_quad.svg")
        self.Vgrid_add_submenu2(self.dggs_menu, icon)

        # Add Vgrid DGGS items
        # icon = QIcon(os.path.dirname(__file__) + "/images/generator/grid_h3.svg")
        # self.h3_action = QAction(u'H3', self.iface.mainWindow())
        # self.h3_action.setCheckable(True)
        # self.h3_action.setChecked(False)
        # self.h3_action.toggled.connect(self.h3_grid)  # use toggled(bool)
        # self.dggs_menu.addAction(self.h3_action)

        icon = QIcon(os.path.dirname(__file__) + "/images/generator/grid_h3.svg")

        self.h3_widget_action = QWidgetAction(self.dggs_menu)
        checkbox = QCheckBox("H3")
        checkbox.setIcon(icon)
        checkbox.setChecked(False)  # optional initial state
        checkbox.toggled.connect(
            lambda checked: (self.h3grid.enable_h3(checked), self.h3grid.h3_grid())
            if checked
            else self.h3grid.enable_h3(False)
        )
        self.h3_widget_action.setDefaultWidget(checkbox)
        self.dggs_menu.addAction(self.h3_widget_action)

        # S2
        icon = QIcon(os.path.dirname(__file__) + "/images/generator/grid_s2.svg")
        self.s2_widget_action = QWidgetAction(self.dggs_menu)
        s2_checkbox = QCheckBox("S2")
        s2_checkbox.setIcon(icon)
        s2_checkbox.setChecked(False)
        s2_checkbox.toggled.connect(
            lambda checked: (self.s2grid.enable_s2(checked), self.s2grid.s2_grid())
            if checked
            else self.s2grid.enable_s2(False)
        )
        self.s2_widget_action.setDefaultWidget(s2_checkbox)
        self.dggs_menu.addAction(self.s2_widget_action)

          # A5
        icon = QIcon(os.path.dirname(__file__) + "/images/generator/grid_a5.svg")
        self.a5_widget_action = QWidgetAction(self.dggs_menu)
        a5_checkbox = QCheckBox("A5")
        a5_checkbox.setIcon(icon)
        a5_checkbox.setChecked(False)
        a5_checkbox.toggled.connect(
            lambda checked: (self.a5grid.enable_a5(checked), self.a5grid.a5_grid())
            if checked
            else self.a5grid.enable_a5(False)
        )
        self.a5_widget_action.setDefaultWidget(a5_checkbox)
        self.dggs_menu.addAction(self.a5_widget_action)

        # rHEALPix
        icon = QIcon(os.path.dirname(__file__) + "/images/generator/grid_rhealpix.svg")
        self.rhealpix_widget_action = QWidgetAction(self.dggs_menu)
        rhealpix_checkbox = QCheckBox("rHEALPix")
        rhealpix_checkbox.setIcon(icon)
        rhealpix_checkbox.setChecked(False)
        rhealpix_checkbox.toggled.connect(
            lambda checked: (
                self.rhealpixgrid.enable_rhealpix(checked),
                self.rhealpixgrid.rhealpix_grid(),
            )
            if checked
            else self.rhealpixgrid.enable_rhealpix(False)
        )
        self.rhealpix_widget_action.setDefaultWidget(rhealpix_checkbox)
        self.dggs_menu.addAction(self.rhealpix_widget_action)

        
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

    def unload(self):
        for expr in exprs:
            if QgsExpression.isFunctionName(expr.name()):
                QgsExpression.unregisterFunction(expr.name())

        if self.Vgrid_menu is not None:
            self.iface.mainWindow().menuBar().removeAction(self.Vgrid_menu.menuAction())

        self.iface.removeToolBarIcon(self.latlon2DGGSAction)
        del self.toolbar

        if self.latlon2DGGSDialog:
            self.latlon2DGGSDialog.removeMarker()
            self.iface.removeDockWidget(self.latlon2DGGSDialog)
            self.latlon2DGGSDialog = None

        # Cleanup H3 grid rubber bands and signals
        if self.h3grid:
            self.h3grid.cleanup()
        if hasattr(self, "a5grid") and self.a5grid:
            self.a5grid.cleanup()
        if hasattr(self, "s2grid") and self.s2grid:
            self.s2grid.cleanup()
        if hasattr(self, "rhealpixgrid") and self.rhealpixgrid:
            self.rhealpixgrid.cleanup()

        self.settingsDialog = None
        QgsApplication.processingRegistry().removeProvider(self.provider)

    def latlon2DGGS(self):
        """Display the Convert Coordinate Tool Dialog box."""
        if self.latlon2DGGSDialog is None:
            self.latlon2DGGSDialog = LatLon2DGGSWidget(
                self, self.settingsDialog, self.iface, self.iface.mainWindow()
            )
            self.latlon2DGGSDialog.setFloating(True)
            self.iface.addDockWidget(Qt.RightDockWidgetArea, self.latlon2DGGSDialog)
        self.latlon2DGGSDialog.show()

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
        if self.Vgrid_menu != None:
            self.Vgrid_menu.addMenu(submenu)
        else:
            self.iface.addPluginToMenu("&Vgrid", submenu.menuAction())

    def Vgrid_add_submenu2(self, submenu, icon):
        if self.Vgrid_menu != None:
            submenu.setIcon(QIcon(icon))
            self.Vgrid_menu.addMenu(submenu)
        else:
            self.iface.addPluginToMenu("&Vgrid", submenu.menuAction())

    def Vgrid_add_submenu3(self, submenu, icon):
        if self.dggs_menu != None:
            submenu.setIcon(QIcon(icon))
            self.dggs_menu.addMenu(submenu)
        else:
            self.iface.addPluginToMenu("&DGGS", submenu.menuAction())

    def VgridHome(self):
        webbrowser.open("https://vgrid.vn")
