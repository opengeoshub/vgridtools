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

__author__ = 'Thang Quach'
__date__ = '2024-11-20'
__copyright__ = '(L) 2024 by Thang Quach'

# This will get replaced with a git SHA1 when you do a git archive

__revision__ = '$Format:%H$'

import webbrowser  
import os
import sys
import inspect
from PyQt5.QtWidgets import *
from qgis.core import (
                       QgsApplication,
                       QgsExpression)

from PyQt5.QtCore import *
from PyQt5.QtGui import *

from .vgrid_provider import VgridProvider
from .expressions import *
from .processing_provider.conversion.dggs_settings import DGGSettingsDialog
# from .vgrid_dialogs import *
exprs =(latlon2h3, latlon2s2, latlon2rhealpix, latlon2isea4t, latlon2isea3h, latlon2qtm,\
        latlon2olc, latlon2geohash, latlon2georef, latlon2mgrs, latlon2tilecode, latlon2quadkey, latlon2maidenhead, latlon2gars)
    
class VgridPlugin(object):

    def __init__(self, iface,):
        self.provider = None
        self.plugin_dir = os.path.dirname(__file__)
        self.iface = iface
        self.Vgrid_menu = None                 
        self.settings_action = None

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
        self.settings_action = QAction(
            QIcon(":/plugins/vgridtools/images/settings.svg"),
            "DGGS Settings",
            self.iface.mainWindow()
        )
        self.settings_action.triggered.connect(self.showSettings)
        self.iface.addPluginToMenu("&VGridTools", self.settings_action)

    def unload(self):
        QgsApplication.processingRegistry().removeProvider(self.provider)
        for expr in exprs:
            if QgsExpression.isFunctionName(expr.name()):
                QgsExpression.unregisterFunction(expr.name())
        if self.Vgrid_menu is not None:
            self.iface.mainWindow().menuBar().removeAction(self.Vgrid_menu.menuAction())

    def showSettings(self):
        """Show the settings dialog."""
        dialog = DGGSettingsDialog(self.iface)
        dialog.exec_()

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
    
