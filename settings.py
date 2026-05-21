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
import enum

from qgis.PyQt.uic import loadUiType
from qgis.PyQt.QtWidgets import QDialog, QDialogButtonBox, QMessageBox
from qgis.core import QgsSettings
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtCore import Qt
from .utils import tr

try:
    from vgrid.utils.constants import DGGRID_TYPES
except ImportError:
    DGGRID_TYPES = {}

FORM_CLASS, _ = loadUiType(os.path.join(os.path.dirname(__file__), "ui/settings.ui"))

_DEFAULT_DGGRID_COLOR = "#159bc1"


def _dggrid_settings_prefix(dggs_type: str) -> str:
    return f"/vgrid/dggrid_{dggs_type.lower()}"


@enum.unique
class CoordOrder(enum.IntEnum):
    OrderYX = 0
    OrderXY = 1


class Settings:
    def __init__(self):
        self.readSettings()

    def readSettings(self):
        """Load the user selected settings. The settings are retained even when
        the user quits QGIS. This just loads the saved information into variables,
        but does not update the widgets. The widgets are updated with showEvent."""
        qset = QgsSettings()

        ### General Settings ###
        self.zoomLevel = int(qset.value("/vgrid/zoomLevel", Qt.CheckState.Checked))
        self.gridLabel = int(qset.value("/vgrid/gridLabel", Qt.CheckState.Checked))
        self.persistentMarker = int(
            qset.value("/vgrid/persistentMarker", Qt.CheckState.Checked)
        )
        self.splitAntimeridian = int(
            qset.value("/vgrid/splitAntimeridian", Qt.CheckState.Checked)
        )
        self.coordOrder = int(qset.value("/vgrid/coordOrder", CoordOrder.OrderYX))
        self.epsg4326Precision = int(qset.value("/vgrid/epsg4326Precision", 8))

        self.markerColor = QColor(qset.value("/vgrid/markerColor", "#ff0000"))
        self.markerColor.setAlpha(int(qset.value("/vgrid/markerColorOpacity", 255)))
        self.markerSize = int(qset.value("/vgrid/markerSize", 18))
        self.markerWidth = int(qset.value("/vgrid/markerWidth", 2))

        self.gridWidth = int(qset.value("/vgrid/gridWidth", 2))

        self.A5SgementsSpinBox = int(qset.value("/vgrid/A5SgementsSpinBox", 30))
        self.dggridDensificationSpinBox = int(
            qset.value("/vgrid/dggridDensificationSpinBox", 30)
        )

        ### Other DGGS Settings ###
        self.h3Res = int(qset.value("/vgrid/h3Res", 10))
        self.h3Color = QColor(qset.value("/vgrid/h3Color", "#1e54b7"))
        self.h3Color.setAlpha(int(qset.value("/vgrid/h3ColorOpacity", 255)))
        self.h3Visible = int(qset.value("/vgrid/h3Visible", Qt.CheckState.Checked))

        self.s2Res = int(qset.value("/vgrid/s2Res", 16))
        self.s2Color = QColor(qset.value("/vgrid/s2Color", "#de6b00"))
        self.s2Color.setAlpha(int(qset.value("/vgrid/s2ColorOpacity", 255)))
        self.s2Visible = int(qset.value("/vgrid/s2Visible", Qt.CheckState.Checked))

        self.a5Res = int(qset.value("/vgrid/a5Res", 15))
        self.a5Color = QColor(qset.value("/vgrid/a5Color", "#00aa55"))
        self.a5Color.setAlpha(int(qset.value("/vgrid/a5ColorOpacity", 255)))
        self.a5Visible = int(qset.value("/vgrid/a5Visible", Qt.CheckState.Checked))

        self.rhealpixRes = int(qset.value("/vgrid/rhealpixRes", 10))
        self.rhealpixColor = QColor(qset.value("/vgrid/rhealpixColor", "#7b0bff"))
        self.rhealpixColor.setAlpha(int(qset.value("/vgrid/rhealpixColorOpacity", 255)))
        self.rhealpixVisible = int(
            qset.value("/vgrid/rhealpixVisible", Qt.CheckState.Checked)
        )

        self.isea4tRes = int(qset.value("/vgrid/isea4tRes", 16))
        self.isea4tColor = QColor(qset.value("/vgrid/isea4tColor", "#159bc1"))
        self.isea4tColor.setAlpha(int(qset.value("/vgrid/isea4tColorOpacity", 255)))
        self.isea4tVisible = int(
            qset.value("/vgrid/isea4tVisible", Qt.CheckState.Checked)
        )

        self.isea3hRes = int(qset.value("/vgrid/isea3hRes", 20))
        self.isea3hColor = QColor(qset.value("/vgrid/isea3hColor", "#159bc1"))
        self.isea3hColor.setAlpha(int(qset.value("/vgrid/isea3hColorOpacity", 255)))
        self.isea3hVisible = int(
            qset.value("/vgrid/isea3hVisible", Qt.CheckState.Unchecked)
        )

        self.easeRes = int(qset.value("/vgrid/easeRes", 4))
        self.easeColor = QColor(qset.value("/vgrid/easeColor", "#7a0019"))
        self.easeColor.setAlpha(int(qset.value("/vgrid/easeColorOpacity", 255)))
        self.easeVisible = int(
            qset.value("/vgrid/easeVisible", Qt.CheckState.Unchecked)
        )

        self.qtmRes = int(qset.value("/vgrid/qtmRes", 18))
        self.qtmColor = QColor(qset.value("/vgrid/qtmColor", "#672a5c"))
        self.qtmColor.setAlpha(int(qset.value("/vgrid/qtmColorOpacity", 255)))
        self.qtmVisible = int(qset.value("/vgrid/qtmVisible", Qt.CheckState.Unchecked))

        self.olcRes = int(qset.value("/vgrid/olcRes", 8))
        self.olcColor = QColor(qset.value("/vgrid/olcColor", "#4285f4"))
        self.olcColor.setAlpha(int(qset.value("/vgrid/olcColorOpacity", 255)))
        self.olcVisible = int(qset.value("/vgrid/olcVisible", Qt.CheckState.Checked))

        self.geohashRes = int(qset.value("/vgrid/geohashRes", 7))
        self.geohashColor = QColor(qset.value("/vgrid/geohashColor", "#672a5c"))
        self.geohashColor.setAlpha(int(qset.value("/vgrid/geohashColorOpacity", 255)))
        self.geohashVisible = int(
            qset.value("/vgrid/geohashVisible", Qt.CheckState.Checked)
        )

        self.georefRes = int(qset.value("/vgrid/georefRes", 3))
        self.georefColor = QColor(qset.value("/vgrid/georefColor", "#672a5c"))
        self.georefColor.setAlpha(int(qset.value("/vgrid/georefColorOpacity", 255)))
        self.georefVisible = int(
            qset.value("/vgrid/georefVisible", Qt.CheckState.Checked)
        )

        self.mgrsRes = int(qset.value("/vgrid/mgrsRes", 3))
        self.mgrsColor = QColor(qset.value("/vgrid/mgrsColor", "#0052b4"))
        self.mgrsColor.setAlpha(int(qset.value("/vgrid/mgrsColorOpacity", 255)))
        self.mgrsVisible = int(qset.value("/vgrid/mgrsVisible", Qt.CheckState.Checked))

        self.tilecodeRes = int(qset.value("/vgrid/tilecodeRes", 18))
        self.tilecodeColor = QColor(qset.value("/vgrid/tilecodeColor", "#672a5c"))
        self.tilecodeColor.setAlpha(int(qset.value("/vgrid/tilecodeColorOpacity", 255)))
        self.tilecodeVisible = int(
            qset.value("/vgrid/tilecodeVisible", Qt.CheckState.Checked)
        )

        self.quadkeyRes = int(qset.value("/vgrid/quadkeyRes", 18))
        self.quadkeyColor = QColor(qset.value("/vgrid/quadkeyColor", "#672a5c"))
        self.quadkeyColor.setAlpha(int(qset.value("/vgrid/quadkeyColorOpacity", 255)))
        self.quadkeyVisible = int(
            qset.value("/vgrid/quadkeyVisible", Qt.CheckState.Checked)
        )

        self.maidenheadRes = int(qset.value("/vgrid/maidenheadRes", 4))
        self.maidenheadColor = QColor(qset.value("/vgrid/maidenheadColor", "#672a5c"))
        self.maidenheadColor.setAlpha(
            int(qset.value("/vgrid/maidenheadColorOpacity", 255))
        )
        self.maidenheadVisible = int(
            qset.value("/vgrid/maidenheadVisible", Qt.CheckState.Checked)
        )

        self.garsRes = int(qset.value("/vgrid/garsRes", 4))
        self.garsColor = QColor(qset.value("/vgrid/garsColor", "#672a5c"))
        self.garsColor.setAlpha(int(qset.value("/vgrid/garsColorOpacity", 255)))
        self.garsVisible = int(qset.value("/vgrid/garsVisible", Qt.CheckState.Checked))

        self.digipinRes = int(qset.value("/vgrid/digipinRes", 4))
        self.digipinColor = QColor(qset.value("/vgrid/digipinColor", "#672a5c"))
        self.digipinColor.setAlpha(int(qset.value("/vgrid/digipinColorOpacity", 255)))
        self.digipinVisible = int(
            qset.value("/vgrid/digipinVisible", Qt.CheckState.Unchecked)
        )

        ### DGGAL Settings ###
        self.dggal_gnosisRes = int(qset.value("/vgrid/dggal_gnosisRes", 16))
        self.dggal_gnosisColor = QColor(
            qset.value("/vgrid/dggal_gnosisColor", "#00008B")
        )
        self.dggal_gnosisColor.setAlpha(
            int(qset.value("/vgrid/dggal_gnosisColorOpacity", 255))
        )
        self.dggal_gnosisVisible = int(
            qset.value("/vgrid/dggal_gnosisVisible", Qt.CheckState.Checked)
        )

        self.dggal_isea4rRes = int(qset.value("/vgrid/dggal_isea4rRes", 12))
        self.dggal_isea4rColor = QColor(
            qset.value("/vgrid/dggal_isea4rColor", "#00008B")
        )
        self.dggal_isea4rColor.setAlpha(
            int(qset.value("/vgrid/dggal_isea4rColorOpacity", 255))
        )
        self.dggal_isea4rVisible = int(
            qset.value("/vgrid/dggal_isea4rVisible", Qt.CheckState.Unchecked)
        )

        self.dggal_isea9rRes = int(qset.value("/vgrid/dggal_isea9rRes", 10))
        self.dggal_isea9rColor = QColor(
            qset.value("/vgrid/dggal_isea9rColor", "#00008B")
        )
        self.dggal_isea9rColor.setAlpha(
            int(qset.value("/vgrid/dggal_isea9rColorOpacity", 255))
        )
        self.dggal_isea9rVisible = int(
            qset.value("/vgrid/dggal_isea9rVisible", Qt.CheckState.Unchecked)
        )

        self.dggal_isea3hRes = int(qset.value("/vgrid/dggal_isea3hRes", 21))
        self.dggal_isea3hColor = QColor(
            qset.value("/vgrid/dggal_isea3hColor", "#00008B")
        )
        self.dggal_isea3hColor.setAlpha(
            int(qset.value("/vgrid/dggal_isea3hColorOpacity", 255))
        )
        self.dggal_isea3hVisible = int(
            qset.value("/vgrid/dggal_isea3hVisible", Qt.CheckState.Unchecked)
        )

        self.dggal_isea7hRes = int(qset.value("/vgrid/dggal_isea7hRes", 12))
        self.dggal_isea7hColor = QColor(
            qset.value("/vgrid/dggal_isea7hColor", "#00008B")
        )
        self.dggal_isea7hColor.setAlpha(
            int(qset.value("/vgrid/dggal_isea7hColorOpacity", 255))
        )
        self.dggal_isea7hVisible = int(
            qset.value("/vgrid/dggal_isea7hVisible", Qt.CheckState.Unchecked)
        )

        self.dggal_isea7h_z7Res = int(qset.value("/vgrid/dggal_isea7h_z7Res", 12))
        self.dggal_isea7h_z7Color = QColor(
            qset.value("/vgrid/dggal_isea7h_z7Color", "#00008B")
        )
        self.dggal_isea7h_z7Color.setAlpha(
            int(qset.value("/vgrid/dggal_isea7h_z7ColorOpacity", 255))
        )
        self.dggal_isea7h_z7Visible = int(
            qset.value("/vgrid/dggal_isea7h_z7Visible", Qt.CheckState.Unchecked)
        )

        self.dggal_ivea4rRes = int(qset.value("/vgrid/dggal_ivea4rRes", 15))
        self.dggal_ivea4rColor = QColor(
            qset.value("/vgrid/dggal_ivea4rColor", "#00008B")
        )
        self.dggal_ivea4rColor.setAlpha(
            int(qset.value("/vgrid/dggal_ivea4rColorOpacity", 255))
        )
        self.dggal_ivea4rVisible = int(
            qset.value("/vgrid/dggal_ivea4rVisible", Qt.CheckState.Checked)
        )
        self.dggal_ivea9rRes = int(qset.value("/vgrid/dggal_ivea9rRes", 10))
        self.dggal_ivea9rColor = QColor(
            qset.value("/vgrid/dggal_ivea9rColor", "#00008B")
        )
        self.dggal_ivea9rColor.setAlpha(
            int(qset.value("/vgrid/dggal_ivea9rColorOpacity", 255))
        )
        self.dggal_ivea9rVisible = int(
            qset.value("/vgrid/dggal_ivea9rVisible", Qt.CheckState.Checked)
        )

        self.dggal_ivea3hRes = int(qset.value("/vgrid/dggal_ivea3hRes", 21))
        self.dggal_ivea3hColor = QColor(
            qset.value("/vgrid/dggal_ivea3hColor", "#00008B")
        )
        self.dggal_ivea3hColor.setAlpha(
            int(qset.value("/vgrid/dggal_ivea3hColorOpacity", 255))
        )
        self.dggal_ivea3hVisible = int(
            qset.value("/vgrid/dggal_ivea3hVisible", Qt.CheckState.Checked)
        )

        self.dggal_ivea7hRes = int(qset.value("/vgrid/dggal_ivea7hRes", 12))
        self.dggal_ivea7hColor = QColor(
            qset.value("/vgrid/dggal_ivea7hColor", "#00008B")
        )
        self.dggal_ivea7hColor.setAlpha(
            int(qset.value("/vgrid/dggal_ivea7hColorOpacity", 255))
        )
        self.dggal_ivea7hVisible = int(
            qset.value("/vgrid/dggal_ivea7hVisible", Qt.CheckState.Checked)
        )

        self.dggal_ivea7h_z7Res = int(qset.value("/vgrid/dggal_ivea7h_z7Res", 12))
        self.dggal_ivea7h_z7Color = QColor(
            qset.value("/vgrid/dggal_ivea7h_z7Color", "#00008B")
        )
        self.dggal_ivea7h_z7Color.setAlpha(
            int(qset.value("/vgrid/dggal_ivea7h_z7ColorOpacity", 255))
        )
        self.dggal_ivea7h_z7Visible = int(
            qset.value("/vgrid/dggal_ivea7h_z7Visible", Qt.CheckState.Checked)
        )

        self.dggal_rtea4rRes = int(qset.value("/vgrid/dggal_rtea4rRes", 15))
        self.dggal_rtea4rColor = QColor(
            qset.value("/vgrid/dggal_rtea4rColor", "#00008B")
        )
        self.dggal_rtea4rColor.setAlpha(
            int(qset.value("/vgrid/dggal_rtea4rColorOpacity", 255))
        )
        self.dggal_rtea4rVisible = int(
            qset.value("/vgrid/dggal_rtea4rVisible", Qt.CheckState.Unchecked)
        )
        self.dggal_rtea9rRes = int(qset.value("/vgrid/dggal_rtea9rRes", 10))
        self.dggal_rtea9rColor = QColor(
            qset.value("/vgrid/dggal_rtea9rColor", "#00008B")
        )
        self.dggal_rtea9rColor.setAlpha(
            int(qset.value("/vgrid/dggal_rtea9rColorOpacity", 255))
        )
        self.dggal_rtea9rVisible = int(
            qset.value("/vgrid/dggal_rtea9rVisible", Qt.CheckState.Unchecked)
        )

        self.dggal_rtea3hRes = int(qset.value("/vgrid/dggal_rtea3hRes", 21))
        self.dggal_rtea3hColor = QColor(
            qset.value("/vgrid/dggal_rtea3hColor", "#00008B")
        )
        self.dggal_rtea3hColor.setAlpha(
            int(qset.value("/vgrid/dggal_rtea3hColorOpacity", 255))
        )
        self.dggal_rtea3hVisible = int(
            qset.value("/vgrid/dggal_rtea3hVisible", Qt.CheckState.Unchecked)
        )

        self.dggal_rtea7hRes = int(qset.value("/vgrid/dggal_rtea7hRes", 12))
        self.dggal_rtea7hColor = QColor(
            qset.value("/vgrid/dggal_rtea7hColor", "#00008B")
        )
        self.dggal_rtea7hColor.setAlpha(
            int(qset.value("/vgrid/dggal_rtea7hColorOpacity", 255))
        )
        self.dggal_rtea7hVisible = int(
            qset.value("/vgrid/dggal_rtea7hVisible", Qt.CheckState.Unchecked)
        )

        self.dggal_rtea7h_z7Res = int(qset.value("/vgrid/dggal_rtea7h_z7Res", 12))
        self.dggal_rtea7h_z7Color = QColor(
            qset.value("/vgrid/dggal_rtea7h_z7Color", "#00008B")
        )
        self.dggal_rtea7h_z7Color.setAlpha(
            int(qset.value("/vgrid/dggal_rtea7h_z7ColorOpacity", 255))
        )
        self.dggal_rtea7h_z7Visible = int(
            qset.value("/vgrid/dggal_rtea7h_z7Visible", Qt.CheckState.Unchecked)
        )

        self.dggal_healpixRes = int(qset.value("/vgrid/dggal_healpixRes", 16))
        self.dggal_healpixColor = QColor(
            qset.value("/vgrid/dggal_healpixColor", "#00008B")
        )
        self.dggal_healpixColor.setAlpha(
            int(qset.value("/vgrid/dggal_healpixColorOpacity", 255))
        )
        self.dggal_healpixVisible = int(
            qset.value("/vgrid/dggal_healpixVisible", Qt.CheckState.Checked)
        )

        self.dggal_rhealpixRes = int(qset.value("/vgrid/dggal_rhealpixRes", 10))
        self.dggal_rhealpixColor = QColor(
            qset.value("/vgrid/dggal_rhealpixColor", "#00008B")
        )
        self.dggal_rhealpixColor.setAlpha(
            int(qset.value("/vgrid/dggal_rhealpixColorOpacity", 255))
        )
        self.dggal_rhealpixVisible = int(
            qset.value("/vgrid/dggal_rhealpixVisible", Qt.CheckState.Checked)
        )

        ### DGGRID  Settings ###
        self.dggrid_superfundRes = int(qset.value("/vgrid/dggrid_superfundRes", 9))
        self.dggrid_superfundColor = QColor(
            qset.value("/vgrid/dggrid_superfundColor", "#6025b0")
        )
        self.dggrid_superfundColor.setAlpha(
            int(qset.value("/vgrid/dggrid_superfundColorOpacity", 255))
        )
        self.dggrid_superfundVisible = int(
            qset.value("/vgrid/dggrid_superfundVisible", Qt.CheckState.Checked)
        )

        self.dggrid_planetriskRes = int(qset.value("/vgrid/dggrid_planetriskRes", 13))
        self.dggrid_planetriskColor = QColor(
            qset.value("/vgrid/dggrid_planetriskColor", "#6025b0")
        )
        self.dggrid_planetriskColor.setAlpha(
            int(qset.value("/vgrid/dggrid_planetriskColorOpacity", 255))
        )
        self.dggrid_planetriskVisible = int(
            qset.value("/vgrid/dggrid_planetriskVisible", Qt.CheckState.Checked)
        )

        self.dggrid_isea3hRes = int(qset.value("/vgrid/dggrid_isea3hRes", 20))
        self.dggrid_isea3hColor = QColor(
            qset.value("/vgrid/dggrid_isea3hColor", "#6025b0")
        )
        self.dggrid_isea3hColor.setAlpha(
            int(qset.value("/vgrid/dggrid_isea3hColorOpacity", 255))
        )
        self.dggrid_isea3hVisible = int(
            qset.value("/vgrid/dggrid_isea3hVisible", Qt.CheckState.Checked)
        )

        self.dggrid_isea4hRes = int(qset.value("/vgrid/dggrid_isea4hRes", 16))
        self.dggrid_isea4hColor = QColor(
            qset.value("/vgrid/dggrid_isea4hColor", "#6025b0")
        )
        self.dggrid_isea4hColor.setAlpha(
            int(qset.value("/vgrid/dggrid_isea4hColorOpacity", 255))
        )
        self.dggrid_isea4hVisible = int(
            qset.value("/vgrid/dggrid_isea4hVisible", Qt.CheckState.Checked)
        )

        self.dggrid_isea4tRes = int(qset.value("/vgrid/dggrid_isea4tRes", 15))
        self.dggrid_isea4tColor = QColor(
            qset.value("/vgrid/dggrid_isea4tColor", "#6025b0")
        )
        self.dggrid_isea4tColor.setAlpha(
            int(qset.value("/vgrid/dggrid_isea4tColorOpacity", 255))
        )
        self.dggrid_isea4tVisible = int(
            qset.value("/vgrid/dggrid_isea4tVisible", Qt.CheckState.Checked)
        )

        self.dggrid_isea4dRes = int(qset.value("/vgrid/dggrid_isea4dRes", 16))
        self.dggrid_isea4dColor = QColor(
            qset.value("/vgrid/dggrid_isea4dColor", "#6025b0")
        )
        self.dggrid_isea4dColor.setAlpha(
            int(qset.value("/vgrid/dggrid_isea4dColorOpacity", 255))
        )
        self.dggrid_isea4dVisible = int(
            qset.value("/vgrid/dggrid_isea4dVisible", Qt.CheckState.Checked)
        )

        self.dggrid_isea43hRes = int(qset.value("/vgrid/dggrid_isea43hRes", 10))
        self.dggrid_isea43hColor = QColor(
            qset.value("/vgrid/dggrid_isea43hColor", "#6025b0")
        )
        self.dggrid_isea43hColor.setAlpha(
            int(qset.value("/vgrid/dggrid_isea43hColorOpacity", 255))
        )
        self.dggrid_isea43hVisible = int(
            qset.value("/vgrid/dggrid_isea43hVisible", Qt.CheckState.Checked)
        )

        self.dggrid_isea7hRes = int(qset.value("/vgrid/dggrid_isea7hRes", 11))
        self.dggrid_isea7hColor = QColor(
            qset.value("/vgrid/dggrid_isea7hColor", "#6025b0")
        )
        self.dggrid_isea7hColor.setAlpha(
            int(qset.value("/vgrid/dggrid_isea7hColorOpacity", 255))
        )
        self.dggrid_isea7hVisible = int(
            qset.value("/vgrid/dggrid_isea7hVisible", Qt.CheckState.Checked)
        )

        self.dggrid_igeo7Res = int(qset.value("/vgrid/dggrid_igeo7Res", 12))
        self.dggrid_igeo7Color = QColor(
            qset.value("/vgrid/dggrid_igeo7Color", "#6025b0")
        )
        self.dggrid_igeo7Color.setAlpha(
            int(qset.value("/vgrid/dggrid_igeo7ColorOpacity", 255))
        )
        self.dggrid_igeo7Visible = int(
            qset.value("/vgrid/dggrid_igeo7Visible", Qt.CheckState.Checked)
        )

        self.dggrid_fuller3hRes = int(qset.value("/vgrid/dggrid_fuller3hRes", 20))
        self.dggrid_fuller3hColor = QColor(
            qset.value("/vgrid/dggrid_fuller3hColor", "#6025b0")
        )
        self.dggrid_fuller3hColor.setAlpha(
            int(qset.value("/vgrid/dggrid_fuller3hColorOpacity", 255))
        )
        self.dggrid_fuller3hVisible = int(
            qset.value("/vgrid/dggrid_fuller3hVisible", Qt.CheckState.Unchecked)
        )

        self.dggrid_fuller4hRes = int(qset.value("/vgrid/dggrid_fuller4hRes", 16))
        self.dggrid_fuller4hColor = QColor(
            qset.value("/vgrid/dggrid_fuller4hColor", "#6025b0")
        )
        self.dggrid_fuller4hColor.setAlpha(
            int(qset.value("/vgrid/dggrid_fuller4hColorOpacity", 255))
        )
        self.dggrid_fuller4hVisible = int(
            qset.value("/vgrid/dggrid_fuller4hVisible", Qt.CheckState.Unchecked)
        )

        self.dggrid_fuller4tRes = int(qset.value("/vgrid/dggrid_fuller4tRes", 15))
        self.dggrid_fuller4tColor = QColor(
            qset.value("/vgrid/dggrid_fuller4tColor", "#6025b0")
        )
        self.dggrid_fuller4tColor.setAlpha(
            int(qset.value("/vgrid/dggrid_fuller4tColorOpacity", 255))
        )
        self.dggrid_fuller4tVisible = int(
            qset.value("/vgrid/dggrid_fuller4tVisible", Qt.CheckState.Unchecked)
        )

        self.dggrid_fuller4dRes = int(qset.value("/vgrid/dggrid_fuller4dRes", 16))
        self.dggrid_fuller4dColor = QColor(
            qset.value("/vgrid/dggrid_fuller4dColor", "#6025b0")
        )
        self.dggrid_fuller4dColor.setAlpha(
            int(qset.value("/vgrid/dggrid_fuller4dColorOpacity", 255))
        )
        self.dggrid_fuller4dVisible = int(
            qset.value("/vgrid/dggrid_fuller4dVisible", Qt.CheckState.Unchecked)
        )

        self.dggrid_fuller43hRes = int(qset.value("/vgrid/dggrid_fuller43hRes", 10))
        self.dggrid_fuller43hColor = QColor(
            qset.value("/vgrid/dggrid_fuller43hColor", "#6025b0")
        )
        self.dggrid_fuller43hColor.setAlpha(
            int(qset.value("/vgrid/dggrid_fuller43hColorOpacity", 255))
        )
        self.dggrid_fuller43hVisible = int(
            qset.value("/vgrid/dggrid_fuller43hVisible", Qt.CheckState.Unchecked)
        )

        self.dggrid_fuller7hRes = int(qset.value("/vgrid/dggrid_fuller7hRes", 11))
        self.dggrid_fuller7hColor = QColor(
            qset.value("/vgrid/dggrid_fuller7hColor", "#6025b0")
        )
        self.dggrid_fuller7hColor.setAlpha(
            int(qset.value("/vgrid/dggrid_fuller7hColorOpacity", 255))
        )
        self.dggrid_fuller7hVisible = int(
            qset.value("/vgrid/dggrid_fuller7hVisible", Qt.CheckState.Unchecked)
        )

    def getResolution(self, dggs_type):
        """
        Get resolution settings for a specific DGGS type.
        Returns tuple (min_res, max_res, default_res) or None if not found.
        """
        # Define resolution ranges and defaults for each DGGS type
        resolution_config = {
            "H3": (0, 15, self.h3Res),
            "S2": (0, 30, self.s2Res),
            "A5": (0, 29, self.a5Res),
            "rHEALPix": (0, 15, self.rhealpixRes),
            "ISEA4T": (0, 39, self.isea4tRes),
            "ISEA3H": (0, 40, self.isea3hRes),
            "EASE": (0, 6, self.easeRes),
            "QTM": (1, 24, self.qtmRes),
            "OLC": (2, 15, self.olcRes),
            "Geohash": (1, 12, self.geohashRes),
            "GEOREF": (0, 10, self.georefRes),
            "MGRS": (0, 5, self.mgrsRes),
            "Tilecode": (0, 29, self.tilecodeRes),
            "Quadkey": (0, 29, self.quadkeyRes),
            "Maidenhead": (1, 4, self.maidenheadRes),
            "GARS": (1, 4, self.garsRes),
            "DIGIPIN": (1, 10, self.digipinRes),
            # DGGAL ###
            "DGGAL_GNOSIS": (0, 28, self.dggal_gnosisRes),
            "DGGAL_ISEA4R": (0, 20, self.dggal_isea4rRes),
            "DGGAL_ISEA9R": (0, 16, self.dggal_isea9rRes),
            "DGGAL_ISEA3H": (0, 33, self.dggal_isea3hRes),
            "DGGAL_ISEA7H": (0, 19, self.dggal_isea7hRes),
            "DGGAL_ISEA7H_Z7": (0, 19, self.dggal_isea7h_z7Res),
            "DGGAL_IVEA4R": (0, 20, self.dggal_ivea4rRes),
            "DGGAL_IVEA9R": (0, 16, self.dggal_ivea9rRes),
            "DGGAL_IVEA3H": (0, 33, self.dggal_ivea3hRes),
            "DGGAL_IVEA7H": (0, 19, self.dggal_ivea7hRes),
            "DGGAL_IVEA7H_Z7": (0, 19, self.dggal_ivea7h_z7Res),
            "DGGAL_RTEA4R": (0, 20, self.dggal_rtea4rRes),
            "DGGAL_RTEA9R": (0, 16, self.dggal_rtea9rRes),
            "DGGAL_RTEA3H": (0, 33, self.dggal_rtea3hRes),
            "DGGAL_RTEA7H": (0, 19, self.dggal_rtea7hRes),
            "DGGAL_RTEA7H_Z7": (0, 19, self.dggal_rtea7h_z7Res),
            "DGGAL_HEALPix": (0, 26, self.dggal_healpixRes),
            "DGGAL_rHEALPix": (0, 16, self.dggal_rhealpixRes),
            # DGGRID ###
            "DGGRID_SUPERFUND": (0, 16, self.dggrid_superfundRes),
            "DGGRID_PLANETRISK": (0, 20, self.dggrid_planetriskRes),
            "DGGRID_ISEA3H": (0, 35, self.dggrid_isea3hRes),
            "DGGRID_ISEA4H": (0, 30, self.dggrid_isea4hRes),
            "DGGRID_ISEA4T": (0, 29, self.dggrid_isea4tRes),
            "DGGRID_ISEA4D": (0, 30, self.dggrid_isea4dRes),
            "DGGRID_ISEA43H": (0, 18, self.dggrid_isea43hRes),
            "DGGRID_ISEA7H": (0, 21, self.dggrid_isea7hRes),
            "DGGRID_IGEO7": (0, 20, self.dggrid_igeo7Res),
            "DGGRID_FULLER3H": (0, 35, self.dggrid_fuller3hRes),
            "DGGRID_FULLER4H": (0, 30, self.dggrid_fuller4hRes),
            "DGGRID_FULLER4T": (0, 29, self.dggrid_fuller4tRes),
            "DGGRID_FULLER4D": (0, 30, self.dggrid_fuller4dRes),
            "DGGRID_FULLER43H": (0, 18, self.dggrid_fuller43hRes),
            "DGGRID_FULLER7H": (0, 21, self.dggrid_fuller7hRes),
        }

        return resolution_config.get(dggs_type)


