# -*- coding: utf-8 -*-

"""
/***************************************************************************
 vgrid
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


# noinspection PyPep8Naming
def classFactory(iface):  # pylint: disable=invalid-name
    """Load vgrid class from file vgrid.
    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """
    #
    from .vgrid import VgridPlugin
    # from .vgrid_menu import vgrid_menu

    return VgridPlugin(iface)
    # return vgrid_menu(iface)