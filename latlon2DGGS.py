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
from qgis.PyQt.QtCore import QSize, QTimer
from qgis.PyQt.QtGui import QIcon, QColor
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
    QgsRectangle,
)

from qgis.gui import QgsRubberBand

from .utils import tr
from .utils.latlon import epsg4326, parseDMSString
from .settings import settings
from .utils.utm import latLon2Utm, isUtm, utm2Point
from .utils.captureCoordinate import CaptureCoordinate
from vgrid.conversion.latlon2dggs import *
from .utils.captureCoordinate import CaptureCoordinate
from vgrid.conversion.dggs2geo import *
from vgrid.conversion.dggs2geo.a52geo import a52geo
from vgrid.utils.geometry import geodesic_dggs_metrics

from vgrid.dggs.rhealpixdggs.dggs import RHEALPixDGGS
from vgrid.dggs.rhealpixdggs.ellipsoids import WGS84_ELLIPSOID
import traceback

from shapely.geometry import Polygon, box
from vgrid.utils.geometry import geodesic_dggs_metrics, fix_h3_antimeridian_cells
from math import log2


FORM_CLASS, _ = loadUiType(os.path.join(os.path.dirname(__file__), "ui/latlon2dggs.ui"))

s_invalid = tr("Invalid")
s_copied = tr("copied to the clipboard")


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
        self.rhealpixLineEdit.returnPressed.connect(self.commitRHEALPIX)
        self.isea4tLineEdit.returnPressed.connect(self.commitISEA4T)
        self.isea3hLineEdit.returnPressed.connect(self.commitISEA3H)
        self.easeLineEdit.returnPressed.connect(self.commitEASE)

        self.dggal_gnosisLineEdit.returnPressed.connect(self.commitDGGAL_GNOSIS)
        self.dggal_isea3hLineEdit.returnPressed.connect(self.commitDGGAL_ISEA3H)
        self.dggal_isea9rLineEdit.returnPressed.connect(self.commitDGGAL_ISEA9R)
        self.dggal_ivea3hLineEdit.returnPressed.connect(self.commitDGGAL_IVEA3H)
        self.dggal_ivea9rLineEdit.returnPressed.connect(self.commitDGGAL_IVEA9R)
        self.dggal_rtea3hLineEdit.returnPressed.connect(self.commitDGGAL_RTEA3H)
        self.dggal_rtea9rLineEdit.returnPressed.connect(self.commitDGGAL_RTEA9R)
        self.dggal_rhealpixLineEdit.returnPressed.connect(self.commitDGGAL_RHEALPIX)

        self.qtmLineEdit.returnPressed.connect(self.commitQTM)
        self.olcLineEdit.returnPressed.connect(self.commitOLC)
        self.geohashLineEdit.returnPressed.connect(self.commitGeohash)
        self.georefLineEdit.returnPressed.connect(self.commitGEOREF)
        self.mgrsLineEdit.returnPressed.connect(self.commitMGRS)
        self.tilecodeLineEdit.returnPressed.connect(self.commitTilecode)
        self.quadkeyLineEdit.returnPressed.connect(self.commitQuadkey)
        self.maidenheadLineEdit.returnPressed.connect(self.commitMaidenhead)
        self.garsLineEdit.returnPressed.connect(self.commitGARS)

        icon = QIcon(":/images/themes/default/mActionEditCopy.svg")
        self.wgs84CopyButton.setIcon(icon)
        self.projCopyButton.setIcon(icon)
        self.customCopyButton.setIcon(icon)
        self.utmCopyButton.setIcon(icon)

        self.h3CopyButton.setIcon(icon)
        self.s2CopyButton.setIcon(icon)
        self.a5CopyButton.setIcon(icon)
        self.rhealpixCopyButton.setIcon(icon)
        self.isea4tCopyButton.setIcon(icon)
        self.isea3hCopyButton.setIcon(icon)
        self.easeCopyButton.setIcon(icon)

        self.dggal_gnosisCopyButton.setIcon(icon)
        self.dggal_isea3hCopyButton.setIcon(icon)
        self.dggal_isea9rCopyButton.setIcon(icon)
        self.dggal_ivea3hCopyButton.setIcon(icon)
        self.dggal_ivea9rCopyButton.setIcon(icon)
        self.dggal_rtea3hCopyButton.setIcon(icon)
        self.dggal_rtea9rCopyButton.setIcon(icon)
        self.dggal_rhealpixCopyButton.setIcon(icon)

        self.qtmCopyButton.setIcon(icon)
        self.olcCopyButton.setIcon(icon)
        self.geohashCopyButton.setIcon(icon)
        self.georefCopyButton.setIcon(icon)
        self.mgrsCopyButton.setIcon(icon)
        self.tilecodeCopyButton.setIcon(icon)
        self.quadkeyCopyButton.setIcon(icon)
        self.maidenheadCopyButton.setIcon(icon)
        self.garsCopyButton.setIcon(icon)

        self.wgs84CopyButton.clicked.connect(self.copyWGS84)
        self.projCopyButton.clicked.connect(self.copyPROJ)
        self.customCopyButton.clicked.connect(self.copyCUSTOM)
        self.utmCopyButton.clicked.connect(self.copyUTM)

        self.h3CopyButton.clicked.connect(self.copyH3)
        self.s2CopyButton.clicked.connect(self.copyS2)
        self.a5CopyButton.clicked.connect(self.copyA5)
        self.rhealpixCopyButton.clicked.connect(self.copyRHEALPIX)
        self.isea4tCopyButton.clicked.connect(self.copyISEA4T)
        self.isea3hCopyButton.clicked.connect(self.copyISEA3H)
        self.easeCopyButton.clicked.connect(self.copyEASE)

        self.dggal_gnosisCopyButton.clicked.connect(self.copyDGGAL_GNOSIS)
        self.dggal_isea3hCopyButton.clicked.connect(self.copyDGGAL_ISEA3H)
        self.dggal_isea9rCopyButton.clicked.connect(self.copyDGGAL_ISEA9R)
        self.dggal_ivea3hCopyButton.clicked.connect(self.copyDGGAL_IVEA3H)
        self.dggal_ivea9rCopyButton.clicked.connect(self.copyDGGAL_IVEA9R)
        self.dggal_rtea3hCopyButton.clicked.connect(self.copyDGGAL_RTEA3H)
        self.dggal_rtea9rCopyButton.clicked.connect(self.copyDGGAL_RTEA9R)
        self.dggal_rhealpixCopyButton.clicked.connect(self.copyDGGAL_RHEALPIX)

        self.qtmCopyButton.clicked.connect(self.copyQTM)
        self.olcCopyButton.clicked.connect(self.copyOLC)
        self.geohashCopyButton.clicked.connect(self.copyGeohash)
        self.georefCopyButton.clicked.connect(self.copyGEOREF)
        self.mgrsCopyButton.clicked.connect(self.copyMGRS)
        self.tilecodeCopyButton.clicked.connect(self.copyTilecode)
        self.quadkeyCopyButton.clicked.connect(self.copyQuadkey)
        self.maidenheadCopyButton.clicked.connect(self.copyMaidenhead)
        self.garsCopyButton.clicked.connect(self.copyGARS)

        self.customProjectionSelectionWidget.setCrs(epsg4326)
        self.customProjectionSelectionWidget.crsChanged.connect(self.customCrsChanged)

        zoomto_icon = QIcon(":/images/themes/default/mActionZoomIn.svg")
        self.h3ZoomtoButton.setIcon(zoomto_icon)
        self.s2ZoomtoButton.setIcon(zoomto_icon)
        self.a5ZoomtoButton.setIcon(zoomto_icon)
        self.rhealpixZoomtoButton.setIcon(zoomto_icon)
        self.isea4tZoomtoButton.setIcon(zoomto_icon)
        self.isea3hZoomtoButton.setIcon(zoomto_icon)
        self.easeZoomtoButton.setIcon(zoomto_icon)

        self.dggal_gnosisZoomtoButton.setIcon(zoomto_icon)
        self.dggal_isea3hZoomtoButton.setIcon(zoomto_icon)
        self.dggal_isea9rZoomtoButton.setIcon(zoomto_icon)
        self.dggal_ivea3hZoomtoButton.setIcon(zoomto_icon)
        self.dggal_ivea9rZoomtoButton.setIcon(zoomto_icon)
        self.dggal_rtea3hZoomtoButton.setIcon(zoomto_icon)
        self.dggal_rtea9rZoomtoButton.setIcon(zoomto_icon)
        self.dggal_rhealpixZoomtoButton.setIcon(zoomto_icon)

        self.qtmZoomtoButton.setIcon(zoomto_icon)
        self.olcZoomtoButton.setIcon(zoomto_icon)
        self.geohashZoomtoButton.setIcon(zoomto_icon)
        self.georefZoomtoButton.setIcon(zoomto_icon)
        self.mgrsZoomtoButton.setIcon(zoomto_icon)
        self.tilecodeZoomtoButton.setIcon(zoomto_icon)
        self.quadkeyZoomtoButton.setIcon(zoomto_icon)
        self.maidenheadZoomtoButton.setIcon(zoomto_icon)
        self.garsZoomtoButton.setIcon(zoomto_icon)

        self.h3ZoomtoButton.clicked.connect(self.zoomToH3)
        self.s2ZoomtoButton.clicked.connect(self.zoomToS2)
        self.a5ZoomtoButton.clicked.connect(self.zoomToA5)
        self.rhealpixZoomtoButton.clicked.connect(self.zoomToRHEALPIX)
        self.isea4tZoomtoButton.clicked.connect(self.zoomToISEA4T)
        self.isea3hZoomtoButton.clicked.connect(self.zoomToISEA3H)
        self.easeZoomtoButton.clicked.connect(self.zoomToEASE)

        self.dggal_gnosisZoomtoButton.clicked.connect(self.zoomToDGGAL_GNOSIS)
        self.dggal_isea3hZoomtoButton.clicked.connect(self.zoomToDGGAL_ISEA3H)
        self.dggal_isea9rZoomtoButton.clicked.connect(self.zoomToDGGAL_ISEA9R)
        self.dggal_ivea3hZoomtoButton.clicked.connect(self.zoomToDGGAL_IVEA3H)
        self.dggal_ivea9rZoomtoButton.clicked.connect(self.zoomToDGGAL_IVEA9R)
        self.dggal_rtea3hZoomtoButton.clicked.connect(self.zoomToDGGAL_RTEA3H)
        self.dggal_rtea9rZoomtoButton.clicked.connect(self.zoomToDGGAL_RTEA9R)
        self.dggal_rhealpixZoomtoButton.clicked.connect(self.zoomToDGGAL_RHEALPIX)

        self.qtmZoomtoButton.clicked.connect(self.zoomToQTM)
        self.olcZoomtoButton.clicked.connect(self.zoomToOLC)
        self.geohashZoomtoButton.clicked.connect(self.zoomToGeohash)
        self.georefZoomtoButton.clicked.connect(self.zoomToGEOREF)
        self.mgrsZoomtoButton.clicked.connect(self.zoomToMGRS)
        self.tilecodeZoomtoButton.clicked.connect(self.zoomToTilecode)
        self.quadkeyZoomtoButton.clicked.connect(self.zoomToQuadkey)
        self.maidenheadZoomtoButton.clicked.connect(self.zoomToMaidenhead)
        self.garsZoomtoButton.clicked.connect(self.zoomToGARS)

        self.updateMarker()

    def updateMarker(self):
        self.marker = QgsRubberBand(self.canvas, QgsWkbTypes.PointGeometry)
        self.marker.setColor(settings.markerColor)
        self.marker.setStrokeColor(settings.markerColor)
        self.marker.setWidth(settings.markerWidth)
        self.marker.setIconSize(settings.markerSize)
        self.marker.setIcon(QgsRubberBand.ICON_CROSS)

        self.h3_marker = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
        self.h3_marker.setStrokeColor(settings.h3Color)
        self.h3_marker.setWidth(settings.gridWidth)

        self.s2_marker = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
        self.s2_marker.setStrokeColor(settings.s2Color)
        self.s2_marker.setWidth(settings.gridWidth)

        self.a5_marker = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
        self.a5_marker.setStrokeColor(settings.a5Color)
        self.a5_marker.setWidth(settings.gridWidth)

        self.isea4t_marker = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
        self.isea4t_marker.setStrokeColor(settings.isea4tColor)
        self.isea4t_marker.setWidth(settings.gridWidth)

        self.isea3h_marker = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
        self.isea3h_marker.setStrokeColor(settings.isea3hColor)
        self.rhealpix_marker = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
        self.rhealpix_marker.setStrokeColor(settings.rhealpixColor)
        self.rhealpix_marker.setWidth(settings.gridWidth)

        self.ease_marker = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
        self.ease_marker.setStrokeColor(settings.easeColor)
        self.ease_marker.setWidth(settings.gridWidth)

        self.dggal_gnosis_marker = QgsRubberBand(
            self.canvas, QgsWkbTypes.PolygonGeometry
        )
        self.dggal_gnosis_marker.setStrokeColor(settings.dggal_gnosisColor)
        self.dggal_gnosis_marker.setWidth(settings.gridWidth)

        self.dggal_isea3h_marker = QgsRubberBand(
            self.canvas, QgsWkbTypes.PolygonGeometry
        )
        self.dggal_isea3h_marker.setStrokeColor(settings.dggal_isea3hColor)
        self.dggal_isea3h_marker.setWidth(settings.gridWidth)

        self.dggal_isea9r_marker = QgsRubberBand(
            self.canvas, QgsWkbTypes.PolygonGeometry
        )
        self.dggal_isea9r_marker.setStrokeColor(settings.dggal_isea9rColor)
        self.dggal_isea9r_marker.setWidth(settings.gridWidth)

        self.dggal_ivea3h_marker = QgsRubberBand(
            self.canvas, QgsWkbTypes.PolygonGeometry
        )
        self.dggal_ivea3h_marker.setStrokeColor(settings.dggal_ivea3hColor)
        self.dggal_ivea3h_marker.setWidth(settings.gridWidth)

        self.dggal_ivea9r_marker = QgsRubberBand(
            self.canvas, QgsWkbTypes.PolygonGeometry
        )
        self.dggal_ivea9r_marker.setStrokeColor(settings.dggal_ivea9rColor)
        self.dggal_ivea9r_marker.setWidth(settings.gridWidth)

        self.dggal_rtea3h_marker = QgsRubberBand(
            self.canvas, QgsWkbTypes.PolygonGeometry
        )
        self.dggal_rtea3h_marker.setStrokeColor(settings.dggal_rtea3hColor)
        self.dggal_rtea3h_marker.setWidth(settings.gridWidth)

        self.dggal_rtea9r_marker = QgsRubberBand(
            self.canvas, QgsWkbTypes.PolygonGeometry
        )
        self.dggal_rtea9r_marker.setStrokeColor(settings.dggal_rtea9rColor)
        self.dggal_rtea9r_marker.setWidth(settings.gridWidth)

        self.dggal_rhealpix_marker = QgsRubberBand(
            self.canvas, QgsWkbTypes.PolygonGeometry
        )
        self.dggal_rhealpix_marker.setStrokeColor(settings.dggal_rhealpixColor)
        self.dggal_rhealpix_marker.setWidth(settings.gridWidth)

        self.qtm_marker = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
        self.qtm_marker.setStrokeColor(settings.qtmColor)
        self.qtm_marker.setWidth(settings.gridWidth)

        self.olc_marker = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
        self.olc_marker.setStrokeColor(settings.olcColor)
        self.olc_marker.setWidth(settings.gridWidth)

        self.geohash_marker = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
        self.geohash_marker.setStrokeColor(settings.geohashColor)
        self.geohash_marker.setWidth(settings.gridWidth)

        self.georef_marker = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
        self.georef_marker.setStrokeColor(settings.georefColor)
        self.georef_marker.setWidth(settings.gridWidth)

        self.mgrs_marker = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
        self.mgrs_marker.setStrokeColor(settings.mgrsColor)
        self.mgrs_marker.setWidth(settings.gridWidth)

        self.tilecode_marker = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
        self.tilecode_marker.setStrokeColor(settings.tilecodeColor)
        self.tilecode_marker.setWidth(settings.gridWidth)

        self.quadkey_marker = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
        self.quadkey_marker.setStrokeColor(settings.quadkeyColor)
        self.quadkey_marker.setWidth(settings.gridWidth)

        self.maidenhead_marker = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
        self.maidenhead_marker.setStrokeColor(settings.maidenheadColor)
        self.maidenhead_marker.setWidth(settings.gridWidth)

        self.gars_marker = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
        self.gars_marker.setStrokeColor(settings.garsColor)
        self.gars_marker.setWidth(settings.gridWidth)

    def configure(self):
        self.removeMarker()
        self.updateMarker()

    def showEvent(self, e):
        self.inputXYOrder = settings.coordOrder
        self.xyButton.setDefaultAction(self.xymenu.actions()[settings.coordOrder])
        self.updateLabel()
        self.configure()

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
            self.isea4tLineEdit.setText(s_invalid)
        if id != 9:
            self.isea3hLineEdit.setText(s_invalid)
        if id != 10:
            self.easeLineEdit.setText(s_invalid)

        if id != 11:
            self.dggal_gnosisLineEdit.setText(s_invalid)
        if id != 12:
            self.dggal_isea3hLineEdit.setText(s_invalid)
        if id != 13:
            self.dggal_isea9rLineEdit.setText(s_invalid)
        if id != 14:
            self.dggal_ivea3hLineEdit.setText(s_invalid)
        if id != 15:
            self.dggal_ivea9rLineEdit.setText(s_invalid)
        if id != 16:
            self.dggal_rtea3hLineEdit.setText(s_invalid)
        if id != 17:
            self.dggal_rtea9rLineEdit.setText(s_invalid)
        if id != 18:
            self.dggal_rhealpixLineEdit.setText(s_invalid)

        if id != 19:
            self.qtmLineEdit.setText(s_invalid)
        if id != 20:
            self.olcLineEdit.setText(s_invalid)
        if id != 21:
            self.geohashLineEdit.setText(s_invalid)
        if id != 22:
            self.georefLineEdit.setText(s_invalid)
        if id != 23:
            self.mgrsLineEdit.setText(s_invalid)
        if id != 24:
            self.tilecodeLineEdit.setText(s_invalid)
        if id != 25:
            self.quadkeyLineEdit.setText(s_invalid)
        if id != 26:
            self.maidenheadLineEdit.setText(s_invalid)
        if id != 27:
            self.garsLineEdit.setText(s_invalid)

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
        self.isea4tLineEdit.setText("")
        self.isea3hLineEdit.setText("")
        self.easeLineEdit.setText("")

        self.dggal_gnosisLineEdit.setText("")
        self.dggal_isea3hLineEdit.setText("")
        self.dggal_isea9rLineEdit.setText("")
        self.dggal_ivea3hLineEdit.setText("")
        self.dggal_ivea9rLineEdit.setText("")
        self.dggal_rtea3hLineEdit.setText("")
        self.dggal_rtea9rLineEdit.setText("")
        self.dggal_rhealpixLineEdit.setText("")

        self.qtmLineEdit.setText("")
        self.olcLineEdit.setText("")
        self.geohashLineEdit.setText("")
        self.georefLineEdit.setText("")
        self.mgrsLineEdit.setText("")
        self.tilecodeLineEdit.setText("")
        self.quadkeyLineEdit.setText("")
        self.maidenheadLineEdit.setText("")
        self.garsLineEdit.setText("")

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

        if id != 4:  # H3
            try:
                s = latlon2h3(pt4326.y(), pt4326.x(), settings.h3Res)
            except Exception:
                s = s_invalid
            self.h3LineEdit.setText(s)
        if id != 5:  # S2
            try:
                s = latlon2s2(pt4326.y(), pt4326.x(), settings.s2Res)
            except Exception:
                s = s_invalid
            self.s2LineEdit.setText(s)
        if id != 6:  # A5
            try:
                s = latlon2a5(pt4326.y(), pt4326.x(), settings.a5Res)
            except Exception:
                s = s_invalid
            self.a5LineEdit.setText(s)
        if id != 7:  # RHEALPIX
            try:
                s = latlon2rhealpix(pt4326.y(), pt4326.x(), settings.rhealpixRes)
            except Exception:
                s = s_invalid
            self.rhealpixLineEdit.setText(s)
        if id != 8:  # ISEA4T
            try:
                s = latlon2isea4t(pt4326.y(), pt4326.x(), settings.isea4tRes)
            except Exception:
                s = s_invalid
            self.isea4tLineEdit.setText(s)
        if id != 9:  # ISEA3H
            try:
                s = latlon2isea3h(pt4326.y(), pt4326.x(), settings.isea3hRes)
            except Exception:
                s = s_invalid
            self.isea3hLineEdit.setText(s)
        if id != 10:  # EASE
            try:
                s = latlon2ease(pt4326.y(), pt4326.x(), settings.easeRes)
            except Exception:
                s = s_invalid
            self.easeLineEdit.setText(s)

        ### DGGAL
        if id != 11:
            try:
                s = latlon2dggal(
                    "gnosis", pt4326.y(), pt4326.x(), settings.dggal_gnosisRes
                )
            except Exception:
                s = s_invalid
            self.dggal_gnosisLineEdit.setText(s)
        if id != 12:
            try:
                s = latlon2dggal(
                    "isea3h", pt4326.y(), pt4326.x(), settings.dggal_isea3hRes
                )
            except Exception:
                s = s_invalid
            self.dggal_isea3hLineEdit.setText(s)
        if id != 13:
            try:
                s = latlon2dggal(
                    "isea9r", pt4326.y(), pt4326.x(), settings.dggal_isea9rRes
                )
            except Exception:
                s = s_invalid
            self.dggal_isea9rLineEdit.setText(s)
        if id != 14:
            try:
                s = latlon2dggal(
                    "ivea3h", pt4326.y(), pt4326.x(), settings.dggal_ivea3hRes
                )
            except Exception:
                s = s_invalid
            self.dggal_ivea3hLineEdit.setText(s)
        if id != 15:
            try:
                s = latlon2dggal(
                    "ivea9r", pt4326.y(), pt4326.x(), settings.dggal_ivea9rRes
                )
            except Exception:
                s = s_invalid
            self.dggal_ivea9rLineEdit.setText(s)
        if id != 16:
            try:
                s = latlon2dggal(
                    "rtea3h", pt4326.y(), pt4326.x(), settings.dggal_rtea3hRes
                )
            except Exception:
                s = s_invalid
            self.dggal_rtea3hLineEdit.setText(s)
        if id != 17:
            try:
                s = latlon2dggal(
                    "rtea9r", pt4326.y(), pt4326.x(), settings.dggal_rtea9rRes
                )
            except Exception:
                s = s_invalid
            self.dggal_rtea9rLineEdit.setText(s)
        if id != 18:
            try:
                s = latlon2dggal(
                    "rhealpix", pt4326.y(), pt4326.x(), settings.dggal_rhealpixRes
                )
            except Exception:
                s = s_invalid
            self.dggal_rhealpixLineEdit.setText(s)

        ### QTM
        if id != 19:
            try:
                s = latlon2qtm(pt4326.y(), pt4326.x(), settings.qtmRes)
            except Exception:
                s = s_invalid
            self.qtmLineEdit.setText(s)

        ### Graticule-based DGGS

        if id != 20:
            try:
                s = latlon2olc(pt4326.y(), pt4326.x(), settings.olcRes)
            except Exception:
                s = s_invalid
            self.olcLineEdit.setText(s)
        if id != 21:
            try:
                s = latlon2geohash(pt4326.y(), pt4326.x(), settings.geohashRes)
            except Exception:
                s = s_invalid
            self.geohashLineEdit.setText(s)
        if id != 22:
            try:
                s = latlon2georef(pt4326.y(), pt4326.x(), settings.georefRes)
            except Exception:
                s = s_invalid
            self.georefLineEdit.setText(s)
        if id != 23:
            try:
                s = latlon2mgrs(pt4326.y(), pt4326.x(), settings.mgrsRes)
            except Exception:
                s = s_invalid
            self.mgrsLineEdit.setText(s)
        if id != 24:
            try:
                s = latlon2tilecode(pt4326.y(), pt4326.x(), settings.tilecodeRes)
            except Exception:
                s = s_invalid
            self.tilecodeLineEdit.setText(s)
        if id != 25:
            try:
                s = latlon2quadkey(pt4326.y(), pt4326.x(), settings.quadkeyRes)
            except Exception:
                s = s_invalid
            self.quadkeyLineEdit.setText(s)
        if id != 26:
            try:
                s = latlon2maidenhead(pt4326.y(), pt4326.x(), settings.maidenheadRes)
            except Exception:
                s = s_invalid
            self.maidenheadLineEdit.setText(s)
        if id != 27:
            try:
                s = latlon2gars(pt4326.y(), pt4326.x(), settings.garsRes)
            except Exception:
                s = s_invalid
            self.garsLineEdit.setText(s)

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

    def commitRHEALPIX(self):
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

    def commitISEA4T(self):
        text = self.isea4tLineEdit.text().strip()
        try:
            isea4t_geometry = isea4t2geo(text)
            num_edges = 3
            center_lat, center_lon, _, _, _ = geodesic_dggs_metrics(
                isea4t_geometry, num_edges
            )
            pt = QgsPoint(center_lon, center_lat)
            self.updateCoordinates(8, pt, epsg4326)
        except Exception:
            self.showInvalid(8)

    def commitISEA3H(self):
        text = self.isea3hLineEdit.text().strip()
        try:
            isea3h_geometry = isea3h2geo(text)
            num_edges = 6
            center_lat, center_lon, _, _, _ = geodesic_dggs_metrics(
                isea3h_geometry, num_edges
            )
            pt = QgsPoint(center_lon, center_lat)
            self.updateCoordinates(9, pt, epsg4326)
        except Exception:
            self.showInvalid(9)

    def commitEASE(self):
        text = self.easeLineEdit.text().strip()
        try:
            ease_geometry = ease2geo(text)
            num_edges = 4
            center_lat, center_lon, _, _, _ = geodesic_dggs_metrics(
                ease_geometry, num_edges
            )
            pt = QgsPoint(center_lon, center_lat)
            self.updateCoordinates(10, pt, epsg4326)
        except Exception:
            self.showInvalid(10)

    def commitDGGAL_GNOSIS(self):
        text = self.dggal_gnosisLineEdit.text().strip()
        try:
            dggal_gnosis_geometry = dggal2geo("gnosis", text)
            num_edges = 4
            center_lat, center_lon, _, _, _ = geodesic_dggs_metrics(
                dggal_gnosis_geometry, num_edges
            )
            pt = QgsPoint(center_lon, center_lat)
            self.updateCoordinates(11, pt, epsg4326)
        except Exception:
            self.showInvalid(11)

    def commitDGGAL_ISEA3H(self):
        text = self.dggal_isea3hLineEdit.text().strip()
        try:
            dggal_isea3h_geometry = dggal2geo("isea3h", text)
            num_edges = 6
            center_lat, center_lon, _, _, _ = geodesic_dggs_metrics(
                dggal_isea3h_geometry, num_edges
            )
            pt = QgsPoint(center_lon, center_lat)
            self.updateCoordinates(12, pt, epsg4326)
        except Exception:
            self.showInvalid(12)

    def commitDGGAL_ISEA9R(self):
        text = self.dggal_isea9rLineEdit.text().strip()
        try:
            dggal_isea9r_geometry = dggal2geo("isea9r", text)
            num_edges = 4
            center_lat, center_lon, _, _, _ = geodesic_dggs_metrics(
                dggal_isea9r_geometry, num_edges
            )
            pt = QgsPoint(center_lon, center_lat)
            self.updateCoordinates(13, pt, epsg4326)
        except Exception:
            self.showInvalid(13)

    def commitDGGAL_IVEA3H(self):
        text = self.dggal_ivea3hLineEdit.text().strip()
        try:
            dggal_ivea3h_geometry = dggal2geo("ivea3h", text)
            num_edges = 6
            center_lat, center_lon, _, _, _ = geodesic_dggs_metrics(
                dggal_ivea3h_geometry, num_edges
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

    def commitDGGAL_RTEA3H(self):
        text = self.dggal_rtea3hLineEdit.text().strip()
        try:
            dggal_rtea3h_geometry = dggal2geo("rtea3h", text)
            num_edges = 6
            center_lat, center_lon, _, _, _ = geodesic_dggs_metrics(
                dggal_rtea3h_geometry, num_edges
            )
            pt = QgsPoint(center_lon, center_lat)
            self.updateCoordinates(16, pt, epsg4326)
        except Exception:
            self.showInvalid(16)

    def commitDGGAL_RTEA9R(self):
        text = self.dggal_rtea9rLineEdit.text().strip()
        try:
            dggal_rtea9r_geometry = dggal2geo("rtea9r", text)
            num_edges = 4
            center_lat, center_lon, _, _, _ = geodesic_dggs_metrics(
                dggal_rtea9r_geometry, num_edges
            )
            pt = QgsPoint(center_lon, center_lat)
            self.updateCoordinates(17, pt, epsg4326)
        except Exception:
            self.showInvalid(17)

    def commitDGGAL_RHEALPIX(self):
        text = self.dggal_rhealpixLineEdit.text().strip()
        try:
            dggal_rhealpix_geometry = dggal2geo("rhealpix", text)
            num_edges = 4
            center_lat, center_lon, _, _, _ = geodesic_dggs_metrics(
                dggal_rhealpix_geometry, num_edges
            )
            pt = QgsPoint(center_lon, center_lat)
            self.updateCoordinates(18, pt, epsg4326)
        except Exception:
            self.showInvalid(18)

    def commitQTM(self):
        text = self.qtmLineEdit.text().strip()
        try:
            qtm_geometry = qtm2geo(text)
            num_edges = 3
            center_lat, center_lon, _, _, _ = geodesic_dggs_metrics(
                qtm_geometry, num_edges
            )
            pt = QgsPoint(center_lon, center_lat)
            self.updateCoordinates(19, pt, epsg4326)
        except Exception:
            self.showInvalid(19)

    def commitOLC(self):
        text = self.olcLineEdit.text().strip()
        text = re.sub(r"\s+", "", text)  # Remove all white space
        try:
            olc_geometry = olc2geo(text)
            num_edges = 4
            center_lat, center_lon, _, _, _ = geodesic_dggs_metrics(
                olc_geometry, num_edges
            )
            pt = QgsPoint(center_lon, center_lat)
            self.updateCoordinates(20, pt, epsg4326)
        except Exception:
            self.showInvalid(20)

    def commitGeohash(self):
        text = self.geohashLineEdit.text().strip()
        text = re.sub(r"\s+", "", text)  # Remove all white space
        try:
            geohash_geometry = geohash2geo(text)
            num_edges = 4
            center_lat, center_lon, _, _, _ = geodesic_dggs_metrics(
                geohash_geometry, num_edges
            )
            pt = QgsPoint(center_lon, center_lat)
            self.updateCoordinates(21, pt, epsg4326)
        except Exception:
            self.showInvalid(21)

    def commitGEOREF(self):
        text = self.georefLineEdit.text().strip()
        try:
            georef_geometry = georef2geo(text)
            num_edges = 4
            center_lat, center_lon, _, _, _ = geodesic_dggs_metrics(
                georef_geometry, num_edges
            )
            pt = QgsPoint(center_lon, center_lat)
            self.updateCoordinates(22, pt, epsg4326)
        except Exception:
            traceback.print_exc()
            self.showInvalid(22)

    def commitMGRS(self):
        text = self.mgrsLineEdit.text().strip()
        text = re.sub(r"\s+", "", text)  # Remove all white space
        text = re.sub(r"\s+", "", text)  # Remove all white space
        try:
            mgrs_geometry = mgrs2geo(text)
            num_edges = 4
            center_lat, center_lon, _, _, _ = geodesic_dggs_metrics(
                mgrs_geometry, num_edges
            )
            pt = QgsPoint(center_lon, center_lat)
            self.updateCoordinates(23, pt, epsg4326)
        except Exception:
            self.showInvalid(23)

    def commitTilecode(self):
        text = self.tilecodeLineEdit.text().strip()
        try:
            tilecode_geometry = tilecode2geo(text)
            num_edges = 4
            center_lat, center_lon, _, _, _ = geodesic_dggs_metrics(
                tilecode_geometry, num_edges
            )
            pt = QgsPoint(center_lon, center_lat)
            self.updateCoordinates(24, pt, epsg4326)
        except Exception:
            self.showInvalid(24)

    def commitQuadkey(self):
        text = self.quadkeyLineEdit.text().strip()
        try:
            quadkey_geometry = quadkey2geo(text)
            num_edges = 4
            center_lat, center_lon, _, _, _ = geodesic_dggs_metrics(
                quadkey_geometry, num_edges
            )
            pt = QgsPoint(center_lon, center_lat)
            self.updateCoordinates(25, pt, epsg4326)
        except Exception:
            self.showInvalid(25)

    def commitMaidenhead(self):
        text = self.maidenheadLineEdit.text().strip()
        try:
            maidenhead_geometry = maidenhead2geo(text)
            num_edges = 4
            center_lat, center_lon, _, _, _ = geodesic_dggs_metrics(
                maidenhead_geometry, num_edges
            )
            pt = QgsPoint(center_lon, center_lat)
            self.updateCoordinates(26, pt, epsg4326)
        except Exception:
            self.showInvalid(26)

    def commitGARS(self):
        text = self.garsLineEdit.text().strip()
        try:
            gars_geometry = gars2geo(text)
            num_edges = 4
            center_lat, center_lon, _, _, _ = geodesic_dggs_metrics(
                gars_geometry, num_edges
            )
            pt = QgsPoint(center_lon, center_lat)
            self.updateCoordinates(27, pt, epsg4326)
        except Exception:
            traceback.print_exc()
            self.showInvalid(27)

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
        self.projectLabel.setText(label)

        label = "WGS 84 {}".format(latlon)
        self.wgs84Label.setText(label)

        crs = self.customProjectionSelectionWidget.crs()
        if crs.isGeographic():
            label = "→ {}".format(latlon)
        else:
            label = "→ {}".format(xy)
        self.customLabel.setText(label)

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

    def copyQTM(self):
        s = self.qtmLineEdit.text()
        self.clipboard.setText(s)
        self.iface.statusBarIface().showMessage("'{}' {}".format(s, s_copied), 3000)

    def copyOLC(self):
        s = self.plusLineEdit.text()
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

    def customCrsChanged(self):
        if self.origPt is not None:
            self.updateCoordinates(-1, self.origPt, self.origCrs)
        self.updateLabel()

    def zoomToH3(self):
        try:
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
            text = self.a5LineEdit.text().strip()
            if not text:
                return

            cell_polygon = a52geo(text)
            num_edges = 5
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

    def zoomToDGGAL_RHEALPIX(self):
        try:
            text = self.dggal_rhealpixLineEdit.text().strip()
            if not text:
                return

            cell_polygon = dggal2geo("rhealpix", text)
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

    def getH3Resolution(self, zoom):
        if zoom <= 3.0:
            return 0
        if zoom <= 4.4:
            return 1
        if zoom <= 5.7:
            return 2
        if zoom <= 7.1:
            return 3
        if zoom <= 8.4:
            return 4
        if zoom <= 9.8:
            return 5
        if zoom <= 11.4:
            return 6
        if zoom <= 12.7:
            return 7
        if zoom <= 14.1:
            return 8
        if zoom <= 15.5:
            return 9
        if zoom <= 16.8:
            return 10
        if zoom <= 18.2:
            return 11
        if zoom <= 19.5:
            return 12
        if zoom <= 21.1:
            return 13
        if zoom <= 21.9:
            return 14
        return 15

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
        self.isea4t_marker.reset(QgsWkbTypes.PolygonGeometry)
        self.isea3h_marker.reset(QgsWkbTypes.PolygonGeometry)
        self.ease_marker.reset(QgsWkbTypes.PolygonGeometry)
        self.dggal_gnosis_marker.reset(QgsWkbTypes.PolygonGeometry)
        self.dggal_isea3h_marker.reset(QgsWkbTypes.PolygonGeometry)
        self.dggal_isea9r_marker.reset(QgsWkbTypes.PolygonGeometry)
        self.dggal_ivea3h_marker.reset(QgsWkbTypes.PolygonGeometry)
        self.dggal_ivea9r_marker.reset(QgsWkbTypes.PolygonGeometry)
        self.dggal_rtea3h_marker.reset(QgsWkbTypes.PolygonGeometry)
        self.dggal_rtea9r_marker.reset(QgsWkbTypes.PolygonGeometry)
        self.dggal_rhealpix_marker.reset(QgsWkbTypes.PolygonGeometry)
        self.qtm_marker.reset(QgsWkbTypes.PolygonGeometry)
        self.olc_marker.reset(QgsWkbTypes.PolygonGeometry)
        self.geohash_marker.reset(QgsWkbTypes.PolygonGeometry)
        self.georef_marker.reset(QgsWkbTypes.PolygonGeometry)
        self.mgrs_marker.reset(QgsWkbTypes.PolygonGeometry)
        self.tilecode_marker.reset(QgsWkbTypes.PolygonGeometry)
        self.quadkey_marker.reset(QgsWkbTypes.PolygonGeometry)
        self.maidenhead_marker.reset(QgsWkbTypes.PolygonGeometry)
        self.gars_marker.reset(QgsWkbTypes.PolygonGeometry)

    def showSettings(self):
        self.settings.showTab(0)

    def zoomTo(self):
        text = self.wgs84LineEdit.text().strip()
        try:
            lat, lon = parseDMSString(text, self.inputXYOrder)
            pt = self.vgridtools.zoomTo(epsg4326, lat, lon)
            self.marker.reset(QgsWkbTypes.PointGeometry)
            self.marker.addPoint(pt)
        except Exception:
            pass
