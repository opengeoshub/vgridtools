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
import re
from qgis.PyQt.QtCore import QSize, Qt
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QDockWidget, QMenu, QApplication
from qgis.PyQt.QtCore import pyqtSlot
from qgis.PyQt.uic import loadUiType
from qgis.core import (
    Qgis,
    QgsWkbTypes,
    QgsCoordinateTransform,
    QgsGeometry,
    QgsPoint,
    QgsPointXY,
    QgsProject,
)

from qgis.gui import QgsRubberBand

from .utils import tr
from .utils.latlon import epsg4326, parseDMSString
from .settings import settings
from .utils.dggrid_instance import (
    DGGRID_TYPES_NO_ANTIMERIDIAN,
    cached_dggrid_cell_geometry,
    cached_latlon2dggrid,
    dggrid_latlon_cell_options,
    get_plugin_dggrid_instance,
)
from .utils.utm import latLon2Utm, isUtm, utm2Point
from .utils.captureCoordinate import CaptureCoordinate
from vgrid.conversion.latlon2dggs import *
from vgrid.conversion.dggs2geo import *
from vgrid.utils.geometry import geodesic_dggs_metrics, graticule_dggs_metrics

from vgrid.dggs.rhealpixdggs.dggs import RHEALPixDGGS
from vgrid.dggs.rhealpixdggs.ellipsoids import WGS84_ELLIPSOID
import traceback
from vgrid.utils.antimeridian import fix_polygon

FORM_CLASS, _ = loadUiType(os.path.join(os.path.dirname(__file__), "ui/latlon2dggs.ui"))

s_invalid = tr("Invalid")
s_copied = tr("copied to the clipboard")

# (widget prefix, DGGRID type name, updateCoordinates id)
DGGRID_LATLON_ROWS = (
    ("dggrid_superfund", "SUPERFUND", 26),
    ("dggrid_planetrisk", "PLANETRISK", 27),
    ("dggrid_isea3h", "ISEA3H", 28),
    ("dggrid_isea4h", "ISEA4H", 29),
    ("dggrid_isea4t", "ISEA4T", 30),
    ("dggrid_isea4d", "ISEA4D", 31),
    ("dggrid_isea43h", "ISEA43H", 32),
    ("dggrid_isea7h", "ISEA7H", 33),
    ("dggrid_igeo7", "IGEO7", 34),
    ("dggrid_fuller3h", "FULLER3H", 35),
    ("dggrid_fuller4h", "FULLER4H", 36),
    ("dggrid_fuller4t", "FULLER4T", 37),
    ("dggrid_fuller4d", "FULLER4D", 38),
    ("dggrid_fuller43h", "FULLER43H", 39),
    ("dggrid_fuller7h", "FULLER7H", 40),
)


