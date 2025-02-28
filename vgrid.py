# -*- coding: utf-8 -*-

"""
/***************************************************************************
 Vgrid
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
from .vgridlibrary.grid import gzd
# from .vgrid_dialogs import *
exprs =(latlon2olc,latlon2mgrs,latlon2geohash,latlon2georef,latlon2s2,latlon2vcode,latlon2maidenhead,latlon2gars)

    
class VgridPlugin(object):

    def __init__(self, iface,):
        self.provider = None
        self.plugin_dir = os.path.dirname(__file__)
        self.iface = iface
        self.Vgrid_menu = None                 
    

    def initProcessing(self):
        """Init Processing provider for QGIS >= 3.8."""
        self.provider = VgridProvider()
        QgsApplication.processingRegistry().addProvider(self.provider)


    def initGui(self):       
        self.initProcessing()
        for expr in exprs:
            if not QgsExpression.isFunctionName(expr.name()):
                QgsExpression.registerFunction(expr)
        
        # self.Vgrid_menu = QMenu(QCoreApplication.translate("Vgrid", "Vgrid"))
        # self.iface.mainWindow().menuBar().insertMenu(self.iface.firstRightStandardMenu().menuAction(), self.Vgrid_menu)
        
        # self.VgridGenerator_menu = QMenu(u'Vgrid')	
        # icon = QIcon(os.path.dirname(__file__) + "/images/grid_generator.png")	
        # self.Vgrid_add_submenu2(self.VgridGenerator_menu, icon)
        

        # icon = QIcon(os.path.dirname(__file__) + "/images/grid_gzd.png")  
        # self.VgridGZD_action = QAction(icon, u'Grid Zone Designators', self.iface.mainWindow())
        # self.VgridGZD_action.triggered.connect(lambda: gzd.main())
        # self.VgridGenerator_menu.addAction(self.VgridGZD_action)


        # self.VgridHome_menu = QMenu(u'Vgrid Home')	
        # icon = QIcon(os.path.dirname(__file__) + "/images/vgrid.svg")	
        # self.Vgrid_add_submenu2(self.VgridHome_menu, icon)
        # self.VgridHome_action = QAction(icon, u'Vgrid Home', self.iface.mainWindow())
        # self.VgridHome_action.triggered.connect(self.VgridHome)
        # self.VgridHome_menu.addAction(self.VgridHome_action)	

    def unload(self):
        QgsApplication.processingRegistry().removeProvider(self.provider)
        for expr in exprs:
            if QgsExpression.isFunctionName(expr.name()):
                QgsExpression.unregisterFunction(expr.name())
        # if self.Vgrid_menu != None:
        #     self.iface.mainWindow().menuBar().removeAction(self.Vgrid_menu.menuAction())
        # else:
        #     self.iface.removePluginMenu("&Vgrid", self.VgridHome_menu.menuAction())          

   
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
    
