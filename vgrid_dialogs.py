# -*- coding: utf-8 -*-

"""
/***************************************************************************
 vgrid
                                 A QGIS plugin
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

import os.path
import sys

from qgis.core import *
from PyQt5 import QtCore, QtWidgets
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
#from owslib.ogcapi import Features
from qgis.gui import QgsMessageBar
from glob import glob
from time import sleep
from xml.etree.ElementTree import XML, fromstring
from PyQt5.QtWidgets import QApplication


try:
    from vgridlibrary.grid import gridgenerator
except:
    from .vgridlibrary.grid import gridgenerator


sys.path.append(os.path.dirname(os.path.abspath(__file__)) + "/forms")

from grid_geohash_form import *

# ------------------------------------------------------------------------------
#    vgrid_dialog - base class for vgrid dialogs containing utility functions
# ------------------------------------------------------------------------------
class vgrid_dialog(QtWidgets.QDialog):
    def __init__(self, iface):
        QtWidgets.QDialog.__init__(self)
        self.iface = iface

    def vgrid_initialize_spatial_output_file_widget(self, file_widget, name, ext = ".shp"):
        initial_file_name = self.vgrid_temp_file_name(name, ext)
        file_widget.setFilePath(initial_file_name)
        file_widget.setStorageMode(QgsFileWidget.SaveFile)

        file_widget.setFilter("ESRI Shapefile (*.shp);;GeoJSON (*.geojson);;KML (*.kml);;" + \
            "Spatialite (*.sqlite);;GPKG (*.gpkg)")

    def vgrid_temp_file_name(self, name, ext):
        project = QgsProject.instance()
        home_path = project.homePath()
        if not home_path:
            home_path = os.path.expanduser('~')
        for x in range(1, 10):
            file_name = home_path + "/" +name + str(x) + ext
            if not os.path.isfile(file_name):
                return file_name
        return home_path + "/"+ name + ext

    def vgrid_set_status_bar(self, status_bar, status_lable):
        status_bar.setMinimum(0)
        status_bar.setMaximum(100)
        status_bar.setValue(0)
        status_bar.setFormat("Ready")
        self.status_bar = status_bar
        self.status_lable = status_lable

    def vgrid_status_callback(self, percent_complete, lable):
        try:
            self.status_lable.setText(lable)
            message = str(int(percent_complete)) + "%"
            self.status_bar.setFormat(message)

            if percent_complete < 0:
                self.status_bar.setValue(0)
            elif percent_complete > 100:
                self.status_bar.setValue(100)
            else:
                self.status_bar.setValue(int(percent_complete))

            self.iface.statusBarIface().showMessage(message)

            # print("status_callback(" + message + ")")
        except:
            print(message)

        # add handling of "Close" button
        return 0

########################################################
# Geohash
#########################################################
class vgrid_geohash_dialog(vgrid_dialog, Ui_grid_geohash_form):
    def __init__(self, iface):
        vgrid_dialog.__init__(self, iface)
        self.setupUi(self)
        self.BtnApplyClose.button(QtWidgets.QDialogButtonBox.Apply).clicked.connect(self.run)
        self.BtnOutputFolder.clicked.connect(self.browse_outfile)
        project = QgsProject.instance()
        home_path = project.homePath()
        if not home_path:
            home_path = os.path.expanduser('~')
        self.LinOutputFolder.setText(home_path)
        self.vgrid_set_status_bar(self.status,self.LblStatus)

        # for i in range(1, 31):  # Add integers 1 to 30
        #     self.cboPrec.addItem(str(i))  # Add each integer as a string item
        # self.cboPrec.setCurrentIndex(0)
        # self.cboPrec.setStyleSheet("QComboBox {combobox-popup: 0; }") # To enable the setMaxVisibleItems
        # self.cboPrec.setMaxVisibleItems(10)
        # self.cboPrec.view().setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)

    def browse_outfile(self):
        newname = QFileDialog.getExistingDirectory(None, "Output Folder",self.LinOutputFolder.displayText())

        if newname != None:
            self.LinOutputFolder.setText(newname)

    def run(self):
        outdir = self.LinOutputFolder.displayText()
        prec = self.spinPrecision.value()
        gridgenerator.geohash_grid(prec,outdir)
        return