class LatLon2DGGSWidget(QDockWidget, FORM_CLASS):
    inputProjection = 0
    origPt = None
    origCrs = epsg4326

    def __init__(self, vgridtools, settingsDialog, iface, parent):
        super(LatLon2DGGSWidget, self).__init__(parent)
        self.setupUi(self)
        self.iface = iface
        self.canvas = iface.mapCanvas()
        self.vgridtools = vgridtools
        self.settings = settingsDialog
        self.savedMapTool = None
        self.clipboard = QApplication.clipboard()

        # Set up a connection with the coordinate capture tool
        self.captureCoordinate = CaptureCoordinate(self.canvas)
        self.captureCoordinate.capturePoint.connect(self.capturedPoint)
        self.captureCoordinate.captureStopped.connect(self.stopCapture)

        self.xymenu = QMenu()
        icon = QIcon(os.path.dirname(__file__) + "/images/yx.svg")
        a = self.xymenu.addAction(icon, tr("Y, X (Lat, Lon) Order"))
        a.setData(0)
        icon = QIcon(os.path.dirname(__file__) + "/images/xy.svg")
        a = self.xymenu.addAction(icon, tr("X, Y (Lon, Lat) Order"))
        a.setData(1)
        self.xyButton.setIconSize(QSize(16, 16))
        self.xyButton.setIcon(icon)
        self.xyButton.setMenu(self.xymenu)
        self.xyButton.triggered.connect(self.xyTriggered)
        self.inputXYOrder = settings.coordOrder
        self.clearFormButton.setIcon(
            QIcon(":/images/themes/default/mIconClearText.svg")
        )
        self.clearFormButton.clicked.connect(self.clearForm)

        self.coordCaptureButton.setIcon(
            QIcon(os.path.dirname(__file__) + "/images/coordCapture.svg")
        )
        self.coordCaptureButton.clicked.connect(self.startCapture)

        self.zoomButton.setIcon(QIcon(":/images/themes/default/mActionZoomIn.svg"))
        self.zoomButton.clicked.connect(self.zoomTo)

        self.optionsButton.setIcon(
            QIcon(os.path.dirname(__file__) + "/images/settings.svg")
        )
        self.optionsButton.clicked.connect(self.showSettings)

        self.wgs84LineEdit.returnPressed.connect(self.commitWGS84)
        self.projLineEdit.returnPressed.connect(self.commitPROJ)
        self.customLineEdit.returnPressed.connect(self.commitCUSTOM)
        self.utmLineEdit.returnPressed.connect(self.commitUTM)

        self.h3LineEdit.returnPressed.connect(self.commitH3)
        self.s2LineEdit.returnPressed.connect(self.commitS2)
        self.a5LineEdit.returnPressed.connect(self.commitA5)
        self.rhealpixLineEdit.returnPressed.connect(self.commitrHEALPix)
       
        self.dggal_gnosisLineEdit.returnPressed.connect(self.commitDGGAL_GNOSIS)

        self.dggal_isea4rLineEdit.returnPressed.connect(self.commitDGGAL_ISEA4R)
        self.dggal_isea9rLineEdit.returnPressed.connect(self.commitDGGAL_ISEA9R)
        self.dggal_isea3hLineEdit.returnPressed.connect(self.commitDGGAL_ISEA3H)
        self.dggal_isea7hLineEdit.returnPressed.connect(self.commitDGGAL_ISEA7H)
        self.dggal_isea7h_z7LineEdit.returnPressed.connect(self.commitDGGAL_ISEA7H_Z7)

        self.dggal_ivea4rLineEdit.returnPressed.connect(self.commitDGGAL_IVEA4R)
        self.dggal_ivea9rLineEdit.returnPressed.connect(self.commitDGGAL_IVEA9R)
        self.dggal_ivea3hLineEdit.returnPressed.connect(self.commitDGGAL_IVEA3H)
        self.dggal_ivea7hLineEdit.returnPressed.connect(self.commitDGGAL_IVEA7H)
        self.dggal_ivea7h_z7LineEdit.returnPressed.connect(self.commitDGGAL_IVEA7H_Z7)


        self.dggal_rtea4rLineEdit.returnPressed.connect(self.commitDGGAL_RTEA4R)
        self.dggal_rtea9rLineEdit.returnPressed.connect(self.commitDGGAL_RTEA9R)
        self.dggal_rtea3hLineEdit.returnPressed.connect(self.commitDGGAL_RTEA3H)
        self.dggal_rtea7hLineEdit.returnPressed.connect(self.commitDGGAL_RTEA7H)
        self.dggal_rtea7h_z7LineEdit.returnPressed.connect(self.commitDGGAL_RTEA7H_Z7)
        
        self.dggal_healpixLineEdit.returnPressed.connect(self.commitDGGAL_HEALPix)
        self.dggal_rhealpixLineEdit.returnPressed.connect(self.commitDGGAL_rHEALPix)

        self.dggrid_superfundLineEdit.returnPressed.connect(self.commitDGGRID_SUPERFUND)
        self.dggrid_planetriskLineEdit.returnPressed.connect(self.commitDGGRID_PLANETRISK)
        self.dggrid_isea3hLineEdit.returnPressed.connect(self.commitDGGRID_ISEA3H)
        self.dggrid_isea4hLineEdit.returnPressed.connect(self.commitDGGRID_ISEA4H)
        self.dggrid_isea4tLineEdit.returnPressed.connect(self.commitDGGRID_ISEA4T)
        self.dggrid_isea4dLineEdit.returnPressed.connect(self.commitDGGRID_ISEA4D)
        self.dggrid_isea43hLineEdit.returnPressed.connect(self.commitDGGRID_ISEA43H)
        self.dggrid_isea7hLineEdit.returnPressed.connect(self.commitDGGRID_ISEA7H)
        self.dggrid_igeo7LineEdit.returnPressed.connect(self.commitDGGRID_IGEO7)
        self.dggrid_fuller3hLineEdit.returnPressed.connect(self.commitDGGRID_FULLER3H)
        self.dggrid_fuller4hLineEdit.returnPressed.connect(self.commitDGGRID_FULLER4H)
        self.dggrid_fuller4tLineEdit.returnPressed.connect(self.commitDGGRID_FULLER4T)
        self.dggrid_fuller4dLineEdit.returnPressed.connect(self.commitDGGRID_FULLER4D)
        self.dggrid_fuller43hLineEdit.returnPressed.connect(self.commitDGGRID_FULLER43H)
        self.dggrid_fuller7hLineEdit.returnPressed.connect(self.commitDGGRID_FULLER7H)      


        self.isea4tLineEdit.returnPressed.connect(self.commitISEA4T)
        self.isea3hLineEdit.returnPressed.connect(self.commitISEA3H)
        self.easeLineEdit.returnPressed.connect(self.commitEASE)
        self.qtmLineEdit.returnPressed.connect(self.commitQTM)
        self.olcLineEdit.returnPressed.connect(self.commitOLC)
        self.geohashLineEdit.returnPressed.connect(self.commitGeohash)
        self.georefLineEdit.returnPressed.connect(self.commitGEOREF)
        self.mgrsLineEdit.returnPressed.connect(self.commitMGRS)
        self.tilecodeLineEdit.returnPressed.connect(self.commitTilecode)
        self.quadkeyLineEdit.returnPressed.connect(self.commitQuadkey)
        self.maidenheadLineEdit.returnPressed.connect(self.commitMaidenhead)
        self.garsLineEdit.returnPressed.connect(self.commitGARS)
        self.digipinLineEdit.returnPressed.connect(self.commitDIGIPIN)


        icon = QIcon(":/images/themes/default/mActionEditCopy.svg")
        self.wgs84CopyButton.setIcon(icon)
        self.projCopyButton.setIcon(icon)
        self.customCopyButton.setIcon(icon)
        self.utmCopyButton.setIcon(icon)

        self.h3CopyButton.setIcon(icon)
        self.s2CopyButton.setIcon(icon)
        self.a5CopyButton.setIcon(icon)
        self.rhealpixCopyButton.setIcon(icon)
       

        self.dggal_gnosisCopyButton.setIcon(icon)

        self.dggal_isea4rCopyButton.setIcon(icon)
        self.dggal_isea9rCopyButton.setIcon(icon)           
        self.dggal_isea3hCopyButton.setIcon(icon)
        self.dggal_isea7hCopyButton.setIcon(icon)
        self.dggal_isea7h_z7CopyButton.setIcon(icon)

        self.dggal_ivea4rCopyButton.setIcon(icon)
        self.dggal_ivea3hCopyButton.setIcon(icon)
        self.dggal_ivea9rCopyButton.setIcon(icon)
        self.dggal_ivea7hCopyButton.setIcon(icon)
        self.dggal_ivea7h_z7CopyButton.setIcon(icon)
        
        self.dggal_rtea4rCopyButton.setIcon(icon)
        self.dggal_rtea9rCopyButton.setIcon(icon)
        self.dggal_rtea3hCopyButton.setIcon(icon)
        self.dggal_rtea7hCopyButton.setIcon(icon)
        self.dggal_rtea7h_z7CopyButton.setIcon(icon)
        
        self.dggal_healpixCopyButton.setIcon(icon)
        self.dggal_rhealpixCopyButton.setIcon(icon)


        self.dggrid_superfundCopyButton.setIcon(icon)
        self.dggrid_planetriskCopyButton.setIcon(icon)
        self.dggrid_isea3hCopyButton.setIcon(icon)
        self.dggrid_isea4hCopyButton.setIcon(icon)
        self.dggrid_isea4tCopyButton.setIcon(icon)
        self.dggrid_isea4dCopyButton.setIcon(icon)
        self.dggrid_isea43hCopyButton.setIcon(icon)
        self.dggrid_isea7hCopyButton.setIcon(icon)
        self.dggrid_igeo7CopyButton.setIcon(icon)
        self.dggrid_fuller3hCopyButton.setIcon(icon)
        self.dggrid_fuller4hCopyButton.setIcon(icon)
        self.dggrid_fuller4tCopyButton.setIcon(icon)
        self.dggrid_fuller4dCopyButton.setIcon(icon)
        self.dggrid_fuller43hCopyButton.setIcon(icon)
        self.dggrid_fuller7hCopyButton.setIcon(icon)

        self.isea4tCopyButton.setIcon(icon)
        self.isea3hCopyButton.setIcon(icon)
        self.easeCopyButton.setIcon(icon)        
        self.qtmCopyButton.setIcon(icon)
        self.olcCopyButton.setIcon(icon)
        self.geohashCopyButton.setIcon(icon)
        self.georefCopyButton.setIcon(icon)
        self.mgrsCopyButton.setIcon(icon)
        self.tilecodeCopyButton.setIcon(icon)
        self.quadkeyCopyButton.setIcon(icon)
        self.maidenheadCopyButton.setIcon(icon)
        self.garsCopyButton.setIcon(icon)
        self.digipinCopyButton.setIcon(icon)

        self.wgs84CopyButton.clicked.connect(self.copyWGS84)
        self.projCopyButton.clicked.connect(self.copyPROJ)
        self.customCopyButton.clicked.connect(self.copyCUSTOM)
        self.utmCopyButton.clicked.connect(self.copyUTM)

        self.h3CopyButton.clicked.connect(self.copyH3)
        self.s2CopyButton.clicked.connect(self.copyS2)
        self.a5CopyButton.clicked.connect(self.copyA5)
        self.rhealpixCopyButton.clicked.connect(self.copyRHEALPIX)

        self.dggal_gnosisCopyButton.clicked.connect(self.copyDGGAL_GNOSIS)

        self.dggal_isea4rCopyButton.clicked.connect(self.copyDGGAL_ISEA4R)      
        self.dggal_isea9rCopyButton.clicked.connect(self.copyDGGAL_ISEA9R)
        self.dggal_isea3hCopyButton.clicked.connect(self.copyDGGAL_ISEA3H)
        self.dggal_isea7hCopyButton.clicked.connect(self.copyDGGAL_ISEA7H)
        self.dggal_isea7h_z7CopyButton.clicked.connect(self.copyDGGAL_ISEA7H_Z7)
        
        self.dggal_ivea4rCopyButton.clicked.connect(self.copyDGGAL_IVEA4R)
        self.dggal_ivea9rCopyButton.clicked.connect(self.copyDGGAL_IVEA9R)
        self.dggal_ivea3hCopyButton.clicked.connect(self.copyDGGAL_IVEA3H)
        self.dggal_ivea7hCopyButton.clicked.connect(self.copyDGGAL_IVEA7H)
        self.dggal_ivea7h_z7CopyButton.clicked.connect(self.copyDGGAL_IVEA7H_Z7)
        
        self.dggal_rtea4rCopyButton.clicked.connect(self.copyDGGAL_RTEA4R)
        self.dggal_rtea9rCopyButton.clicked.connect(self.copyDGGAL_RTEA9R)
        self.dggal_rtea3hCopyButton.clicked.connect(self.copyDGGAL_RTEA3H)
        self.dggal_rtea7hCopyButton.clicked.connect(self.copyDGGAL_RTEA7H)
        self.dggal_rtea7h_z7CopyButton.clicked.connect(self.copyDGGAL_RTEA7H_Z7)    

        self.dggal_healpixCopyButton.clicked.connect(self.copyDGGAL_HEALPIX)
        self.dggal_rhealpixCopyButton.clicked.connect(self.copyDGGAL_RHEALPIX)  


        self.dggrid_superfundCopyButton.clicked.connect(self.copyDGGRID_SUPERFUND)
        self.dggrid_planetriskCopyButton.clicked.connect(self.copyDGGRID_PLANETRISK)
        self.dggrid_isea3hCopyButton.clicked.connect(self.copyDGGRID_ISEA3H)
        self.dggrid_isea4hCopyButton.clicked.connect(self.copyDGGRID_ISEA4H)
        self.dggrid_isea4tCopyButton.clicked.connect(self.copyDGGRID_ISEA4T)
        self.dggrid_isea4dCopyButton.clicked.connect(self.copyDGGRID_ISEA4D)
        self.dggrid_isea43hCopyButton.clicked.connect(self.copyDGGRID_ISEA43H)
        self.dggrid_isea7hCopyButton.clicked.connect(self.copyDGGRID_ISEA7H)
        self.dggrid_igeo7CopyButton.clicked.connect(self.copyDGGRID_IGEO7)
        self.dggrid_fuller3hCopyButton.clicked.connect(self.copyDGGRID_FULLER3H)
        self.dggrid_fuller4hCopyButton.clicked.connect(self.copyDGGRID_FULLER4H)
        self.dggrid_fuller4tCopyButton.clicked.connect(self.copyDGGRID_FULLER4T)
        self.dggrid_fuller4dCopyButton.clicked.connect(self.copyDGGRID_FULLER4D)
        self.dggrid_fuller43hCopyButton.clicked.connect(self.copyDGGRID_FULLER43H)
        self.dggrid_fuller7hCopyButton.clicked.connect(self.copyDGGRID_FULLER7H)
        
        self.isea4tCopyButton.clicked.connect(self.copyISEA4T)
        self.isea3hCopyButton.clicked.connect(self.copyISEA3H)
        self.easeCopyButton.clicked.connect(self.copyEASE)
        self.qtmCopyButton.clicked.connect(self.copyQTM)
        self.olcCopyButton.clicked.connect(self.copyOLC)
        self.geohashCopyButton.clicked.connect(self.copyGeohash)
        self.georefCopyButton.clicked.connect(self.copyGEOREF)
        self.mgrsCopyButton.clicked.connect(self.copyMGRS)
        self.tilecodeCopyButton.clicked.connect(self.copyTilecode)
        self.quadkeyCopyButton.clicked.connect(self.copyQuadkey)
        self.maidenheadCopyButton.clicked.connect(self.copyMaidenhead)
        self.garsCopyButton.clicked.connect(self.copyGARS)
        self.digipinCopyButton.clicked.connect(self.copyDIGIPIN)

        self.customProjectionSelectionWidget.setCrs(epsg4326)
        self.customProjectionSelectionWidget.crsChanged.connect(self.customCrsChanged)

        zoomto_icon = QIcon(":/images/themes/default/mActionZoomIn.svg")
        self.wgs84ZoomtoButton.setIcon(zoomto_icon) 
        self.h3ZoomtoButton.setIcon(zoomto_icon)
        self.s2ZoomtoButton.setIcon(zoomto_icon)
        self.a5ZoomtoButton.setIcon(zoomto_icon)
        self.rhealpixZoomtoButton.setIcon(zoomto_icon)
        

        self.dggal_gnosisZoomtoButton.setIcon(zoomto_icon)      

        self.dggal_isea4rZoomtoButton.setIcon(zoomto_icon)
        self.dggal_isea9rZoomtoButton.setIcon(zoomto_icon)
        self.dggal_isea3hZoomtoButton.setIcon(zoomto_icon)
        self.dggal_isea7hZoomtoButton.setIcon(zoomto_icon)
        self.dggal_isea7h_z7ZoomtoButton.setIcon(zoomto_icon)
        
        self.dggal_ivea4rZoomtoButton.setIcon(zoomto_icon)
        self.dggal_ivea9rZoomtoButton.setIcon(zoomto_icon)
        self.dggal_ivea3hZoomtoButton.setIcon(zoomto_icon)
        self.dggal_ivea7hZoomtoButton.setIcon(zoomto_icon)
        self.dggal_ivea7h_z7ZoomtoButton.setIcon(zoomto_icon)
        
        self.dggal_rtea4rZoomtoButton.setIcon(zoomto_icon)
        self.dggal_rtea9rZoomtoButton.setIcon(zoomto_icon)
        self.dggal_rtea3hZoomtoButton.setIcon(zoomto_icon)
        self.dggal_rtea7hZoomtoButton.setIcon(zoomto_icon)
        self.dggal_rtea7h_z7ZoomtoButton.setIcon(zoomto_icon)
        
        self.dggal_healpixZoomtoButton.setIcon(zoomto_icon)
        self.dggal_rhealpixZoomtoButton.setIcon(zoomto_icon)


        self.dggrid_superfundZoomtoButton.setIcon(zoomto_icon)
        self.dggrid_planetriskZoomtoButton.setIcon(zoomto_icon)
        self.dggrid_isea3hZoomtoButton.setIcon(zoomto_icon)
        self.dggrid_isea4hZoomtoButton.setIcon(zoomto_icon)
        self.dggrid_isea4tZoomtoButton.setIcon(zoomto_icon)
        self.dggrid_isea4dZoomtoButton.setIcon(zoomto_icon)
        self.dggrid_isea43hZoomtoButton.setIcon(zoomto_icon)
        self.dggrid_isea7hZoomtoButton.setIcon(zoomto_icon)
        self.dggrid_igeo7ZoomtoButton.setIcon(zoomto_icon)
        self.dggrid_fuller3hZoomtoButton.setIcon(zoomto_icon)
        self.dggrid_fuller4hZoomtoButton.setIcon(zoomto_icon)
        self.dggrid_fuller4tZoomtoButton.setIcon(zoomto_icon)
        self.dggrid_fuller4dZoomtoButton.setIcon(zoomto_icon)
        self.dggrid_fuller43hZoomtoButton.setIcon(zoomto_icon)
        self.dggrid_fuller7hZoomtoButton.setIcon(zoomto_icon)


        self.isea4tZoomtoButton.setIcon(zoomto_icon)
        self.isea3hZoomtoButton.setIcon(zoomto_icon)
        self.easeZoomtoButton.setIcon(zoomto_icon)
        
        self.qtmZoomtoButton.setIcon(zoomto_icon)
        self.olcZoomtoButton.setIcon(zoomto_icon)
        self.geohashZoomtoButton.setIcon(zoomto_icon)
        self.georefZoomtoButton.setIcon(zoomto_icon)
        self.mgrsZoomtoButton.setIcon(zoomto_icon)
        self.tilecodeZoomtoButton.setIcon(zoomto_icon)
        self.quadkeyZoomtoButton.setIcon(zoomto_icon)
        self.maidenheadZoomtoButton.setIcon(zoomto_icon)
        self.garsZoomtoButton.setIcon(zoomto_icon)
        self.digipinZoomtoButton.setIcon(zoomto_icon)

      
        self.wgs84ZoomtoButton.clicked.connect(self.zoomToWGS84)
        self.h3ZoomtoButton.clicked.connect(self.zoomToH3)
        self.s2ZoomtoButton.clicked.connect(self.zoomToS2)
        self.a5ZoomtoButton.clicked.connect(self.zoomToA5)
        self.rhealpixZoomtoButton.clicked.connect(self.zoomToRHEALPIX)

        self.dggal_gnosisZoomtoButton.clicked.connect(self.zoomToDGGAL_GNOSIS)

        self.dggal_isea4rZoomtoButton.clicked.connect(self.zoomToDGGAL_ISEA4R)
        self.dggal_isea9rZoomtoButton.clicked.connect(self.zoomToDGGAL_ISEA9R)
        self.dggal_isea3hZoomtoButton.clicked.connect(self.zoomToDGGAL_ISEA3H)
        self.dggal_isea7hZoomtoButton.clicked.connect(self.zoomToDGGAL_ISEA7H)
        self.dggal_isea7h_z7ZoomtoButton.clicked.connect(self.zoomToDGGAL_ISEA7H_Z7)

        self.dggal_ivea4rZoomtoButton.clicked.connect(self.zoomToDGGAL_IVEA4R)
        self.dggal_ivea9rZoomtoButton.clicked.connect(self.zoomToDGGAL_IVEA9R)
        self.dggal_ivea3hZoomtoButton.clicked.connect(self.zoomToDGGAL_IVEA3H)
        self.dggal_ivea7hZoomtoButton.clicked.connect(self.zoomToDGGAL_IVEA7H)
        self.dggal_ivea7h_z7ZoomtoButton.clicked.connect(self.zoomToDGGAL_IVEA7H_Z7)
        
        self.dggal_rtea4rZoomtoButton.clicked.connect(self.zoomToDGGAL_RTEA4R)
        self.dggal_rtea9rZoomtoButton.clicked.connect(self.zoomToDGGAL_RTEA9R)
        self.dggal_rtea3hZoomtoButton.clicked.connect(self.zoomToDGGAL_RTEA3H)
        self.dggal_rtea7hZoomtoButton.clicked.connect(self.zoomToDGGAL_RTEA7H)
        self.dggal_rtea7h_z7ZoomtoButton.clicked.connect(self.zoomToDGGAL_RTEA7H_Z7)
        
        self.dggal_healpixZoomtoButton.clicked.connect(self.zoomToDGGAL_HEALPix)
        self.dggal_rhealpixZoomtoButton.clicked.connect(self.zoomToDGGAL_rHEALPix)


        self.dggrid_superfundZoomtoButton.clicked.connect(self.zoomToDGGRID_SUPERFUND)
        self.dggrid_planetriskZoomtoButton.clicked.connect(self.zoomToDGGRID_PLANETRISK)
        self.dggrid_isea3hZoomtoButton.clicked.connect(self.zoomToDGGRID_ISEA3H)
        self.dggrid_isea4hZoomtoButton.clicked.connect(self.zoomToDGGRID_ISEA4H)
        self.dggrid_isea4tZoomtoButton.clicked.connect(self.zoomToDGGRID_ISEA4T)
        self.dggrid_isea4dZoomtoButton.clicked.connect(self.zoomToDGGRID_ISEA4D)
        self.dggrid_isea43hZoomtoButton.clicked.connect(self.zoomToDGGRID_ISEA43H)
        self.dggrid_isea7hZoomtoButton.clicked.connect(self.zoomToDGGRID_ISEA7H)
        self.dggrid_igeo7ZoomtoButton.clicked.connect(self.zoomToDGGRID_IGEO7)
        self.dggrid_fuller3hZoomtoButton.clicked.connect(self.zoomToDGGRID_FULLER3H)
        self.dggrid_fuller4hZoomtoButton.clicked.connect(self.zoomToDGGRID_FULLER4H)
        self.dggrid_fuller4tZoomtoButton.clicked.connect(self.zoomToDGGRID_FULLER4T)
        self.dggrid_fuller4dZoomtoButton.clicked.connect(self.zoomToDGGRID_FULLER4D)
        self.dggrid_fuller43hZoomtoButton.clicked.connect(self.zoomToDGGRID_FULLER43H)
        self.dggrid_fuller7hZoomtoButton.clicked.connect(self.zoomToDGGRID_FULLER7H)


        self.isea4tZoomtoButton.clicked.connect(self.zoomToISEA4T)
        self.isea3hZoomtoButton.clicked.connect(self.zoomToISEA3H)
        self.easeZoomtoButton.clicked.connect(self.zoomToEASE)
        self.qtmZoomtoButton.clicked.connect(self.zoomToQTM)
        self.olcZoomtoButton.clicked.connect(self.zoomToOLC)
        self.geohashZoomtoButton.clicked.connect(self.zoomToGeohash)    
        self.georefZoomtoButton.clicked.connect(self.zoomToGEOREF)
        self.mgrsZoomtoButton.clicked.connect(self.zoomToMGRS)
        self.tilecodeZoomtoButton.clicked.connect(self.zoomToTilecode)
        self.quadkeyZoomtoButton.clicked.connect(self.zoomToQuadkey)
        self.maidenheadZoomtoButton.clicked.connect(self.zoomToMaidenhead)
        self.garsZoomtoButton.clicked.connect(self.zoomToGARS)
        self.digipinZoomtoButton.clicked.connect(self.zoomToDIGIPIN)

        self.updateMarker()

    def updateMarker(self):
        self.marker = QgsRubberBand(self.canvas, QgsWkbTypes.PointGeometry)
        self.marker.setColor(settings.markerColor)
        self.marker.setStrokeColor(settings.markerColor)
        self.marker.setWidth(settings.markerWidth)
        self.marker.setIconSize(settings.markerSize)
        self.marker.setIcon(QgsRubberBand.ICON_CROSS)

        self.h3_marker = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
        self.h3_marker.setStrokeColor(settings.markerColor)
        self.h3_marker.setWidth(settings.gridWidth)

        self.s2_marker = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
        self.s2_marker.setStrokeColor(settings.markerColor)
        self.s2_marker.setWidth(settings.gridWidth)

        self.a5_marker = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
        self.a5_marker.setStrokeColor(settings.markerColor)
        self.a5_marker.setWidth(settings.gridWidth)

        self.rhealpix_marker = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
        self.rhealpix_marker.setStrokeColor(settings.markerColor)
        self.rhealpix_marker.setWidth(settings.gridWidth)

        self.dggal_gnosis_marker = QgsRubberBand(
            self.canvas, QgsWkbTypes.PolygonGeometry
        )
        self.dggal_gnosis_marker.setStrokeColor(settings.markerColor)
        self.dggal_gnosis_marker.setWidth(settings.gridWidth)

        self.dggal_isea4r_marker = QgsRubberBand(
            self.canvas, QgsWkbTypes.PolygonGeometry
        )
        self.dggal_isea4r_marker.setStrokeColor(settings.markerColor)
        self.dggal_isea4r_marker.setWidth(settings.gridWidth)
        self.dggal_isea9r_marker = QgsRubberBand(
            self.canvas, QgsWkbTypes.PolygonGeometry
        )
        self.dggal_isea9r_marker.setStrokeColor(settings.markerColor)
        self.dggal_isea9r_marker.setWidth(settings.gridWidth)
        self.dggal_isea3h_marker = QgsRubberBand(
            self.canvas, QgsWkbTypes.PolygonGeometry
        )
        self.dggal_isea3h_marker.setStrokeColor(settings.markerColor)
        self.dggal_isea3h_marker.setWidth(settings.gridWidth)   
        self.dggal_isea7h_marker = QgsRubberBand(
            self.canvas, QgsWkbTypes.PolygonGeometry
        )
        self.dggal_isea7h_marker.setStrokeColor(settings.markerColor)
        self.dggal_isea7h_marker.setWidth(settings.gridWidth)

        self.dggal_isea7h_z7_marker = QgsRubberBand(
            self.canvas, QgsWkbTypes.PolygonGeometry
        )
        self.dggal_isea7h_z7_marker.setStrokeColor(settings.markerColor)
        self.dggal_isea7h_z7_marker.setWidth(settings.gridWidth)


        self.dggal_ivea4r_marker = QgsRubberBand(
            self.canvas, QgsWkbTypes.PolygonGeometry
        )
        self.dggal_ivea4r_marker.setStrokeColor(settings.markerColor)
        self.dggal_ivea4r_marker.setWidth(settings.gridWidth)
        self.dggal_ivea9r_marker = QgsRubberBand(
            self.canvas, QgsWkbTypes.PolygonGeometry
        )
        self.dggal_ivea9r_marker.setStrokeColor(settings.markerColor)
        self.dggal_ivea9r_marker.setWidth(settings.gridWidth)
        self.dggal_ivea3h_marker = QgsRubberBand(
            self.canvas, QgsWkbTypes.PolygonGeometry
        )
        self.dggal_ivea3h_marker.setStrokeColor(settings.markerColor)
        self.dggal_ivea3h_marker.setWidth(settings.gridWidth)
        self.dggal_ivea7h_marker = QgsRubberBand(
            self.canvas, QgsWkbTypes.PolygonGeometry
        )
        self.dggal_ivea7h_marker.setStrokeColor(settings.markerColor)
        self.dggal_ivea7h_marker.setWidth(settings.gridWidth)
        self.dggal_ivea7h_z7_marker = QgsRubberBand(
            self.canvas, QgsWkbTypes.PolygonGeometry
        )
        self.dggal_ivea7h_z7_marker.setStrokeColor(settings.markerColor)
        self.dggal_ivea7h_z7_marker.setWidth(settings.gridWidth)
        
        self.dggal_rtea4r_marker = QgsRubberBand(
            self.canvas, QgsWkbTypes.PolygonGeometry
        )
        self.dggal_rtea4r_marker.setStrokeColor(settings.markerColor)
        self.dggal_rtea4r_marker.setWidth(settings.gridWidth)
        self.dggal_rtea9r_marker = QgsRubberBand(
            self.canvas, QgsWkbTypes.PolygonGeometry
        )
        self.dggal_rtea9r_marker.setStrokeColor(settings.markerColor)
        self.dggal_rtea9r_marker.setWidth(settings.gridWidth)
        self.dggal_rtea3h_marker = QgsRubberBand(
            self.canvas, QgsWkbTypes.PolygonGeometry
        )
        self.dggal_rtea3h_marker.setStrokeColor(settings.markerColor)
        self.dggal_rtea3h_marker.setWidth(settings.gridWidth)
        self.dggal_rtea7h_marker = QgsRubberBand(
            self.canvas, QgsWkbTypes.PolygonGeometry
        )        
        self.dggal_rtea7h_marker.setStrokeColor(settings.markerColor)
        self.dggal_rtea7h_marker.setWidth(settings.gridWidth)
        self.dggal_rtea7h_z7_marker = QgsRubberBand(
            self.canvas, QgsWkbTypes.PolygonGeometry
        )
        self.dggal_rtea7h_z7_marker.setStrokeColor(settings.markerColor)
        self.dggal_rtea7h_z7_marker.setWidth(settings.gridWidth)

        self.dggal_healpix_marker = QgsRubberBand(
            self.canvas, QgsWkbTypes.PolygonGeometry
        )
        self.dggal_healpix_marker.setStrokeColor(settings.markerColor)
        self.dggal_healpix_marker.setWidth(settings.gridWidth)

        self.dggal_rhealpix_marker = QgsRubberBand(
            self.canvas, QgsWkbTypes.PolygonGeometry
        )
        self.dggal_rhealpix_marker.setStrokeColor(settings.markerColor)
        self.dggal_rhealpix_marker.setWidth(settings.gridWidth)

        self.dggrid_superfund_marker = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
        self.dggrid_superfund_marker.setStrokeColor(settings.markerColor)
        self.dggrid_superfund_marker.setWidth(settings.gridWidth)
        
        self.dggrid_planetrisk_marker = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
        self.dggrid_planetrisk_marker.setStrokeColor(settings.markerColor)
        self.dggrid_planetrisk_marker.setWidth(settings.gridWidth)
       
        self.dggrid_isea3h_marker = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
        self.dggrid_isea3h_marker.setStrokeColor(settings.markerColor)
        self.dggrid_isea3h_marker.setWidth(settings.gridWidth)
        
        self.dggrid_isea4h_marker = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
        self.dggrid_isea4h_marker.setStrokeColor(settings.markerColor)
        self.dggrid_isea4h_marker.setWidth(settings.gridWidth)
        
        self.dggrid_isea4t_marker = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
        self.dggrid_isea4t_marker.setStrokeColor(settings.markerColor)
        self.dggrid_isea4t_marker.setWidth(settings.gridWidth)
        
        self.dggrid_isea4d_marker = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
        self.dggrid_isea4d_marker.setStrokeColor(settings.markerColor)
        self.dggrid_isea4d_marker.setWidth(settings.gridWidth)
        
        self.dggrid_isea43h_marker = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
        self.dggrid_isea43h_marker.setStrokeColor(settings.markerColor)
        self.dggrid_isea43h_marker.setWidth(settings.gridWidth)
        
        self.dggrid_isea7h_marker = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
        self.dggrid_isea7h_marker.setStrokeColor(settings.markerColor)
        self.dggrid_isea7h_marker.setWidth(settings.gridWidth)

        self.dggrid_igeo7_marker = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
        self.dggrid_igeo7_marker.setStrokeColor(settings.markerColor)
        self.dggrid_igeo7_marker.setWidth(settings.gridWidth)

        self.dggrid_fuller3h_marker = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
        self.dggrid_fuller3h_marker.setStrokeColor(settings.markerColor)
        self.dggrid_fuller3h_marker.setWidth(settings.gridWidth)
        
        self.dggrid_fuller4h_marker = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
        self.dggrid_fuller4h_marker.setStrokeColor(settings.markerColor)
        self.dggrid_fuller4h_marker.setWidth(settings.gridWidth)
        
        self.dggrid_fuller4t_marker = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
        self.dggrid_fuller4t_marker.setStrokeColor(settings.markerColor)
        self.dggrid_fuller4t_marker.setWidth(settings.gridWidth)
        
        self.dggrid_fuller4d_marker = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
        self.dggrid_fuller4d_marker.setStrokeColor(settings.markerColor)
        self.dggrid_fuller4d_marker.setWidth(settings.gridWidth)
        
        self.dggrid_fuller43h_marker = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
        self.dggrid_fuller43h_marker.setStrokeColor(settings.markerColor)
        self.dggrid_fuller43h_marker.setWidth(settings.gridWidth)
        
        self.dggrid_fuller7h_marker = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
        self.dggrid_fuller7h_marker.setStrokeColor(settings.markerColor)
        self.dggrid_fuller7h_marker.setWidth(settings.gridWidth)    


        self.isea4t_marker = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
        self.isea4t_marker.setStrokeColor(settings.markerColor)
        self.isea4t_marker.setWidth(settings.gridWidth)
        self.isea3h_marker = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
        self.isea3h_marker.setStrokeColor(settings.markerColor)
        self.ease_marker = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
        self.ease_marker.setStrokeColor(settings.markerColor)
        self.ease_marker.setWidth(settings.gridWidth)


        self.qtm_marker = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
        self.qtm_marker.setStrokeColor(settings.markerColor)
        self.qtm_marker.setWidth(settings.gridWidth)

        self.olc_marker = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
        self.olc_marker.setStrokeColor(settings.markerColor)
        self.olc_marker.setWidth(settings.gridWidth)

        self.geohash_marker = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
        self.geohash_marker.setStrokeColor(settings.markerColor)
        self.geohash_marker.setWidth(settings.gridWidth)

        self.georef_marker = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
        self.georef_marker.setStrokeColor(settings.markerColor)
        self.georef_marker.setWidth(settings.gridWidth)

        self.mgrs_marker = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
        self.mgrs_marker.setStrokeColor(settings.markerColor)
        self.mgrs_marker.setWidth(settings.gridWidth)

        self.tilecode_marker = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
        self.tilecode_marker.setStrokeColor(settings.markerColor)
        self.tilecode_marker.setWidth(settings.gridWidth)

        self.quadkey_marker = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
        self.quadkey_marker.setStrokeColor(settings.markerColor)
        self.quadkey_marker.setWidth(settings.gridWidth)

        self.maidenhead_marker = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
        self.maidenhead_marker.setStrokeColor(settings.markerColor)
        self.maidenhead_marker.setWidth(settings.gridWidth)

        self.gars_marker = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
        self.gars_marker.setStrokeColor(settings.markerColor)
        self.gars_marker.setWidth(settings.gridWidth)

        self.digipin_marker = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
        self.digipin_marker.setStrokeColor(settings.markerColor)
        self.digipin_marker.setWidth(settings.gridWidth)


    def _dggs_row_label(self, prefix):
        """Return the form-row label widget for a DGGS prefix."""
        for name in (f"{prefix}Label", f"{prefix}Llabel"):
            widget = getattr(self, name, None)
            if widget is not None:
                return widget
        return None

    def _apply_dggs_row_visibility(self):
        rows = (
            ("h3Visible", "h3"),
            ("s2Visible", "s2"),
            ("a5Visible", "a5"),
            ("rhealpixVisible", "rhealpix"),
            ("isea4tVisible", "isea4t"),
            ("isea3hVisible", "isea3h"),
            ("easeVisible", "ease"),
            ("dggal_gnosisVisible", "dggal_gnosis"),
            ("dggal_isea4rVisible", "dggal_isea4r"),
            ("dggal_isea9rVisible", "dggal_isea9r"),
            ("dggal_isea3hVisible", "dggal_isea3h"),
            ("dggal_isea7hVisible", "dggal_isea7h"),
            ("dggal_isea7h_z7Visible", "dggal_isea7h_z7"),
            ("dggal_ivea4rVisible", "dggal_ivea4r"),
            ("dggal_ivea9rVisible", "dggal_ivea9r"),
            ("dggal_ivea3hVisible", "dggal_ivea3h"),
            ("dggal_ivea7hVisible", "dggal_ivea7h"),
            ("dggal_ivea7h_z7Visible", "dggal_ivea7h_z7"),
            ("dggal_rtea4rVisible", "dggal_rtea4r"),
            ("dggal_rtea9rVisible", "dggal_rtea9r"),
            ("dggal_rtea3hVisible", "dggal_rtea3h"),
            ("dggal_rtea7hVisible", "dggal_rtea7h"),
            ("dggal_rtea7h_z7Visible", "dggal_rtea7h_z7"),
            ("dggal_healpixVisible", "dggal_healpix"),
            ("dggal_rhealpixVisible", "dggal_rhealpix"),
            ("dggrid_superfundVisible", "dggrid_superfund"),
            ("dggrid_planetriskVisible", "dggrid_planetrisk"),
            ("dggrid_isea3hVisible", "dggrid_isea3h"),
            ("dggrid_isea4hVisible", "dggrid_isea4h"),
            ("dggrid_isea4tVisible", "dggrid_isea4t"),
            ("dggrid_isea4dVisible", "dggrid_isea4d"),
            ("dggrid_isea43hVisible", "dggrid_isea43h"),
            ("dggrid_isea7hVisible", "dggrid_isea7h"),
            ("dggrid_igeo7Visible", "dggrid_igeo7"),
            ("dggrid_fuller3hVisible", "dggrid_fuller3h"),
            ("dggrid_fuller4hVisible", "dggrid_fuller4h"),
            ("dggrid_fuller4tVisible", "dggrid_fuller4t"),
            ("dggrid_fuller4dVisible", "dggrid_fuller4d"),
            ("dggrid_fuller43hVisible", "dggrid_fuller43h"),
            ("dggrid_fuller7hVisible", "dggrid_fuller7h"),
            ("qtmVisible", "qtm"),
            ("olcVisible", "olc"),
            ("geohashVisible", "geohash"),
            ("georefVisible", "georef"),
            ("mgrsVisible", "mgrs"),
            ("tilecodeVisible", "tilecode"),
            ("quadkeyVisible", "quadkey"),
            ("maidenheadVisible", "maidenhead"),
            ("garsVisible", "gars"),
            ("digipinVisible", "digipin"),
        )
        for settings_key, prefix in rows:
            state = int(getattr(settings, settings_key, Qt.CheckState.Checked))
            visible = state == Qt.CheckState.Checked
            row_widget = self._dggs_row_label(prefix)
            if row_widget is None:
                row_widget = getattr(self, f"{prefix}LineEdit", None)
            if row_widget is not None:
                self.formLayout.setRowVisible(row_widget, visible)

    def _dggs_visible(self, settings_key):
        state = int(getattr(settings, settings_key, Qt.CheckState.Checked))
        return state == Qt.CheckState.Checked

    def _should_update_coord(self, id, coord_id, visible_key=None):
        if id == coord_id:
            return False
        if id == -1 and visible_key is not None:
            return self._dggs_visible(visible_key)
        return True

    def configure(self):
        settings.readSettings()
        self._apply_dggs_row_visibility()
        self.removeMarker()
        self.updateMarker()

    def showEvent(self, e):
        self.inputXYOrder = settings.coordOrder
        self.xyButton.setDefaultAction(self.xymenu.actions()[settings.coordOrder])
        self.updateLabel()
        self.configure()
        try:
            get_plugin_dggrid_instance()
        except Exception:
            pass

    def closeEvent(self, e):
        self.removeMarker()
        if self.savedMapTool:
            self.canvas.setMapTool(self.savedMapTool)
            self.savedMapTool = None
        QDockWidget.closeEvent(self, e)

    def xyTriggered(self, action):
        self.xyButton.setDefaultAction(action)
        self.inputXYOrder = action.data()
        if self.origPt is not None:
            self.updateCoordinates(-1, self.origPt, self.origCrs)
        self.updateLabel()

    def showInvalid(self, id):
        self.origPt = None
        if id != 0:
            self.wgs84LineEdit.setText(s_invalid)
        if id != 1:
            self.projLineEdit.setText(s_invalid)
        if id != 2:
            self.customLineEdit.setText(s_invalid)
        if id != 3:
            self.utmLineEdit.setText(s_invalid)
        if id != 4:
            self.h3LineEdit.setText(s_invalid)
        if id != 5:
            self.s2LineEdit.setText(s_invalid)
        if id != 6:
            self.a5LineEdit.setText(s_invalid)
        if id != 7:
            self.rhealpixLineEdit.setText(s_invalid)      
        
        if id != 8:
            self.dggal_gnosisLineEdit.setText(s_invalid)
        
        if id != 9: 
            self.dggal_isea4rLineEdit.setText(s_invalid)
        if id != 10:
            self.dggal_isea9rLineEdit.setText(s_invalid)
        if id != 11:
            self.dggal_isea3hLineEdit.setText(s_invalid)
        if id != 12:
            self.dggal_isea7hLineEdit.setText(s_invalid)
        if id != 13:
            self.dggal_isea7h_z7LineEdit.setText(s_invalid)
        
        if id != 14:
            self.dggal_ivea4rLineEdit.setText(s_invalid)
        if id != 15:
            self.dggal_ivea9rLineEdit.setText(s_invalid)
        if id != 16:
            self.dggal_ivea3hLineEdit.setText(s_invalid)
        if id != 17:
            self.dggal_ivea7hLineEdit.setText(s_invalid)
        if id != 18:        
            self.dggal_ivea7h_z7LineEdit.setText(s_invalid)
       
        if id != 19:
            self.dggal_rtea4rLineEdit.setText(s_invalid)
        if id != 20:
            self.dggal_rtea9rLineEdit.setText(s_invalid)
        if id != 21:
            self.dggal_rtea3hLineEdit.setText(s_invalid)
        if id != 22:
            self.dggal_rtea7hLineEdit.setText(s_invalid)
        if id != 23:            
            self.dggal_rtea7h_z7LineEdit.setText(s_invalid)     
        if id != 24:
            self.dggal_healpixLineEdit.setText(s_invalid)
        if id != 25:
            self.dggal_rhealpixLineEdit.setText(s_invalid)

        if id != 26:
            self.dggrid_superfundLineEdit.setText(s_invalid)
        if id != 27:
            self.dggrid_planetriskLineEdit.setText(s_invalid)
        if id != 28:
            self.dggrid_isea3hLineEdit.setText(s_invalid)
        if id != 29:
            self.dggrid_isea4hLineEdit.setText(s_invalid)
        if id != 30:
            self.dggrid_isea4tLineEdit.setText(s_invalid)
        if id != 31:
            self.dggrid_isea4dLineEdit.setText(s_invalid)
        if id != 32:
            self.dggrid_isea43hLineEdit.setText(s_invalid)
        if id != 33:
            self.dggrid_isea7hLineEdit.setText(s_invalid)   
        if id != 35:    
            self.dggrid_igeo7LineEdit.setText(s_invalid)
        if id != 36:
            self.dggrid_fuller3hLineEdit.setText(s_invalid)
        if id != 37:
            self.dggrid_fuller4hLineEdit.setText(s_invalid)
        if id != 38:
            self.dggrid_fuller4tLineEdit.setText(s_invalid)
        if id != 39:
            self.dggrid_fuller4dLineEdit.setText(s_invalid)
        if id != 40:
            self.dggrid_fuller43hLineEdit.setText(s_invalid)
        if id != 41:
            self.dggrid_fuller7hLineEdit.setText(s_invalid)
        
        if id != 42:
            self.isea4tLineEdit.setText(s_invalid)
        if id != 43:
            self.isea3hLineEdit.setText(s_invalid)
        if id != 44:
            self.easeLineEdit.setText(s_invalid)

        if id != 45:
            self.qtmLineEdit.setText(s_invalid)
        if id != 45:
            self.olcLineEdit.setText(s_invalid)
        if id != 46:
            self.geohashLineEdit.setText(s_invalid)
        if id != 47:
            self.georefLineEdit.setText(s_invalid)
        if id != 48:
            self.mgrsLineEdit.setText(s_invalid)
        if id != 49:
            self.tilecodeLineEdit.setText(s_invalid)
        if id != 50:
            self.quadkeyLineEdit.setText(s_invalid)
        if id != 51:
            self.maidenheadLineEdit.setText(s_invalid)
        if id != 52:
            self.garsLineEdit.setText(s_invalid)
        if id != 53:
            self.digipinLineEdit.setText(s_invalid)

    def clearForm(self):
        self.removeMarker()
        self.origPt = None

        self.wgs84LineEdit.setText("")
        self.projLineEdit.setText("")
        self.customLineEdit.setText("")
        self.utmLineEdit.setText("")

        self.h3LineEdit.setText("")
        self.s2LineEdit.setText("")
        self.a5LineEdit.setText("")
        self.rhealpixLineEdit.setText("")

        self.dggal_gnosisLineEdit.setText("")

        self.dggal_isea4rLineEdit.setText("")
        self.dggal_isea9rLineEdit.setText("")
        self.dggal_isea3hLineEdit.setText("")
        self.dggal_isea7hLineEdit.setText("")
        self.dggal_isea7h_z7LineEdit.setText("")

        self.dggal_ivea4rLineEdit.setText("")
        self.dggal_ivea9rLineEdit.setText("")
        self.dggal_ivea3hLineEdit.setText("")
        self.dggal_ivea7hLineEdit.setText("")
        self.dggal_ivea7h_z7LineEdit.setText("")

        self.dggal_rtea4rLineEdit.setText("")
        self.dggal_rtea9rLineEdit.setText("")
        self.dggal_rtea3hLineEdit.setText("")   
        self.dggal_rtea7hLineEdit.setText("")
        self.dggal_rtea7h_z7LineEdit.setText("")

        self.dggal_healpixLineEdit.setText("")
        self.dggal_rhealpixLineEdit.setText("")         

        self.dggrid_superfundLineEdit.setText("")
        self.dggrid_planetriskLineEdit.setText("")
        self.dggrid_isea3hLineEdit.setText("")
        self.dggrid_isea4hLineEdit.setText("")
        self.dggrid_isea4tLineEdit.setText("")
        self.dggrid_isea4dLineEdit.setText("")
        self.dggrid_isea43hLineEdit.setText("")
        self.dggrid_isea7hLineEdit.setText("")
        self.dggrid_igeo7LineEdit.setText("")
        self.dggrid_fuller3hLineEdit.setText("")
        self.dggrid_fuller4hLineEdit.setText("")
        self.dggrid_fuller4tLineEdit.setText("")
        self.dggrid_fuller4dLineEdit.setText("")
        self.dggrid_fuller43hLineEdit.setText("")
        self.dggrid_fuller7hLineEdit.setText("")

        self.isea4tLineEdit.setText("")
        self.isea3hLineEdit.setText("")
        self.easeLineEdit.setText("")
        self.qtmLineEdit.setText("")
        self.olcLineEdit.setText("")
        self.geohashLineEdit.setText("")
        self.georefLineEdit.setText("")
        self.mgrsLineEdit.setText("")
        self.tilecodeLineEdit.setText("")
        self.quadkeyLineEdit.setText("")
        self.maidenheadLineEdit.setText("")
        self.garsLineEdit.setText("")
        self.digipinLineEdit.setText("")


    def updateCoordinates(self, id, pt, crs):
        self.origPt = pt
        self.origCrs = crs
        projCRS = self.canvas.mapSettings().destinationCrs()
        customCRS = self.customProjectionSelectionWidget.crs()
        if crs == epsg4326:
            pt4326 = pt
        else:
            trans = QgsCoordinateTransform(crs, epsg4326, QgsProject.instance())
            pt4326 = trans.transform(pt.x(), pt.y())
        if id != 0:  # WGS 84
            if self.inputXYOrder == 0:  # Y, X
                s = "{:.{prec}f}{}{:.{prec}f}".format(
                    pt4326.y(), ",", pt4326.x(), prec=settings.epsg4326Precision
                )
            else:
                s = "{:.{prec}f}{}{:.{prec}f}".format(
                    pt4326.x(), ",", pt4326.y(), prec=settings.epsg4326Precision
                )
            self.wgs84LineEdit.setText(s)
        if id != 1:  # Project CRS
            try:
                if crs == projCRS:
                    newpt = pt
                else:
                    trans = QgsCoordinateTransform(crs, projCRS, QgsProject.instance())
                    newpt = trans.transform(pt.x(), pt.y())
                if self.inputXYOrder == 0:  # Y, X
                    s = "{:.{prec}f}{}{:.{prec}f}".format(
                        newpt.y(), ",", newpt.x(), prec=settings.epsg4326Precision
                    )
                else:
                    s = "{:.{prec}f}{}{:.{prec}f}".format(
                        newpt.x(), ",", newpt.y(), prec=settings.epsg4326Precision
                    )
            except Exception:
                s = s_invalid
            self.projLineEdit.setText(s)

        if id != 2:  # Custom CRS
            try:
                if crs == customCRS:
                    newpt = pt
                else:
                    trans = QgsCoordinateTransform(
                        crs, customCRS, QgsProject.instance()
                    )
                    newpt = trans.transform(pt.x(), pt.y())
                if self.inputXYOrder == 0:  # Y, X
                    s = "{:.{prec}f}{}{:.{prec}f}".format(
                        newpt.y(), ",", newpt.x(), prec=settings.epsg4326Precision
                    )
                else:
                    s = "{:.{prec}f}{}{:.{prec}f}".format(
                        newpt.x(), ",", newpt.y(), prec=settings.epsg4326Precision
                    )
            except Exception:
                s = s_invalid
            self.customLineEdit.setText(s)

        if id != 3:  # UTM
            s = latLon2Utm(pt4326.y(), pt4326.x(), 2)
            self.utmLineEdit.setText(s)

        if self._should_update_coord(id, 4, "h3Visible"):  # H3
            try:
                s = latlon2h3(pt4326.y(), pt4326.x(), settings.h3Res)
            except Exception:
                s = s_invalid
            self.h3LineEdit.setText(s)
        if self._should_update_coord(id, 5, "s2Visible"):  # S2
            try:
                s = latlon2s2(pt4326.y(), pt4326.x(), settings.s2Res)
            except Exception:
                s = s_invalid
            self.s2LineEdit.setText(s)
        if self._should_update_coord(id, 6, "a5Visible"):  # A5
            try:
                s = latlon2a5(pt4326.y(), pt4326.x(), settings.a5Res)
            except Exception:
                s = s_invalid
            self.a5LineEdit.setText(s)
        if self._should_update_coord(id, 7, "rhealpixVisible"):  # rHEALPix
            try:
                s = latlon2rhealpix(pt4326.y(), pt4326.x(), settings.rhealpixRes)
            except Exception:
                s = s_invalid
            self.rhealpixLineEdit.setText(s)
    
        ### DGGAL
        if self._should_update_coord(id, 8, "dggal_gnosisVisible"):
            try:
                s = latlon2dggal(
                    "gnosis", pt4326.y(), pt4326.x(), settings.dggal_gnosisRes
                )
            except Exception:
                s = s_invalid
            self.dggal_gnosisLineEdit.setText(s)
        
        if self._should_update_coord(id, 9, "dggal_isea4rVisible"):
            try:
                s = latlon2dggal(
                    "isea4r", pt4326.y(), pt4326.x(), settings.dggal_isea4rRes
                )
            except Exception:
                s = s_invalid
            self.dggal_isea4rLineEdit.setText(s)        
        if self._should_update_coord(id, 10, "dggal_isea9rVisible"):
            try:
                s = latlon2dggal(
                    "isea9r", pt4326.y(), pt4326.x(), settings.dggal_isea9rRes
                )
            except Exception:
                s = s_invalid
            self.dggal_isea9rLineEdit.setText(s)
        if self._should_update_coord(id, 11, "dggal_isea3hVisible"):
            try:
                s = latlon2dggal(
                    "isea3h", pt4326.y(), pt4326.x(), settings.dggal_isea3hRes
                )
            except Exception:
                s = s_invalid
            self.dggal_isea3hLineEdit.setText(s)
        if self._should_update_coord(id, 12, "dggal_isea7hVisible"):
            try:
                s = latlon2dggal(
                    "isea7h", pt4326.y(), pt4326.x(), settings.dggal_isea7hRes
                )
            except Exception:
                s = s_invalid
            self.dggal_isea7hLineEdit.setText(s)
        if self._should_update_coord(id, 13, "dggal_isea7h_z7Visible"):
            try:
                s = latlon2dggal(
                    "isea7h_z7", pt4326.y(), pt4326.x(), settings.dggal_isea7h_z7Res
                )
            except Exception:
                s = s_invalid
            self.dggal_isea7h_z7LineEdit.setText(s)
        
        if self._should_update_coord(id, 14, "dggal_ivea4rVisible"):
            try:
                s = latlon2dggal(
                    "ivea4r", pt4326.y(), pt4326.x(), settings.dggal_ivea4rRes
                )
            except Exception:
                s = s_invalid
            self.dggal_ivea4rLineEdit.setText(s)
        if self._should_update_coord(id, 15, "dggal_ivea9rVisible"):
            try:
                s = latlon2dggal(
                    "ivea9r", pt4326.y(), pt4326.x(), settings.dggal_ivea9rRes
                )
            except Exception:
                s = s_invalid
            self.dggal_ivea9rLineEdit.setText(s)
        if self._should_update_coord(id, 16, "dggal_ivea3hVisible"):
            try:
                s = latlon2dggal(
                    "ivea3h", pt4326.y(), pt4326.x(), settings.dggal_ivea3hRes
                )
            except Exception:
                s = s_invalid
            self.dggal_ivea3hLineEdit.setText(s)
        if self._should_update_coord(id, 17, "dggal_ivea7hVisible"):
            try:
                s = latlon2dggal(
                    "ivea7h", pt4326.y(), pt4326.x(), settings.dggal_ivea7hRes
                )
            except Exception:
                s = s_invalid
            self.dggal_ivea7hLineEdit.setText(s)
        if self._should_update_coord(id, 18, "dggal_ivea7h_z7Visible"):
            try:
                s = latlon2dggal(
                    "ivea7h_z7", pt4326.y(), pt4326.x(), settings.dggal_ivea7h_z7Res
                )
            except Exception:
                s = s_invalid
            self.dggal_ivea7h_z7LineEdit.setText(s)

        if self._should_update_coord(id, 19, "dggal_rtea4rVisible"):
            try:
                s = latlon2dggal(
                    "rtea4r", pt4326.y(), pt4326.x(), settings.dggal_rtea4rRes
                )
            except Exception:
                s = s_invalid
            self.dggal_rtea4rLineEdit.setText(s)
        if self._should_update_coord(id, 20, "dggal_rtea9rVisible"):
            try:
                s = latlon2dggal(
                    "rtea9r", pt4326.y(), pt4326.x(), settings.dggal_rtea9rRes
                )
            except Exception:
                s = s_invalid
            self.dggal_rtea9rLineEdit.setText(s)
        if self._should_update_coord(id, 21, "dggal_rtea3hVisible"):
            try:
                s = latlon2dggal(
                    "rtea3h", pt4326.y(), pt4326.x(), settings.dggal_rtea3hRes
                )
            except Exception:
                s = s_invalid
            self.dggal_rtea3hLineEdit.setText(s)
        if self._should_update_coord(id, 22, "dggal_rtea7hVisible"):
            try:
                s = latlon2dggal(
                    "rtea7h", pt4326.y(), pt4326.x(), settings.dggal_rtea7hRes
                )
            except Exception:
                s = s_invalid
            self.dggal_rtea7hLineEdit.setText(s)
        if self._should_update_coord(id, 23, "dggal_rtea7h_z7Visible"):
            try:
                s = latlon2dggal(
                    "rtea7h_z7", pt4326.y(), pt4326.x(), settings.dggal_rtea7h_z7Res
                )
            except Exception:
                s = s_invalid
            self.dggal_rtea7h_z7LineEdit.setText(s)

        if self._should_update_coord(id, 24, "dggal_healpixVisible"):
            try:
                s = latlon2dggal(
                    "healpix", pt4326.y(), pt4326.x(), settings.dggal_healpixRes
                )
            except Exception:
                s = s_invalid
            self.dggal_healpixLineEdit.setText(s)
        if self._should_update_coord(id, 25, "dggal_rhealpixVisible"):
            try:
                s = latlon2dggal(
                    "rhealpix", pt4326.y(), pt4326.x(), settings.dggal_rhealpixRes
                )
            except Exception:
                s = s_invalid
            self.dggal_rhealpixLineEdit.setText(s)    
        

        ### DGGRID
        dggrid_instance = None
        for prefix, dggs_type, coord_id in DGGRID_LATLON_ROWS:
            if self._should_update_coord(id, coord_id, f"{prefix}Visible"):
                if dggrid_instance is None:
                    dggrid_instance = get_plugin_dggrid_instance()
                try:
                    s = cached_latlon2dggrid(
                        dggrid_instance,
                        dggs_type,
                        pt4326.y(),
                        pt4326.x(),
                        getattr(settings, f"{prefix}Res"),
                    )
                except Exception:
                    s = s_invalid
                getattr(self, f"{prefix}LineEdit").setText(s)

      
        if self._should_update_coord(id, 41, "isea4tVisible"):  # ISEA4T
            try:
                s = latlon2isea4t(pt4326.y(), pt4326.x(), settings.isea4tRes)
            except Exception:
                s = s_invalid
            self.isea4tLineEdit.setText(s)
        
        
        if self._should_update_coord(id, 42, "isea3hVisible"):  # ISEA3H
            try:
                s = latlon2isea3h(pt4326.y(), pt4326.x(), settings.isea3hRes)
            except Exception:
                s = s_invalid
            self.isea3hLineEdit.setText(s)
        if self._should_update_coord(id, 43, "easeVisible"):  # EASE
            try:
                s = latlon2ease(pt4326.y(), pt4326.x(), settings.easeRes)
            except Exception:
                s = s_invalid
            self.easeLineEdit.setText(s)

        ### QTM
        if self._should_update_coord(id, 44, "qtmVisible"):
            try:
                s = latlon2qtm(pt4326.y(), pt4326.x(), settings.qtmRes)
            except Exception:
                s = s_invalid
            self.qtmLineEdit.setText(s)

        ### Graticule-based DGGS
        if self._should_update_coord(id, 45, "olcVisible"):
            try:
                s = latlon2olc(pt4326.y(), pt4326.x(), settings.olcRes)
            except Exception:
                s = s_invalid
            self.olcLineEdit.setText(s)
        if self._should_update_coord(id, 46, "geohashVisible"):
            try:
                s = latlon2geohash(pt4326.y(), pt4326.x(), settings.geohashRes)
            except Exception:
                s = s_invalid
            self.geohashLineEdit.setText(s)
        if self._should_update_coord(id, 47, "georefVisible"):
            try:
                s = latlon2georef(pt4326.y(), pt4326.x(), settings.georefRes)
            except Exception:
                s = s_invalid
            self.georefLineEdit.setText(s)
        if self._should_update_coord(id, 48, "mgrsVisible"):
            try:
                s = latlon2mgrs(pt4326.y(), pt4326.x(), settings.mgrsRes)
            except Exception:
                s = s_invalid
            self.mgrsLineEdit.setText(s)
        if self._should_update_coord(id, 49, "tilecodeVisible"):
            try:
                s = latlon2tilecode(pt4326.y(), pt4326.x(), settings.tilecodeRes)
            except Exception:
                s = s_invalid
            self.tilecodeLineEdit.setText(s)
        if self._should_update_coord(id, 50, "quadkeyVisible"):
            try:
                s = latlon2quadkey(pt4326.y(), pt4326.x(), settings.quadkeyRes)
            except Exception:
                s = s_invalid
            self.quadkeyLineEdit.setText(s)
        if self._should_update_coord(id, 51, "maidenheadVisible"):
            try:
                s = latlon2maidenhead(pt4326.y(), pt4326.x(), settings.maidenheadRes)
            except Exception:
                s = s_invalid
            self.maidenheadLineEdit.setText(s)
        if self._should_update_coord(id, 52, "garsVisible"):
            try:
                s = latlon2gars(pt4326.y(), pt4326.x(), settings.garsRes)
            except Exception:
                s = s_invalid
            self.garsLineEdit.setText(s)

        ### DIGIPIN
        if self._should_update_coord(id, 53, "digipinVisible"):
            try:
                s = latlon2digipin(pt4326.y(), pt4326.x(), settings.digipinRes)
            except Exception:
                s = s_invalid
            self.digipinLineEdit.setText(s)

    def commitWGS84(self):
        text = self.wgs84LineEdit.text().strip()
        try:
            lat, lon = parseDMSString(text, self.inputXYOrder)
            pt = QgsPoint(lon, lat)
        except Exception:
            traceback.print_exc()
            self.showInvalid(0)
        self.updateCoordinates(0, pt, epsg4326)

    def commitPROJ(self):
        projCRS = self.canvas.mapSettings().destinationCrs()
        text = self.projLineEdit.text().strip()
        try:
            if projCRS == epsg4326:
                lat, lon = parseDMSString(text, self.inputXYOrder)
            else:
                coords = re.split(r"[\s,;:]+", text, 1)
                if len(coords) < 2:
                    self.showInvalid(1)
                    return
                if self.inputXYOrder == 0:  # Lat, Lon
                    lat = float(coords[0])
                    lon = float(coords[1])
                else:  # Lon, Lat
                    lon = float(coords[0])
                    lat = float(coords[1])
        except Exception:
            self.showInvalid(1)
            return

        pt = QgsPoint(lon, lat)
        self.updateCoordinates(1, pt, projCRS)

    def commitCUSTOM(self):
        customCRS = self.customProjectionSelectionWidget.crs()
        text = self.customLineEdit.text().strip()
        try:
            if customCRS == epsg4326:
                lat, lon = parseDMSString(text, self.inputXYOrder)
            else:
                coords = re.split(r"[\s,;:]+", text, 1)
                if len(coords) < 2:
                    self.showInvalid(2)
                    return
                if self.inputXYOrder == 0:  # Lat, Lon
                    lat = float(coords[0])
                    lon = float(coords[1])
                else:  # Lon, Lat
                    lon = float(coords[0])
                    lat = float(coords[1])
        except Exception:
            self.showInvalid(2)
            return

        pt = QgsPoint(lon, lat)
        self.updateCoordinates(2, pt, customCRS)

    def commitUTM(self):
        text = self.utmLineEdit.text().strip()
        if isUtm(text):
            pt = utm2Point(text, epsg4326)
            self.updateCoordinates(3, QgsPoint(pt), epsg4326)
        else:
            self.showInvalid(3)

    def commitH3(self):
        text = self.h3LineEdit.text().strip()
        try:
            h3_geometry = h32geo(text)
            num_edges = 6
            if h3.is_pentagon(text):
                num_edges = 5
            center_lat, center_lon, _, _, _ = geodesic_dggs_metrics(
                h3_geometry, num_edges
            )
            pt = QgsPoint(center_lon, center_lat)
            self.updateCoordinates(4, pt, epsg4326)
        except Exception:
            self.showInvalid(4)

    def commitS2(self):
        text = self.s2LineEdit.text().strip()
        try:
            s2_geometry = s22geo(text)
            num_edges = 4
            center_lat, center_lon, _, _, _ = geodesic_dggs_metrics(
                s2_geometry, num_edges
            )
            pt = QgsPoint(center_lon, center_lat)
            self.updateCoordinates(5, pt, epsg4326)
        except Exception:
            self.showInvalid(5)

    def commitA5(self):
        text = self.a5LineEdit.text().strip()
        try:
            a5_geometry = a52geo(text)
            num_edges = 5
            center_lat, center_lon, _, _, _ = geodesic_dggs_metrics(
                a5_geometry, num_edges
            )
            pt = QgsPoint(center_lon, center_lat)
            self.updateCoordinates(6, pt, epsg4326)
        except Exception:
            self.showInvalid(6)

    def commitrHEALPix(self):
        text = self.rhealpixLineEdit.text().strip()
        try:
            rhealpix_dggs = RHEALPixDGGS(
                ellipsoid=WGS84_ELLIPSOID, north_square=1, south_square=3, N_side=3
            )
            rhealpix_geometry = rhealpix2geo(text)
            rhealpix_uids = (text[0],) + tuple(map(int, text[1:]))
            rhealpix_cell = rhealpix_dggs.cell(rhealpix_uids)
            num_edges = 4
            if rhealpix_cell.ellipsoidal_shape() == "dart":
                num_edges = 3
            center_lat, center_lon, _, _, _ = geodesic_dggs_metrics(
                rhealpix_geometry, num_edges
            )
            pt = QgsPoint(center_lon, center_lat)
            self.updateCoordinates(7, pt, epsg4326)
        except Exception:
            self.showInvalid(7)

    def commitDGGAL_GNOSIS(self):
        text = self.dggal_gnosisLineEdit.text().strip()
        try:
            dggal_gnosis_geometry = dggal2geo("gnosis", text)
            num_edges = 4
            center_lat, center_lon, _, _, _ = geodesic_dggs_metrics(
                dggal_gnosis_geometry, num_edges
            )
            pt = QgsPoint(center_lon, center_lat)
            self.updateCoordinates(8, pt, epsg4326)
        except Exception:
            self.showInvalid(8)    

    def commitDGGAL_ISEA4R(self):
        text = self.dggal_isea4rLineEdit.text().strip()
        try:
            dggal_isea4r_geometry = dggal2geo("isea4r", text)
            num_edges = 4
            center_lat, center_lon, _, _, _ = geodesic_dggs_metrics(
                dggal_isea4r_geometry, num_edges
            )
            pt = QgsPoint(center_lon, center_lat)
            self.updateCoordinates(9, pt, epsg4326)
        except Exception:
            self.showInvalid(9)

    def commitDGGAL_ISEA9R(self):
        text = self.dggal_isea9rLineEdit.text().strip()
        try:
            dggal_isea9r_geometry = dggal2geo("isea9r", text)
            num_edges = 4
            center_lat, center_lon, _, _, _ = geodesic_dggs_metrics(
                dggal_isea9r_geometry, num_edges
            )
            pt = QgsPoint(center_lon, center_lat)
            self.updateCoordinates(10, pt, epsg4326)
        except Exception:
            self.showInvalid(10)

    def commitDGGAL_ISEA3H(self):
        text = self.dggal_isea3hLineEdit.text().strip()
        try:
            dggal_isea3h_geometry = dggal2geo("isea3h", text)
            num_edges = 6
            center_lat, center_lon, _, _, _ = geodesic_dggs_metrics(
                dggal_isea3h_geometry, num_edges
            )
            pt = QgsPoint(center_lon, center_lat)
            self.updateCoordinates(11, pt, epsg4326)
        except Exception:
            self.showInvalid(11)

    def commitDGGAL_ISEA7H(self):
            text = self.dggal_isea7hLineEdit.text().strip()
            try:
                dggal_isea7h_geometry = dggal2geo("isea7h", text)
                num_edges = 6
                center_lat, center_lon, _, _, _ = geodesic_dggs_metrics(
                    dggal_isea7h_geometry, num_edges
                )
                pt = QgsPoint(center_lon, center_lat)
                self.updateCoordinates(12, pt, epsg4326)
            except Exception:
                self.showInvalid(12)

    def commitDGGAL_ISEA7H_Z7(self):
        text = self.dggal_isea7h_z7LineEdit.text().strip()
        try:
            dggal_isea7h_z7_geometry = dggal2geo("isea7h_z7", text)
            num_edges = 6
            center_lat, center_lon, _, _, _ = geodesic_dggs_metrics(
                dggal_isea7h_z7_geometry, num_edges
            )
            pt = QgsPoint(center_lon, center_lat)
            self.updateCoordinates(13, pt, epsg4326)
        except Exception:
            self.showInvalid(13)

    def commitDGGAL_IVEA4R(self):
        text = self.dggal_ivea4rLineEdit.text().strip()
        try:
            dggal_ivea4r_geometry = dggal2geo("ivea4r", text)
            num_edges = 4
            center_lat, center_lon, _, _, _ = geodesic_dggs_metrics(
                dggal_ivea4r_geometry, num_edges
            )
            pt = QgsPoint(center_lon, center_lat)
            self.updateCoordinates(14, pt, epsg4326)
        except Exception:
            self.showInvalid(14)
    
    def commitDGGAL_IVEA9R(self):
        text = self.dggal_ivea9rLineEdit.text().strip()
        try:
            dggal_ivea9r_geometry = dggal2geo("ivea9r", text)
            num_edges = 4
            center_lat, center_lon, _, _, _ = geodesic_dggs_metrics(
                dggal_ivea9r_geometry, num_edges
            )
            pt = QgsPoint(center_lon, center_lat)
            self.updateCoordinates(15, pt, epsg4326)
        except Exception:
            self.showInvalid(15)
    
    def commitDGGAL_IVEA3H(self):
        text = self.dggal_ivea3hLineEdit.text().strip()
        try:
            dggal_ivea3h_geometry = dggal2geo("ivea3h", text)
            num_edges = 6
            center_lat, center_lon, _, _, _ = geodesic_dggs_metrics(
                dggal_ivea3h_geometry, num_edges
            )
            pt = QgsPoint(center_lon, center_lat)
            self.updateCoordinates(16, pt, epsg4326)
        except Exception:
            self.showInvalid(16)

    def commitDGGAL_IVEA7H(self):
        text = self.dggal_ivea7hLineEdit.text().strip()
        try:
            dggal_ivea7h_geometry = dggal2geo("ivea7h", text)
            num_edges = 6
            center_lat, center_lon, _, _, _ = geodesic_dggs_metrics(
                dggal_ivea7h_geometry, num_edges
            )
            pt = QgsPoint(center_lon, center_lat)
            self.updateCoordinates(17, pt, epsg4326)
        except Exception:
            self.showInvalid(17)

    def commitDGGAL_IVEA7H_Z7(self):
        text = self.dggal_ivea7h_z7LineEdit.text().strip()
        try:
            dggal_ivea7h_z7_geometry = dggal2geo("ivea7h_z7", text)
            num_edges = 6
            center_lat, center_lon, _, _, _ = geodesic_dggs_metrics(
                dggal_ivea7h_z7_geometry, num_edges
            )
            pt = QgsPoint(center_lon, center_lat)
            self.updateCoordinates(18, pt, epsg4326)
        except Exception:
            self.showInvalid(18)
    
    def commitDGGAL_RTEA4R(self):
        text = self.dggal_rtea4rLineEdit.text().strip()
        try:
            dggal_rtea4r_geometry = dggal2geo("rtea4r", text)
            num_edges = 4
            center_lat, center_lon, _, _, _ = geodesic_dggs_metrics(
                dggal_rtea4r_geometry, num_edges
            )
            pt = QgsPoint(center_lon, center_lat)
            self.updateCoordinates(19, pt, epsg4326)
        except Exception:
            self.showInvalid(19)

    def commitDGGAL_RTEA9R(self):
        text = self.dggal_rtea9rLineEdit.text().strip()
        try:
            dggal_rtea9r_geometry = dggal2geo("rtea9r", text)
            num_edges = 4
            center_lat, center_lon, _, _, _ = geodesic_dggs_metrics(
                dggal_rtea9r_geometry, num_edges
            )
            pt = QgsPoint(center_lon, center_lat)
            self.updateCoordinates(20, pt, epsg4326)
        except Exception:
            self.showInvalid(20)

    def commitDGGAL_RTEA3H(self):
        text = self.dggal_rtea3hLineEdit.text().strip()
        try:
            dggal_rtea3h_geometry = dggal2geo("rtea3h", text)
            num_edges = 6
            center_lat, center_lon, _, _, _ = geodesic_dggs_metrics(
                dggal_rtea3h_geometry, num_edges
            )
            pt = QgsPoint(center_lon, center_lat)
            self.updateCoordinates(21, pt, epsg4326)
        except Exception:
            self.showInvalid(21)

    def commitDGGAL_RTEA7H(self):
        text = self.dggal_rtea7hLineEdit.text().strip()
        try:
            dggal_rtea7h_geometry = dggal2geo("rtea7h", text)
            num_edges = 6
            center_lat, center_lon, _, _, _ = geodesic_dggs_metrics(
                dggal_rtea7h_geometry, num_edges
            )
            pt = QgsPoint(center_lon, center_lat)
            self.updateCoordinates(22, pt, epsg4326)
        except Exception:
            self.showInvalid(22)

    def commitDGGAL_RTEA7H_Z7(self):
        text = self.dggal_rtea7h_z7LineEdit.text().strip()
        try:
            dggal_rtea7h_z7_geometry = dggal2geo("rtea7h_z7", text)
            num_edges = 6
            center_lat, center_lon, _, _, _ = geodesic_dggs_metrics(
                dggal_rtea7h_z7_geometry, num_edges
            )
            pt = QgsPoint(center_lon, center_lat)
            self.updateCoordinates(23, pt, epsg4326)
        except Exception:
            self.showInvalid(23)

    def commitDGGAL_HEALPix(self):
        text = self.dggal_healpixLineEdit.text().strip()
        try:
            dggal_healpix_geometry = dggal2geo("healpix", text)
            num_edges = 4
            center_lat, center_lon, _, _, _ = geodesic_dggs_metrics(
                dggal_healpix_geometry, num_edges
            )
            pt = QgsPoint(center_lon, center_lat)
            self.updateCoordinates(24, pt, epsg4326)
        except Exception:
            self.showInvalid(24)


    def commitDGGAL_rHEALPix(self):
        text = self.dggal_rhealpixLineEdit.text().strip()
        try:
            dggal_rhealpix_geometry = dggal2geo("rhealpix", text)
            num_edges = 4
            center_lat, center_lon, _, _, _ = geodesic_dggs_metrics(
                dggal_rhealpix_geometry, num_edges
            )
            pt = QgsPoint(center_lon, center_lat)
            self.updateCoordinates(25, pt, epsg4326)
        except Exception:
            self.showInvalid(25)
    
    ### DGGRID
    def _plugin_dggrid(self):
        return get_plugin_dggrid_instance()

    def _dggrid_cell_polygon(self, dggs_type, cell_id, res):
        split = (
            settings.splitAntimeridian
            and dggs_type not in DGGRID_TYPES_NO_ANTIMERIDIAN
        )
        return cached_dggrid_cell_geometry(
            self._plugin_dggrid(),
            dggs_type,
            cell_id,
            res,
            split_antimeridian=split,
            options=dggrid_latlon_cell_options(),
        )

    def _commit_dggrid_row(self, line_edit, dggs_type, res, coord_id):
        text = line_edit.text().strip()
        try:
            cell_polygon = self._dggrid_cell_polygon(dggs_type, text, res)
            num_edges = len(cell_polygon.exterior.coords) - 1
            center_lat, center_lon, _, _, _ = geodesic_dggs_metrics(
                cell_polygon, num_edges
            )
            self.updateCoordinates(
                coord_id, QgsPoint(center_lon, center_lat), epsg4326
            )
        except Exception:
            self.showInvalid(coord_id)

    def _zoom_to_dggrid(self, line_edit, marker, dggs_type, res):
        try:
            text = line_edit.text().strip()
            if not text:
                return
            cell_polygon = self._dggrid_cell_polygon(dggs_type, text, res)
            num_edges = len(cell_polygon.exterior.coords) - 1
            center_lat, center_lon, _, _, _ = geodesic_dggs_metrics(
                cell_polygon, num_edges
            )
            pt = self.vgridtools.zoomTo(epsg4326, center_lat, center_lon)
            self.marker.reset(QgsWkbTypes.PointGeometry)
            self.marker.addPoint(pt)
            canvas_crs = self.canvas.mapSettings().destinationCrs()
            cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)
            if epsg4326 != canvas_crs:
                trans_to_canvas = QgsCoordinateTransform(
                    epsg4326, canvas_crs, QgsProject.instance()
                )
                cell_geometry.transform(trans_to_canvas)
            bbox = cell_geometry.boundingBox()
            bbox.scale(2.0, QgsPointXY(bbox.center()))
            self.canvas.setExtent(bbox)
            self.canvas.refresh()
            if not settings.persistentMarker:
                marker.reset(QgsWkbTypes.PolygonGeometry)
            marker.addGeometry(cell_geometry, None)
        except Exception as e:
            traceback.print_exc()
            self.iface.messageBar().pushMessage(
                "",
                tr("Invalid Coordinate: {}").format(str(e)),
                level=Qgis.Warning,
                duration=2,
            )

    def commitDGGRID_SUPERFUND(self):
        self._commit_dggrid_row(
            self.dggrid_superfundLineEdit,
            "SUPERFUND",
            settings.dggrid_superfundRes,
            26,
        )

    def commitDGGRID_PLANETRISK(self):
        self._commit_dggrid_row(
            self.dggrid_planetriskLineEdit,
            "PLANETRISK",
            settings.dggrid_planetriskRes,
            27,
        )

    def commitDGGRID_ISEA3H(self):
        self._commit_dggrid_row(
            self.dggrid_isea3hLineEdit,
            "ISEA3H",
            settings.dggrid_isea3hRes,
            28,
        )

    def commitDGGRID_ISEA4H(self):
        self._commit_dggrid_row(
            self.dggrid_isea4hLineEdit,
            "ISEA4H",
            settings.dggrid_isea4hRes,
            29,
        )

    def commitDGGRID_ISEA4T(self):
        self._commit_dggrid_row(
            self.dggrid_isea4tLineEdit,
            "ISEA4T",
            settings.dggrid_isea4tRes,
            30,
        )

    def commitDGGRID_ISEA4D(self):
        self._commit_dggrid_row(
            self.dggrid_isea4dLineEdit,
            "ISEA4D",
            settings.dggrid_isea4dRes,
            31,
        )

    def commitDGGRID_ISEA43H(self):
        self._commit_dggrid_row(
            self.dggrid_isea43hLineEdit,
            "ISEA43H",
            settings.dggrid_isea43hRes,
            32,
        )

    def commitDGGRID_ISEA7H(self):
        self._commit_dggrid_row(
            self.dggrid_isea7hLineEdit,
            "ISEA7H",
            settings.dggrid_isea7hRes,
            33,
        )

    def commitDGGRID_IGEO7(self):
        self._commit_dggrid_row(
            self.dggrid_igeo7LineEdit,
            "IGEO7",
            settings.dggrid_igeo7Res,
            34,
        )

    def commitDGGRID_FULLER3H(self):
        self._commit_dggrid_row(
            self.dggrid_fuller3hLineEdit,
            "FULLER3H",
            settings.dggrid_fuller3hRes,
            35,
        )

    def commitDGGRID_FULLER4H(self):
        self._commit_dggrid_row(
            self.dggrid_fuller4hLineEdit,
            "FULLER4H",
            settings.dggrid_fuller4hRes,
            36,
        )

    def commitDGGRID_FULLER4T(self):
        self._commit_dggrid_row(
            self.dggrid_fuller4tLineEdit,
            "FULLER4T",
            settings.dggrid_fuller4tRes,
            37,
        )

    def commitDGGRID_FULLER4D(self):
        self._commit_dggrid_row(
            self.dggrid_fuller4dLineEdit,
            "FULLER4D",
            settings.dggrid_fuller4dRes,
            38,
        )

    def commitDGGRID_FULLER43H(self):
        self._commit_dggrid_row(
            self.dggrid_fuller43hLineEdit,
            "FULLER43H",
            settings.dggrid_fuller43hRes,
            39,
        )

    def commitDGGRID_FULLER7H(self):
        self._commit_dggrid_row(
            self.dggrid_fuller7hLineEdit,
            "FULLER7H",
            settings.dggrid_fuller7hRes,
            40,
        )

    def commitISEA4T(self):
        text = self.isea4tLineEdit.text().strip()
        try:
            isea4t_geometry = isea4t2geo(text)
            num_edges = 3
            center_lat, center_lon, _, _, _ = geodesic_dggs_metrics(
                isea4t_geometry, num_edges
            )
            pt = QgsPoint(center_lon, center_lat)
            self.updateCoordinates(41, pt, epsg4326)
        except Exception:
            self.showInvalid(41)

    def commitISEA3H(self):
        text = self.isea3hLineEdit.text().strip()
        try:
            isea3h_geometry = isea3h2geo(text)
            num_edges = 6
            center_lat, center_lon, _, _, _ = geodesic_dggs_metrics(
                isea3h_geometry, num_edges
            )
            pt = QgsPoint(center_lon, center_lat)
            self.updateCoordinates(42, pt, epsg4326)
        except Exception:
            self.showInvalid(42)

    def commitEASE(self):
        text = self.easeLineEdit.text().strip()
        try:
            ease_geometry = ease2geo(text)
            num_edges = 4
            center_lat, center_lon, _, _, _ = geodesic_dggs_metrics(
                ease_geometry, num_edges
            )
            pt = QgsPoint(center_lon, center_lat)
            self.updateCoordinates(43, pt, epsg4326)
        except Exception:
            self.showInvalid(43)

    def commitQTM(self):
        text = self.qtmLineEdit.text().strip()
        try:
            qtm_geometry = qtm2geo(text)
            num_edges = 3
            center_lat, center_lon, _, _, _ = geodesic_dggs_metrics(
                qtm_geometry, num_edges
            )
            pt = QgsPoint(center_lon, center_lat)
            self.updateCoordinates(44, pt, epsg4326)
        except Exception:
            self.showInvalid(44)

    def commitOLC(self):
        text = self.olcLineEdit.text().strip()
        text = re.sub(r"\s+", "", text)  # Remove all white space
        try:
            olc_geometry = olc2geo(text)
            center_lat, center_lon, _, _, _ ,_ = graticule_dggs_metrics(olc_geometry)
            pt = QgsPoint(center_lon, center_lat)
            self.updateCoordinates(45, pt, epsg4326)
        except Exception:
            self.showInvalid(45)

    def commitGeohash(self):
        text = self.geohashLineEdit.text().strip()
        text = re.sub(r"\s+", "", text)  # Remove all white space
        try:
            geohash_geometry = geohash2geo(text)
            center_lat, center_lon, _, _, _, _ = graticule_dggs_metrics(geohash_geometry)
            pt = QgsPoint(center_lon, center_lat)
            self.updateCoordinates(46, pt, epsg4326)
        except Exception:
            self.showInvalid(46)

    def commitGEOREF(self):
        text = self.georefLineEdit.text().strip()
        try:
            georef_geometry = georef2geo(text)
            center_lat, center_lon, _, _, _, _ = graticule_dggs_metrics(georef_geometry)
            pt = QgsPoint(center_lon, center_lat)
            self.updateCoordinates(47, pt, epsg4326)
        except Exception:
            traceback.print_exc()
            self.showInvalid(47)

    def commitMGRS(self):
        text = self.mgrsLineEdit.text().strip()
        text = re.sub(r"\s+", "", text)  # Remove all white space
        text = re.sub(r"\s+", "", text)  # Remove all white space
        try:
            mgrs_geometry = mgrs2geo(text)        
                
            center_lat, center_lon, _, _, _, _ = graticule_dggs_metrics(mgrs_geometry)
            pt = QgsPoint(center_lon, center_lat)
            self.updateCoordinates(48, pt, epsg4326)
        except Exception:
            self.showInvalid(48)

    def commitTilecode(self):
        text = self.tilecodeLineEdit.text().strip()
        try:
            tilecode_geometry = tilecode2geo(text)
            center_lat, center_lon, _, _, _, _ = graticule_dggs_metrics(tilecode_geometry)
            pt = QgsPoint(center_lon, center_lat)
            self.updateCoordinates(49, pt, epsg4326)
        except Exception:
            self.showInvalid(49)

    def commitQuadkey(self):
        text = self.quadkeyLineEdit.text().strip()
        try:
            quadkey_geometry = quadkey2geo(text)
            center_lat, center_lon, _, _, _, _ = graticule_dggs_metrics(quadkey_geometry)
            pt = QgsPoint(center_lon, center_lat)
            self.updateCoordinates(50, pt, epsg4326)
        except Exception:
            self.showInvalid(50)

    def commitMaidenhead(self):
        text = self.maidenheadLineEdit.text().strip()
        try:
            maidenhead_geometry = maidenhead2geo(text)
            center_lat, center_lon, _, _, _, _ = graticule_dggs_metrics(maidenhead_geometry)
            pt = QgsPoint(center_lon, center_lat)
            self.updateCoordinates(51, pt, epsg4326)
        except Exception:
            self.showInvalid(51)

    def commitGARS(self):
        text = self.garsLineEdit.text().strip()
        try:
            gars_geometry = gars2geo(text)
            center_lat, center_lon, _, _, _, _ = graticule_dggs_metrics(gars_geometry)
            pt = QgsPoint(center_lon, center_lat)
            self.updateCoordinates(52, pt, epsg4326)    
        except Exception:
            traceback.print_exc()
            self.showInvalid(52)
    
    def commitDIGIPIN(self):
        text = self.digipinLineEdit.text().strip()
        try:
            digipin_geometry = digipin2geo(text)
            center_lat, center_lon, _, _, _, _ = graticule_dggs_metrics(digipin_geometry)
            pt = QgsPoint(center_lon, center_lat)
            self.updateCoordinates(53, pt, epsg4326)
        except Exception:
            self.showInvalid(53)

    def updateLabel(self):
        if self.inputXYOrder == 0:  # Y, X
            xy = "(Y, X)"
            latlon = "(lat,lon)"
        else:
            xy = "(X, Y)"
            latlon = "(lon,lat)"

        crs = self.canvas.mapSettings().destinationCrs()
        self.projectCRSLabel.setText("{}".format(crs.authid()))
        if crs.isGeographic():
            label = "→ {}".format(latlon)
        else:
            label = "→ {}".format(xy)
        self.latlonLabel.setText(label)

        label = "WGS 84 {}".format(latlon)
        self.wgs84Label.setText(label)

        crs = self.customProjectionSelectionWidget.crs()
        if crs.isGeographic():
            label = "→ {}".format(latlon)
        else:
            label = "→ {}".format(xy)
        self.customlatlonLabel.setText(label)

    def copyWGS84(self):
        s = self.wgs84LineEdit.text()
        self.clipboard.setText(s)
        self.iface.statusBarIface().showMessage("'{}' {}".format(s, s_copied), 3000)

    def copyPROJ(self):
        s = self.projLineEdit.text()
        self.clipboard.setText(s)
        self.iface.statusBarIface().showMessage("'{}' {}".format(s, s_copied), 3000)

    def copyCUSTOM(self):
        s = self.customLineEdit.text()
        self.clipboard.setText(s)
        self.iface.statusBarIface().showMessage("'{}' {}".format(s, s_copied), 3000)

    def copyUTM(self):
        s = self.utmLineEdit.text()
        self.clipboard.setText(s)
        self.iface.statusBarIface().showMessage("'{}' {}".format(s, s_copied), 3000)

    def copyH3(self):
        s = self.h3LineEdit.text()
        self.clipboard.setText(s)
        self.iface.statusBarIface().showMessage("'{}' {}".format(s, s_copied), 3000)

    def copyS2(self):
        s = self.s2LineEdit.text()
        self.clipboard.setText(s)
        self.iface.statusBarIface().showMessage("'{}' {}".format(s, s_copied), 3000)

    def copyA5(self):
        s = self.a5LineEdit.text()
        self.clipboard.setText(s)
        self.iface.statusBarIface().showMessage("'{}' {}".format(s, s_copied), 3000)

    def copyRHEALPIX(self):
        s = self.rhealpixLineEdit.text()
        self.clipboard.setText(s)
        self.iface.statusBarIface().showMessage("'{}' {}".format(s, s_copied), 3000)

    def copyDGGAL_GNOSIS(self):
        s = self.dggal_gnosisLineEdit.text()
        self.clipboard.setText(s)
        self.iface.statusBarIface().showMessage("'{}' {}".format(s, s_copied), 3000)

    def copyDGGAL_ISEA3H(self):
        s = self.dggal_isea3hLineEdit.text()
        self.clipboard.setText(s)
        self.iface.statusBarIface().showMessage("'{}' {}".format(s, s_copied), 3000)

    def copyDGGAL_ISEA9R(self):
        s = self.dggal_isea9rLineEdit.text()
        self.clipboard.setText(s)
        self.iface.statusBarIface().showMessage("'{}' {}".format(s, s_copied), 3000)

    def copyDGGAL_IVEA3H(self):
        s = self.dggal_ivea3hLineEdit.text()
        self.clipboard.setText(s)
        self.iface.statusBarIface().showMessage("'{}' {}".format(s, s_copied), 3000)

    def copyDGGAL_IVEA9R(self):
        s = self.dggal_ivea9rLineEdit.text()
        self.clipboard.setText(s)
        self.iface.statusBarIface().showMessage("'{}' {}".format(s, s_copied), 3000)

    def copyDGGAL_RTEA3H(self):
        s = self.dggal_rtea3hLineEdit.text()
        self.clipboard.setText(s)
        self.iface.statusBarIface().showMessage("'{}' {}".format(s, s_copied), 3000)

    def copyDGGAL_RTEA9R(self):
        s = self.dggal_rtea9rLineEdit.text()
        self.clipboard.setText(s)
        self.iface.statusBarIface().showMessage("'{}' {}".format(s, s_copied), 3000)

    def copyDGGAL_RHEALPIX(self):
        s = self.dggal_rhealpixLineEdit.text()
        self.clipboard.setText(s)
        self.iface.statusBarIface().showMessage("'{}' {}".format(s, s_copied), 3000)

    def copyDGGAL_ISEA4R(self):
        s = self.dggal_isea4rLineEdit.text()
        self.clipboard.setText(s)
        self.iface.statusBarIface().showMessage("'{}' {}".format(s, s_copied), 3000)

    def copyDGGAL_ISEA7H(self):
        s = self.dggal_isea7hLineEdit.text()
        self.clipboard.setText(s)
        self.iface.statusBarIface().showMessage("'{}' {}".format(s, s_copied), 3000)

    def copyDGGAL_ISEA7H_Z7(self):
        s = self.dggal_isea7h_z7LineEdit.text()
        self.clipboard.setText(s)
        self.iface.statusBarIface().showMessage("'{}' {}".format(s, s_copied), 3000)

    def copyDGGAL_IVEA4R(self):
        s = self.dggal_ivea4rLineEdit.text()
        self.clipboard.setText(s)
        self.iface.statusBarIface().showMessage("'{}' {}".format(s, s_copied), 3000)

    def copyDGGAL_IVEA7H(self):
        s = self.dggal_ivea7hLineEdit.text()
        self.clipboard.setText(s)
        self.iface.statusBarIface().showMessage("'{}' {}".format(s, s_copied), 3000)

    def copyDGGAL_IVEA7H_Z7(self):
        s = self.dggal_ivea7h_z7LineEdit.text()
        self.clipboard.setText(s)
        self.iface.statusBarIface().showMessage("'{}' {}".format(s, s_copied), 3000)

    def copyDGGAL_RTEA4R(self):
        s = self.dggal_rtea4rLineEdit.text()
        self.clipboard.setText(s)
        self.iface.statusBarIface().showMessage("'{}' {}".format(s, s_copied), 3000)

    def copyDGGAL_RTEA7H(self):
        s = self.dggal_rtea7hLineEdit.text()
        self.clipboard.setText(s)
        self.iface.statusBarIface().showMessage("'{}' {}".format(s, s_copied), 3000)

    def copyDGGAL_RTEA7H_Z7(self):
        s = self.dggal_rtea7h_z7LineEdit.text()
        self.clipboard.setText(s)
        self.iface.statusBarIface().showMessage("'{}' {}".format(s, s_copied), 3000)

    def copyDGGAL_HEALPIX(self):
        s = self.dggal_healpixLineEdit.text()
        self.clipboard.setText(s)
        self.iface.statusBarIface().showMessage("'{}' {}".format(s, s_copied), 3000)
   
    def copyDGGRID_SUPERFUND(self):
        s = self.dggrid_superfundLineEdit.text()
        self.clipboard.setText(s)
        self.iface.statusBarIface().showMessage("'{}' {}".format(s, s_copied), 3000)
    def copyDGGRID_PLANETRISK(self):
        s = self.dggrid_planetriskLineEdit.text()
        self.clipboard.setText(s)
        self.iface.statusBarIface().showMessage("'{}' {}".format(s, s_copied), 3000)
    def copyDGGRID_ISEA3H(self):
        s = self.dggrid_isea3hLineEdit.text()
        self.clipboard.setText(s)
        self.iface.statusBarIface().showMessage("'{}' {}".format(s, s_copied), 3000)
    def copyDGGRID_ISEA4H(self):
        s = self.dggrid_isea4hLineEdit.text()
        self.clipboard.setText(s)
        self.iface.statusBarIface().showMessage("'{}' {}".format(s, s_copied), 3000)
    def copyDGGRID_ISEA4T(self):
        s = self.dggrid_isea4tLineEdit.text()
        self.clipboard.setText(s)
        self.iface.statusBarIface().showMessage("'{}' {}".format(s, s_copied), 3000)
    def copyDGGRID_ISEA4D(self):
        s = self.dggrid_isea4dLineEdit.text()
        self.clipboard.setText(s)
        self.iface.statusBarIface().showMessage("'{}' {}".format(s, s_copied), 3000)
    def copyDGGRID_ISEA43H(self):
        s = self.dggrid_isea43hLineEdit.text()
        self.clipboard.setText(s)
        self.iface.statusBarIface().showMessage("'{}' {}".format(s, s_copied), 3000)
    def copyDGGRID_ISEA7H(self):        
        s = self.dggrid_isea7hLineEdit.text()
        self.clipboard.setText(s)
        self.iface.statusBarIface().showMessage("'{}' {}".format(s, s_copied), 3000)
    def copyDGGRID_IGEO7(self):
        s = self.dggrid_igeo7LineEdit.text()
        self.clipboard.setText(s)
        self.iface.statusBarIface().showMessage("'{}' {}".format(s, s_copied), 3000)
    def copyDGGRID_FULLER3H(self):
        s = self.dggrid_fuller3hLineEdit.text()
    
        self.iface.statusBarIface().showMessage("'{}' {}".format(s, s_copied), 3000)
    def copyDGGRID_FULLER4H(self):
        s = self.dggrid_fuller4hLineEdit.text()
        self.clipboard.setText(s)
        self.iface.statusBarIface().showMessage("'{}' {}".format(s, s_copied), 3000)
    def copyDGGRID_FULLER4T(self):
        s = self.dggrid_fuller4tLineEdit.text()
        self.clipboard.setText(s)
        self.iface.statusBarIface().showMessage("'{}' {}".format(s, s_copied), 3000)
    def copyDGGRID_FULLER4D(self):
        s = self.dggrid_fuller4dLineEdit.text()
        self.clipboard.setText(s)
        self.iface.statusBarIface().showMessage("'{}' {}".format(s, s_copied), 3000)
    def copyDGGRID_FULLER43H(self):
        s = self.dggrid_fuller43hLineEdit.text()
        self.clipboard.setText(s)
        self.iface.statusBarIface().showMessage("'{}' {}".format(s, s_copied), 3000)
    def copyDGGRID_FULLER7H(self):
        s = self.dggrid_fuller7hLineEdit.text()
        self.clipboard.setText(s)


    def copyISEA4T(self):
        s = self.isea4tLineEdit.text()
        self.clipboard.setText(s)
        self.iface.statusBarIface().showMessage("'{}' {}".format(s, s_copied), 3000)

    def copyISEA3H(self):
        s = self.isea3hLineEdit.text()
        self.clipboard.setText(s)
        self.iface.statusBarIface().showMessage("'{}' {}".format(s, s_copied), 3000)

    def copyEASE(self):
        s = self.easeLineEdit.text()
        self.clipboard.setText(s)
        self.iface.statusBarIface().showMessage("'{}' {}".format(s, s_copied), 3000)

    def copyQTM(self):
        s = self.qtmLineEdit.text()
        self.clipboard.setText(s)
        self.iface.statusBarIface().showMessage("'{}' {}".format(s, s_copied), 3000)

    def copyOLC(self):
        s = self.olcLineEdit.text()
        self.clipboard.setText(s)
        self.iface.statusBarIface().showMessage("'{}' {}".format(s, s_copied), 3000)

    def copyGeohash(self):
        s = self.geohashLineEdit.text()
        self.clipboard.setText(s)
        self.iface.statusBarIface().showMessage("'{}' {}".format(s, s_copied), 3000)

    def copyGEOREF(self):
        s = self.georefLineEdit.text()
        self.clipboard.setText(s)
        self.iface.statusBarIface().showMessage("'{}' {}".format(s, s_copied), 3000)

    def copyMGRS(self):
        s = self.mgrsLineEdit.text()
        self.clipboard.setText(s)
        self.iface.statusBarIface().showMessage("'{}' {}".format(s, s_copied), 3000)

    def copyTilecode(self):
        s = self.tilecodeLineEdit.text()
        self.clipboard.setText(s)
        self.iface.statusBarIface().showMessage("'{}' {}".format(s, s_copied), 3000)

    def copyQuadkey(self):
        s = self.quadkeyLineEdit.text()
        self.clipboard.setText(s)
        self.iface.statusBarIface().showMessage("'{}' {}".format(s, s_copied), 3000)

    def copyMaidenhead(self):
        s = self.maidenheadLineEdit.text()
        self.clipboard.setText(s)
        self.iface.statusBarIface().showMessage("'{}' {}".format(s, s_copied), 3000)

    def copyGARS(self):
        s = self.garsLineEdit.text()
        self.clipboard.setText(s)
        self.iface.statusBarIface().showMessage("'{}' {}".format(s, s_copied), 3000)
    
    def copyDIGIPIN(self):
        s = self.digipinLineEdit.text()
        self.clipboard.setText(s)
        self.iface.statusBarIface().showMessage("'{}' {}".format(s, s_copied), 3000)



    def customCrsChanged(self):
        if self.origPt is not None:
            self.updateCoordinates(-1, self.origPt, self.origCrs)
        self.updateLabel()

    def zoomToWGS84(self):
        try:
            text = self.wgs84LineEdit.text().strip()
            if not text:
                return
            lat, lon = parseDMSString(text, self.inputXYOrder)
            pt = self.vgridtools.zoomTo(epsg4326, lat, lon)
            self.marker.reset(QgsWkbTypes.PointGeometry)
            self.marker.addPoint(pt)
        except Exception:
            self.showInvalid(0)
    
    def zoomToH3(self):
        try:
            canvas_crs = self.canvas.mapSettings().destinationCrs()
            text = self.h3LineEdit.text().strip()
            if not text:
                return

            cell_polygon = h32geo(text)
            num_edges = 6
            if h3.is_pentagon(text):
                num_edges = 5
            center_lat, center_lon, _, _, _ = geodesic_dggs_metrics(
                cell_polygon, num_edges
            )
            pt = self.vgridtools.zoomTo(epsg4326, center_lat, center_lon)
            self.marker.reset(QgsWkbTypes.PointGeometry)
            self.marker.addPoint(pt)

            if epsg4326 != canvas_crs:
                trans_to_canvas = QgsCoordinateTransform(
                    epsg4326, canvas_crs, QgsProject.instance()
                )
                if settings.splitAntimeridian:
                    cell_polygon = fix_polygon(cell_polygon)
                cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)
                cell_geometry.transform(trans_to_canvas)
            else:
                cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)

            # Set the map extent - double the extent
            bbox = cell_geometry.boundingBox()
            bbox.scale(2.0, QgsPointXY(bbox.center()))

            self.canvas.setExtent(bbox)
            self.canvas.refresh()
            if not settings.persistentMarker:
                self.h3_marker.reset(QgsWkbTypes.PolygonGeometry)
            self.h3_marker.addGeometry(cell_geometry, None)

        except Exception as e:
            traceback.print_exc()
            self.iface.messageBar().pushMessage(
                "",
                tr("Invalid Coordinate: {}").format(str(e)),
                level=Qgis.Warning,
                duration=2,
            )
            return

    def zoomToS2(self):
        try:
            text = self.s2LineEdit.text().strip()
            if not text:
                return

            cell_polygon = s22geo(text)
            num_edges = 4
            center_lat, center_lon, _, _, _ = geodesic_dggs_metrics(
                cell_polygon, num_edges
            )

            cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)

            pt = self.vgridtools.zoomTo(epsg4326, center_lat, center_lon)
            self.marker.reset(QgsWkbTypes.PointGeometry)
            self.marker.addPoint(pt)

            canvas_crs = self.canvas.mapSettings().destinationCrs()
            if epsg4326 != canvas_crs:
                trans = QgsCoordinateTransform(
                    epsg4326, canvas_crs, QgsProject.instance()
                )
                cell_geometry.transform(trans)

            bbox = cell_geometry.boundingBox()
            bbox.scale(2.0, QgsPointXY(bbox.center()))
            self.canvas.setExtent(bbox)
            self.canvas.refresh()
            if not settings.persistentMarker:
                self.s2_marker.reset(QgsWkbTypes.PolygonGeometry)
            self.s2_marker.addGeometry(cell_geometry, None)

        except Exception as e:
            traceback.print_exc()
            self.iface.messageBar().pushMessage(
                "",
                tr("Invalid Coordinate: {}").format(str(e)),
                level=Qgis.Warning,
                duration=2,
            )
            return

    def zoomToA5(self):
        try:
            canvas_crs = self.canvas.mapSettings().destinationCrs()
            text = self.a5LineEdit.text().strip()
            if not text:
                return

            cell_polygon = a52geo(text)
            num_edges = 5
            center_lat, center_lon, _, _, _ = geodesic_dggs_metrics(
                cell_polygon, num_edges
            )

            pt = self.vgridtools.zoomTo(epsg4326, center_lat, center_lon)
            self.marker.reset(QgsWkbTypes.PointGeometry)
            self.marker.addPoint(pt)

            if epsg4326 != canvas_crs:
                trans_to_canvas = QgsCoordinateTransform(
                    epsg4326, canvas_crs, QgsProject.instance()
                )
                if settings.splitAntimeridian:
                    cell_polygon = fix_polygon(cell_polygon)
                cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)
                cell_geometry.transform(trans_to_canvas)
            else:
                cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)

            # Set the map extent - double the extent
            bbox = cell_geometry.boundingBox()
            bbox.scale(2.0, QgsPointXY(bbox.center()))
            self.canvas.setExtent(bbox)
            self.canvas.refresh()

            if not settings.persistentMarker:
                self.a5_marker.reset(QgsWkbTypes.PolygonGeometry)

            self.a5_marker.addGeometry(cell_geometry, None)

        except Exception as e:
            traceback.print_exc()
            self.iface.messageBar().pushMessage(
                "",
                tr("Invalid Coordinate: {}").format(str(e)),
                level=Qgis.Warning,
                duration=2,
            )
            return

    def zoomToRHEALPIX(self):
        try:
            text = self.rhealpixLineEdit.text().strip()
            if not text:
                return

            rhealpix_dggs = RHEALPixDGGS(
                ellipsoid=WGS84_ELLIPSOID, north_square=1, south_square=3, N_side=3
            )
            cell_polygon = rhealpix2geo(text)
            rhealpix_uids = (text[0],) + tuple(map(int, text[1:]))
            rhealpix_cell = rhealpix_dggs.cell(rhealpix_uids)
            num_edges = 4
            if rhealpix_cell.ellipsoidal_shape() == "dart":
                num_edges = 3
            center_lat, center_lon, _, _, _ = geodesic_dggs_metrics(
                cell_polygon, num_edges
            )

            pt = self.vgridtools.zoomTo(epsg4326, center_lat, center_lon)
            self.marker.reset(QgsWkbTypes.PointGeometry)
            self.marker.addPoint(pt)

            canvas_crs = self.canvas.mapSettings().destinationCrs()
            if epsg4326 != canvas_crs:
                trans_to_canvas = QgsCoordinateTransform(
                    epsg4326, canvas_crs, QgsProject.instance()
                )
                if settings.splitAntimeridian:
                    cell_polygon = fix_polygon(cell_polygon)
                cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)
                cell_geometry.transform(trans_to_canvas)
            else:
                cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)

            # Set the map extent - double the extent
            bbox = cell_geometry.boundingBox()
            bbox.scale(2.0, QgsPointXY(bbox.center()))
            self.canvas.setExtent(bbox)
            self.canvas.refresh()

            if not settings.persistentMarker:
                self.rhealpix_marker.reset(QgsWkbTypes.PolygonGeometry)

            self.rhealpix_marker.addGeometry(cell_geometry, None)

        except Exception as e:
            traceback.print_exc()
            self.iface.messageBar().pushMessage(
                "",
                tr("Invalid Coordinate: {}").format(str(e)),
                level=Qgis.Warning,
                duration=2,
            )
            return


    def zoomToDGGAL_GNOSIS(self):
        try:
            text = self.dggal_gnosisLineEdit.text().strip()
            if not text:
                return

            cell_polygon = dggal2geo("gnosis", text)
            num_edges = 4
            center_lat, center_lon, _, _, _ = geodesic_dggs_metrics(
                cell_polygon, num_edges
            )

            cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)
            pt = self.vgridtools.zoomTo(epsg4326, center_lat, center_lon)
            self.marker.reset(QgsWkbTypes.PointGeometry)
            self.marker.addPoint(pt)

            canvas_crs = self.canvas.mapSettings().destinationCrs()
            if epsg4326 != canvas_crs:
                trans = QgsCoordinateTransform(
                    epsg4326, canvas_crs, QgsProject.instance()
                )
                cell_geometry.transform(trans)

            # Set the map extent - double the extent
            bbox = cell_geometry.boundingBox()
            bbox.scale(2.0, QgsPointXY(bbox.center()))
            self.canvas.setExtent(bbox)
            self.canvas.refresh()

            if not settings.persistentMarker:
                self.dggal_gnosis_marker.reset(QgsWkbTypes.PolygonGeometry)

            self.dggal_gnosis_marker.addGeometry(cell_geometry, None)

        except Exception as e:
            traceback.print_exc()
            self.iface.messageBar().pushMessage(
                "",
                tr("Invalid Coordinate: {}").format(str(e)),
                level=Qgis.Warning,
                duration=2,
            )
            return


    def zoomToDGGAL_ISEA4R(self):
        try:
            text = self.dggal_isea4rLineEdit.text().strip()
            if not text:
                return

            cell_polygon = dggal2geo("isea4r", text)
            num_edges = 4
            center_lat, center_lon, _, _, _ = geodesic_dggs_metrics(
                cell_polygon, num_edges
            )

            pt = self.vgridtools.zoomTo(epsg4326, center_lat, center_lon)
            self.marker.reset(QgsWkbTypes.PointGeometry)
            self.marker.addPoint(pt)

            canvas_crs = self.canvas.mapSettings().destinationCrs()
            if epsg4326 != canvas_crs:
                trans_to_canvas = QgsCoordinateTransform(
                    epsg4326, canvas_crs, QgsProject.instance()
                )
                if settings.splitAntimeridian:
                    cell_polygon = fix_polygon(cell_polygon)
                cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)
                cell_geometry.transform(trans_to_canvas)
            else:
                cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)

            bbox = cell_geometry.boundingBox()
            bbox.scale(2.0, QgsPointXY(bbox.center()))
            self.canvas.setExtent(bbox)
            self.canvas.refresh()

            if not settings.persistentMarker:
                self.dggal_isea4r_marker.reset(QgsWkbTypes.PolygonGeometry)

            self.dggal_isea4r_marker.addGeometry(cell_geometry, None)

        except Exception as e:
            traceback.print_exc()
            self.iface.messageBar().pushMessage(
                "",
                tr("Invalid Coordinate: {}").format(str(e)),
                level=Qgis.Warning,
                duration=2,
            )
            return

    def zoomToDGGAL_ISEA9R(self):
        try:
            text = self.dggal_isea9rLineEdit.text().strip()
            if not text:
                return

            cell_polygon = dggal2geo("isea9r", text)
            num_edges = 4
            center_lat, center_lon, _, _, _ = geodesic_dggs_metrics(
                cell_polygon, num_edges
            )

            pt = self.vgridtools.zoomTo(epsg4326, center_lat, center_lon)
            self.marker.reset(QgsWkbTypes.PointGeometry)
            self.marker.addPoint(pt)

            canvas_crs = self.canvas.mapSettings().destinationCrs()
            if epsg4326 != canvas_crs:
                trans_to_canvas = QgsCoordinateTransform(
                    epsg4326, canvas_crs, QgsProject.instance()
                )
                if settings.splitAntimeridian:
                    cell_polygon = fix_polygon(cell_polygon)
                cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)
                cell_geometry.transform(trans_to_canvas)
            else:
                cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)
            # Set the map extent - double the extent
            bbox = cell_geometry.boundingBox()
            bbox.scale(3.0, QgsPointXY(bbox.center()))
            self.canvas.setExtent(bbox)
            self.canvas.refresh()

            if not settings.persistentMarker:
                self.dggal_isea9r_marker.reset(QgsWkbTypes.PolygonGeometry)

            self.dggal_isea9r_marker.addGeometry(cell_geometry, None)

        except Exception as e:
            traceback.print_exc()
            self.iface.messageBar().pushMessage(
                "",
                tr("Invalid Coordinate: {}").format(str(e)),
                level=Qgis.Warning,
                duration=2,
            )
            return

    def zoomToDGGAL_ISEA3H(self):
        try:
            text = self.dggal_isea3hLineEdit.text().strip()
            if not text:
                return

            cell_polygon = dggal2geo("isea3h", text)
            num_edges = 6
            center_lat, center_lon, _, _, _ = geodesic_dggs_metrics(
                cell_polygon, num_edges
            )

            pt = self.vgridtools.zoomTo(epsg4326, center_lat, center_lon)
            self.marker.reset(QgsWkbTypes.PointGeometry)
            self.marker.addPoint(pt)

            canvas_crs = self.canvas.mapSettings().destinationCrs()
            if epsg4326 != canvas_crs:
                trans_to_canvas = QgsCoordinateTransform(
                    epsg4326, canvas_crs, QgsProject.instance()
                )
                if settings.splitAntimeridian:
                    cell_polygon = fix_polygon(cell_polygon)
                cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)
                cell_geometry.transform(trans_to_canvas)
            else:
                cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)

            # Set the map extent - double the extent
            bbox = cell_geometry.boundingBox()
            bbox.scale(2.0, QgsPointXY(bbox.center()))
            self.canvas.setExtent(bbox)
            self.canvas.refresh()

            if not settings.persistentMarker:
                self.dggal_isea3h_marker.reset(QgsWkbTypes.PolygonGeometry)

            self.dggal_isea3h_marker.addGeometry(cell_geometry, None)

        except Exception as e:
            traceback.print_exc()
            self.iface.messageBar().pushMessage(
                "",
                tr("Invalid Coordinate: {}").format(str(e)),
                level=Qgis.Warning,
                duration=2,
            )
            return   

    def zoomToDGGAL_ISEA7H(self):
        try:
            text = self.dggal_isea7hLineEdit.text().strip()
            if not text:
                return

            cell_polygon = dggal2geo("isea7h", text)
            num_edges = 6
            center_lat, center_lon, _, _, _ = geodesic_dggs_metrics(
                cell_polygon, num_edges
            )

            pt = self.vgridtools.zoomTo(epsg4326, center_lat, center_lon)
            self.marker.reset(QgsWkbTypes.PointGeometry)
            self.marker.addPoint(pt)

            canvas_crs = self.canvas.mapSettings().destinationCrs()
            if epsg4326 != canvas_crs:
                trans_to_canvas = QgsCoordinateTransform(
                    epsg4326, canvas_crs, QgsProject.instance()
                )
                if settings.splitAntimeridian:
                    cell_polygon = fix_polygon(cell_polygon)
                cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)
                cell_geometry.transform(trans_to_canvas)
            else:
                cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)

            bbox = cell_geometry.boundingBox()
            bbox.scale(2.0, QgsPointXY(bbox.center()))
            self.canvas.setExtent(bbox)
            self.canvas.refresh()

            if not settings.persistentMarker:
                self.dggal_isea7h_marker.reset(QgsWkbTypes.PolygonGeometry)

            self.dggal_isea7h_marker.addGeometry(cell_geometry, None)

        except Exception as e:
            traceback.print_exc()
            self.iface.messageBar().pushMessage(
                "",
                tr("Invalid Coordinate: {}").format(str(e)),
                level=Qgis.Warning,
                duration=2,
            )
            return

    def zoomToDGGAL_ISEA7H_Z7(self):
        try:
            text = self.dggal_isea7h_z7LineEdit.text().strip()
            if not text:
                return

            cell_polygon = dggal2geo("isea7h_z7", text)
            num_edges = 6
            center_lat, center_lon, _, _, _ = geodesic_dggs_metrics(
                cell_polygon, num_edges
            )

            pt = self.vgridtools.zoomTo(epsg4326, center_lat, center_lon)
            self.marker.reset(QgsWkbTypes.PointGeometry)
            self.marker.addPoint(pt)

            canvas_crs = self.canvas.mapSettings().destinationCrs()
            if epsg4326 != canvas_crs:
                trans_to_canvas = QgsCoordinateTransform(
                    epsg4326, canvas_crs, QgsProject.instance()
                )
                if settings.splitAntimeridian:
                    cell_polygon = fix_polygon(cell_polygon)
                cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)
                cell_geometry.transform(trans_to_canvas)
            else:
                cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)

            bbox = cell_geometry.boundingBox()
            bbox.scale(2.0, QgsPointXY(bbox.center()))
            self.canvas.setExtent(bbox)
            self.canvas.refresh()

            if not settings.persistentMarker:
                self.dggal_isea7h_z7_marker.reset(QgsWkbTypes.PolygonGeometry)

            self.dggal_isea7h_z7_marker.addGeometry(cell_geometry, None)

        except Exception as e:
            traceback.print_exc()
            self.iface.messageBar().pushMessage(
                "",
                tr("Invalid Coordinate: {}").format(str(e)),
                level=Qgis.Warning,
                duration=2,
            )
            return

    def zoomToDGGAL_IVEA4R(self):
        try:
            text = self.dggal_ivea4rLineEdit.text().strip()
            if not text:
                return

            cell_polygon = dggal2geo("ivea4r", text)
            num_edges = 4
            center_lat, center_lon, _, _, _ = geodesic_dggs_metrics(
                cell_polygon, num_edges
            )

            pt = self.vgridtools.zoomTo(epsg4326, center_lat, center_lon)
            self.marker.reset(QgsWkbTypes.PointGeometry)
            self.marker.addPoint(pt)

            canvas_crs = self.canvas.mapSettings().destinationCrs()
            if epsg4326 != canvas_crs:
                trans_to_canvas = QgsCoordinateTransform(
                    epsg4326, canvas_crs, QgsProject.instance()
                )
                if settings.splitAntimeridian:
                    cell_polygon = fix_polygon(cell_polygon)
                cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)
                cell_geometry.transform(trans_to_canvas)
            else:
                cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)

            bbox = cell_geometry.boundingBox()
            bbox.scale(2.0, QgsPointXY(bbox.center()))
            self.canvas.setExtent(bbox)
            self.canvas.refresh()

            if not settings.persistentMarker:
                self.dggal_ivea4r_marker.reset(QgsWkbTypes.PolygonGeometry)

            self.dggal_ivea4r_marker.addGeometry(cell_geometry, None)

        except Exception as e:
            traceback.print_exc()
            self.iface.messageBar().pushMessage(
                "",
                tr("Invalid Coordinate: {}").format(str(e)),
                level=Qgis.Warning,
                duration=2,
            )
            return


    def zoomToDGGAL_IVEA9R(self):
        try:
            text = self.dggal_ivea9rLineEdit.text().strip()
            if not text:
                return

            cell_polygon = dggal2geo("ivea9r", text)
            num_edges = 4
            center_lat, center_lon, _, _, _ = geodesic_dggs_metrics(
                cell_polygon, num_edges
            )

            pt = self.vgridtools.zoomTo(epsg4326, center_lat, center_lon)
            self.marker.reset(QgsWkbTypes.PointGeometry)
            self.marker.addPoint(pt)

            canvas_crs = self.canvas.mapSettings().destinationCrs()
            if epsg4326 != canvas_crs:
                trans_to_canvas = QgsCoordinateTransform(
                    epsg4326, canvas_crs, QgsProject.instance()
                )
                if settings.splitAntimeridian:
                    cell_polygon = fix_polygon(cell_polygon)
                cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)
                cell_geometry.transform(trans_to_canvas)
            else:
                cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)

            # Set the map extent - double the extent
            bbox = cell_geometry.boundingBox()
            bbox.scale(3.0, QgsPointXY(bbox.center()))
            self.canvas.setExtent(bbox)
            self.canvas.refresh()

            if not settings.persistentMarker:
                self.dggal_ivea9r_marker.reset(QgsWkbTypes.PolygonGeometry)

            self.dggal_ivea9r_marker.addGeometry(cell_geometry, None)

        except Exception as e:
            traceback.print_exc()
            self.iface.messageBar().pushMessage(
                "",
                tr("Invalid Coordinate: {}").format(str(e)),
                level=Qgis.Warning,
                duration=2,
            )
            return


    def zoomToDGGAL_IVEA3H(self):
        try:
            text = self.dggal_ivea3hLineEdit.text().strip()
            if not text:
                return

            cell_polygon = dggal2geo("ivea3h", text)
            num_edges = 6
            center_lat, center_lon, _, _, _ = geodesic_dggs_metrics(
                cell_polygon, num_edges
            )

            pt = self.vgridtools.zoomTo(epsg4326, center_lat, center_lon)
            self.marker.reset(QgsWkbTypes.PointGeometry)
            self.marker.addPoint(pt)

            canvas_crs = self.canvas.mapSettings().destinationCrs()
            if epsg4326 != canvas_crs:
                trans_to_canvas = QgsCoordinateTransform(
                    epsg4326, canvas_crs, QgsProject.instance()
                )
                if settings.splitAntimeridian:
                    cell_polygon = fix_polygon(cell_polygon)
                cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)
                cell_geometry.transform(trans_to_canvas)
            else:
                cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)

            # Set the map extent - double the extent
            bbox = cell_geometry.boundingBox()
            bbox.scale(2.0, QgsPointXY(bbox.center()))
            self.canvas.setExtent(bbox)
            self.canvas.refresh()

            if not settings.persistentMarker:
                self.dggal_ivea3h_marker.reset(QgsWkbTypes.PolygonGeometry)

            self.dggal_ivea3h_marker.addGeometry(cell_geometry, None)

        except Exception as e:
            traceback.print_exc()
            self.iface.messageBar().pushMessage(
                "",
                tr("Invalid Coordinate: {}").format(str(e)),
                level=Qgis.Warning,
                duration=2,
            )
            return

    def zoomToDGGAL_IVEA7H(self):
        try:
            text = self.dggal_ivea7hLineEdit.text().strip()
            if not text:
                return

            cell_polygon = dggal2geo("ivea7h", text)
            num_edges = 6
            center_lat, center_lon, _, _, _ = geodesic_dggs_metrics(
                cell_polygon, num_edges
            )

            pt = self.vgridtools.zoomTo(epsg4326, center_lat, center_lon)
            self.marker.reset(QgsWkbTypes.PointGeometry)
            self.marker.addPoint(pt)

            canvas_crs = self.canvas.mapSettings().destinationCrs()
            if epsg4326 != canvas_crs:
                trans_to_canvas = QgsCoordinateTransform(
                    epsg4326, canvas_crs, QgsProject.instance()
                )
                if settings.splitAntimeridian:
                    cell_polygon = fix_polygon(cell_polygon)
                cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)
                cell_geometry.transform(trans_to_canvas)
            else:
                cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)

            bbox = cell_geometry.boundingBox()
            bbox.scale(2.0, QgsPointXY(bbox.center()))
            self.canvas.setExtent(bbox)
            self.canvas.refresh()

            if not settings.persistentMarker:
                self.dggal_ivea7h_marker.reset(QgsWkbTypes.PolygonGeometry)

            self.dggal_ivea7h_marker.addGeometry(cell_geometry, None)

        except Exception as e:
            traceback.print_exc()
            self.iface.messageBar().pushMessage(
                "",
                tr("Invalid Coordinate: {}").format(str(e)),
                level=Qgis.Warning,
                duration=2,
            )
            return

    def zoomToDGGAL_IVEA7H_Z7(self):
        try:
            text = self.dggal_ivea7h_z7LineEdit.text().strip()
            if not text:
                return

            cell_polygon = dggal2geo("ivea7h_z7", text)
            num_edges = 6
            center_lat, center_lon, _, _, _ = geodesic_dggs_metrics(
                cell_polygon, num_edges
            )

            pt = self.vgridtools.zoomTo(epsg4326, center_lat, center_lon)
            self.marker.reset(QgsWkbTypes.PointGeometry)
            self.marker.addPoint(pt)

            canvas_crs = self.canvas.mapSettings().destinationCrs()
            if epsg4326 != canvas_crs:
                trans_to_canvas = QgsCoordinateTransform(
                    epsg4326, canvas_crs, QgsProject.instance()
                )
                if settings.splitAntimeridian:
                    cell_polygon = fix_polygon(cell_polygon)
                cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)
                cell_geometry.transform(trans_to_canvas)
            else:
                cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)

            bbox = cell_geometry.boundingBox()
            bbox.scale(2.0, QgsPointXY(bbox.center()))
            self.canvas.setExtent(bbox)
            self.canvas.refresh()

            if not settings.persistentMarker:
                self.dggal_ivea7h_z7_marker.reset(QgsWkbTypes.PolygonGeometry)

            self.dggal_ivea7h_z7_marker.addGeometry(cell_geometry, None)

        except Exception as e:
            traceback.print_exc()
            self.iface.messageBar().pushMessage(
                "",
                tr("Invalid Coordinate: {}").format(str(e)),
                level=Qgis.Warning,
                duration=2,
            )
            return

    def zoomToDGGAL_RTEA4R(self):
        try:
            text = self.dggal_rtea4rLineEdit.text().strip()
            if not text:
                return

            cell_polygon = dggal2geo("rtea4r", text)
            num_edges = 4
            center_lat, center_lon, _, _, _ = geodesic_dggs_metrics(
                cell_polygon, num_edges
            )

            pt = self.vgridtools.zoomTo(epsg4326, center_lat, center_lon)
            self.marker.reset(QgsWkbTypes.PointGeometry)
            self.marker.addPoint(pt)

            canvas_crs = self.canvas.mapSettings().destinationCrs()
            if epsg4326 != canvas_crs:
                trans_to_canvas = QgsCoordinateTransform(
                    epsg4326, canvas_crs, QgsProject.instance()
                )
                if settings.splitAntimeridian:
                    cell_polygon = fix_polygon(cell_polygon)
                cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)
                cell_geometry.transform(trans_to_canvas)
            else:
                cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)

            bbox = cell_geometry.boundingBox()
            bbox.scale(2.0, QgsPointXY(bbox.center()))
            self.canvas.setExtent(bbox)
            self.canvas.refresh()

            if not settings.persistentMarker:
                self.dggal_rtea4r_marker.reset(QgsWkbTypes.PolygonGeometry)

            self.dggal_rtea4r_marker.addGeometry(cell_geometry, None)

        except Exception as e:
            traceback.print_exc()
            self.iface.messageBar().pushMessage(
                "",
                tr("Invalid Coordinate: {}").format(str(e)),
                level=Qgis.Warning,
                duration=2,
            )
            return
    
    def zoomToDGGAL_RTEA9R(self):
        try:
            text = self.dggal_rtea9rLineEdit.text().strip()
            if not text:
                return

            cell_polygon = dggal2geo("rtea9r", text)
            num_edges = 4
            center_lat, center_lon, _, _, _ = geodesic_dggs_metrics(
                cell_polygon, num_edges
            )

            pt = self.vgridtools.zoomTo(epsg4326, center_lat, center_lon)
            self.marker.reset(QgsWkbTypes.PointGeometry)
            self.marker.addPoint(pt)

            canvas_crs = self.canvas.mapSettings().destinationCrs()
            if epsg4326 != canvas_crs:
                trans_to_canvas = QgsCoordinateTransform(
                    epsg4326, canvas_crs, QgsProject.instance()
                )
                if settings.splitAntimeridian:
                    cell_polygon = fix_polygon(cell_polygon)
                cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)
                cell_geometry.transform(trans_to_canvas)
            else:
                cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)

            # Set the map extent - double the extent
            bbox = cell_geometry.boundingBox()
            bbox.scale(3.0, QgsPointXY(bbox.center()))
            self.canvas.setExtent(bbox)
            self.canvas.refresh()

            if not settings.persistentMarker:
                self.dggal_rtea9r_marker.reset(QgsWkbTypes.PolygonGeometry)

            self.dggal_rtea9r_marker.addGeometry(cell_geometry, None)

        except Exception as e:
            traceback.print_exc()
            self.iface.messageBar().pushMessage(
                "",
                tr("Invalid Coordinate: {}").format(str(e)),
                level=Qgis.Warning,
                duration=2,
            )
            return

    def zoomToDGGAL_RTEA7H(self):
        try:
            text = self.dggal_rtea7hLineEdit.text().strip()
            if not text:
                return

            cell_polygon = dggal2geo("rtea7h", text)
            num_edges = 6
            center_lat, center_lon, _, _, _ = geodesic_dggs_metrics(
                cell_polygon, num_edges
            )

            pt = self.vgridtools.zoomTo(epsg4326, center_lat, center_lon)
            self.marker.reset(QgsWkbTypes.PointGeometry)
            self.marker.addPoint(pt)

            canvas_crs = self.canvas.mapSettings().destinationCrs()
            if epsg4326 != canvas_crs:
                trans_to_canvas = QgsCoordinateTransform(
                    epsg4326, canvas_crs, QgsProject.instance()
                )
                if settings.splitAntimeridian:
                    cell_polygon = fix_polygon(cell_polygon)
                cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)
                cell_geometry.transform(trans_to_canvas)
            else:
                cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)

            bbox = cell_geometry.boundingBox()
            bbox.scale(2.0, QgsPointXY(bbox.center()))
            self.canvas.setExtent(bbox)
            self.canvas.refresh()

            if not settings.persistentMarker:
                self.dggal_rtea7h_marker.reset(QgsWkbTypes.PolygonGeometry)

            self.dggal_rtea7h_marker.addGeometry(cell_geometry, None)

        except Exception as e:
            traceback.print_exc()
            self.iface.messageBar().pushMessage(
                "",
                tr("Invalid Coordinate: {}").format(str(e)),
                level=Qgis.Warning,
                duration=2,
            )
            return

    def zoomToDGGAL_RTEA7H_Z7(self):
        try:
            text = self.dggal_rtea7h_z7LineEdit.text().strip()
            if not text:
                return

            cell_polygon = dggal2geo("rtea7h_z7", text)
            num_edges = 6
            center_lat, center_lon, _, _, _ = geodesic_dggs_metrics(
                cell_polygon, num_edges
            )

            pt = self.vgridtools.zoomTo(epsg4326, center_lat, center_lon)
            self.marker.reset(QgsWkbTypes.PointGeometry)
            self.marker.addPoint(pt)

            canvas_crs = self.canvas.mapSettings().destinationCrs()
            if epsg4326 != canvas_crs:
                trans_to_canvas = QgsCoordinateTransform(
                    epsg4326, canvas_crs, QgsProject.instance()
                )
                if settings.splitAntimeridian:
                    cell_polygon = fix_polygon(cell_polygon)
                cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)
                cell_geometry.transform(trans_to_canvas)
            else:
                cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)

            bbox = cell_geometry.boundingBox()
            bbox.scale(2.0, QgsPointXY(bbox.center()))
            self.canvas.setExtent(bbox)
            self.canvas.refresh()

            if not settings.persistentMarker:
                self.dggal_rtea7h_z7_marker.reset(QgsWkbTypes.PolygonGeometry)

            self.dggal_rtea7h_z7_marker.addGeometry(cell_geometry, None)

        except Exception as e:
            traceback.print_exc()
            self.iface.messageBar().pushMessage(
                "",
                tr("Invalid Coordinate: {}").format(str(e)),
                level=Qgis.Warning,
                duration=2,
            )
            return

    def zoomToDGGAL_RTEA3H(self):
        try:
            text = self.dggal_rtea3hLineEdit.text().strip()
            if not text:
                return

            cell_polygon = dggal2geo("rtea3h", text)
            num_edges = 6
            center_lat, center_lon, _, _, _ = geodesic_dggs_metrics(
                cell_polygon, num_edges
            )

            pt = self.vgridtools.zoomTo(epsg4326, center_lat, center_lon)
            self.marker.reset(QgsWkbTypes.PointGeometry)
            self.marker.addPoint(pt)

            canvas_crs = self.canvas.mapSettings().destinationCrs()
            if epsg4326 != canvas_crs:
                trans_to_canvas = QgsCoordinateTransform(
                    epsg4326, canvas_crs, QgsProject.instance()
                )
                if settings.splitAntimeridian:
                    cell_polygon = fix_polygon(cell_polygon)
                cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)
                cell_geometry.transform(trans_to_canvas)
            else:
                cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)

            bbox = cell_geometry.boundingBox()

            # Set the map extent - double the extent
            bbox.scale(2.0, QgsPointXY(bbox.center()))
            self.canvas.setExtent(bbox)
            self.canvas.refresh()

            if not settings.persistentMarker:
                self.dggal_rtea3h_marker.reset(QgsWkbTypes.PolygonGeometry)

            self.dggal_rtea3h_marker.addGeometry(cell_geometry, None)

        except Exception as e:
            traceback.print_exc()
            self.iface.messageBar().pushMessage(
                "",
                tr("Invalid Coordinate: {}").format(str(e)),
                level=Qgis.Warning,
                duration=2,
            )
            return
    

    def zoomToDGGAL_HEALPix(self):
        try:
            text = self.dggal_healpixLineEdit.text().strip()
            if not text:
                return

            cell_polygon = dggal2geo("healpix", text)
            num_edges = 4
            center_lat, center_lon, _, _, _ = geodesic_dggs_metrics(
                cell_polygon, num_edges
            )

            pt = self.vgridtools.zoomTo(epsg4326, center_lat, center_lon)
            self.marker.reset(QgsWkbTypes.PointGeometry)
            self.marker.addPoint(pt)

            canvas_crs = self.canvas.mapSettings().destinationCrs()
            if epsg4326 != canvas_crs:
                trans_to_canvas = QgsCoordinateTransform(
                    epsg4326, canvas_crs, QgsProject.instance()
                )
                if settings.splitAntimeridian:
                    cell_polygon = fix_polygon(cell_polygon)
                cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)
                cell_geometry.transform(trans_to_canvas)
            else:
                cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)

            bbox = cell_geometry.boundingBox()
            bbox.scale(2.0, QgsPointXY(bbox.center()))
            self.canvas.setExtent(bbox)
            self.canvas.refresh()

            if not settings.persistentMarker:
                self.dggal_healpix_marker.reset(QgsWkbTypes.PolygonGeometry)

            self.dggal_healpix_marker.addGeometry(cell_geometry, None)

        except Exception as e:
            traceback.print_exc()
            self.iface.messageBar().pushMessage(
                "",
                tr("Invalid Coordinate: {}").format(str(e)),
                level=Qgis.Warning,
                duration=2,
            )
            return

    def zoomToDGGAL_rHEALPix(self):
        try:
            text = self.dggal_rhealpixLineEdit.text().strip()
            if not text:
                return

            cell_polygon = dggal2geo("rhealpix", text)
            num_edges = 4
            center_lat, center_lon, _, _, _ = geodesic_dggs_metrics(
                cell_polygon, num_edges
            )

            pt = self.vgridtools.zoomTo(epsg4326, center_lat, center_lon)
            self.marker.reset(QgsWkbTypes.PointGeometry)
            self.marker.addPoint(pt)

            canvas_crs = self.canvas.mapSettings().destinationCrs()
            if epsg4326 != canvas_crs:
                trans_to_canvas = QgsCoordinateTransform(
                    epsg4326, canvas_crs, QgsProject.instance()
                )
                if settings.splitAntimeridian:
                    cell_polygon = fix_polygon(cell_polygon)
                cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)
                cell_geometry.transform(trans_to_canvas)
            else:
                cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)
            # Set the map extent - double the extent
            bbox = cell_geometry.boundingBox()
            bbox.scale(2.0, QgsPointXY(bbox.center()))
            self.canvas.setExtent(bbox)
            self.canvas.refresh()
            self.marker.reset(QgsWkbTypes.PointGeometry)
            self.marker.addPoint(pt)

            if not settings.persistentMarker:
                self.dggal_isea9r_marker.reset(QgsWkbTypes.PolygonGeometry)

            self.dggal_isea9r_marker.addGeometry(cell_geometry, None)

        except Exception as e:
            traceback.print_exc()
            self.iface.messageBar().pushMessage(
                "",
                tr("Invalid Coordinate: {}").format(str(e)),
                level=Qgis.Warning,
                duration=2,
            )
            return

    def zoomToDGGRID_SUPERFUND(self):
        self._zoom_to_dggrid(
            self.dggrid_superfundLineEdit,
            self.dggrid_superfund_marker,
            "SUPERFUND",
            settings.dggrid_superfundRes,
        )

    def zoomToDGGRID_PLANETRISK(self):
        self._zoom_to_dggrid(
            self.dggrid_planetriskLineEdit,
            self.dggrid_planetrisk_marker,
            "PLANETRISK",
            settings.dggrid_planetriskRes,
        )

    def zoomToDGGRID_ISEA3H(self):
        self._zoom_to_dggrid(
            self.dggrid_isea3hLineEdit,
            self.dggrid_isea3h_marker,
            "ISEA3H",
            settings.dggrid_isea3hRes,
        )

    def zoomToDGGRID_ISEA4H(self):
        self._zoom_to_dggrid(
            self.dggrid_isea4hLineEdit,
            self.dggrid_isea4h_marker,
            "ISEA4H",
            settings.dggrid_isea4hRes,
        )

    def zoomToDGGRID_ISEA4T(self):
        self._zoom_to_dggrid(
            self.dggrid_isea4tLineEdit,
            self.dggrid_isea4t_marker,
            "ISEA4T",
            settings.dggrid_isea4tRes,
        )

    def zoomToDGGRID_ISEA4D(self):
        self._zoom_to_dggrid(
            self.dggrid_isea4dLineEdit,
            self.dggrid_isea4d_marker,
            "ISEA4D",
            settings.dggrid_isea4dRes,
        )

    def zoomToDGGRID_ISEA43H(self):
        self._zoom_to_dggrid(
            self.dggrid_isea43hLineEdit,
            self.dggrid_isea43h_marker,
            "ISEA43H",
            settings.dggrid_isea43hRes,
        )

    def zoomToDGGRID_ISEA7H(self):
        self._zoom_to_dggrid(
            self.dggrid_isea7hLineEdit,
            self.dggrid_isea7h_marker,
            "ISEA7H",
            settings.dggrid_isea7hRes,
        )

    def zoomToDGGRID_IGEO7(self):
        self._zoom_to_dggrid(
            self.dggrid_igeo7LineEdit,
            self.dggrid_igeo7_marker,
            "IGEO7",
            settings.dggrid_igeo7Res,
        )

    def zoomToDGGRID_FULLER3H(self):
        self._zoom_to_dggrid(
            self.dggrid_fuller3hLineEdit,
            self.dggrid_fuller3h_marker,
            "FULLER3H",
            settings.dggrid_fuller3hRes,
        )

    def zoomToDGGRID_FULLER4H(self):
        self._zoom_to_dggrid(
            self.dggrid_fuller4hLineEdit,
            self.dggrid_fuller4h_marker,
            "FULLER4H",
            settings.dggrid_fuller4hRes,
        )

    def zoomToDGGRID_FULLER4T(self):
        self._zoom_to_dggrid(
            self.dggrid_fuller4tLineEdit,
            self.dggrid_fuller4t_marker,
            "FULLER4T",
            settings.dggrid_fuller4tRes,
        )

    def zoomToDGGRID_FULLER4D(self):
        self._zoom_to_dggrid(
            self.dggrid_fuller4dLineEdit,
            self.dggrid_fuller4d_marker,
            "FULLER4D",
            settings.dggrid_fuller4dRes,
        )

    def zoomToDGGRID_FULLER43H(self):
        self._zoom_to_dggrid(
            self.dggrid_fuller43hLineEdit,
            self.dggrid_fuller43h_marker,
            "FULLER43H",
            settings.dggrid_fuller43hRes,
        )

    def zoomToDGGRID_FULLER7H(self):
        self._zoom_to_dggrid(
            self.dggrid_fuller7hLineEdit,
            self.dggrid_fuller7h_marker,
            "FULLER7H",
            settings.dggrid_fuller7hRes,
        )

    def zoomToISEA4T(self):
        try:
            text = self.isea4tLineEdit.text().strip()
            if not text:
                return

            cell_polygon = isea4t2geo(text)
            num_edges = 3
            center_lat, center_lon, _, _, _ = geodesic_dggs_metrics(
                cell_polygon, num_edges
            )

            pt = self.vgridtools.zoomTo(epsg4326, center_lat, center_lon)
            self.marker.reset(QgsWkbTypes.PointGeometry)
            self.marker.addPoint(pt)

            canvas_crs = self.canvas.mapSettings().destinationCrs()
            if epsg4326 != canvas_crs:
                trans_to_canvas = QgsCoordinateTransform(
                    epsg4326, canvas_crs, QgsProject.instance()
                )
                if settings.splitAntimeridian:
                    cell_polygon = fix_polygon(cell_polygon)
                cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)
                cell_geometry.transform(trans_to_canvas)
            else:
                cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)

            # Set the map extent - double the extent
            bbox = cell_geometry.boundingBox()
            bbox.scale(2.0, QgsPointXY(bbox.center()))
            self.canvas.setExtent(bbox)
            self.canvas.refresh()

            if not settings.persistentMarker:
                self.isea4t_marker.reset(QgsWkbTypes.PolygonGeometry)

            self.isea4t_marker.addGeometry(cell_geometry, None)

        except Exception as e:
            traceback.print_exc()
            self.iface.messageBar().pushMessage(
                "",
                tr("Invalid Coordinate: {}").format(str(e)),
                level=Qgis.Warning,
                duration=2,
            )
            return

    def zoomToISEA3H(self):
        try:
            text = self.isea3hLineEdit.text().strip()
            if not text:
                return

            cell_polygon = isea3h2geo(text)
            num_edges = 6
            center_lat, center_lon, _, _, _ = geodesic_dggs_metrics(
                cell_polygon, num_edges
            )

            cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)

            pt = self.vgridtools.zoomTo(epsg4326, center_lat, center_lon)
            self.marker.reset(QgsWkbTypes.PointGeometry)
            self.marker.addPoint(pt)

            canvas_crs = self.canvas.mapSettings().destinationCrs()
            if epsg4326 != canvas_crs:
                trans = QgsCoordinateTransform(
                    epsg4326, canvas_crs, QgsProject.instance()
                )
                cell_geometry.transform(trans)

            # Set the map extent - double the extent
            bbox = cell_geometry.boundingBox()
            bbox.scale(2.0, QgsPointXY(bbox.center()))
            self.canvas.setExtent(bbox)
            self.canvas.refresh()

            if not settings.persistentMarker:
                self.isea3h_marker.reset(QgsWkbTypes.PolygonGeometry)

            self.isea3h_marker.addGeometry(cell_geometry, None)

        except Exception as e:
            traceback.print_exc()
            self.iface.messageBar().pushMessage(
                "",
                tr("Invalid Coordinate: {}").format(str(e)),
                level=Qgis.Warning,
                duration=2,
            )
            return

    def zoomToEASE(self):
        try:
            text = self.easeLineEdit.text().strip()
            if not text:
                return

            cell_polygon = ease2geo(text)
            num_edges = 4
            center_lat, center_lon, _, _, _ = geodesic_dggs_metrics(
                cell_polygon, num_edges
            )

            cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)

            pt = self.vgridtools.zoomTo(epsg4326, center_lat, center_lon)
            self.marker.reset(QgsWkbTypes.PointGeometry)
            self.marker.addPoint(pt)

            canvas_crs = self.canvas.mapSettings().destinationCrs()
            if epsg4326 != canvas_crs:
                trans = QgsCoordinateTransform(
                    epsg4326, canvas_crs, QgsProject.instance()
                )
                cell_geometry.transform(trans)

            # Set the map extent - double the extent
            bbox = cell_geometry.boundingBox()
            bbox.scale(2.0, QgsPointXY(bbox.center()))
            self.canvas.setExtent(bbox)
            self.canvas.refresh()

            if not settings.persistentMarker:
                self.ease_marker.reset(QgsWkbTypes.PolygonGeometry)

            self.ease_marker.addGeometry(cell_geometry, None)

        except Exception as e:
            traceback.print_exc()
            self.iface.messageBar().pushMessage(
                "",
                tr("Invalid Coordinate: {}").format(str(e)),
                level=Qgis.Warning,
                duration=2,
            )
            return

    def zoomToQTM(self):
        try:
            text = self.qtmLineEdit.text().strip()
            if not text:
                return

            cell_polygon = qtm2geo(text)
            num_edges = 3
            center_lat, center_lon, _, _, _ = geodesic_dggs_metrics(
                cell_polygon, num_edges
            )

            cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)

            pt = self.vgridtools.zoomTo(epsg4326, center_lat, center_lon)
            self.marker.reset(QgsWkbTypes.PointGeometry)
            self.marker.addPoint(pt)

            canvas_crs = self.canvas.mapSettings().destinationCrs()
            if epsg4326 != canvas_crs:
                trans = QgsCoordinateTransform(
                    epsg4326, canvas_crs, QgsProject.instance()
                )
                cell_geometry.transform(trans)

            # Set the map extent - double the extent
            bbox = cell_geometry.boundingBox()
            bbox.scale(2.0, QgsPointXY(bbox.center()))
            self.canvas.setExtent(bbox)
            self.canvas.refresh()

            if not settings.persistentMarker:
                self.dggal_ivea3h_marker.reset(QgsWkbTypes.PolygonGeometry)

            self.dggal_ivea3h_marker.addGeometry(cell_geometry, None)

        except Exception as e:
            traceback.print_exc()
            self.iface.messageBar().pushMessage(
                "",
                tr("Invalid Coordinate: {}").format(str(e)),
                level=Qgis.Warning,
                duration=2,
            )
            return

    def zoomToOLC(self):
        try:
            text = self.olcLineEdit.text().strip()
            if not text:
                return
            cell_polygon = olc2geo(text)
            center_lat, center_lon, _, _, _ ,_ = graticule_dggs_metrics(cell_polygon)

            cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)

            pt = self.vgridtools.zoomTo(epsg4326, center_lat, center_lon)
            self.marker.reset(QgsWkbTypes.PointGeometry)
            self.marker.addPoint(pt)

            canvas_crs = self.canvas.mapSettings().destinationCrs()
            if epsg4326 != canvas_crs:
                trans = QgsCoordinateTransform(
                    epsg4326, canvas_crs, QgsProject.instance()
                )
                cell_geometry.transform(trans)

            # Set the map extent - double the extent
            bbox = cell_geometry.boundingBox()
            bbox.scale(2.0, QgsPointXY(bbox.center()))
            self.canvas.setExtent(bbox)
            self.canvas.refresh()

            if not settings.persistentMarker:
                self.dggal_ivea9r_marker.reset(QgsWkbTypes.PolygonGeometry)

            self.dggal_ivea9r_marker.addGeometry(cell_geometry, None)

        except Exception as e:
            traceback.print_exc()
            self.iface.messageBar().pushMessage(
                "",
                tr("Invalid Coordinate: {}").format(str(e)),
                level=Qgis.Warning,
                duration=2,
            )
            return

    def zoomToGeohash(self):
        try:
            text = self.geohashLineEdit.text().strip()
            if not text:
                return

            cell_polygon = geohash2geo(text)
            center_lat, center_lon, _, _, _ ,_ = graticule_dggs_metrics(cell_polygon)

            cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)

            pt = self.vgridtools.zoomTo(epsg4326, center_lat, center_lon)
            self.marker.reset(QgsWkbTypes.PointGeometry)
            self.marker.addPoint(pt)

            canvas_crs = self.canvas.mapSettings().destinationCrs()
            if epsg4326 != canvas_crs:
                trans = QgsCoordinateTransform(
                    epsg4326, canvas_crs, QgsProject.instance()
                )
                cell_geometry.transform(trans)

            # Set the map extent - double the extent
            bbox = cell_geometry.boundingBox()
            bbox.scale(2.0, QgsPointXY(bbox.center()))
            self.canvas.setExtent(bbox)
            self.canvas.refresh()

            if not settings.persistentMarker:
                self.dggal_rtea3h_marker.reset(QgsWkbTypes.PolygonGeometry)

            self.dggal_rtea3h_marker.addGeometry(cell_geometry, None)

        except Exception as e:
            traceback.print_exc()
            self.iface.messageBar().pushMessage(
                "",
                tr("Invalid Coordinate: {}").format(str(e)),
                level=Qgis.Warning,
                duration=2,
            )
            return

    def zoomToGEOREF(self):
        try:
            text = self.georefLineEdit.text().strip()
            if not text:
                return

            cell_polygon = georef2geo(text)
            center_lat, center_lon, _, _, _ ,_ = graticule_dggs_metrics(cell_polygon)

            cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)

            pt = self.vgridtools.zoomTo(epsg4326, center_lat, center_lon)
            self.marker.reset(QgsWkbTypes.PointGeometry)
            self.marker.addPoint(pt)

            canvas_crs = self.canvas.mapSettings().destinationCrs()
            if epsg4326 != canvas_crs:
                trans = QgsCoordinateTransform(
                    epsg4326, canvas_crs, QgsProject.instance()
                )
                cell_geometry.transform(trans)

            # Set the map extent - double the extent
            bbox = cell_geometry.boundingBox()
            bbox.scale(2.0, QgsPointXY(bbox.center()))
            self.canvas.setExtent(bbox)
            self.canvas.refresh()

            if not settings.persistentMarker:
                self.georef_marker.reset(QgsWkbTypes.PolygonGeometry)

            self.georef_marker.addGeometry(cell_geometry, None)

        except Exception as e:
            traceback.print_exc()
            self.iface.messageBar().pushMessage(
                "",
                tr("Invalid Coordinate: {}").format(str(e)),
                level=Qgis.Warning,
                duration=2,
            )
            return

    def zoomToMGRS(self):
        try:
            text = self.mgrsLineEdit.text().strip()
            if not text:
                return            
            cell_polygon = mgrs2geo(text)           
            center_lat, center_lon, _, _, _, _ = graticule_dggs_metrics(cell_polygon)

            cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)

            pt = self.vgridtools.zoomTo(epsg4326, center_lat, center_lon)
            self.marker.reset(QgsWkbTypes.PointGeometry)
            self.marker.addPoint(pt)

            canvas_crs = self.canvas.mapSettings().destinationCrs()
            if epsg4326 != canvas_crs:
                trans = QgsCoordinateTransform(
                    epsg4326, canvas_crs, QgsProject.instance()
                )
                cell_geometry.transform(trans)

            # Set the map extent - double the extent
            bbox = cell_geometry.boundingBox()
            bbox.scale(2.0, QgsPointXY(bbox.center()))
            self.canvas.setExtent(bbox)
            self.canvas.refresh()

            if not settings.persistentMarker:
                self.mgrs_marker.reset(QgsWkbTypes.PolygonGeometry)

            self.mgrs_marker.addGeometry(cell_geometry, None)

        except Exception as e:
            traceback.print_exc()
            self.iface.messageBar().pushMessage(
                "",
                tr("Invalid Coordinate: {}").format(str(e)),
                level=Qgis.Warning,
                duration=2,
            )
            return

    def zoomToTilecode(self):
        try:
            text = self.tilecodeLineEdit.text().strip()
            if not text:
                return

            cell_polygon = tilecode2geo(text)
            center_lat, center_lon, _, _, _ ,_ = graticule_dggs_metrics(cell_polygon)

            cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)

            pt = self.vgridtools.zoomTo(epsg4326, center_lat, center_lon)
            self.marker.reset(QgsWkbTypes.PointGeometry)
            self.marker.addPoint(pt)

            canvas_crs = self.canvas.mapSettings().destinationCrs()
            if epsg4326 != canvas_crs:
                trans = QgsCoordinateTransform(
                    epsg4326, canvas_crs, QgsProject.instance()
                )
                cell_geometry.transform(trans)

            # Set the map extent - double the extent
            bbox = cell_geometry.boundingBox()
            bbox.scale(2.0, QgsPointXY(bbox.center()))
            self.canvas.setExtent(bbox)
            self.canvas.refresh()

            if not settings.persistentMarker:
                self.tilecode_marker.reset(QgsWkbTypes.PolygonGeometry)

            self.tilecode_marker.addGeometry(cell_geometry, None)

        except Exception as e:
            traceback.print_exc()
            self.iface.messageBar().pushMessage(
                "",
                tr("Invalid Coordinate: {}").format(str(e)),
                level=Qgis.Warning,
                duration=2,
            )
            return

    def zoomToQuadkey(self):
        try:
            text = self.quadkeyLineEdit.text().strip()
            if not text:
                return

            cell_polygon = quadkey2geo(text)
            center_lat, center_lon, _, _, _ ,_ = graticule_dggs_metrics(cell_polygon)

            cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)

            pt = self.vgridtools.zoomTo(epsg4326, center_lat, center_lon)
            self.marker.reset(QgsWkbTypes.PointGeometry)
            self.marker.addPoint(pt)

            canvas_crs = self.canvas.mapSettings().destinationCrs()
            if epsg4326 != canvas_crs:
                trans = QgsCoordinateTransform(
                    epsg4326, canvas_crs, QgsProject.instance()
                )
                cell_geometry.transform(trans)

            # Set the map extent - double the extent
            bbox = cell_geometry.boundingBox()
            bbox.scale(2.0, QgsPointXY(bbox.center()))
            self.canvas.setExtent(bbox)
            self.canvas.refresh()

            if not settings.persistentMarker:
                self.quadkey_marker.reset(QgsWkbTypes.PolygonGeometry)

            self.quadkey_marker.addGeometry(cell_geometry, None)

        except Exception as e:
            traceback.print_exc()
            self.iface.messageBar().pushMessage(
                "",
                tr("Invalid Coordinate: {}").format(str(e)),
                level=Qgis.Warning,
                duration=2,
            )
            return

    def zoomToMaidenhead(self):
        try:
            text = self.maidenheadLineEdit.text().strip()
            if not text:
                return

            cell_polygon = maidenhead2geo(text)
            center_lat, center_lon, _, _, _ ,_ = graticule_dggs_metrics(cell_polygon)

            cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)

            pt = self.vgridtools.zoomTo(epsg4326, center_lat, center_lon)
            self.marker.reset(QgsWkbTypes.PointGeometry)
            self.marker.addPoint(pt)

            canvas_crs = self.canvas.mapSettings().destinationCrs()
            if epsg4326 != canvas_crs:
                trans = QgsCoordinateTransform(
                    epsg4326, canvas_crs, QgsProject.instance()
                )
                cell_geometry.transform(trans)

            # Set the map extent - double the extent
            bbox = cell_geometry.boundingBox()
            bbox.scale(2.0, QgsPointXY(bbox.center()))
            self.canvas.setExtent(bbox)
            self.canvas.refresh()

            if not settings.persistentMarker:
                self.maidenhead_marker.reset(QgsWkbTypes.PolygonGeometry)

            self.maidenhead_marker.addGeometry(cell_geometry, None)

        except Exception as e:
            traceback.print_exc()
            self.iface.messageBar().pushMessage(
                "",
                tr("Invalid Coordinate: {}").format(str(e)),
                level=Qgis.Warning,
                duration=2,
            )
            return

    def zoomToGARS(self):
        try:
            text = self.garsLineEdit.text().strip()
            if not text:
                return

            cell_polygon = gars2geo(text)
            center_lat, center_lon, _, _, _ ,_ = graticule_dggs_metrics(cell_polygon)

            cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)

            pt = self.vgridtools.zoomTo(epsg4326, center_lat, center_lon)
            self.marker.reset(QgsWkbTypes.PointGeometry)
            self.marker.addPoint(pt)

            canvas_crs = self.canvas.mapSettings().destinationCrs()
            if epsg4326 != canvas_crs:
                trans = QgsCoordinateTransform(
                    epsg4326, canvas_crs, QgsProject.instance()
                )
                cell_geometry.transform(trans)

            # Set the map extent - double the extent
            bbox = cell_geometry.boundingBox()
            bbox.scale(2.0, QgsPointXY(bbox.center()))
            self.canvas.setExtent(bbox)
            self.canvas.refresh()

            if not settings.persistentMarker:
                self.gars_marker.reset(QgsWkbTypes.PolygonGeometry)

            self.gars_marker.addGeometry(cell_geometry, None)

        except Exception as e:
            traceback.print_exc()
            self.iface.messageBar().pushMessage(
                "",
                tr("Invalid Coordinate: {}").format(str(e)),
                level=Qgis.Warning,
                duration=2,
            )
            return

    def zoomToDIGIPIN(self):
        try:
            text = self.digipinLineEdit.text().strip()
            if not text:
                return

            cell_polygon = digipin2geo(text)
            center_lat, center_lon, _, _, _ ,_ = graticule_dggs_metrics(cell_polygon)

            pt = self.vgridtools.zoomTo(epsg4326, center_lat, center_lon)
            self.marker.reset(QgsWkbTypes.PointGeometry)
            self.marker.addPoint(pt)

            canvas_crs = self.canvas.mapSettings().destinationCrs()
            if epsg4326 != canvas_crs:
                trans_to_canvas = QgsCoordinateTransform(
                    epsg4326, canvas_crs, QgsProject.instance()
                )
                if settings.splitAntimeridian:
                    cell_polygon = fix_polygon(cell_polygon)
                cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)
                cell_geometry.transform(trans_to_canvas)
            else:
                cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)

            bbox = cell_geometry.boundingBox()
            bbox.scale(2.0, QgsPointXY(bbox.center()))
            self.canvas.setExtent(bbox)
            self.canvas.refresh()

            if not settings.persistentMarker:
                self.digipin_marker.reset(QgsWkbTypes.PolygonGeometry)

            self.digipin_marker.addGeometry(cell_geometry, None)

        except Exception as e:
            traceback.print_exc()
            self.iface.messageBar().pushMessage(
                "",
                tr("Invalid Coordinate: {}").format(str(e)),
                level=Qgis.Warning,
                duration=2,
            )
            return


    @pyqtSlot(QgsPointXY)
    def capturedPoint(self, pt):
        if self.isVisible() and self.coordCaptureButton.isChecked():
            self.updateCoordinates(-1, pt, epsg4326)

    def startCapture(self):
        if self.coordCaptureButton.isChecked():
            self.savedMapTool = self.canvas.mapTool()
            self.canvas.setMapTool(self.captureCoordinate)
        else:
            if self.savedMapTool:
                self.canvas.setMapTool(self.savedMapTool)
                self.savedMapTool = None

    @pyqtSlot()
    def stopCapture(self):
        self.coordCaptureButton.setChecked(False)

    def removeMarker(self):
        self.marker.reset(QgsWkbTypes.PointGeometry)

        self.h3_marker.reset(QgsWkbTypes.PolygonGeometry)
        self.s2_marker.reset(QgsWkbTypes.PolygonGeometry)
        self.a5_marker.reset(QgsWkbTypes.PolygonGeometry)
        self.rhealpix_marker.reset(QgsWkbTypes.PolygonGeometry)

        self.dggal_gnosis_marker.reset(QgsWkbTypes.PolygonGeometry)
        self.dggal_isea3h_marker.reset(QgsWkbTypes.PolygonGeometry)
        self.dggal_isea9r_marker.reset(QgsWkbTypes.PolygonGeometry)
        self.dggal_ivea3h_marker.reset(QgsWkbTypes.PolygonGeometry)
        self.dggal_ivea9r_marker.reset(QgsWkbTypes.PolygonGeometry)
        self.dggal_rtea3h_marker.reset(QgsWkbTypes.PolygonGeometry)
        self.dggal_rtea9r_marker.reset(QgsWkbTypes.PolygonGeometry)
        self.dggal_rhealpix_marker.reset(QgsWkbTypes.PolygonGeometry)
        self.dggal_isea4r_marker.reset(QgsWkbTypes.PolygonGeometry)
        self.dggal_isea7h_marker.reset(QgsWkbTypes.PolygonGeometry)
        self.dggal_isea7h_z7_marker.reset(QgsWkbTypes.PolygonGeometry)
        self.dggal_ivea4r_marker.reset(QgsWkbTypes.PolygonGeometry)
        self.dggal_ivea7h_marker.reset(QgsWkbTypes.PolygonGeometry)
        self.dggal_ivea7h_z7_marker.reset(QgsWkbTypes.PolygonGeometry)
        self.dggal_rtea4r_marker.reset(QgsWkbTypes.PolygonGeometry)
        self.dggal_rtea7h_marker.reset(QgsWkbTypes.PolygonGeometry)
        self.dggal_rtea7h_z7_marker.reset(QgsWkbTypes.PolygonGeometry)
        self.dggal_healpix_marker.reset(QgsWkbTypes.PolygonGeometry)


        self.dggrid_superfund_marker.reset(QgsWkbTypes.PolygonGeometry)
        self.dggrid_planetrisk_marker.reset(QgsWkbTypes.PolygonGeometry)
        self.dggrid_isea3h_marker.reset(QgsWkbTypes.PolygonGeometry)
        self.dggrid_isea4h_marker.reset(QgsWkbTypes.PolygonGeometry)
        self.dggrid_isea4t_marker.reset(QgsWkbTypes.PolygonGeometry)
        self.dggrid_isea4d_marker.reset(QgsWkbTypes.PolygonGeometry)
        self.dggrid_isea43h_marker.reset(QgsWkbTypes.PolygonGeometry)
        self.dggrid_isea7h_marker.reset(QgsWkbTypes.PolygonGeometry)
        self.dggrid_igeo7_marker.reset(QgsWkbTypes.PolygonGeometry)
        self.dggrid_fuller3h_marker.reset(QgsWkbTypes.PolygonGeometry)
        self.dggrid_fuller4h_marker.reset(QgsWkbTypes.PolygonGeometry)
        self.dggrid_fuller4t_marker.reset(QgsWkbTypes.PolygonGeometry)
        self.dggrid_fuller4d_marker.reset(QgsWkbTypes.PolygonGeometry)
        self.dggrid_fuller43h_marker.reset(QgsWkbTypes.PolygonGeometry)
        self.dggrid_fuller7h_marker.reset(QgsWkbTypes.PolygonGeometry)  
        
        
        self.isea4t_marker.reset(QgsWkbTypes.PolygonGeometry)
        self.isea3h_marker.reset(QgsWkbTypes.PolygonGeometry)
        self.ease_marker.reset(QgsWkbTypes.PolygonGeometry)
        self.qtm_marker.reset(QgsWkbTypes.PolygonGeometry)
        self.olc_marker.reset(QgsWkbTypes.PolygonGeometry)
        self.geohash_marker.reset(QgsWkbTypes.PolygonGeometry)
        self.georef_marker.reset(QgsWkbTypes.PolygonGeometry)
        self.mgrs_marker.reset(QgsWkbTypes.PolygonGeometry)
        self.tilecode_marker.reset(QgsWkbTypes.PolygonGeometry)
        self.quadkey_marker.reset(QgsWkbTypes.PolygonGeometry)
        self.maidenhead_marker.reset(QgsWkbTypes.PolygonGeometry)
        self.gars_marker.reset(QgsWkbTypes.PolygonGeometry)
        self.digipin_marker.reset(QgsWkbTypes.PolygonGeometry)

    def showSettings(self):
        self.settings.showTab(1)

    def zoomTo(self):
        text = self.wgs84LineEdit.text().strip()
        try:
            lat, lon = parseDMSString(text, self.inputXYOrder)
            pt = self.vgridtools.zoomTo(epsg4326, lat, lon)
            self.marker.reset(QgsWkbTypes.PointGeometry)
            self.marker.addPoint(pt)
        except Exception:
            pass
