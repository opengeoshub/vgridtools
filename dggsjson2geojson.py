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
from qgis.PyQt.QtWidgets import QWidget, QApplication, QDialog, QDialogButtonBox, QFileDialog, QMessageBox
from qgis.PyQt.uic import loadUiType
from qgis.core import QgsProject, QgsVectorLayer
from PyQt5 import QtCore, QtWidgets
from urllib.parse import urlparse
import requests, json
from dggal import *
from vgrid.utils.geometry import dggal_generatezonefeature
FORM_CLASS, _ = loadUiType(os.path.join(os.path.dirname(__file__), "ui/dggsjon2geojson.ui"))
from PyQt5.QtCore import Qt


class DGGSJSON2GeoJSONWidget(QDialog, FORM_CLASS):
    def __init__(self, vgridtools, settingsDialog, iface, parent):
        super(DGGSJSON2GeoJSONWidget, self).__init__(parent)
        self.setupUi(self)
        self.iface = iface
        self.canvas = iface.mapCanvas()
        self.vgridtools = vgridtools
        self.settings = settingsDialog
        self.set_status_bar(self.status,self.LblStatus)
        self.BtnApplyClose.button(QDialogButtonBox.Close).setAutoDefault(False)
                
        self.form_clear()
        self.BtnInputFolder.clicked.connect(self.read_json)
        self.BtnApplyClose.button(QtWidgets.QDialogButtonBox.Apply).clicked.connect(self.run)
        self.BtnApplyClose.button(QtWidgets.QDialogButtonBox.Close).clicked.connect(self.form_clear)


    def read_json(self):
        # Prompt user to select a directory
        newname = QFileDialog.getExistingDirectory(None, "Select Input Folder", self.LinInputFolder.displayText())
        
        # Validate selection
        if newname and os.path.isdir(newname) and os.path.basename(newname):
            # Update input folder text
            self.LinInputFolder.setText(newname)
            
            # Clear existing items in the CSV list
            self.lsDGGSJSON.clear()
            
            # Get all CSV files in the selected directory and subdirectories
            try:
                json_files = []
                for root, _, files in os.walk(newname):
                    for file in files:
                        if file.lower().endswith('.json'):  # Case-insensitive check
                            json_files.append(os.path.join(root, file))
                
                # Add CSV files to the list widget
                self.lsDGGSJSON.addItems(json_files)
                
                # Update label with the number of files loaded
                self.lblDGGSJSON.setText(f"{len(json_files)} files loaded")
                
                # Select the first item if any files were loaded
                if json_files:
                    self.lsDGGSJSON.setCurrentRow(0)
                
                # Clear the status label and update the status bar
                self.LblStatus.clear()
                self.set_status_bar(self.status, self.LblStatus)
            
            except Exception as e:
                QMessageBox.critical(None, "Error", f"Failed to load files: {e}")
        else:
            # Warn the user if an invalid folder was selected
            QMessageBox.warning(None, "Choose Folder", "Please choose a valid folder, not a disk like C:/.")

    def run(self):
        item_count = 0
        error_count = 0
        items = []
        for index in range(self.lsDGGSJSON.count()):
            items.append(self.lsDGGSJSON.item(index))
        self.txtError.clear()
        self.lsDGGSJSON.blockSignals(True)
        self.LinInputFolder.setEnabled(False)
        self.BtnInputFolder.setEnabled(False)
        self.status_bar.setEnabled(False)

        for item in items:
            self.lsDGGSJSON.setCurrentRow(item_count)
            input_dggsjson_name = item.text()

            temp_file_name = item.text()
            output_file_name = temp_file_name.replace(".json", ".geojson", 1)

            message = self.dggal_dggsjsonfile2geojson(input_dggsjson_name, output_file_name, {}, self.status_callback)
            if message:
                error_count+=1
                self.txtError.append(str(error_count)+ ". "+ input_dggsjson_name + ": " + message)
                continue
            else:
                item_count +=1
                self.LblStatus.setText (str(item_count)+"/ "+ str(self.lsDGGSJSON.count()) + " files converted")

        self.lsDGGSJSON.blockSignals(False)
        self.LinInputFolder.setEnabled(True)
        self.BtnInputFolder.setEnabled(True)
        self.status_bar.setEnabled(True)


    def dggal_dggsjsonfile2geojson(self, input_file, output_file=None, options: dict = {},status_callback = None):
        exitCode = 1
        try:
            if status_callback:
                status_callback(0, "Reading DGGS-JSON file...")
            
            # Check if input is a URL
            parsed_url = urlparse(input_file)
            is_url_input = all([parsed_url.scheme, parsed_url.netloc])
            
            # Read the JSON file from URL or local file
            if is_url_input:
                try:
                    if status_callback:
                        status_callback(10, "Downloading from URL...")
                    response = requests.get(input_file)
                    response.raise_for_status()
                    if status_callback:
                        status_callback(20, "Parsing JSON data...")
                    dggal_json = response.json()
                except requests.RequestException as e:
                    print(f"Failure to download file from URL {input_file}: {str(e)}")
                    return exitCode
            else:
                # Read from local file
                if status_callback:
                    status_callback(10, "Reading local file...")
                with open(input_file, 'r', encoding='utf-8') as f:
                    if status_callback:
                        status_callback(20, "Parsing JSON data...")
                    dggal_json = json.load(f)
            
            if dggal_json:
                if status_callback:
                    status_callback(30, "Extracting options...")
                
                # Extract options
                centroids = options.get('centroids') if options else False
                crsOption = options.get('crs') if options else None
                crs = None

                # Convert CRS option string to CRS object
                if crsOption:
                    if crsOption == "5x6":
                        crs = CRS(ogc, 153456)
                    elif crsOption == "isea":
                        crs = CRS(ogc, 1534)

                if status_callback:
                    status_callback(40, "Converting DGGS-JSON to GeoJSON...")

                # Use dggal_dggsjson2geojson to convert
                # Create a wrapper callback to scale progress from 40% to 80%
                def scaled_callback(percent, label):
                    if status_callback:
                        # Scale from 0-100 to 40-80
                        scaled_percent = 40 + int((percent / 100.0) * 40)
                        return status_callback(scaled_percent, label)
                    return 0
                
                geojson_result = self.dggal_dggsjson2geojson(dggal_json, crs=crs, centroids=centroids, status_callback=scaled_callback)
                
                if geojson_result:
                    if status_callback:
                        status_callback(80, "Preparing output file...")
                    
                    # Generate output filename: <input file name>.geojson
                    if is_url_input:
                    # Extract filename from URL path
                        url_path = parsed_url.path.rstrip('/')
                        if url_path:
                            input_basename = os.path.splitext(os.path.basename(url_path))[0]
                            # If no filename in URL path, use domain name
                            if not input_basename:
                                input_basename = parsed_url.netloc.replace('.', '_') if parsed_url.netloc else 'output'
                        else:
                            # No path in URL, use domain name
                            input_basename = parsed_url.netloc.replace('.', '_') if parsed_url.netloc else 'output'
                    else:
                        # Local file: use the basename without extension
                        input_basename = os.path.splitext(os.path.basename(input_file))[0]
                    
                    if output_file is None:
                        output_file = os.path.join(os.getcwd(), f"{input_basename}.geojson")
                    
                    if status_callback:
                        status_callback(90, "Writing GeoJSON file...")
                    
                    # Write GeoJSON to file
                    with open(output_file, 'w', encoding='utf-8') as f:
                        json.dump(geojson_result, f, indent=2)
                    
                    if status_callback:
                        status_callback(100, "Conversion completed")
                    
                    return None

                    exitCode = 0
                else:
                    return f"Failed to convert DGGS-JSON to GeoJSON"
            else:
                return f"Failure to parse DGGS-JSON file {input_file}"
        except FileNotFoundError:
            return f"Failure to open file {input_file}"
        except json.JSONDecodeError as e:
            return f"Failure to parse DGGS-JSON file {input_file}: {str(e)}"
        except Exception as e:
            return f"Error processing file {input_file}: {str(e)}"
    
    def dggal_dggsjson2geojson(self, dggal_json, crs: CRS = None, centroids: bool = False, status_callback = None):
        result = None
        if dggal_json is not None:
            if status_callback:
                status_callback(0, "Identifying DGGS type...")
            
            dggrsClass = None
            dggrsID = getLastDirectory(dggal_json['dggrs'])

            # We could use globals()['GNOSISGlobalGrid'] to be more generic, but here we limit to DGGRSs we know
            if   not strnicmp(dggrsID, "GNOSIS", 6): dggrsClass = GNOSISGlobalGrid
            elif not strnicmp(dggrsID, "ISEA4R", 6): dggrsClass = ISEA4R
            elif not strnicmp(dggrsID, "ISEA9R", 6): dggrsClass = ISEA9R
            elif not strnicmp(dggrsID, "ISEA3H", 6): dggrsClass = ISEA3H
            elif not strnicmp(dggrsID, "ISEA7H", 6): dggrsClass = ISEA7H
            elif not strnicmp(dggrsID, "IVEA4R", 6): dggrsClass = IVEA4R
            elif not strnicmp(dggrsID, "IVEA9R", 6): dggrsClass = IVEA9R
            elif not strnicmp(dggrsID, "IVEA3H", 6): dggrsClass = IVEA3H
            elif not strnicmp(dggrsID, "IVEA7H", 6): dggrsClass = IVEA7H
            elif not strnicmp(dggrsID, "RTEA4R", 6): dggrsClass = RTEA4R
            elif not strnicmp(dggrsID, "RTEA9R", 6): dggrsClass = RTEA9R
            elif not strnicmp(dggrsID, "RTEA3H", 6): dggrsClass = RTEA3H
            elif not strnicmp(dggrsID, "RTEA7H", 6): dggrsClass = RTEA7H
            elif not strnicmp(dggrsID, "HEALPix", 7): dggrsClass = HEALPix
            elif not strnicmp(dggrsID, "rHEALPix", 8): dggrsClass = rHEALPix

            if dggrsClass:
                if status_callback:
                    status_callback(10, "Getting zone from ID...")
                
                zoneID = dggal_json['zoneId']
                dggrs = dggrsClass()
                zone = dggrs.getZoneFromTextID(zoneID)

                if zone != nullZone:
                    if status_callback:
                        status_callback(20, "Processing depths...")
                    
                    depths = dggal_json['depths']
                    if depths:
                        maxDepth = -1

                        for d in range(len(depths)):
                            depth = depths[d]
                            if depth > maxDepth:
                                maxDepth = depth
                                break;
                        if d < len(depths):
                            depth = maxDepth
                            
                            if status_callback:
                                status_callback(30, "Getting sub-zones...")
                            
                            subZones = dggrs.getSubZones(zone, depth)
                            if subZones:
                                if status_callback:
                                    status_callback(40, "Generating features...")
                                
                                i = 0
                                values = dggal_json['values']
                                features = [ ]
                                total_zones = len(subZones)
                                
                                for z in subZones:
                                    # Update progress for each zone processed
                                    if status_callback and total_zones > 0:
                                        # Progress from 40% to 90% for feature generation
                                        percent = 40 + int((i / total_zones) * 50)
                                        if (i % 10 == 0) or (i == total_zones - 1):
                                            if status_callback(percent, f"Processing zone {i + 1} of {total_zones}"):
                                                return None  # Cancelled
                                    
                                    props = { }

                                    # NOTE: We should eventually try to support __iter__ on containers
                                    #       for key, depths in dggal_json.values.items():
                                    for key, vDepths in values.items():
                                        if key and vDepths and len(vDepths) > d:
                                            djDepth = vDepths[d]
                                            data = djDepth['data']
                                            props[key] = data[i]

                                    features.append(dggal_generatezonefeature(dggrs, z, crs, i + 1, centroids, True, props))
                                    i += 1
                                
                                if status_callback:
                                    status_callback(100, "Creating FeatureCollection...")
                                
                                result = {
                                'type': 'FeatureCollection',
                                'features': features
                                }
        return result



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
    
    def form_clear(self):
        # Clear UI elements when dialog is closed
        self.lblDGGSJSON.clear()
        self.lsDGGSJSON.clear()
        self.txtError.clear()
        self.LblStatus.clear()
        self.set_status_bar(self.status,self.LblStatus)

          # Set default output folder
        project = QgsProject.instance()
        home_path = project.homePath()
        if not home_path:
            home_path = os.path.expanduser('~')
        self.LinInputFolder.setText(home_path)   
        
        # Restore cursor
        QApplication.setOverrideCursor(Qt.ArrowCursor)
        QApplication.restoreOverrideCursor()
        
        self.close()