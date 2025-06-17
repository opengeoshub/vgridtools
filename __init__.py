# -*- coding: utf-8 -*-

"""
/***************************************************************************
 Vgrid Tools
                                 A QGIS plugin
 Tools for Geoprocessing in QGIS.
                              -------------------
        begin                : 2024-11-20
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
  This script initializes the plugin, making it known to QGIS.

"""

__author__ = 'Thang Quach'
__date__ = '2024-11-20'
__copyright__ = '(L) 2024 by Thang Quach'

from PyQt5.QtWidgets import QInputDialog

# noinspection PyPep8Naming
def classFactory(iface):  # pylint: disable=invalid-name  
  try:
      import vgrid
  except ImportError:
    command = "import pip\npip.main(['install','vgrid --upgrade'])"   
    text, ok = QInputDialog.getMultiLineText(None, "Vgrid DGGS - Vgrid module not found", 
                                            "To run Vgrid Tools, please copy and run this code in the Python console to install vgrid package and reload QGIS:", 
                                            command)

  from .vgrid import VgridPlugin
  # from .vgrid_menu import vgrid_menu

  return VgridPlugin(iface)
  # return vgrid_menu(iface)
  