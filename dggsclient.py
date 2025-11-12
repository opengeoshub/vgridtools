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
from qgis.PyQt.QtWidgets import QWidget, QApplication, QDialog,QDialogButtonBox, QTableWidgetItem, QFileDialog, QMessageBox
from qgis.PyQt.uic import loadUiType
from qgis.core import QgsProject       
from owslib.ogcapi import *  
from .utils import tr
from PyQt5.QtCore import Qt
from PyQt5 import QtCore, QtGui, QtWidgets

from urllib.request import urlopen
import json
import requests
import ssl
import urllib.request
import zipfile

FORM_CLASS, _ = loadUiType(os.path.join(os.path.dirname(__file__), "ui/dggsclient.ui"))


class DGGSClientWidget(QDialog, FORM_CLASS):
    def __init__(self, vgridtools, settingsDialog, iface, parent):
        super(DGGSClientWidget, self).__init__(parent)
        self.setupUi(self)
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
        self.ChkSaveShapefile.stateChanged.connect(self.toggleouputfolder)

        columns = ['Zone ID', 'Map', 'Data', 'Zone Geometry']
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

        self.cboFormat.setEnabled(False)
        self.set_status_bar(self.status,self.LblStatus)

        self.cboServerName.setStyleSheet("QComboBox {combobox-popup: 0; }") # To enable the setMaxVisibleItems
        self.cboServerName.setMaxVisibleItems(10)
        self.cboServerName.view().setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)

        self.TblZones.doubleClicked.connect(self.onDoubleClick)
        self.BtnApplyClose.button(QtWidgets.QDialogButtonBox.Apply).clicked.connect(self.run)
        self.BtnApplyClose.button(QtWidgets.QDialogButtonBox.Close).clicked.connect(self.closeDialog)

        self.dggs_servers = [
            'GNOSIS Map Server'
            ]

        self.dggs_urls = [
            'https://maps.gnosis.earth/ogcapi',
        ]
        self.cboServerName.addItems(self.dggs_servers)

    def closeDialog(self):
        QApplication.setOverrideCursor(Qt.ArrowCursor)
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
                for col in collections:
                    self.cboCollections.addItem(col['id'], col['id'])  # Store ID as data
                self._updating_combos = False
                
                if len(collections) > 0:
                    message = str(len(collections)) + " collections loaded"
                    MessageBar = self.iface.messageBar()
                    MessageBar.pushMessage(message, 0, 2)
        except Exception as e:
            QMessageBox.warning(None, "Connection Error", "Failed to load collections:\n" + str(e))

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
                for item in dggs_items:
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
                self._updating_combos = False
        except Exception as e:
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
                if len(zones) > 0:
                    for i, zone in enumerate(zones):
                        self.TblZones.insertRow(i)
                        
                        # Extract data from zone
                        zone_id = None
                        zone_map = None
                        zone_data = None
                        zone_geometry = None
                        
                        if isinstance(zone, dict):
                            # Get Zone ID
                            zone_id = zone.get('id') or zone.get('zone_id') or zone.get('zoneId')
                            if not zone_id and 'properties' in zone:
                                zone_id = (zone['properties'].get('id') or 
                                          zone['properties'].get('zone_id') or
                                          zone['properties'].get('zoneId'))
                            
                            # Get Map
                            zone_map = zone.get('map')
                            if not zone_map and 'properties' in zone:
                                zone_map = zone['properties'].get('map')
                            
                            # Get Data
                            zone_data = zone.get('data')
                            if not zone_data and 'properties' in zone:
                                zone_data = zone['properties'].get('data')
                            # If data is a dict, convert to JSON string
                            if isinstance(zone_data, dict):
                                zone_data = json.dumps(zone_data)
                            
                            # Get Zone Geometry
                            zone_geometry = zone.get('geometry')
                            if not zone_geometry and 'properties' in zone:
                                zone_geometry = zone['properties'].get('geometry')
                            # If geometry is a dict, convert to JSON string
                            if isinstance(zone_geometry, dict):
                                zone_geometry = json.dumps(zone_geometry)
                        elif isinstance(zone, str):
                            zone_id = zone
                        
                        # Set default values if not found
                        if not zone_id:
                            zone_id = "Zone " + str(i + 1)
                        if zone_map is None:
                            zone_map = ""
                        if zone_data is None:
                            zone_data = ""
                        if zone_geometry is None:
                            zone_geometry = ""
                        
                        # Create items for each column
                        # Column 0: Zone ID
                        zone_id_item = QTableWidgetItem(str(zone_id))
                        # Store full zone data as UserRole if it's a dict
                        if isinstance(zone, dict):
                            zone_id_item.setData(QtCore.Qt.UserRole, zone)
                        else:
                            zone_id_item.setData(QtCore.Qt.UserRole, zone_id)
                        zone_id_item.setFlags(QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled)
                        self.TblZones.setItem(i, 0, zone_id_item)
                        
                        # Column 1: Map
                        map_item = QTableWidgetItem(str(zone_map))
                        map_item.setFlags(QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled)
                        self.TblZones.setItem(i, 1, map_item)
                        
                        # Column 2: Data
                        data_item = QTableWidgetItem(str(zone_data))
                        data_item.setFlags(QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled)
                        self.TblZones.setItem(i, 2, data_item)
                        
                        # Column 3: Zone Geometry
                        geometry_item = QTableWidgetItem(str(zone_geometry))
                        geometry_item.setFlags(QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled)
                        self.TblZones.setItem(i, 3, geometry_item)
                    
                    message = str(len(zones)) + " zones loaded"
                    self.LblZones.setText(message)
                    MessageBar = self.iface.messageBar()
                    MessageBar.pushMessage(message, 0, 2)
                    self.Filter.setEnabled(True)
                else:
                    self.LblZones.setText("0 zones loaded")
                    self.Filter.setEnabled(False)
        except Exception as e:
            QMessageBox.warning(None, "Connection Error", "Failed to load zones:\n" + str(e))
            self.LblZones.setText("Error loading zones")

    def togglesave(self):
        self.ChkSaveShapefile.setChecked(self.cboFormat.currentIndex()>0)

    def browse_outfile(self):
        newname = QFileDialog.getExistingDirectory(None, "Output Folder",self.LinOutputFolder.displayText())
        if newname != None:
            self.LinOutputFolder.setText(newname)

    def toggleouputfolder(self,state):
        if state > 0:
            self.LinOutputFolder.setEnabled(True)
            self.BtnOutputFolder.setEnabled(True)
            self.cboFormat.setEnabled(True)
        else:
            self.LinOutputFolder.setEnabled(False)
            self.BtnOutputFolder.setEnabled(False)
            self.cboFormat.setEnabled(False)

    def onDoubleClick(self, index):
        """Handle double-click on zone item to display zone details"""
        row = index.row()
        item = self.TblZones.item(row, 0)
        if item is not None:
            # Get zone data from stored data
            zone_data = item.data(QtCore.Qt.UserRole)
            
          
    def run(self):
        self.loaddggs()

    def loaddggs(self):
        self.set_status_bar(self.status,self.LblStatus)
        self.LblStatus.clear()
        idx = self.cboServerName.currentIndex()
        # opendata_url =self.wfs_urls[idx]
        opendata_url =self.TxtURL.text().strip()
        outdir = self.LinOutputFolder.displayText()
        wfs_format  = self.cboFormat.currentText().lower()
        unzip_folder = ''
        ext = "." + wfs_format
        if (wfs_format == "shape-zip"):
            ext = ".zip"
        elif (wfs_format == "xlsx"):
            wfs_format = "excel2007"
        elif (wfs_format == "gml"):
            wfs_format = "gml3"

        layernames = []
        rows = []
        for index in self.TblZones.selectedIndexes():
            if index.row() not in rows:
                rows.append(index.row())
        for row_index in rows:
            item = self.TblZones.item(row_index, 0)
            if item is not None:
                # Get collection ID from stored data (UserRole), fallback to text if not available
                collection_id = item.data(QtCore.Qt.UserRole)
                if collection_id:
                    layernames.append(collection_id)
                else:
                    layernames.append(item.text())
        # print(rows)
        if layernames is not None:
            ii = 0
            for layer_name in layernames:
                # uri = opendata_url + "/wfs?version=1.0.0&request=GetFeature&format_options=CHARSET:UTF-8&typename="+ str(layer_name)
                uri = opendata_url + "/wfs?request=GetFeature&format_options=CHARSET:UTF-8&typename="+ str(layer_name)
               #uri = opendata_url + "/ows?service=DGGS&request=GetFeature&typename="+ str(layer_name)
                if (not self.ChkSaveShapefile.isChecked()):
                    try:
                        self.iface.addVectorLayer(uri, layer_name,"DGGS")
                        self.iface.zoomToActiveLayer()
                        ii+=1
                        self.LblStatus.setText (str(ii)+"/ "+ str(len(layernames)) + " layers added")
                        percent_complete = ii/len(layernames)*100
                        self.status_bar.setValue(int(round(percent_complete)))
                        message = str(int(round(percent_complete))) + "%"
                        self.status.setFormat(message)
                    except Exception as e:
                        QMessageBox.critical(self.iface.mainWindow(), "DGGS", e)
                else:
                    #uri = opendata_url + "/ows?service=DGGS&request=GetFeature&typename="+ str(layer_name)
                    uri += '&outputFormat='
                    uri += wfs_format
                    try:
                        if wfs_format == "shape-zip":
                            headers = ""
                            contents = requests.get(uri, headers=headers, stream=True, allow_redirects=True, verify = False)
                            filename = outdir + "/"+ str(layer_name).replace(":","_") + ext
                            # total_size = int(len(contents.content))
                            # total_size_MB = round(total_size*10**(-6),2)
                            # chunk_size = int(total_size/100)
                            if  (contents.status_code == 200):
                                f = open(filename, 'wb')
                                for chunk in contents.iter_content(chunk_size = 1024):
                                    if not chunk:
                                        break
                                    f.write(chunk)
                                f.close()
                                unzip_folder = filename.replace('.zip','')
                                if not os.path.exists (unzip_folder):
                                    os.mkdir(unzip_folder)
                                with zipfile.ZipFile(filename) as zip_ref:
                                    zip_ref.extractall(unzip_folder)
                                wholelist = os.listdir(unzip_folder)
                                i = 0
                                for file in wholelist:
                                    if ".cst" in file:
                                        new_file_name = os.path.splitext(file)[0]+'.cpg'
                                        if not os.path.exists (os.path.join(unzip_folder,new_file_name)):
                                            os.rename(os.path.join(unzip_folder,file),os.path.join(unzip_folder,new_file_name))
                                    if ".shp" in file:
                                        fileroute= unzip_folder+'/'+file
                                        layer = QgsVectorLayer(fileroute,file[:-4],"ogr")
                                        if (layer.isValid()):
                                            QgsProject.instance().addMapLayer(layer)
                                            self.iface.zoomToActiveLayer()
                                            ii+=1
                                            self.LblStatus.setText (str(ii)+"/ "+ str(len(layernames)) + " layers saved and added")
                                            percent_complete = ii/len(layernames)*100
                                            self.status_bar.setValue(int(round(percent_complete)))
                                            message = str(int(round(percent_complete))) + "%"
                                            self.status.setFormat(message)
                        else:
                            filename = outdir + "/"+ str(layer_name).replace(":","_") + ext
                            ssl._create_default_https_context = ssl._create_unverified_context
                            #urllib.request.urlretrieve(uri,filename,context=ssl._create_unverified_context())
                            # print (uri)
                            urllib.request.urlretrieve(uri,filename)
                            layer = QgsVectorLayer(filename, QFileInfo(filename).baseName(), 'ogr')
                            layer.dataProvider().setEncoding(u'UTF-8')
                            if (layer.isValid()):
                                QgsProject.instance().addMapLayer(layer)
                                self.iface.zoomToActiveLayer()
                                ii+=1
                                self.LblStatus.setText (str(ii)+"/ "+ str(len(layernames)) + " layers saved and added")
                                percent_complete = ii/len(layernames)*100
                                self.status_bar.setValue(int(round(percent_complete)))
                                message = str(int(round(percent_complete))) + "%"
                                self.status.setFormat(message)
                    except Exception as e:
                        # qgis.utils.iface.addVectorLayer(uri, str(layer_name),"DGGS")
                        QMessageBox.critical(self.iface.mainWindow(), "DGGS", str(e))
        return

    def loadogc(self):
        self.set_status_bar(self.status,self.LblStatus)
        self.LblStatus.clear()
        idx = self.cboServerName.currentIndex()
        # opendata_url =self.ogc_urls[idx]
        opendata_url =self.TxtURL.text().strip()
        outdir = self.LinOutputFolder.displayText()
        ogc_format  = self.cboFormat.currentText().lower()
        ext = "." + ogc_format
        # if (ogc_format == "json"):
        #     ogc_format = "application/json"
        if (ogc_format == "kml"):
            ogc_format = "application%2Fvnd.google-earth.kml%2Bxml"
        elif (ogc_format == "csv"):
            ogc_format = "text%2Fcsv"
        elif (ogc_format == "gml"):
            ogc_format = "application%2Fgml%2Bxml%3Bversion%3D3.2"

        layernames = []
        rows = []
        for index in self.TblZones.selectedIndexes():
            if index.row() not in rows:
                rows.append(index.row())
        for row_index in rows:
            item = self.TblZones.item(row_index, 0)
            if item is not None:
                # Get collection ID from stored data (UserRole), fallback to text if not available
                collection_id = item.data(QtCore.Qt.UserRole)
                if collection_id:
                    layernames.append(collection_id)
                else:
                    layernames.append(item.text())
        # print(rows)
        # print(layernames)
        ii = 0
        if layernames is not None:
            for layer_name in layernames:
                if (not self.ChkSaveShapefile.isChecked()):
                    try:
                        uri = opendata_url + "/collections/"+ str(layer_name) + '/items?f=json'
                        # print (uri)
                        ogc_layer = QgsVectorLayer(uri, layer_name)
                        if (ogc_layer.isValid()):
                            QgsProject.instance().addMapLayer(ogc_layer)
                            self.iface.zoomToActiveLayer()
                            # success = qgis.utils.iface.addVectorLayer(uri, layer_name,"OGC API - Features")
                            ii+=1
                            self.LblStatus.setText (str(ii)+"/ "+ str(len(layernames)) + " layers added")
                            percent_complete = ii/len(layernames)*100
                            self.status_bar.setValue(int(round(percent_complete)))
                            message = str(int(round(percent_complete))) + "%"
                            self.status.setFormat(message)

                    except Exception as e:
                        QMessageBox.critical(self.iface.mainWindow(), "OGC API Feature", str(e))
                else:
                    try:
                        uri = opendata_url + "/collections/"+ str(layer_name) + '/items?f=' + ogc_format
                        # print (uri)
                        filename = outdir + "/"+ str(layer_name).replace(":","_") + ext
                        ssl._create_default_https_context = ssl._create_unverified_context
                        #urllib.request.urlretrieve(uri,filename,context=ssl._create_unverified_context())
                        urllib.request.urlretrieve(uri,filename)
                        layer = QgsVectorLayer(filename, QFileInfo(filename).baseName(), 'ogr')
                        layer.dataProvider().setEncoding(u'UTF-8')
                        if (layer.isValid()):
                            QgsProject.instance().addMapLayer(layer)
                            self.iface.zoomToActiveLayer()
                            ii+=1
                            self.LblStatus.setText (str(ii)+"/ "+ str(len(layernames)) + " layers saved and added")
                            percent_complete = ii/len(layernames)*100
                            self.status_bar.setValue(int(round(percent_complete)))
                            message = str(int(round(percent_complete))) + "%"
                            self.status.setFormat(message)

                    except Exception as e:
                        QMessageBox.critical(self.iface.mainWindow(), "OGC API Feature", str(e))
        return
    
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