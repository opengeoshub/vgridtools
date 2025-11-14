"""
/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""

import os
from qgis.PyQt.QtWidgets import QWidget, QApplication, QDialog,QDialogButtonBox, QTableWidgetItem, QFileDialog, QMessageBox, QMenu
from qgis.PyQt.uic import loadUiType
from qgis.core import QgsProject, QgsVectorLayer       
from owslib.ogcapi import *  
from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtGui import QDesktopServices, QColor
from PyQt5 import QtCore, QtWidgets

from urllib.request import urlopen
import json
import ssl
import urllib.request

FORM_CLASS, _ = loadUiType(os.path.join(os.path.dirname(__file__), "ui/dggsclient.ui"))


class DGGSClientWidget(QDialog, FORM_CLASS):
    def __init__(self, vgridtools, settingsDialog, iface, parent):
        super(DGGSClientWidget, self).__init__(parent)
        self.setupUi(self)
        # Make dialog resizable
        self.setMinimumSize(500, 400)
        self.iface = iface
        self.canvas = iface.mapCanvas()
        self.vgridtools = vgridtools
        self.settings = settingsDialog
        self.set_status_bar(self.status,self.LblStatus)


        self.BtnApplyClose.button(QDialogButtonBox.Close).setAutoDefault(False)
        self.Filter.setFocus(True)
        QWidget.setTabOrder(self.Filter, self.TblZones)
        self.BtnOutputFolder.clicked.connect(self.browse_outfile)
        self.BtnConnect.clicked.connect(self.readdggs)

        project = QgsProject.instance()
        home_path = project.homePath()
        if not home_path:
            home_path = os.path.expanduser('~')
        self.LinOutputFolder.setText(home_path)

        columns = ['Zone ID', 'Data', 'DGGS-JSON', 'Zone Geometry']
        self.TblZones.setColumnCount(len(columns))
        self.TblZones.setHorizontalHeaderLabels(columns)
        self.TblZones.resizeColumnsToContents()
        self.TblZones.resizeRowsToContents()
        self.TblZones.horizontalHeader().setStretchLastSection(True)


        self.Filter.setEnabled(False)
        self.Filter.valueChanged.connect(self.updateDGGSTable)

        # self.TblZones.setDragDropMode(QAbstractItemView.DragOnly)
        # self.TblZones.setDragEnabled(True)

        self.cboServerName.currentIndexChanged.connect(self.updateURL)
        self.cboServerName.setCurrentIndex(-1)
        
        # Connect collection and DGGS combobox handlers
        self.cboCollections.currentIndexChanged.connect(self.onCollectionChanged)
        self.cboDGGS.currentIndexChanged.connect(self.onDGGSChanged)
        
        # Flag to prevent handlers from firing during programmatic changes
        self._updating_combos = False

        self.cboServerName.setStyleSheet("QComboBox {combobox-popup: 0; }") # To enable the setMaxVisibleItems
        self.cboServerName.setMaxVisibleItems(10)
        self.cboServerName.view().setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)

        self.TblZones.itemSelectionChanged.connect(self.onZoneSelectionChanged)
        self.TblZones.itemClicked.connect(self.onTableItemClicked)
        # Enable context menu
        self.TblZones.setContextMenuPolicy(Qt.CustomContextMenu)
        self.TblZones.customContextMenuRequested.connect(self.showContextMenu)
        self.BtnApplyClose.button(QtWidgets.QDialogButtonBox.Close).clicked.connect(self.closeDialog)

        self.dggs_servers = [
            'GNOSIS Map Server',
            'Custom',
            ]

        self.dggs_urls = [
            'https://maps.gnosis.earth/ogcapi',
            '',
        ]
        self.cboServerName.addItems(self.dggs_servers)

    def closeDialog(self):
        # Clear UI elements when dialog is closed
        self.cboCollections.clear()
        self.cboDGGS.clear()
        self.TxtAPI.clear()
        self.TblZones.setRowCount(0)
        self.LblStatus.clear()
        self.set_status_bar(self.status,self.LblStatus)
        
        # Restore cursor
        QApplication.setOverrideCursor(Qt.ArrowCursor)
        QApplication.restoreOverrideCursor()
        
        self.close()

    def updateDGGSTable(self):
        name = self.Filter.text().lower()
        if (name != '' and name is not None):
            visible_row = 0
            for row in range(self.TblZones.rowCount()):
                # Search across all columns (Zone ID, Map, Data, Zone Geometry)
                match = False
                for col in range(self.TblZones.columnCount()):
                    item = self.TblZones.item(row, col)
                    if item and name in item.text().lower():
                        match = True
                        break
                # Hide row if search term not found in any column
                self.TblZones.setRowHidden(row, not match)
                if match:
                    visible_row += 1
            if visible_row < self.TblZones.rowCount():
                self.LblZones.setText(str(visible_row) + ' zones filtered')
        else:
            for row in range(self.TblZones.rowCount()):
                self.TblZones.setRowHidden(row, False )
            self.LblZones.setText(str(self.TblZones.rowCount()) + ' zones loaded')

    def updateURL(self):
        self.TblZones.setRowCount(0)
        self.Filter.clear()
        self.TxtURL.clear()
        self.LblStatus.clear()
        self.LblZones.clear()
        # Clear comboboxes
        self._updating_combos = True
        self.cboCollections.clear()
        self.cboDGGS.clear()
        self._updating_combos = False
        idx = self.cboServerName.currentIndex()
        if (self.cboServerName.currentIndex()>-1):
            self.TxtURL.setText(self.dggs_urls[idx])

    def readdggs(self):
        try:
            collections_url = self.TxtURL.text().strip().rstrip('/') + '/collections?f=json'
            self.TxtAPI.setText(collections_url)

            self.TblZones.setRowCount(0)
            self.LblStatus.clear()
            self.set_status_bar(self.status,self.LblStatus)
            self.BtnConnect.setEnabled(False)
            # Clear comboboxes
            self._updating_combos = True
            self.cboCollections.clear()
            self.cboDGGS.clear()
            self._updating_combos = False
            # Fetch collections and populate cboCollections
            url = self.TxtURL.text().strip()     
            self.load_collections(url)
            # Update API endpoint URL
            self.BtnConnect.setEnabled(True)
        except Exception as e:
            self.BtnConnect.setEnabled(True)
            return

    def fill_table_widget(self,table_widget, url, status_callback = None):
        table_widget.setRowCount(0)
        
        self.Filter.clear()
        self.LblZones.clear()
        # url_landingpage = self.ogc_urls[idx]
        url_landingpage = url
        # url_landingpage = url + '/?f=json'
        url_collections = url +'/collections?f=json'
        try:
            collections_response = urlopen(url_collections)
            if collections_response is not None:
                # storing the JSON response from url in data
                data_json = json.loads(collections_response.read())
                # Get only first-level collections from href, exclude nested ones like /collections/NaturalEarth/dggs
                all_collections = data_json.get('collections', [])
                collections = []
                for col in all_collections:
                    # Get href from collection (could be in 'links' array or directly as 'href')
                    href = None
                    if 'href' in col:
                        href = col['href']
                    elif 'links' in col:
                        # Look for self link in links array
                        for link in col['links']:
                            if link.get('rel') == 'self' or link.get('rel') == 'collection':
                                href = link.get('href')
                                break
                    
                    if href:
                        # Extract collection ID from href like "/ogcapi/collections/NaturalEarth"
                        # Remove query parameters and fragments if present
                        href_clean = href.split('?')[0].split('#')[0].rstrip('/')
                        href_parts = [p for p in href_clean.split('/') if p]  # Remove empty parts
                        
                        # Find 'collections' in the path and get the next segment as collection ID
                        # href format: /ogcapi/collections/NaturalEarth (first-level)
                        # vs: /ogcapi/collections/NaturalEarth/dggs (nested - exclude)
                        try:
                            collections_idx = href_parts.index('collections')
                            if collections_idx + 1 < len(href_parts):
                                collection_id = href_parts[collections_idx + 1]
                                # Only include if it's first-level:
                                # 1. No additional path segments after collection name
                                # 2. Collection ID doesn't contain ':' (exclude NaturalEarth:raster, etc.)
                                if (collections_idx + 2 >= len(href_parts) and collection_id and 
                                    ':' not in collection_id):
                                    collections.append({
                                        'id': collection_id,
                                        'href': href
                                    })
                        except ValueError:
                            # 'collections' not found in path, skip
                            pass
                
                if len(collections) > 0:
                    i = 0
                    for i in range (len(collections)):
                        table_widget.insertRow(i)
                        collection_id = collections[i]['id']
                        # Display collection ID in the table
                        id_item = QTableWidgetItem(collection_id)
                        # Store collection ID as data (using UserRole) for consistency
                        id_item.setData(QtCore.Qt.UserRole, collection_id)
                        id_item.setFlags( QtCore.Qt.ItemIsSelectable |  QtCore.Qt.ItemIsEnabled )
                        table_widget.setItem(i, 0, id_item)
                        status_callback(((i+1)/len(collections))*100,None)
                    message = str(i+1) + " layers loaded"
                    MessageBar = self.iface.messageBar()
                    MessageBar.pushMessage(message, 0, 2)
                    self.LblZones.setText(message)
                    self.Filter.setEnabled(True)
                    self.Filter.setFocus(True)
                else:
                    message = " 0 layer loaded"
                    self.LblZones.setText(message)
                    MessageBar = self.iface.messageBar()
                    MessageBar.pushMessage(message, 0, 2)
                    self.Filter.setEnabled(False)
                    self.Filter.setFocus(False)

            else: return
        except Exception as e:
            QMessageBox.warning(None, "Connection Error",str(e))
            return
        return

    def load_collections(self, url):
        """Load first-level collections into cboCollections combobox"""
        # Set cursor to wait
        QApplication.setOverrideCursor(Qt.WaitCursor)
        
        # Update status - loading
        self.LblStatus.setText("Loading collections...")
        self.status_bar.setValue(0)
        self.status_bar.setFormat("0%")
        
        try:
            url_collections = url.rstrip('/') + '/collections?f=json'
            collections_response = urlopen(url_collections)
            if collections_response is not None:
                data_json = json.loads(collections_response.read())
                all_collections = data_json.get('collections', [])
                collections = []
                for col in all_collections:
                    # Get href from collection
                    href = None
                    if 'href' in col:
                        href = col['href']
                    elif 'links' in col:
                        for link in col['links']:
                            if link.get('rel') == 'self' or link.get('rel') == 'collection':
                                href = link.get('href')
                                break
                    
                    if href:
                        href_clean = href.split('?')[0].split('#')[0].rstrip('/')
                        href_parts = [p for p in href_clean.split('/') if p]
                        try:
                            collections_idx = href_parts.index('collections')
                            if collections_idx + 1 < len(href_parts):
                                collection_id = href_parts[collections_idx + 1]
                                if (collections_idx + 2 >= len(href_parts) and collection_id and 
                                    ':' not in collection_id):
                                    collections.append({
                                        'id': collection_id,
                                        'href': href
                                    })
                        except ValueError:
                            pass
                
                # Populate cboCollections
                self._updating_combos = True
                self.cboCollections.clear()
                total_collections = len(collections)
                for i, col in enumerate(collections):
                    self.cboCollections.addItem(col['id'], col['id'])  # Store ID as data
                    # Update progress
                    if total_collections > 0:
                        percent = int(((i + 1) / total_collections) * 100)
                        self.status_bar.setValue(percent)
                        self.status_bar.setFormat(str(percent) + "%")
                self._updating_combos = False
                self.cboCollections.setCurrentIndex(-1)
                
                if len(collections) > 0:
                    message = str(len(collections)) + " collections loaded"
                    MessageBar = self.iface.messageBar()
                    MessageBar.pushMessage(message, 0, 2)
                    # Update status - completed
                    self.LblStatus.setText("Collections loaded")
                    self.status_bar.setValue(100)
                    self.status_bar.setFormat("100%")
                else:
                    # Update status - no collections
                    self.LblStatus.setText("No collections found")
                    self.status_bar.setValue(0)
                    self.status_bar.setFormat("0%")
        except Exception as e:
            # Update status - error
            self.LblStatus.setText("Error loading collections")
            self.status_bar.setValue(0)
            self.status_bar.setFormat("Error")
            QMessageBox.warning(None, "Connection Error", "Failed to load collections:\n" + str(e))
        finally:
            # Restore cursor to default
            QApplication.setOverrideCursor(Qt.ArrowCursor)

    def onCollectionChanged(self, index):
        """Handle collection selection change - load DGGS items into cboDGGS"""
        if self._updating_combos or index < 0:
            return
        
        collection_id = self.cboCollections.itemData(index)
        if not collection_id:
            collection_id = self.cboCollections.currentText()
        
        # Clear DGGS combobox and zones table
        self.cboDGGS.clear()
        self.TblZones.setRowCount(0)
        self.LblZones.clear()
        
        # Fetch /dggs endpoint
        base_url = self.TxtURL.text().strip()
        if not base_url:
            return
        
        dggs_url = base_url.rstrip('/') + "/collections/" + collection_id + "/dggs"
        # Update API endpoint URL
        self.TxtAPI.setText(dggs_url)
        
        # Update status - loading
        self.LblStatus.setText("Loading DGGS items...")
        self.status_bar.setValue(0)
        self.status_bar.setFormat("0%")
        
        try:
            response = urlopen(dggs_url)
            if response is not None:
                data_json = json.loads(response.read())
                # Extract DGGS items - could be in 'dggrs' or 'items' or similar
                dggs_items = []
                if 'dggrs' in data_json:
                    dggs_items = data_json['dggrs']
                elif 'items' in data_json:
                    dggs_items = data_json['items']
                elif isinstance(data_json, list):
                    dggs_items = data_json
                
                # Populate cboDGGS
                self._updating_combos = True
                total_items = len(dggs_items)
                for i, item in enumerate(dggs_items):
                    # Get DGGS ID - could be 'id', 'name', or in 'properties'
                    dggs_id = None
                    if isinstance(item, dict):
                        dggs_id = item.get('id') or item.get('name')
                        if not dggs_id and 'properties' in item:
                            dggs_id = item['properties'].get('id') or item['properties'].get('name')
                    elif isinstance(item, str):
                        dggs_id = item
                    
                    if dggs_id:
                        self.cboDGGS.addItem(dggs_id, dggs_id)
                    
                    # Update progress
                    if total_items > 0:
                        percent = int(((i + 1) / total_items) * 100)
                        self.status_bar.setValue(percent)
                        self.status_bar.setFormat(str(percent) + "%")
                
                self._updating_combos = False
                self.cboDGGS.setCurrentIndex(-1)
                
                # Update status - completed
                self.LblStatus.setText("DGGS items loaded")
                self.status_bar.setValue(100)
                self.status_bar.setFormat("100%")
        except Exception as e:
            self.LblStatus.setText("Error loading DGGS items")
            self.status_bar.setValue(0)
            self.status_bar.setFormat("Error")
            QMessageBox.warning(None, "Connection Error", "Failed to load DGGS items:\n" + str(e))

    def onDGGSChanged(self, index):
        """Handle DGGS selection change - load zones into TblZones"""
        if self._updating_combos or index < 0:
            return
        
        dggs_id = self.cboDGGS.itemData(index)
        if not dggs_id:
            dggs_id = self.cboDGGS.currentText()
        
        collection_id = self.cboCollections.itemData(self.cboCollections.currentIndex())
        if not collection_id:
            collection_id = self.cboCollections.currentText()
        
        # Clear zones table
        self.TblZones.setRowCount(0)
        self.LblZones.clear()
        
        # Fetch /zones endpoint
        base_url = self.TxtURL.text().strip()
        if not base_url:
            return
        
        zones_url = base_url.rstrip('/') + "/collections/" + collection_id + "/dggs/" + dggs_id + "/zones"
        # Update API endpoint URL
        self.TxtAPI.setText(zones_url)
        
        # Update status - loading
        self.LblStatus.setText("Loading zones...")
        self.status_bar.setValue(0)
        self.status_bar.setFormat("0%")
        
        try:
            response = urlopen(zones_url)
            if response is not None:
                data_json = json.loads(response.read())
                # Extract zones - could be in 'zones', 'items', 'features', or direct array
                zones = []
                if 'zones' in data_json:
                    zones = data_json['zones']
                elif 'items' in data_json:
                    zones = data_json['items']
                elif 'features' in data_json:
                    zones = data_json['features']
                elif isinstance(data_json, list):
                    zones = data_json
                
                # Populate TblZones with 4 columns: Zone ID, Map, Data, Zone Geometry
                total_zones = len(zones)
                if len(zones) > 0:
                    for i, zone in enumerate(zones):
                        self.TblZones.insertRow(i)
                        
                        # Extract data from zone
                        zone_id = None
                        
                        if isinstance(zone, dict):
                            # Get Zone ID
                            zone_id = zone.get('id') or zone.get('zone_id') or zone.get('zoneId')
                            if not zone_id and 'properties' in zone:
                                zone_id = (zone['properties'].get('id') or 
                                          zone['properties'].get('zone_id') or
                                          zone['properties'].get('zoneId'))
                        elif isinstance(zone, str):
                            zone_id = zone
                        
                        # Set default values if not found
                        if not zone_id:
                            zone_id = "Zone " + str(i + 1)
                        
                        # Create items for each column
                        # Column 0: Zone ID (as hyperlink)
                        zone_url = base_url.rstrip('/') + "/collections/" + collection_id + "/dggs/" + dggs_id + "/zones/" + zone_id
                        zone_id_item = QTableWidgetItem(str(zone_id))
                        zone_id_item.setFlags(QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled)
                        # Store zone URL in item data
                        zone_id_item.setData(QtCore.Qt.UserRole, zone_url)
                        # Also store full zone data if it's a dict (for backward compatibility)
                        if isinstance(zone, dict):
                            zone_id_item.setData(QtCore.Qt.UserRole + 1, zone)
                        else:
                            zone_id_item.setData(QtCore.Qt.UserRole + 1, zone_id)
                        # Style as link (blue color)
                        zone_id_item.setForeground(QColor(0, 0, 255))  # Blue color
                        self.TblZones.setItem(i, 0, zone_id_item)
                        
                        # Column 1: Data (as hyperlink)
                        data_url = base_url.rstrip('/') + "/collections/" + collection_id + "/dggs/" + dggs_id + "/zones/" + zone_id + '/data'
                        data_item = QTableWidgetItem("Data")
                        data_item.setFlags(QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled)
                        # Store URL in item data
                        data_item.setData(QtCore.Qt.UserRole, data_url)
                        # Style as link (blue color)
                        data_item.setForeground(QColor(0, 0, 255))  # Blue color
                        self.TblZones.setItem(i, 1, data_item)
                        
                        # Column 2: DGGS-JSON (as hyperlink)
                        dggs_json_url = base_url.rstrip('/') + "/collections/" + collection_id + "/dggs/" + dggs_id + "/zones/" + zone_id + '/data.json'
                        dggs_json_item = QTableWidgetItem("DGGS-JSON")
                        dggs_json_item.setFlags(QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled)
                        # Store URL in item data
                        dggs_json_item.setData(QtCore.Qt.UserRole, dggs_json_url)
                        # Style as link (blue color)
                        dggs_json_item.setForeground(QColor(0, 0, 255))  # Blue color
                        self.TblZones.setItem(i, 2, dggs_json_item)
                        
                        # Column 3: Zone Geometry (as hyperlink)
                        geometry_url = base_url.rstrip('/') + "/collections/" + collection_id + "/dggs/" + dggs_id + "/zones/" + zone_id + '.geojson'
                        geometry_item = QTableWidgetItem("GeoJSON")
                        geometry_item.setFlags(QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled)
                        # Store URL in item data
                        geometry_item.setData(QtCore.Qt.UserRole, geometry_url)
                        # Style as link (blue color)
                        geometry_item.setForeground(QColor(0, 0, 255))  # Blue color
                        self.TblZones.setItem(i, 3, geometry_item)
                        
                        # Update progress
                        if total_zones > 0:
                            percent = int(((i + 1) / total_zones) * 100)
                            self.status_bar.setValue(percent)
                            self.status_bar.setFormat(str(percent) + "%")
                    
                    message = str(len(zones)) + " zones loaded"
                    self.LblZones.setText(message)
                    MessageBar = self.iface.messageBar()
                    MessageBar.pushMessage(message, 0, 2)
                    self.Filter.setEnabled(True)
                    # Update status - completed
                    self.LblStatus.setText("Zones loaded")
                    self.status_bar.setValue(100)
                    self.status_bar.setFormat("100%")
                else:
                    self.LblZones.setText("0 zones loaded")
                    self.Filter.setEnabled(False)
                    # Update status - no zones
                    self.LblStatus.setText("No zones found")
                    self.status_bar.setValue(0)
                    self.status_bar.setFormat("0%")
        except Exception as e:
            self.LblStatus.setText("Error loading zones")
            self.status_bar.setValue(0)
            self.status_bar.setFormat("Error")
            QMessageBox.warning(None, "Connection Error", "Failed to load zones:\n" + str(e))
            self.LblZones.setText("Error loading zones")

    def browse_outfile(self):
        newname = QFileDialog.getExistingDirectory(None, "Output Folder",self.LinOutputFolder.displayText())
        if newname != None:
            self.LinOutputFolder.setText(newname)

    def onTableItemClicked(self, item):
        """Handle clicks on table items - open URLs for Zone ID, Data, DGGS-JSON and GeoJSON columns"""
        column = item.column()
        # Check if clicked on Zone ID (column 0), Data (column 1), DGGS-JSON (column 2) or GeoJSON (column 3)
        if column == 0 or column == 1 or column == 2 or column == 3:
            url = item.data(QtCore.Qt.UserRole)
            if url:
                url_obj = QUrl(url)
                if url_obj.isValid():
                    QDesktopServices.openUrl(url_obj)

    def onZoneSelectionChanged(self):
        """Handle zone row selection - update TxtAPI with zone URL"""
        selected_items = self.TblZones.selectedItems()
        if selected_items and len(selected_items) > 0:
            # Get the first selected row
            row = selected_items[0].row()
            item = self.TblZones.item(row, 0)
            if item is not None:
                zone_id = item.text()
                # Get collection_id and dggs_id
                collection_id = self.cboCollections.itemData(self.cboCollections.currentIndex())
                if not collection_id:
                    collection_id = self.cboCollections.currentText()
                
                dggs_id = self.cboDGGS.itemData(self.cboDGGS.currentIndex())
                if not dggs_id:
                    dggs_id = self.cboDGGS.currentText()
                
                base_url = self.TxtURL.text().strip()
                if base_url and collection_id and dggs_id and zone_id:
                    # Construct zone URL: /collections/{collection_id}/dggs/{dggs_id}/zones/{zone_id}
                    zone_url = base_url.rstrip('/') + "/collections/" + collection_id + "/dggs/" + dggs_id + "/zones/" + zone_id
                    self.TxtAPI.setText(zone_url)

    def showContextMenu(self, position):
        """Show context menu for table zones"""
        item = self.TblZones.itemAt(position)
        if item is None:
            return
        
        row = item.row()
        zone_id_item = self.TblZones.item(row, 0)
        if zone_id_item is None:
            return
        
        zone_id = zone_id_item.text()
        
        # Get collection_id and dggs_id
        collection_id = self.cboCollections.itemData(self.cboCollections.currentIndex())
        if not collection_id:
            collection_id = self.cboCollections.currentText()
        
        dggs_id = self.cboDGGS.itemData(self.cboDGGS.currentIndex())
        if not dggs_id:
            dggs_id = self.cboDGGS.currentText()
        
        base_url = self.TxtURL.text().strip()
        if not base_url or not collection_id or not dggs_id:
            return
        
        # Create context menu
        menu = QMenu(self)
        
        # Action 1: Download Data
        # action_download_data = menu.addAction("Download Data")
        # action_download_data.triggered.connect(lambda: self.downloadZoneData(zone_id, collection_id, dggs_id, base_url))
        
        # Action 2: Download Zone Geometry
        # action_download_geometry = menu.addAction("Download Zone Geometry")
        # action_download_geometry.triggered.connect(lambda: self.downloadZoneGeometry(zone_id, collection_id, dggs_id, base_url))
        
        # Action 3: Download and Load into QGIS
        action_download_load = menu.addAction("Download Zone Geometry")
        action_download_load.triggered.connect(lambda: self.downloadAndLoadZone(zone_id, collection_id, dggs_id, base_url))
        
        # Show menu at cursor position
        menu.exec_(self.TblZones.viewport().mapToGlobal(position))

    def downloadZoneData(self, zone_id, collection_id, dggs_id, base_url):
        """Download zone data"""
        try:
            data_url = base_url.rstrip('/') + "/collections/" + collection_id + "/dggs/" + dggs_id + "/zones/" + zone_id + '/data'
            
            # Get output folder
            outdir = self.LinOutputFolder.displayText()
            if not outdir:
                outdir = os.path.expanduser('~')
            
            filename = os.path.join(outdir, zone_id + "_data.json")
            
            # Download the file
            ssl._create_default_https_context = ssl._create_unverified_context
            urllib.request.urlretrieve(data_url, filename)
            
            QMessageBox.information(None, "Download Complete", "Data downloaded to:\n" + filename)
            MessageBar = self.iface.messageBar()
            MessageBar.pushMessage("Data downloaded successfully", 0, 2)
        except Exception as e:
            QMessageBox.warning(None, "Download Error", "Failed to download data:\n" + str(e))

    def downloadZoneGeometry(self, zone_id, collection_id, dggs_id, base_url):
        """Download zone geometry as GeoJSON"""
        try:
            geometry_url = base_url.rstrip('/') + "/collections/" + collection_id + "/dggs/" + dggs_id + "/zones/" + zone_id + '.geojson'
            
            # Get output folder
            outdir = self.LinOutputFolder.displayText()
            if not outdir:
                outdir = os.path.expanduser('~')
            
            filename = os.path.join(outdir, zone_id + ".geojson")
            
            # Download the file
            ssl._create_default_https_context = ssl._create_unverified_context
            urllib.request.urlretrieve(geometry_url, filename)
            
            QMessageBox.information(None, "Download Complete", "Zone geometry downloaded to:\n" + filename)
            MessageBar = self.iface.messageBar()
            MessageBar.pushMessage("Zone geometry downloaded successfully", 0, 2)
        except Exception as e:
            QMessageBox.warning(None, "Download Error", "Failed to download zone geometry:\n" + str(e))

    def downloadAndLoadZone(self, zone_id, collection_id, dggs_id, base_url):
        """Download zone geometry and load into QGIS"""
        try:
            geometry_url = base_url.rstrip('/') + "/collections/" + collection_id + "/dggs/" + dggs_id + "/zones/" + zone_id + '.geojson'
            
            # Save to output folder
            outdir = self.LinOutputFolder.displayText()
            if not outdir:
                outdir = os.path.expanduser('~')
            filename = os.path.join(outdir, zone_id + ".geojson")
            
            # Download the file
            ssl._create_default_https_context = ssl._create_unverified_context
            urllib.request.urlretrieve(geometry_url, filename)
            
            # Load the layer in QGIS
            layer = QgsVectorLayer(filename, zone_id, 'ogr')
            layer.dataProvider().setEncoding(u'UTF-8')
            if layer.isValid():
                QgsProject.instance().addMapLayer(layer)
                self.iface.zoomToActiveLayer()
                self.LblStatus.setText("Zone " + zone_id + " loaded")
                MessageBar = self.iface.messageBar()
                MessageBar.pushMessage("Zone " + zone_id + " downloaded and loaded", 0, 2)
            else:
                QMessageBox.warning(None, "Error", "Failed to load zone GeoJSON file")
        except Exception as e:
            QMessageBox.warning(None, "Download Error", "Failed to download and load zone:\n" + str(e))

    def set_status_bar(self, status_bar, status_lable):
        status_bar.setMinimum(0)
        status_bar.setMaximum(100)
        status_bar.setValue(0)
        status_bar.setFormat("Ready")
        self.status_bar = status_bar
        self.status_lable = status_lable

    def status_callback(self, percent_complete, lable):
        try:
            self.status_lable.setText(lable)
            message = str(int(round(percent_complete))) + "%"
            self.status_bar.setFormat(message)

            if percent_complete < 0:
                self.status_bar.setValue(0)
            elif percent_complete > 100:
                self.status_bar.setValue(100)
            else:
                self.status_bar.setValue(int(round(percent_complete)))

            self.iface.statusBarIface().showMessage(message)

            # print("status_callback(" + message + ")")
        except:
            print(message)

        # add handling of "Close" button
        return 0