settings = Settings()


class SettingsWidget(QDialog, FORM_CLASS):
    def __init__(self, vgridtools, iface, parent):
        super(SettingsWidget, self).__init__(parent)
        self.setupUi(self)
        self.vgridtools = vgridtools
        self.iface = iface
        self.canvas = iface.mapCanvas()
        self.coordOrderComboBox.addItems(
            [tr("Lat, Lon (Y,X) - Google Map Order"), tr("Lon, Lat (X,Y) Order")]
        )
        self.buttonBox.button(
            QDialogButtonBox.StandardButton.RestoreDefaults
        ).clicked.connect(self.restoreDefaults)
        self.readSettings()

    def restoreDefaults(self):
        """Restore all settings to their default state after user confirmation."""
        reply = QMessageBox.question(
            self,
            tr("Restore defaults"),
            tr(
                "Are you sure you want to reset all Vgrid settings to their default values? "
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        ### General Settings ###
        self.zoomLevelCheckBox.setCheckState(Qt.CheckState.Checked)
        self.gridLabelCheckBox.setCheckState(Qt.CheckState.Checked)
        self.persistentMarkerCheckBox.setCheckState(Qt.CheckState.Checked)
        self.splitAntimeridianCheckBox.setCheckState(Qt.CheckState.Checked)
        self.coordOrderComboBox.setCurrentIndex(CoordOrder.OrderYX)
        self.epsg4326PrecisionSpinBox.setValue(8)

        # Marker settings
        self.markerColorButton.setColor(QColor("#ff0000"))
        self.markerSizeSpinBox.setValue(18)
        self.markerWidthSpinBox.setValue(2)

        # Grid settings
        self.gridWidthSpinBox.setValue(2)

        # A5 and DGGRID options
        self.A5SgementsSpinBox.setValue(30)
        self.dggridDensificationSpinBox.setValue(30)
        settings.A5SgementsSpinBox = 30
        settings.dggridDensificationSpinBox = 30

        # Other DGGS settings

        # H3
        self.h3ResSpinBox.setValue(10)
        self.h3ColorButton.setColor(QColor("#1e54b7"))
        self.h3VisibleCheckBox.setChecked(True)

        # S2
        self.s2ResSpinBox.setValue(16)
        self.s2ColorButton.setColor(QColor("#de6b00"))
        self.s2VisibleCheckBox.setChecked(True)

        # A5
        self.a5ResSpinBox.setValue(15)
        self.a5ColorButton.setColor(QColor("#00aa55"))
        self.a5VisibleCheckBox.setChecked(True)

        # rHEALPix
        self.rhealpixResSpinBox.setValue(10)
        self.rhealpixColorButton.setColor(QColor("#7b0bff"))
        self.isea4tVisibleCheckBox.setChecked(True)

        # ISEA4T
        self.isea4tResSpinBox.setValue(16)
        self.isea4tColorButton.setColor(QColor("#159bc1"))
        self.isea4tVisibleCheckBox_2.setChecked(True)

        # ISEA3H
        self.isea3hResSpinBox.setValue(20)
        self.isea3hColorButton.setColor(QColor("#159bc1"))
        self.isea3hVisibleCheckBox.setChecked(False)

        # EASE
        self.easeResSpinBox.setValue(4)
        self.easeColorButton.setColor(QColor("#7a0019"))
        self.ease2VisibleCheckBox.setChecked(False)

        # QTM
        self.qtmResSpinBox.setValue(18)
        self.qtmColorButton.setColor(QColor("#672a5c"))
        self.qtmVisibleCheckBox.setChecked(False)

        # OLC
        self.olcResSpinBox.setValue(8)
        self.olcColorButton.setColor(QColor("#4285f4"))
        self.olcVisibleCheckBox.setChecked(True)

        # Geohash
        self.geohashResSpinBox.setValue(7)
        self.geohashColorButton.setColor(QColor("#672a5c"))
        self.geohashVisibleCheckBox.setChecked(True)

        # GEOREF
        self.georefResSpinBox.setValue(3)
        self.georefColorButton.setColor(QColor("#672a5c"))
        self.georefVisibleCheckbox.setChecked(True)

        # MGRS
        self.mgrsResSpinBox.setValue(3)
        self.mgrsColorButton.setColor(QColor("#0052b4"))
        self.mgrsVisibleCheckBox.setChecked(True)

        # Tilecode
        self.tilecodeResSpinBox.setValue(18)
        self.tilecodeColorButton.setColor(QColor("#672a5c"))
        self.tilecodeVisibleCheckBox.setChecked(True)

        # Quadkey
        self.quadkeyResSpinBox.setValue(18)
        self.quadkeyColorButton.setColor(QColor("#672a5c"))
        self.quadkeyVisibleCheckBox.setChecked(True)

        # Maidenhead
        self.maidenheadResSpinBox.setValue(4)
        self.maidenheadColorButton.setColor(QColor("#672a5c"))
        self.maidenheadVisibleCheckBox.setChecked(True)

        # GARS
        self.garsResSpinBox.setValue(4)
        self.garsColorButton.setColor(QColor("#672a5c"))
        self.garsVisibleCheckBox.setChecked(True)

        # DIGIPIN
        self.digipinResSpinBox.setValue(6)
        self.digipinColorButton.setColor(QColor("#672a5c"))
        self.digipinVisibleCheckBox.setChecked(False)

        # DGGAL_GNOSIS
        self.dggal_gnosisResSpinBox.setValue(16)
        self.dggal_gnosisColorButton.setColor(QColor("#00008B"))
        self.dggal_gnosisVisibleCheckBox.setChecked(True)

        # DGGAL_ISEA4R
        self.dggal_isea4rResSpinBox.setValue(12)
        self.dggal_isea4rColorButton.setColor(QColor("#00008B"))
        self.dggal_isea4rVisibleCheckBox.setChecked(False)

        # DGGAL_ISEA9R
        self.dggal_isea9rResSpinBox.setValue(10)
        self.dggal_isea9rColorButton.setColor(QColor("#00008B"))
        self.dggal_isea9rVisibleCheckBox.setChecked(False)

        # DGGAL_ISEA3H
        self.dggal_isea3hResSpinBox.setValue(21)
        self.dggal_isea3hColorButton.setColor(QColor("#00008B"))
        self.dggal_isea3hVisibleCheckBox.setChecked(False)

        # DGGAL_ISEA7H
        self.dggal_isea7hResSpinBox.setValue(11)
        self.dggal_isea7hColorButton.setColor(QColor("#00008B"))
        self.dggal_isea7hVisibleCheckBox.setChecked(False)

        # DGGAL_ISEA7H_Z7
        self.dggal_isea7h_z7ResSpinBox.setValue(11)
        self.dggal_isea7h_z7ColorButton.setColor(QColor("#00008B"))
        self.dggal_isea3h_z7VisibleCheckBox.setChecked(False)

        # DGGAL_IVEA4R
        self.dggal_ivea4rResSpinBox.setValue(15)
        self.dggal_ivea4rColorButton.setColor(QColor("#00008B"))
        self.dggal_ivea4rVisibleCheckBox.setChecked(True)

        # DGGAL_IVEA9R
        self.dggal_ivea9rResSpinBox.setValue(10)
        self.dggal_ivea9rColorButton.setColor(QColor("#00008B"))
        self.dggal_ivea9rVisibleCheckBox.setChecked(True)

        # DGGAL_IVEA3H
        self.dggal_ivea3hResSpinBox.setValue(21)
        self.dggal_ivea3hColorButton.setColor(QColor("#00008B"))
        self.dggal_ivea3hVisibleCheckBox.setChecked(True)

        # DGGAL_IVEA7H
        self.dggal_ivea7hResSpinBox.setValue(11)
        self.dggal_ivea7hColorButton.setColor(QColor("#00008B"))
        self.dggal_ivea7hVisibleCheckBox.setChecked(True)

        # DGGAL_IVEA7H_Z7
        self.dggal_ivea7h_z7ResSpinBox.setValue(11)
        self.dggal_ivea7h_z7ColorButton.setColor(QColor("#00008B"))
        self.dggal_ivea7h_z7VisibleCheckBox.setChecked(True)

        # DGGAL_RTEA4R
        self.dggal_rtea4rResSpinBox.setValue(12)
        self.dggal_rtea4rColorButton.setColor(QColor("#00008B"))
        self.dggal_rtea4rVisibleCheckBox.setChecked(False)

        # DGGAL_RTEA9R
        self.dggal_rtea9rResSpinBox.setValue(10)
        self.dggal_rtea9rColorButton.setColor(QColor("#00008B"))
        self.dggal_rtea9rVisibleCheckBox.setChecked(False)

        # DGGAL_RTEA3H
        self.dggal_rtea3hResSpinBox.setValue(21)
        self.dggal_rtea3hColorButton.setColor(QColor("#00008B"))
        self.dggal_rtea3hVisibleCheckBox.setChecked(False)

        # DGGAL_RTEA7H
        self.dggal_rtea7hResSpinBox.setValue(11)
        self.dggal_rtea7hColorButton.setColor(QColor("#00008B"))
        self.dggal_rtea7hCheckBox.setChecked(False)

        # DGGAL_RTEA7H_Z7
        self.dggal_rtea7h_z7ResSpinBox.setValue(11)
        self.dggal_rtea7h_z7ColorButton.setColor(QColor("#00008B"))
        self.dggal_rtea7h_z7VisibleCheckBox.setChecked(False)

        # DGGAL_HEALPix
        self.dggal_healpixResSpinBox.setValue(18)
        self.dggal_healpixColorButton.setColor(QColor("#00008B"))
        self.dggal_healpixVisibleCheckBox.setChecked(True)

        # DGGAL_RHEALPIX
        self.dggal_rhealpixResSpinBox.setValue(10)
        self.dggal_rhealpixColorButton.setColor(QColor("#00008B"))
        self.dggal_rhealpixVisibleCheckBox.setChecked(True)

        ### DGGRID Settings ###
        self.dggrid_superfundResSpinBox.setValue(9)
        self.dggrid_superfundColorButton.setColor(QColor("#6025b0"))
        self.dggrid_superfundVisibleCheckBox.setChecked(True)

        self.dggrid_planetriskResSpinBox.setValue(13)
        self.dggrid_planetriskColorButton.setColor(QColor("#6025b0"))
        self.dggrid_planetVisibleCheckBox.setChecked(True)

        self.dggrid_isea3hResSpinBox.setValue(20)
        self.dggrid_isea3hColorButton.setColor(QColor("#6025b0"))
        self.dggrid_isea3hVisibleCheckBox.setChecked(True)

        self.dggrid_isea4hResSpinBox.setValue(16)
        self.dggrid_isea4hColorButton.setColor(QColor("#6025b0"))
        self.dggrid_isea4hVisibleCheckBox.setChecked(True)

        self.dggrid_isea4tResSpinBox.setValue(15)
        self.dggrid_isea4tColorButton.setColor(QColor("#6025b0"))
        self.dggrid_isea4tVisibleCheckBox.setChecked(True)

        self.dggrid_isea4dResSpinBox.setValue(16)
        self.dggrid_isea4dColorButton.setColor(QColor("#6025b0"))
        self.dggrid_isea4dVisibleCheckBox.setChecked(True)

        self.dggrid_isea43hResSpinBox.setValue(10)
        self.dggrid_isea43hColorButton.setColor(QColor("#6025b0"))
        self.dggrid_isea43hVisibleCheckBox.setChecked(True)

        self.dggrid_isea7hResSpinBox.setValue(11)
        self.dggrid_isea7hColorButton.setColor(QColor("#6025b0"))
        self.dggrid_isea7hVisibleCheckBox.setChecked(True)

        self.dggrid_igeo7ResSpinBox.setValue(12)
        self.dggrid_igeo7ColorButton.setColor(QColor("#6025b0"))
        self.dggrid_igeo7VisibleCheckBox.setChecked(True)

        self.dggrid_fuller3hResSpinBox.setValue(20)
        self.dggrid_fuller3hColorButton.setColor(QColor("#6025b0"))
        self.dggrid_fuller3hVisibleCheckBox.setChecked(False)

        self.dggrid_fuller4hResSpinBox.setValue(16)
        self.dggrid_fuller4hColorButton.setColor(QColor("#6025b0"))
        self.dggrid_fuller4hVisibleCheckBox.setChecked(False)

        self.dggrid_fuller4tResSpinBox.setValue(15)
        self.dggrid_fuller4tColorButton.setColor(QColor("#6025b0"))
        self.dggrid_fuller4tVisibleCheckBox.setChecked(False)

        self.dggrid_fuller4dResSpinBox.setValue(16)
        self.dggrid_fuller4dColorButton.setColor(QColor("#6025b0"))
        self.dggrid_fuller4dVisibleCheckBox.setChecked(False)

        self.dggrid_fuller43hResSpinBox.setValue(10)
        self.dggrid_fuller43hColorButton.setColor(QColor("#6025b0"))
        self.dggrid_fuller43hVisibleCheckBox.setChecked(False)

        self.dggrid_fuller7hResSpinBox.setValue(11)
        self.dggrid_fuller7hColorButton.setColor(QColor("#6025b0"))
        self.dggrid_fuller7hVisibleCheckBox.setChecked(False)

        settings.h3Visible = int(self.h3VisibleCheckBox.checkState())
        settings.s2Visible = int(self.s2VisibleCheckBox.checkState())
        settings.a5Visible = int(self.a5VisibleCheckBox.checkState())
        settings.rhealpixVisible = int(self.isea4tVisibleCheckBox.checkState())
        settings.isea4tVisible = int(self.isea4tVisibleCheckBox_2.checkState())
        settings.isea3hVisible = int(self.isea3hVisibleCheckBox.checkState())
        settings.easeVisible = int(self.ease2VisibleCheckBox.checkState())
        settings.qtmVisible = int(self.qtmVisibleCheckBox.checkState())
        settings.olcVisible = int(self.olcVisibleCheckBox.checkState())
        settings.geohashVisible = int(self.geohashVisibleCheckBox.checkState())
        settings.georefVisible = int(self.georefVisibleCheckbox.checkState())
        settings.mgrsVisible = int(self.mgrsVisibleCheckBox.checkState())
        settings.tilecodeVisible = int(self.tilecodeVisibleCheckBox.checkState())
        settings.quadkeyVisible = int(self.quadkeyVisibleCheckBox.checkState())
        settings.maidenheadVisible = int(self.maidenheadVisibleCheckBox.checkState())
        settings.garsVisible = int(self.garsVisibleCheckBox.checkState())
        settings.digipinVisible = int(self.digipinVisibleCheckBox.checkState())
        settings.dggal_gnosisVisible = int(
            self.dggal_gnosisVisibleCheckBox.checkState()
        )
        settings.dggal_isea4rVisible = int(
            self.dggal_isea4rVisibleCheckBox.checkState()
        )
        settings.dggal_isea9rVisible = int(
            self.dggal_isea9rVisibleCheckBox.checkState()
        )
        settings.dggal_isea3hVisible = int(
            self.dggal_isea3hVisibleCheckBox.checkState()
        )
        settings.dggal_isea7hVisible = int(
            self.dggal_isea7hVisibleCheckBox.checkState()
        )
        settings.dggal_isea7h_z7Visible = int(
            self.dggal_isea3h_z7VisibleCheckBox.checkState()
        )
        settings.dggal_ivea4rVisible = int(
            self.dggal_ivea4rVisibleCheckBox.checkState()
        )
        settings.dggal_ivea9rVisible = int(
            self.dggal_ivea9rVisibleCheckBox.checkState()
        )
        settings.dggal_ivea3hVisible = int(
            self.dggal_ivea3hVisibleCheckBox.checkState()
        )
        settings.dggal_ivea7hVisible = int(
            self.dggal_ivea7hVisibleCheckBox.checkState()
        )
        settings.dggal_ivea7h_z7Visible = int(
            self.dggal_ivea7h_z7VisibleCheckBox.checkState()
        )
        settings.dggal_rtea4rVisible = int(
            self.dggal_rtea4rVisibleCheckBox.checkState()
        )
        settings.dggal_rtea9rVisible = int(
            self.dggal_rtea9rVisibleCheckBox.checkState()
        )
        settings.dggal_rtea3hVisible = int(
            self.dggal_rtea3hVisibleCheckBox.checkState()
        )
        settings.dggal_rtea7hVisible = int(self.dggal_rtea7hCheckBox.checkState())
        settings.dggal_rtea7h_z7Visible = int(
            self.dggal_rtea7h_z7VisibleCheckBox.checkState()
        )
        settings.dggal_healpixVisible = int(
            self.dggal_healpixVisibleCheckBox.checkState()
        )
        settings.dggal_rhealpixVisible = int(
            self.dggal_rhealpixVisibleCheckBox.checkState()
        )
        settings.dggrid_superfundVisible = int(
            self.dggrid_superfundVisibleCheckBox.checkState()
        )
        settings.dggrid_planetriskVisible = int(
            self.dggrid_planetVisibleCheckBox.checkState()
        )
        settings.dggrid_isea3hVisible = int(
            self.dggrid_isea3hVisibleCheckBox.checkState()
        )
        settings.dggrid_isea4hVisible = int(
            self.dggrid_isea4hVisibleCheckBox.checkState()
        )
        settings.dggrid_isea4tVisible = int(
            self.dggrid_isea4tVisibleCheckBox.checkState()
        )
        settings.dggrid_isea4dVisible = int(
            self.dggrid_isea4dVisibleCheckBox.checkState()
        )
        settings.dggrid_isea43hVisible = int(
            self.dggrid_isea43hVisibleCheckBox.checkState()
        )
        settings.dggrid_isea7hVisible = int(
            self.dggrid_isea7hVisibleCheckBox.checkState()
        )
        settings.dggrid_igeo7Visible = int(
            self.dggrid_igeo7VisibleCheckBox.checkState()
        )
        settings.dggrid_fuller3hVisible = int(
            self.dggrid_fuller3hVisibleCheckBox.checkState()
        )
        settings.dggrid_fuller4hVisible = int(
            self.dggrid_fuller4hVisibleCheckBox.checkState()
        )
        settings.dggrid_fuller4tVisible = int(
            self.dggrid_fuller4tVisibleCheckBox.checkState()
        )
        settings.dggrid_fuller4dVisible = int(
            self.dggrid_fuller4dVisibleCheckBox.checkState()
        )
        settings.dggrid_fuller43hVisible = int(
            self.dggrid_fuller43hVisibleCheckBox.checkState()
        )
        settings.dggrid_fuller7hVisible = int(
            self.dggrid_fuller7hVisibleCheckBox.checkState()
        )
        self.vgridtools.settingsChanged()

    def readSettings(self):
        """Load the user selected settings. The settings are retained even when
        the user quits QGIS. This just loads the saved information into varialbles,
        but does not update the widgets. The widgets are updated with showEvent."""
        settings.readSettings()

    def accept(self):
        """Accept the settings and save them for next time."""
        qset = QgsSettings()

        ### General Settings ###
        qset.setValue("/vgrid/zoomLevel", int(self.zoomLevelCheckBox.checkState()))
        qset.setValue("/vgrid/gridLabel", int(self.gridLabelCheckBox.checkState()))
        qset.setValue(
            "/vgrid/persistentMarker", int(self.persistentMarkerCheckBox.checkState())
        )
        qset.setValue(
            "/vgrid/splitAntimeridian", int(self.splitAntimeridianCheckBox.checkState())
        )
        qset.setValue("/vgrid/coordOrder", int(self.coordOrderComboBox.currentIndex()))
        qset.setValue(
            "/vgrid/epsg4326Precision", int(self.epsg4326PrecisionSpinBox.value())
        )

        qset.setValue("/vgrid/markerColor", self.markerColorButton.color().name())
        qset.setValue(
            "/vgrid/markerColorOpacity", self.markerColorButton.color().alpha()
        )
        qset.setValue("/vgrid/markerSize", int(self.markerSizeSpinBox.value()))
        qset.setValue("/vgrid/markerWidth", int(self.markerWidthSpinBox.value()))
        qset.setValue("/vgrid/gridWidth", int(self.gridWidthSpinBox.value()))

        ## A5 and DGGRID Options ##
        qset.setValue("/vgrid/A5SgementsSpinBox", int(self.A5SgementsSpinBox.value()))
        qset.setValue(
            "/vgrid/dggridDensificationSpinBox",
            int(self.dggridDensificationSpinBox.value()),
        )

        ### Other DGGS Settings ###
        qset.setValue("/vgrid/h3Res", int(self.h3ResSpinBox.value()))
        qset.setValue("/vgrid/h3Color", self.h3ColorButton.color().name())
        qset.setValue("/vgrid/h3ColorOpacity", self.h3ColorButton.color().alpha())

        qset.setValue("/vgrid/s2Res", int(self.s2ResSpinBox.value()))
        qset.setValue("/vgrid/s2Color", self.s2ColorButton.color().name())
        qset.setValue("/vgrid/s2ColorOpacity", self.s2ColorButton.color().alpha())

        qset.setValue("/vgrid/a5Res", int(self.a5ResSpinBox.value()))
        qset.setValue("/vgrid/a5Color", self.a5ColorButton.color().name())
        qset.setValue("/vgrid/a5ColorOpacity", self.a5ColorButton.color().alpha())

        qset.setValue("/vgrid/rhealpixRes", int(self.rhealpixResSpinBox.value()))
        qset.setValue("/vgrid/rhealpixColor", self.rhealpixColorButton.color().name())
        qset.setValue(
            "/vgrid/rhealpixColorOpacity", self.rhealpixColorButton.color().alpha()
        )

        qset.setValue("/vgrid/isea4tRes", int(self.isea4tResSpinBox.value()))
        qset.setValue("/vgrid/isea4tColor", self.isea4tColorButton.color().name())
        qset.setValue(
            "/vgrid/isea4tColorOpacity", self.isea4tColorButton.color().alpha()
        )

        qset.setValue("/vgrid/isea3hRes", int(self.isea3hResSpinBox.value()))
        qset.setValue("/vgrid/isea3hColor", self.isea3hColorButton.color().name())
        qset.setValue(
            "/vgrid/isea3hColorOpacity", self.isea3hColorButton.color().alpha()
        )

        qset.setValue("/vgrid/easeRes", int(self.easeResSpinBox.value()))
        qset.setValue("/vgrid/easeColor", self.easeColorButton.color().name())
        qset.setValue("/vgrid/easeColorOpacity", self.easeColorButton.color().alpha())

        qset.setValue("/vgrid/qtmRes", int(self.qtmResSpinBox.value()))
        qset.setValue("/vgrid/qtmColor", self.qtmColorButton.color().name())
        qset.setValue("/vgrid/qtmColorOpacity", self.qtmColorButton.color().alpha())

        qset.setValue("/vgrid/olcRes", int(self.olcResSpinBox.value()))
        qset.setValue("/vgrid/olcColor", self.olcColorButton.color().name())
        qset.setValue("/vgrid/olcColorOpacity", self.olcColorButton.color().alpha())

        qset.setValue("/vgrid/geohashRes", int(self.geohashResSpinBox.value()))
        qset.setValue("/vgrid/georefRes", int(self.georefResSpinBox.value()))
        qset.setValue("/vgrid/georefColor", self.georefColorButton.color().name())
        qset.setValue(
            "/vgrid/georefColorOpacity", self.georefColorButton.color().alpha()
        )

        qset.setValue("/vgrid/mgrsRes", int(self.mgrsResSpinBox.value()))
        qset.setValue("/vgrid/mgrsColor", self.mgrsColorButton.color().name())
        qset.setValue("/vgrid/mgrsColorOpacity", self.mgrsColorButton.color().alpha())

        qset.setValue("/vgrid/tilecodeRes", int(self.tilecodeResSpinBox.value()))
        qset.setValue("/vgrid/tilecodeColor", self.tilecodeColorButton.color().name())
        qset.setValue(
            "/vgrid/tilecodeColorOpacity", self.tilecodeColorButton.color().alpha()
        )

        qset.setValue("/vgrid/quadkeyRes", int(self.quadkeyResSpinBox.value()))
        qset.setValue("/vgrid/quadkeyColor", self.quadkeyColorButton.color().name())
        qset.setValue(
            "/vgrid/quadkeyColorOpacity", self.quadkeyColorButton.color().alpha()
        )

        qset.setValue("/vgrid/maidenheadRes", int(self.maidenheadResSpinBox.value()))
        qset.setValue(
            "/vgrid/maidenheadColor", self.maidenheadColorButton.color().name()
        )
        qset.setValue(
            "/vgrid/maidenheadColorOpacity", self.maidenheadColorButton.color().alpha()
        )

        qset.setValue("/vgrid/garsRes", int(self.garsResSpinBox.value()))
        qset.setValue("/vgrid/garsColor", self.garsColorButton.color().name())
        qset.setValue("/vgrid/garsColorOpacity", self.garsColorButton.color().alpha())

        qset.setValue("/vgrid/digipinRes", int(self.digipinResSpinBox.value()))
        qset.setValue("/vgrid/digipinColor", self.digipinColorButton.color().name())
        qset.setValue(
            "/vgrid/digipinColorOpacity", self.digipinColorButton.color().alpha()
        )

        qset.setValue("/vgrid/h3Visible", int(self.h3VisibleCheckBox.checkState()))
        qset.setValue("/vgrid/s2Visible", int(self.s2VisibleCheckBox.checkState()))
        qset.setValue("/vgrid/a5Visible", int(self.a5VisibleCheckBox.checkState()))
        qset.setValue(
            "/vgrid/rhealpixVisible", int(self.isea4tVisibleCheckBox.checkState())
        )
        qset.setValue(
            "/vgrid/isea4tVisible", int(self.isea4tVisibleCheckBox_2.checkState())
        )
        qset.setValue(
            "/vgrid/isea3hVisible", int(self.isea3hVisibleCheckBox.checkState())
        )
        qset.setValue("/vgrid/easeVisible", int(self.ease2VisibleCheckBox.checkState()))
        qset.setValue("/vgrid/qtmVisible", int(self.qtmVisibleCheckBox.checkState()))
        qset.setValue("/vgrid/olcVisible", int(self.olcVisibleCheckBox.checkState()))
        qset.setValue(
            "/vgrid/geohashVisible", int(self.geohashVisibleCheckBox.checkState())
        )
        qset.setValue(
            "/vgrid/georefVisible", int(self.georefVisibleCheckbox.checkState())
        )
        qset.setValue("/vgrid/mgrsVisible", int(self.mgrsVisibleCheckBox.checkState()))
        qset.setValue(
            "/vgrid/tilecodeVisible", int(self.tilecodeVisibleCheckBox.checkState())
        )
        qset.setValue(
            "/vgrid/quadkeyVisible", int(self.quadkeyVisibleCheckBox.checkState())
        )
        qset.setValue(
            "/vgrid/maidenheadVisible", int(self.maidenheadVisibleCheckBox.checkState())
        )
        qset.setValue("/vgrid/garsVisible", int(self.garsVisibleCheckBox.checkState()))
        qset.setValue(
            "/vgrid/digipinVisible", int(self.digipinVisibleCheckBox.checkState())
        )

        qset.setValue(
            "/vgrid/dggal_gnosisRes", int(self.dggal_gnosisResSpinBox.value())
        )
        qset.setValue(
            "/vgrid/dggal_gnosisColor", self.dggal_gnosisColorButton.color().name()
        )
        qset.setValue(
            "/vgrid/dggal_gnosisColorOpacity",
            self.dggal_gnosisColorButton.color().alpha(),
        )

        qset.setValue(
            "/vgrid/dggal_isea4rRes", int(self.dggal_isea4rResSpinBox.value())
        )
        qset.setValue(
            "/vgrid/dggal_isea4rColor", self.dggal_isea4rColorButton.color().name()
        )
        qset.setValue(
            "/vgrid/dggal_isea4rColorOpacity",
            self.dggal_isea4rColorButton.color().alpha(),
        )

        qset.setValue(
            "/vgrid/dggal_isea9rRes", int(self.dggal_isea9rResSpinBox.value())
        )
        qset.setValue(
            "/vgrid/dggal_isea9rColor", self.dggal_isea9rColorButton.color().name()
        )
        qset.setValue(
            "/vgrid/dggal_isea9rColorOpacity",
            self.dggal_isea9rColorButton.color().alpha(),
        )

        qset.setValue(
            "/vgrid/dggal_isea3hRes", int(self.dggal_isea3hResSpinBox.value())
        )
        qset.setValue(
            "/vgrid/dggal_isea3hColor", self.dggal_isea3hColorButton.color().name()
        )
        qset.setValue(
            "/vgrid/dggal_isea3hColorOpacity",
            self.dggal_isea3hColorButton.color().alpha(),
        )

        qset.setValue(
            "/vgrid/dggal_isea7hRes", int(self.dggal_isea7hResSpinBox.value())
        )
        qset.setValue(
            "/vgrid/dggal_isea7hColor", self.dggal_isea7hColorButton.color().name()
        )
        qset.setValue(
            "/vgrid/dggal_isea7hColorOpacity",
            self.dggal_isea7hColorButton.color().alpha(),
        )

        qset.setValue(
            "/vgrid/dggal_isea7h_z7Res", int(self.dggal_isea7h_z7ResSpinBox.value())
        )
        qset.setValue(
            "/vgrid/dggal_isea7h_z7Color",
            self.dggal_isea7h_z7ColorButton.color().name(),
        )
        qset.setValue(
            "/vgrid/dggal_isea7h_z7ColorOpacity",
            self.dggal_isea7h_z7ColorButton.color().alpha(),
        )

        qset.setValue(
            "/vgrid/dggal_ivea4rRes", int(self.dggal_ivea4rResSpinBox.value())
        )
        qset.setValue(
            "/vgrid/dggal_ivea4rColor", self.dggal_ivea4rColorButton.color().name()
        )
        qset.setValue(
            "/vgrid/dggal_ivea4rColorOpacity",
            self.dggal_ivea4rColorButton.color().alpha(),
        )

        qset.setValue(
            "/vgrid/dggal_ivea9rRes", int(self.dggal_ivea9rResSpinBox.value())
        )
        qset.setValue(
            "/vgrid/dggal_ivea9rColor", self.dggal_ivea9rColorButton.color().name()
        )
        qset.setValue(
            "/vgrid/dggal_ivea9rColorOpacity",
            self.dggal_ivea9rColorButton.color().alpha(),
        )

        qset.setValue(
            "/vgrid/dggal_ivea3hRes", int(self.dggal_ivea3hResSpinBox.value())
        )
        qset.setValue(
            "/vgrid/dggal_ivea3hColor", self.dggal_ivea3hColorButton.color().name()
        )
        qset.setValue(
            "/vgrid/dggal_ivea3hColorOpacity",
            self.dggal_ivea3hColorButton.color().alpha(),
        )

        qset.setValue(
            "/vgrid/dggal_ivea7hRes", int(self.dggal_ivea7hResSpinBox.value())
        )
        qset.setValue(
            "/vgrid/dggal_ivea7hColor", self.dggal_ivea7hColorButton.color().name()
        )
        qset.setValue(
            "/vgrid/dggal_ivea7hColorOpacity",
            self.dggal_ivea7hColorButton.color().alpha(),
        )

        qset.setValue(
            "/vgrid/dggal_ivea7h_z7Res", int(self.dggal_ivea7h_z7ResSpinBox.value())
        )
        qset.setValue(
            "/vgrid/dggal_ivea7h_z7Color",
            self.dggal_ivea7h_z7ColorButton.color().name(),
        )
        qset.setValue(
            "/vgrid/dggal_ivea7h_z7ColorOpacity",
            self.dggal_ivea7h_z7ColorButton.color().alpha(),
        )

        qset.setValue(
            "/vgrid/dggal_rtea4rRes", int(self.dggal_rtea4rResSpinBox.value())
        )
        qset.setValue(
            "/vgrid/dggal_rtea4rColor", self.dggal_rtea4rColorButton.color().name()
        )
        qset.setValue(
            "/vgrid/dggal_rtea4rColorOpacity",
            self.dggal_rtea4rColorButton.color().alpha(),
        )

        qset.setValue(
            "/vgrid/dggal_rtea9rRes", int(self.dggal_rtea9rResSpinBox.value())
        )
        qset.setValue(
            "/vgrid/dggal_rtea9rColor", self.dggal_rtea9rColorButton.color().name()
        )
        qset.setValue(
            "/vgrid/dggal_rtea9rColorOpacity",
            self.dggal_rtea9rColorButton.color().alpha(),
        )

        qset.setValue(
            "/vgrid/dggal_rtea3hRes", int(self.dggal_rtea3hResSpinBox.value())
        )
        qset.setValue(
            "/vgrid/dggal_rtea3hColor", self.dggal_rtea3hColorButton.color().name()
        )
        qset.setValue(
            "/vgrid/dggal_rtea3hColorOpacity",
            self.dggal_rtea3hColorButton.color().alpha(),
        )

        qset.setValue(
            "/vgrid/dggal_rtea7hRes", int(self.dggal_rtea7hResSpinBox.value())
        )
        qset.setValue(
            "/vgrid/dggal_rtea7hColor", self.dggal_rtea7hColorButton.color().name()
        )
        qset.setValue(
            "/vgrid/dggal_rtea7hColorOpacity",
            self.dggal_rtea7hColorButton.color().alpha(),
        )

        qset.setValue(
            "/vgrid/dggal_rtea7h_z7Res", int(self.dggal_rtea7h_z7ResSpinBox.value())
        )

        qset.setValue(
            "/vgrid/dggal_rtea7h_z7Color",
            self.dggal_rtea7h_z7ColorButton.color().name(),
        )
        qset.setValue(
            "/vgrid/dggal_rtea7h_z7ColorOpacity",
            self.dggal_rtea7h_z7ColorButton.color().alpha(),
        )

        qset.setValue(
            "/vgrid/dggal_healpixRes", int(self.dggal_healpixResSpinBox.value())
        )
        qset.setValue(
            "/vgrid/dggal_healpixColor", self.dggal_healpixColorButton.color().name()
        )
        qset.setValue(
            "/vgrid/dggal_healpixColorOpacity",
            self.dggal_healpixColorButton.color().alpha(),
        )

        qset.setValue(
            "/vgrid/dggal_rhealpixRes", int(self.dggal_rhealpixResSpinBox.value())
        )
        qset.setValue(
            "/vgrid/dggal_rhealpixColor", self.dggal_rhealpixColorButton.color().name()
        )
        qset.setValue(
            "/vgrid/dggal_rhealpixColorOpacity",
            self.dggal_rhealpixColorButton.color().alpha(),
        )

        qset.setValue(
            "/vgrid/dggal_gnosisVisible",
            int(self.dggal_gnosisVisibleCheckBox.checkState()),
        )
        qset.setValue(
            "/vgrid/dggal_isea4rVisible",
            int(self.dggal_isea4rVisibleCheckBox.checkState()),
        )
        qset.setValue(
            "/vgrid/dggal_isea9rVisible",
            int(self.dggal_isea9rVisibleCheckBox.checkState()),
        )
        qset.setValue(
            "/vgrid/dggal_isea3hVisible",
            int(self.dggal_isea3hVisibleCheckBox.checkState()),
        )
        qset.setValue(
            "/vgrid/dggal_isea7hVisible",
            int(self.dggal_isea7hVisibleCheckBox.checkState()),
        )
        qset.setValue(
            "/vgrid/dggal_isea7h_z7Visible",
            int(self.dggal_isea3h_z7VisibleCheckBox.checkState()),
        )
        qset.setValue(
            "/vgrid/dggal_ivea4rVisible",
            int(self.dggal_ivea4rVisibleCheckBox.checkState()),
        )
        qset.setValue(
            "/vgrid/dggal_ivea9rVisible",
            int(self.dggal_ivea9rVisibleCheckBox.checkState()),
        )
        qset.setValue(
            "/vgrid/dggal_ivea3hVisible",
            int(self.dggal_ivea3hVisibleCheckBox.checkState()),
        )
        qset.setValue(
            "/vgrid/dggal_ivea7hVisible",
            int(self.dggal_ivea7hVisibleCheckBox.checkState()),
        )
        qset.setValue(
            "/vgrid/dggal_ivea7h_z7Visible",
            int(self.dggal_ivea7h_z7VisibleCheckBox.checkState()),
        )
        qset.setValue(
            "/vgrid/dggal_rtea4rVisible",
            int(self.dggal_rtea4rVisibleCheckBox.checkState()),
        )
        qset.setValue(
            "/vgrid/dggal_rtea9rVisible",
            int(self.dggal_rtea9rVisibleCheckBox.checkState()),
        )
        qset.setValue(
            "/vgrid/dggal_rtea3hVisible",
            int(self.dggal_rtea3hVisibleCheckBox.checkState()),
        )
        qset.setValue(
            "/vgrid/dggal_rtea7hVisible", int(self.dggal_rtea7hCheckBox.checkState())
        )
        qset.setValue(
            "/vgrid/dggal_rtea7h_z7Visible",
            int(self.dggal_rtea7h_z7VisibleCheckBox.checkState()),
        )
        qset.setValue(
            "/vgrid/dggal_healpixVisible",
            int(self.dggal_healpixVisibleCheckBox.checkState()),
        )
        qset.setValue(
            "/vgrid/dggal_rhealpixVisible",
            int(self.dggal_rhealpixVisibleCheckBox.checkState()),
        )

        ### DGGRID Settings ###
        qset.setValue(
            "/vgrid/dggrid_superfundRes", int(self.dggrid_superfundResSpinBox.value())
        )
        qset.setValue(
            "/vgrid/dggrid_superfundColor",
            self.dggrid_superfundColorButton.color().name(),
        )
        qset.setValue(
            "/vgrid/dggrid_superfundColorOpacity",
            self.dggrid_superfundColorButton.color().alpha(),
        )

        qset.setValue(
            "/vgrid/dggrid_planetriskRes", int(self.dggrid_planetriskResSpinBox.value())
        )
        qset.setValue(
            "/vgrid/dggrid_planetriskColor",
            self.dggrid_planetriskColorButton.color().name(),
        )
        qset.setValue(
            "/vgrid/dggrid_planetriskColorOpacity",
            self.dggrid_planetriskColorButton.color().alpha(),
        )

        qset.setValue(
            "/vgrid/dggrid_isea3hRes", int(self.dggrid_isea3hResSpinBox.value())
        )
        qset.setValue(
            "/vgrid/dggrid_isea3hColor", self.dggrid_isea3hColorButton.color().name()
        )
        qset.setValue(
            "/vgrid/dggrid_isea3hColorOpacity",
            self.dggrid_isea3hColorButton.color().alpha(),
        )

        qset.setValue(
            "/vgrid/dggrid_isea4hRes", int(self.dggrid_isea4hResSpinBox.value())
        )
        qset.setValue(
            "/vgrid/dggrid_isea4hColor", self.dggrid_isea4hColorButton.color().name()
        )
        qset.setValue(
            "/vgrid/dggrid_isea4hColorOpacity",
            self.dggrid_isea4hColorButton.color().alpha(),
        )

        qset.setValue(
            "/vgrid/dggrid_isea4tRes", int(self.dggrid_isea4tResSpinBox.value())
        )
        qset.setValue(
            "/vgrid/dggrid_isea4tColor", self.dggrid_isea4tColorButton.color().name()
        )
        qset.setValue(
            "/vgrid/dggrid_isea4tColorOpacity",
            self.dggrid_isea4tColorButton.color().alpha(),
        )

        qset.setValue(
            "/vgrid/dggrid_isea43hRes", int(self.dggrid_isea43hResSpinBox.value())
        )
        qset.setValue(
            "/vgrid/dggrid_isea43hColor", self.dggrid_isea43hColorButton.color().name()
        )
        qset.setValue(
            "/vgrid/dggrid_isea43hColorOpacity",
            self.dggrid_isea43hColorButton.color().alpha(),
        )

        qset.setValue(
            "/vgrid/dggrid_isea7hRes", int(self.dggrid_isea7hResSpinBox.value())
        )
        qset.setValue(
            "/vgrid/dggrid_isea7hColor", self.dggrid_isea7hColorButton.color().name()
        )
        qset.setValue(
            "/vgrid/dggrid_isea7hColorOpacity",
            self.dggrid_isea7hColorButton.color().alpha(),
        )

        qset.setValue(
            "/vgrid/dggrid_igeo7Res", int(self.dggrid_igeo7ResSpinBox.value())
        )
        qset.setValue(
            "/vgrid/dggrid_igeo7Color", self.dggrid_igeo7ColorButton.color().name()
        )
        qset.setValue(
            "/vgrid/dggrid_igeo7ColorOpacity",
            self.dggrid_igeo7ColorButton.color().alpha(),
        )

        qset.setValue(
            "/vgrid/dggrid_fuller3hRes", int(self.dggrid_fuller3hResSpinBox.value())
        )
        qset.setValue(
            "/vgrid/dggrid_fuller3hColor",
            self.dggrid_fuller3hColorButton.color().name(),
        )
        qset.setValue(
            "/vgrid/dggrid_fuller3hColorOpacity",
            self.dggrid_fuller3hColorButton.color().alpha(),
        )

        qset.setValue(
            "/vgrid/dggrid_fuller4hRes", int(self.dggrid_fuller4hResSpinBox.value())
        )
        qset.setValue(
            "/vgrid/dggrid_fuller4hColor",
            self.dggrid_fuller4hColorButton.color().name(),
        )
        qset.setValue(
            "/vgrid/dggrid_fuller4hColorOpacity",
            self.dggrid_fuller4hColorButton.color().alpha(),
        )

        qset.setValue(
            "/vgrid/dggrid_fuller4tRes", int(self.dggrid_fuller4tResSpinBox.value())
        )
        qset.setValue(
            "/vgrid/dggrid_fuller4tColor",
            self.dggrid_fuller4tColorButton.color().name(),
        )
        qset.setValue(
            "/vgrid/dggrid_fuller4tColorOpacity",
            self.dggrid_fuller4tColorButton.color().alpha(),
        )

        qset.setValue(
            "/vgrid/dggrid_fuller4dRes", int(self.dggrid_fuller4dResSpinBox.value())
        )
        qset.setValue(
            "/vgrid/dggrid_fuller4dColor",
            self.dggrid_fuller4dColorButton.color().name(),
        )
        qset.setValue(
            "/vgrid/dggrid_fuller4dColorOpacity",
            self.dggrid_fuller4dColorButton.color().alpha(),
        )

        qset.setValue(
            "/vgrid/dggrid_fuller43hRes", int(self.dggrid_fuller43hResSpinBox.value())
        )
        qset.setValue(
            "/vgrid/dggrid_fuller43hColor",
            self.dggrid_fuller43hColorButton.color().name(),
        )
        qset.setValue(
            "/vgrid/dggrid_fuller43hColorOpacity",
            self.dggrid_fuller43hColorButton.color().alpha(),
        )

        qset.setValue(
            "/vgrid/dggrid_fuller7hRes", int(self.dggrid_fuller7hResSpinBox.value())
        )
        qset.setValue(
            "/vgrid/dggrid_fuller7hColor",
            self.dggrid_fuller7hColorButton.color().name(),
        )
        qset.setValue(
            "/vgrid/dggrid_fuller7hColorOpacity",
            self.dggrid_fuller7hColorButton.color().alpha(),
        )

        qset.setValue(
            "/vgrid/dggrid_superfundVisible",
            int(self.dggrid_superfundVisibleCheckBox.checkState()),
        )
        qset.setValue(
            "/vgrid/dggrid_planetriskVisible",
            int(self.dggrid_planetVisibleCheckBox.checkState()),
        )
        qset.setValue(
            "/vgrid/dggrid_isea3hVisible",
            int(self.dggrid_isea3hVisibleCheckBox.checkState()),
        )
        qset.setValue(
            "/vgrid/dggrid_isea4hVisible",
            int(self.dggrid_isea4hVisibleCheckBox.checkState()),
        )
        qset.setValue(
            "/vgrid/dggrid_isea4tVisible",
            int(self.dggrid_isea4tVisibleCheckBox.checkState()),
        )
        qset.setValue(
            "/vgrid/dggrid_isea4dVisible",
            int(self.dggrid_isea4dVisibleCheckBox.checkState()),
        )
        qset.setValue(
            "/vgrid/dggrid_isea43hVisible",
            int(self.dggrid_isea43hVisibleCheckBox.checkState()),
        )
        qset.setValue(
            "/vgrid/dggrid_isea7hVisible",
            int(self.dggrid_isea7hVisibleCheckBox.checkState()),
        )
        qset.setValue(
            "/vgrid/dggrid_igeo7Visible",
            int(self.dggrid_igeo7VisibleCheckBox.checkState()),
        )
        qset.setValue(
            "/vgrid/dggrid_fuller3hVisible",
            int(self.dggrid_fuller3hVisibleCheckBox.checkState()),
        )
        qset.setValue(
            "/vgrid/dggrid_fuller4hVisible",
            int(self.dggrid_fuller4hVisibleCheckBox.checkState()),
        )
        qset.setValue(
            "/vgrid/dggrid_fuller4tVisible",
            int(self.dggrid_fuller4tVisibleCheckBox.checkState()),
        )
        qset.setValue(
            "/vgrid/dggrid_fuller4dVisible",
            int(self.dggrid_fuller4dVisibleCheckBox.checkState()),
        )
        qset.setValue(
            "/vgrid/dggrid_fuller43hVisible",
            int(self.dggrid_fuller43hVisibleCheckBox.checkState()),
        )
        qset.setValue(
            "/vgrid/dggrid_fuller7hVisible",
            int(self.dggrid_fuller7hVisibleCheckBox.checkState()),
        )

        # The values have been read from the widgets and saved to the registry.
        # Now we will read them back to the variables.
        self.readSettings()
        self.vgridtools.settingsChanged()
        self.close()

    def showTab(self, tab):
        self.tabWidget.setCurrentIndex(tab)
        self.show()

    def showEvent(self, e):
        """The user has selected the settings dialog box so we need to
        read the settings and update the dialog box with the previously
        selected settings."""
        self.readSettings()

        ### General Settings ###
        self.zoomLevelCheckBox.setCheckState(Qt.CheckState(settings.zoomLevel))
        self.gridLabelCheckBox.setCheckState(Qt.CheckState(settings.gridLabel))
        self.persistentMarkerCheckBox.setCheckState(
            Qt.CheckState(settings.persistentMarker)
        )
        self.splitAntimeridianCheckBox.setCheckState(
            Qt.CheckState(settings.splitAntimeridian)
        )
        self.coordOrderComboBox.setCurrentIndex(settings.coordOrder)
        self.epsg4326PrecisionSpinBox.setValue(settings.epsg4326Precision)

        self.markerColorButton.setColor(settings.markerColor)
        self.markerSizeSpinBox.setValue(settings.markerSize)
        self.markerWidthSpinBox.setValue(settings.markerWidth)
        self.gridWidthSpinBox.setValue(settings.gridWidth)
        self.A5SgementsSpinBox.setValue(settings.A5SgementsSpinBox)
        self.dggridDensificationSpinBox.setValue(settings.dggridDensificationSpinBox)

        ### Other DGGS Settings ###
        self.h3ResSpinBox.setValue(settings.h3Res)
        self.h3ColorButton.setColor(settings.h3Color)
        self.h3VisibleCheckBox.setCheckState(Qt.CheckState(settings.h3Visible))

        self.s2ResSpinBox.setValue(settings.s2Res)
        self.s2ColorButton.setColor(settings.s2Color)
        self.s2VisibleCheckBox.setCheckState(Qt.CheckState(settings.s2Visible))

        self.a5ResSpinBox.setValue(settings.a5Res)
        self.a5ColorButton.setColor(settings.a5Color)
        self.a5VisibleCheckBox.setCheckState(Qt.CheckState(settings.a5Visible))

        self.rhealpixResSpinBox.setValue(settings.rhealpixRes)
        self.rhealpixColorButton.setColor(settings.rhealpixColor)
        self.isea4tVisibleCheckBox.setCheckState(
            Qt.CheckState(settings.rhealpixVisible)
        )

        self.isea4tResSpinBox.setValue(settings.isea4tRes)
        self.isea4tColorButton.setColor(settings.isea4tColor)
        self.isea4tVisibleCheckBox_2.setCheckState(
            Qt.CheckState(settings.isea4tVisible)
        )

        self.isea3hResSpinBox.setValue(settings.isea3hRes)
        self.isea3hColorButton.setColor(settings.isea3hColor)
        self.isea3hVisibleCheckBox.setCheckState(Qt.CheckState(settings.isea3hVisible))

        self.easeResSpinBox.setValue(settings.easeRes)
        self.easeColorButton.setColor(settings.easeColor)
        self.ease2VisibleCheckBox.setCheckState(Qt.CheckState(settings.easeVisible))

        self.qtmResSpinBox.setValue(settings.qtmRes)
        self.qtmColorButton.setColor(settings.qtmColor)
        self.qtmVisibleCheckBox.setCheckState(Qt.CheckState(settings.qtmVisible))

        self.olcResSpinBox.setValue(settings.olcRes)
        self.olcColorButton.setColor(settings.olcColor)
        self.olcVisibleCheckBox.setCheckState(Qt.CheckState(settings.olcVisible))

        self.geohashResSpinBox.setValue(settings.geohashRes)
        self.geohashColorButton.setColor(settings.geohashColor)
        self.geohashVisibleCheckBox.setCheckState(
            Qt.CheckState(settings.geohashVisible)
        )

        self.georefResSpinBox.setValue(settings.georefRes)
        self.georefColorButton.setColor(settings.georefColor)
        self.georefVisibleCheckbox.setCheckState(Qt.CheckState(settings.georefVisible))

        self.mgrsResSpinBox.setValue(settings.mgrsRes)
        self.mgrsColorButton.setColor(settings.mgrsColor)
        self.mgrsVisibleCheckBox.setCheckState(Qt.CheckState(settings.mgrsVisible))

        self.tilecodeResSpinBox.setValue(settings.tilecodeRes)
        self.tilecodeColorButton.setColor(settings.tilecodeColor)
        self.tilecodeVisibleCheckBox.setCheckState(
            Qt.CheckState(settings.tilecodeVisible)
        )

        self.quadkeyResSpinBox.setValue(settings.quadkeyRes)
        self.quadkeyColorButton.setColor(settings.quadkeyColor)
        self.quadkeyVisibleCheckBox.setCheckState(
            Qt.CheckState(settings.quadkeyVisible)
        )

        self.maidenheadResSpinBox.setValue(settings.maidenheadRes)
        self.maidenheadColorButton.setColor(settings.maidenheadColor)
        self.maidenheadVisibleCheckBox.setCheckState(
            Qt.CheckState(settings.maidenheadVisible)
        )

        self.garsResSpinBox.setValue(settings.garsRes)
        self.garsColorButton.setColor(settings.garsColor)
        self.garsVisibleCheckBox.setCheckState(Qt.CheckState(settings.garsVisible))

        self.digipinResSpinBox.setValue(settings.digipinRes)
        self.digipinColorButton.setColor(settings.digipinColor)
        self.digipinVisibleCheckBox.setCheckState(
            Qt.CheckState(settings.digipinVisible)
        )

        ### DGGAL Settings ###
        self.dggal_gnosisResSpinBox.setValue(settings.dggal_gnosisRes)
        self.dggal_gnosisColorButton.setColor(settings.dggal_gnosisColor)
        self.dggal_gnosisVisibleCheckBox.setCheckState(
            Qt.CheckState(settings.dggal_gnosisVisible)
        )

        self.dggal_isea4rResSpinBox.setValue(settings.dggal_isea4rRes)
        self.dggal_isea4rColorButton.setColor(settings.dggal_isea4rColor)
        self.dggal_isea4rVisibleCheckBox.setCheckState(
            Qt.CheckState(settings.dggal_isea4rVisible)
        )
        self.dggal_isea9rResSpinBox.setValue(settings.dggal_isea9rRes)
        self.dggal_isea9rColorButton.setColor(settings.dggal_isea9rColor)
        self.dggal_isea9rVisibleCheckBox.setCheckState(
            Qt.CheckState(settings.dggal_isea9rVisible)
        )

        self.dggal_isea3hResSpinBox.setValue(settings.dggal_isea3hRes)
        self.dggal_isea3hColorButton.setColor(settings.dggal_isea3hColor)
        self.dggal_isea3hVisibleCheckBox.setCheckState(
            Qt.CheckState(settings.dggal_isea3hVisible)
        )
        self.dggal_isea7hResSpinBox.setValue(settings.dggal_isea7hRes)
        self.dggal_isea7hColorButton.setColor(settings.dggal_isea7hColor)
        self.dggal_isea7hVisibleCheckBox.setCheckState(
            Qt.CheckState(settings.dggal_isea7hVisible)
        )
        self.dggal_isea7h_z7ResSpinBox.setValue(settings.dggal_isea7h_z7Res)
        self.dggal_isea7h_z7ColorButton.setColor(settings.dggal_isea7h_z7Color)
        self.dggal_isea3h_z7VisibleCheckBox.setCheckState(
            Qt.CheckState(settings.dggal_isea7h_z7Visible)
        )

        self.dggal_ivea4rResSpinBox.setValue(settings.dggal_ivea4rRes)
        self.dggal_ivea4rColorButton.setColor(settings.dggal_ivea4rColor)
        self.dggal_ivea4rVisibleCheckBox.setCheckState(
            Qt.CheckState(settings.dggal_ivea4rVisible)
        )
        self.dggal_ivea9rResSpinBox.setValue(settings.dggal_ivea9rRes)
        self.dggal_ivea9rColorButton.setColor(settings.dggal_ivea9rColor)
        self.dggal_ivea9rVisibleCheckBox.setCheckState(
            Qt.CheckState(settings.dggal_ivea9rVisible)
        )

        self.dggal_ivea3hResSpinBox.setValue(settings.dggal_ivea3hRes)
        self.dggal_ivea3hColorButton.setColor(settings.dggal_ivea3hColor)
        self.dggal_ivea3hVisibleCheckBox.setCheckState(
            Qt.CheckState(settings.dggal_ivea3hVisible)
        )
        self.dggal_ivea7hResSpinBox.setValue(settings.dggal_ivea7hRes)
        self.dggal_ivea7hColorButton.setColor(settings.dggal_ivea7hColor)
        self.dggal_ivea7hVisibleCheckBox.setCheckState(
            Qt.CheckState(settings.dggal_ivea7hVisible)
        )
        self.dggal_ivea7h_z7ResSpinBox.setValue(settings.dggal_ivea7h_z7Res)
        self.dggal_ivea7h_z7ColorButton.setColor(settings.dggal_ivea7h_z7Color)
        self.dggal_ivea7h_z7VisibleCheckBox.setCheckState(
            Qt.CheckState(settings.dggal_ivea7h_z7Visible)
        )

        self.dggal_rtea4rResSpinBox.setValue(settings.dggal_rtea4rRes)
        self.dggal_rtea4rColorButton.setColor(settings.dggal_rtea4rColor)
        self.dggal_rtea4rVisibleCheckBox.setCheckState(
            Qt.CheckState(settings.dggal_rtea4rVisible)
        )
        self.dggal_rtea9rResSpinBox.setValue(settings.dggal_rtea9rRes)
        self.dggal_rtea9rColorButton.setColor(settings.dggal_rtea9rColor)
        self.dggal_rtea9rVisibleCheckBox.setCheckState(
            Qt.CheckState(settings.dggal_rtea9rVisible)
        )

        self.dggal_rtea3hResSpinBox.setValue(settings.dggal_rtea3hRes)
        self.dggal_rtea3hColorButton.setColor(settings.dggal_rtea3hColor)
        self.dggal_rtea3hVisibleCheckBox.setCheckState(
            Qt.CheckState(settings.dggal_rtea3hVisible)
        )
        self.dggal_rtea7hResSpinBox.setValue(settings.dggal_rtea7hRes)
        self.dggal_rtea7hColorButton.setColor(settings.dggal_rtea7hColor)
        self.dggal_rtea7hCheckBox.setCheckState(
            Qt.CheckState(settings.dggal_rtea7hVisible)
        )
        self.dggal_rtea7h_z7ResSpinBox.setValue(settings.dggal_rtea7h_z7Res)
        self.dggal_rtea7h_z7ColorButton.setColor(settings.dggal_rtea7h_z7Color)
        self.dggal_rtea7h_z7VisibleCheckBox.setCheckState(
            Qt.CheckState(settings.dggal_rtea7h_z7Visible)
        )

        self.dggal_healpixResSpinBox.setValue(settings.dggal_healpixRes)
        self.dggal_healpixColorButton.setColor(settings.dggal_healpixColor)
        self.dggal_healpixVisibleCheckBox.setCheckState(
            Qt.CheckState(settings.dggal_healpixVisible)
        )
        self.dggal_rhealpixResSpinBox.setValue(settings.dggal_rhealpixRes)
        self.dggal_rhealpixColorButton.setColor(settings.dggal_rhealpixColor)
        self.dggal_rhealpixVisibleCheckBox.setCheckState(
            Qt.CheckState(settings.dggal_rhealpixVisible)
        )

        ### DGGRID Settings ###
        self.dggrid_superfundResSpinBox.setValue(settings.dggrid_superfundRes)
        self.dggrid_superfundColorButton.setColor(settings.dggrid_superfundColor)
        self.dggrid_superfundVisibleCheckBox.setCheckState(
            Qt.CheckState(settings.dggrid_superfundVisible)
        )

        self.dggrid_planetriskResSpinBox.setValue(settings.dggrid_planetriskRes)
        self.dggrid_planetriskColorButton.setColor(settings.dggrid_planetriskColor)
        self.dggrid_planetVisibleCheckBox.setCheckState(
            Qt.CheckState(settings.dggrid_planetriskVisible)
        )

        self.dggrid_isea3hResSpinBox.setValue(settings.dggrid_isea3hRes)
        self.dggrid_isea3hColorButton.setColor(settings.dggrid_isea3hColor)
        self.dggrid_isea3hVisibleCheckBox.setCheckState(
            Qt.CheckState(settings.dggrid_isea3hVisible)
        )

        self.dggrid_isea4hResSpinBox.setValue(settings.dggrid_isea4hRes)
        self.dggrid_isea4hColorButton.setColor(settings.dggrid_isea4hColor)
        self.dggrid_isea4hVisibleCheckBox.setCheckState(
            Qt.CheckState(settings.dggrid_isea4hVisible)
        )

        self.dggrid_isea4tResSpinBox.setValue(settings.dggrid_isea4tRes)
        self.dggrid_isea4tColorButton.setColor(settings.dggrid_isea4tColor)
        self.dggrid_isea4tVisibleCheckBox.setCheckState(
            Qt.CheckState(settings.dggrid_isea4tVisible)
        )

        self.dggrid_isea4dResSpinBox.setValue(settings.dggrid_isea4dRes)
        self.dggrid_isea4dColorButton.setColor(settings.dggrid_isea4dColor)
        self.dggrid_isea4dVisibleCheckBox.setCheckState(
            Qt.CheckState(settings.dggrid_isea4dVisible)
        )

        self.dggrid_isea43hResSpinBox.setValue(settings.dggrid_isea43hRes)
        self.dggrid_isea43hColorButton.setColor(settings.dggrid_isea43hColor)
        self.dggrid_isea43hVisibleCheckBox.setCheckState(
            Qt.CheckState(settings.dggrid_isea43hVisible)
        )

        self.dggrid_isea7hResSpinBox.setValue(settings.dggrid_isea7hRes)
        self.dggrid_isea7hColorButton.setColor(settings.dggrid_isea7hColor)
        self.dggrid_isea7hVisibleCheckBox.setCheckState(
            Qt.CheckState(settings.dggrid_isea7hVisible)
        )

        self.dggrid_igeo7ResSpinBox.setValue(settings.dggrid_igeo7Res)
        self.dggrid_igeo7ColorButton.setColor(settings.dggrid_igeo7Color)
        self.dggrid_igeo7VisibleCheckBox.setCheckState(
            Qt.CheckState(settings.dggrid_igeo7Visible)
        )

        self.dggrid_fuller3hResSpinBox.setValue(settings.dggrid_fuller3hRes)
        self.dggrid_fuller3hColorButton.setColor(settings.dggrid_fuller3hColor)
        self.dggrid_fuller3hVisibleCheckBox.setCheckState(
            Qt.CheckState(settings.dggrid_fuller3hVisible)
        )

        self.dggrid_fuller4hResSpinBox.setValue(settings.dggrid_fuller4hRes)
        self.dggrid_fuller4hColorButton.setColor(settings.dggrid_fuller4hColor)
        self.dggrid_fuller4hVisibleCheckBox.setCheckState(
            Qt.CheckState(settings.dggrid_fuller4hVisible)
        )

        self.dggrid_fuller4tResSpinBox.setValue(settings.dggrid_fuller4tRes)
        self.dggrid_fuller4tColorButton.setColor(settings.dggrid_fuller4tColor)
        self.dggrid_fuller4tVisibleCheckBox.setCheckState(
            Qt.CheckState(settings.dggrid_fuller4tVisible)
        )

        self.dggrid_fuller4dResSpinBox.setValue(settings.dggrid_fuller4dRes)
        self.dggrid_fuller4dColorButton.setColor(settings.dggrid_fuller4dColor)
        self.dggrid_fuller4dVisibleCheckBox.setCheckState(
            Qt.CheckState(settings.dggrid_fuller4dVisible)
        )

        self.dggrid_fuller43hResSpinBox.setValue(settings.dggrid_fuller43hRes)
        self.dggrid_fuller43hColorButton.setColor(settings.dggrid_fuller43hColor)
        self.dggrid_fuller43hVisibleCheckBox.setCheckState(
            Qt.CheckState(settings.dggrid_fuller43hVisible)
        )

        self.dggrid_fuller7hResSpinBox.setValue(settings.dggrid_fuller7hRes)
        self.dggrid_fuller7hColorButton.setColor(settings.dggrid_fuller7hColor)
        self.dggrid_fuller7hVisibleCheckBox.setCheckState(
            Qt.CheckState(settings.dggrid_fuller7hVisible)
        )
