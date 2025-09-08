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
import sys
import inspect
from PyQt5.QtWidgets import *
from qgis.core import QgsApplication, QgsExpression
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QMenu, QApplication, QToolButton

from PyQt5.QtCore import *
from PyQt5.QtGui import *

from .vgrid_provider import VgridProvider
from .expressions import *
from .settings import SettingsWidget, settings
from .util import tr

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


class VgridPlugin(object):
    latlon2DGGSDialog = None

    def __init__(
        self,
        iface,
    ):
        self.provider = None
        self.plugin_dir = os.path.dirname(__file__)
        self.iface = iface
        self.canvas = iface.mapCanvas()
        self.Vgrid_menu = None
        self.toolbar = self.iface.addToolBar(tr('Vgrid Toolbar'))
        self.toolbar.setObjectName('VgridToolbar')
        self.toolbar.setToolTip(tr('Vgrid Toolbar'))

    def initProcessing(self):
        """Init Processing provider for QGIS >= 3.8."""
        self.provider = VgridProvider()
        QgsApplication.processingRegistry().addProvider(self.provider)

    def initGui(self):
        self.initProcessing()
        for expr in exprs:
            if not QgsExpression.isFunctionName(expr.name()):
                QgsExpression.registerFunction(expr)

        # Create menu
        # self.Vgrid_menu = QMenu(QCoreApplication.translate("Vgrid", "Vgrid"))
        # self.iface.mainWindow().menuBar().insertMenu(self.iface.firstRightStandardMenu().menuAction(), self.Vgrid_menu)

        # Add settings action
        icon = QIcon(os.path.dirname(__file__) + '/images/vgrid.svg')
        self.latlon2DGGSAction = QAction(icon, tr("Lat Lon to DGGS"), self.iface.mainWindow())
        self.latlon2DGGSAction.setObjectName('latlon2DGGS') 
        self.latlon2DGGSAction.setToolTip(tr('Lat Lon to DGGS'))
        self.latlon2DGGSAction.triggered.connect(self.latlon2DGGSTool)
        self.toolbar.addAction(self.latlon2DGGSAction)


        self.settingsDialog = SettingsWidget(self, self.iface, self.iface.mainWindow())
        
        # Initialize the Settings Dialog Box
        settingsicon = QIcon(os.path.dirname(__file__) + '/images/settings.svg')  
        self.settingsAction = QAction(settingsicon, tr("Settings"), self.iface.mainWindow())
        self.settingsAction.setObjectName('settings')
        self.settingsAction.setToolTip(tr('Vgrid Settings'))
        self.settingsAction.triggered.connect(self.settings)
        self.toolbar.addAction(self.settingsAction)


    def unload(self):
        QgsApplication.processingRegistry().removeProvider(self.provider)
        for expr in exprs:
            if QgsExpression.isFunctionName(expr.name()):
                QgsExpression.unregisterFunction(expr.name())
        if self.Vgrid_menu is not None:
            self.iface.mainWindow().menuBar().removeAction(self.Vgrid_menu.menuAction())

        self.iface.removeToolBarIcon(self.latlon2DGGSAction)
        del self.toolbar
        
        if self.latlon2DGGSDialog:
            self.iface.removeDockWidget(self.latlon2DGGSDialog)
            self.latlon2DGGSDialog = None


    def latlon2DGGSTool(self):
        '''Display the Convert Coordinate Tool Dialog box.'''
        if self.latlon2DGGSDialog is None:
            from .latlon2DGGS import LatLon2DGGSWidget
            self.latlon2DGGSDialog = LatLon2DGGSWidget(self, self.settingsDialog, self.iface, self.iface.mainWindow())
            self.latlon2DGGSDialog.setFloating(True)
            self.iface.addDockWidget(Qt.RightDockWidgetArea, self.latlon2DGGSDialog)
        self.latlon2DGGSDialog.show()

    
    def settings(self):
        '''Show the settings dialog box'''
        self.settingsDialog.show()


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

    def VgridHome(self):
        webbrowser.open("https://vgrid.vn")
