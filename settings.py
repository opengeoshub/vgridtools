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
from qgis.PyQt.QtWidgets import QDialog, QDialogButtonBox
from qgis.core import QgsSettings
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtCore import Qt
from .utils import tr

FORM_CLASS, _ = loadUiType(os.path.join(os.path.dirname(__file__), "ui/settings.ui"))


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

        ### DGGS Settings ###
        self.h3Res = int(qset.value("/vgrid/h3Res", 10))
        self.h3Color = QColor(qset.value("/vgrid/h3Color", "#1e54b7"))
        self.h3Color.setAlpha(int(qset.value("/vgrid/h3ColorOpacity", 255)))

        self.s2Res = int(qset.value("/vgrid/s2Res", 16))
        self.s2Color = QColor(qset.value("/vgrid/s2Color", "#de6b00"))
        self.s2Color.setAlpha(int(qset.value("/vgrid/s2ColorOpacity", 255)))

        self.a5Res = int(qset.value("/vgrid/a5Res", 15))
        self.a5Color = QColor(qset.value("/vgrid/a5Color", "#00aa55"))
        self.a5Color.setAlpha(int(qset.value("/vgrid/a5ColorOpacity", 255)))

        self.rhealpixRes = int(qset.value("/vgrid/rhealpixRes", 10))
        self.rhealpixColor = QColor(qset.value("/vgrid/rhealpixColor", "#7b0bff"))
        self.rhealpixColor.setAlpha(int(qset.value("/vgrid/rhealpixColorOpacity", 255)))

        self.isea4tRes = int(qset.value("/vgrid/isea4tRes", 16))
        self.isea4tColor = QColor(qset.value("/vgrid/isea4tColor", "#159bc1"))
        self.isea4tColor.setAlpha(int(qset.value("/vgrid/isea4tColorOpacity", 255)))

        self.isea3hRes = int(qset.value("/vgrid/isea3hRes", 20))
        self.isea3hColor = QColor(qset.value("/vgrid/isea3hColor", "#159bc1"))
        self.isea3hColor.setAlpha(int(qset.value("/vgrid/isea3hColorOpacity", 255)))

        self.easeRes = int(qset.value("/vgrid/easeRes", 4))
        self.easeColor = QColor(qset.value("/vgrid/easeColor", "#7a0019"))
        self.easeColor.setAlpha(int(qset.value("/vgrid/easeColorOpacity", 255)))

        self.dggal_gnosisRes = int(qset.value("/vgrid/dggal_gnosisRes", 16))
        self.dggal_gnosisColor = QColor(
            qset.value("/vgrid/dggal_gnosisColor", "#00008B")
        )
        self.dggal_gnosisColor.setAlpha(
            int(qset.value("/vgrid/dggal_gnosisColorOpacity", 255))
        )

        self.dggal_isea4rRes = int(qset.value("/vgrid/dggal_isea4rRes", 12))
        self.dggal_isea4rColor = QColor(
            qset.value("/vgrid/dggal_isea4rColor", "#00008B")
        )
        self.dggal_isea4rColor.setAlpha(
            int(qset.value("/vgrid/dggal_isea4rColorOpacity", 255))
        )

        self.dggal_isea9rRes = int(qset.value("/vgrid/dggal_isea9rRes", 10))
        self.dggal_isea9rColor = QColor(
            qset.value("/vgrid/dggal_isea9rColor", "#00008B")
        )
        self.dggal_isea9rColor.setAlpha(
            int(qset.value("/vgrid/dggal_isea9rColorOpacity", 255))
        )

        self.dggal_isea3hRes = int(qset.value("/vgrid/dggal_isea3hRes", 21))
        self.dggal_isea3hColor = QColor(
            qset.value("/vgrid/dggal_isea3hColor", "#00008B")
        )
        self.dggal_isea3hColor.setAlpha(
            int(qset.value("/vgrid/dggal_isea3hColorOpacity", 255))
        )

        self.dggal_isea7hRes = int(qset.value("/vgrid/dggal_isea7hRes", 12))
        self.dggal_isea7hColor = QColor(
            qset.value("/vgrid/dggal_isea7hColor", "#00008B")
        )
        self.dggal_isea7hColor.setAlpha(
            int(qset.value("/vgrid/dggal_isea7hColorOpacity", 255))
        )

        self.dggal_isea7h_z7Res = int(qset.value("/vgrid/dggal_isea7h_z7Res", 12))
        self.dggal_isea7h_z7Color = QColor(
            qset.value("/vgrid/dggal_isea7h_z7Color", "#00008B")
        )
        self.dggal_isea7h_z7Color.setAlpha(
            int(qset.value("/vgrid/dggal_isea7h_z7ColorOpacity", 255))
        )


        self.dggal_ivea4rRes = int(qset.value("/vgrid/dggal_ivea4rRes", 15))
        self.dggal_ivea4rColor = QColor(
            qset.value("/vgrid/dggal_ivea4rColor", "#00008B")
        )
        self.dggal_ivea4rColor.setAlpha(
            int(qset.value("/vgrid/dggal_ivea4rColorOpacity", 255))
        )
        self.dggal_ivea9rRes = int(qset.value("/vgrid/dggal_ivea9rRes", 10))
        self.dggal_ivea9rColor = QColor(
            qset.value("/vgrid/dggal_ivea9rColor", "#00008B")
        )
        self.dggal_ivea9rColor.setAlpha(
            int(qset.value("/vgrid/dggal_ivea9rColorOpacity", 255))
        )


        self.dggal_ivea3hRes = int(qset.value("/vgrid/dggal_ivea3hRes", 21))
        self.dggal_ivea3hColor = QColor(
            qset.value("/vgrid/dggal_ivea3hColor", "#00008B")
        )
        self.dggal_ivea3hColor.setAlpha(
            int(qset.value("/vgrid/dggal_ivea3hColorOpacity", 255))
        )

        self.dggal_ivea7hRes = int(qset.value("/vgrid/dggal_ivea7hRes", 12))
        self.dggal_ivea7hColor = QColor(
            qset.value("/vgrid/dggal_ivea7hColor", "#00008B")
        )
        self.dggal_ivea7hColor.setAlpha(
            int(qset.value("/vgrid/dggal_ivea7hColorOpacity", 255))
        )

        self.dggal_ivea7h_z7Res = int(qset.value("/vgrid/dggal_ivea7h_z7Res", 12))
        self.dggal_ivea7h_z7Color = QColor(
            qset.value("/vgrid/dggal_ivea7h_z7Color", "#00008B")
        )
        self.dggal_ivea7h_z7Color.setAlpha(
            int(qset.value("/vgrid/dggal_ivea7h_z7ColorOpacity", 255))
        )


        self.dggal_rtea4rRes = int(qset.value("/vgrid/dggal_rtea4rRes", 15))
        self.dggal_rtea4rColor = QColor(
            qset.value("/vgrid/dggal_rtea4rColor", "#00008B")
        )
        self.dggal_rtea4rColor.setAlpha(
            int(qset.value("/vgrid/dggal_rtea4rColorOpacity", 255))
        )
        self.dggal_rtea9rRes = int(qset.value("/vgrid/dggal_rtea9rRes", 10))
        self.dggal_rtea9rColor = QColor(
            qset.value("/vgrid/dggal_rtea9rColor", "#00008B")
        )
        self.dggal_rtea9rColor.setAlpha(
            int(qset.value("/vgrid/dggal_rtea9rColorOpacity", 255))
        )


        self.dggal_rtea3hRes = int(qset.value("/vgrid/dggal_rtea3hRes", 21))
        self.dggal_rtea3hColor = QColor(
            qset.value("/vgrid/dggal_rtea3hColor", "#00008B")
        )
        self.dggal_rtea3hColor.setAlpha(
            int(qset.value("/vgrid/dggal_rtea3hColorOpacity", 255))
        )

        self.dggal_rtea7hRes = int(qset.value("/vgrid/dggal_rtea7hRes", 12))
        self.dggal_rtea7hColor = QColor(
            qset.value("/vgrid/dggal_rtea7hColor", "#00008B")
        )
        self.dggal_rtea7hColor.setAlpha(
            int(qset.value("/vgrid/dggal_rtea7hColorOpacity", 255))
        )

        self.dggal_rtea7h_z7Res = int(qset.value("/vgrid/dggal_rtea7h_z7Res", 12))
        self.dggal_rtea7h_z7Color = QColor(
            qset.value("/vgrid/dggal_rtea7h_z7Color", "#00008B")
        )
        self.dggal_rtea7h_z7Color.setAlpha(
            int(qset.value("/vgrid/dggal_rtea7h_z7ColorOpacity", 255))
        )

        self.dggal_healpixRes = int(qset.value("/vgrid/dggal_healpixRes", 16))
        self.dggal_healpixColor = QColor(
            qset.value("/vgrid/dggal_healpixColor", "#00008B")
        )
        self.dggal_healpixColor.setAlpha(
            int(qset.value("/vgrid/dggal_healpixColorOpacity", 255))
        )

        self.dggal_rhealpixRes = int(qset.value("/vgrid/dggal_rhealpixRes", 10))
        self.dggal_rhealpixColor = QColor(
            qset.value("/vgrid/dggal_rhealpixColor", "#00008B")
        )
        self.dggal_rhealpixColor.setAlpha(
            int(qset.value("/vgrid/dggal_rhealpixColorOpacity", 255))
        )

        self.qtmRes = int(qset.value("/vgrid/qtmRes", 18))
        self.qtmColor = QColor(qset.value("/vgrid/qtmColor", "#672a5c"))
        self.qtmColor.setAlpha(int(qset.value("/vgrid/qtmColorOpacity", 255)))

        self.olcRes = int(qset.value("/vgrid/olcRes", 8))
        self.olcColor = QColor(qset.value("/vgrid/olcColor", "#4285f4"))
        self.olcColor.setAlpha(int(qset.value("/vgrid/olcColorOpacity", 255)))

        self.geohashRes = int(qset.value("/vgrid/geohashRes", 7))
        self.geohashColor = QColor(qset.value("/vgrid/geohashColor", "#672a5c"))
        self.geohashColor.setAlpha(int(qset.value("/vgrid/geohashColorOpacity", 255)))

        self.georefRes = int(qset.value("/vgrid/georefRes", 3))
        self.georefColor = QColor(qset.value("/vgrid/georefColor", "#672a5c"))
        self.georefColor.setAlpha(int(qset.value("/vgrid/georefColorOpacity", 255)))

        self.mgrsRes = int(qset.value("/vgrid/mgrsRes", 3))
        self.mgrsColor = QColor(qset.value("/vgrid/mgrsColor", "#0052b4"))
        self.mgrsColor.setAlpha(int(qset.value("/vgrid/mgrsColorOpacity", 255)))

        self.tilecodeRes = int(qset.value("/vgrid/tilecodeRes", 18))
        self.tilecodeColor = QColor(qset.value("/vgrid/tilecodeColor", "#672a5c"))
        self.tilecodeColor.setAlpha(int(qset.value("/vgrid/tilecodeColorOpacity", 255)))

        self.quadkeyRes = int(qset.value("/vgrid/quadkeyRes", 18))
        self.quadkeyColor = QColor(qset.value("/vgrid/quadkeyColor", "#672a5c"))
        self.quadkeyColor.setAlpha(int(qset.value("/vgrid/quadkeyColorOpacity", 255)))

        self.maidenheadRes = int(qset.value("/vgrid/maidenheadRes", 4))
        self.maidenheadColor = QColor(qset.value("/vgrid/maidenheadColor", "#672a5c"))
        self.maidenheadColor.setAlpha(
            int(qset.value("/vgrid/maidenheadColorOpacity", 255))
        )

        self.garsRes = int(qset.value("/vgrid/garsRes", 4))
        self.garsColor = QColor(qset.value("/vgrid/garsColor", "#672a5c"))
        self.garsColor.setAlpha(int(qset.value("/vgrid/garsColorOpacity", 255)))

        self.digipinRes = int(qset.value("/vgrid/digipinRes", 4))
        self.digipinColor = QColor(qset.value("/vgrid/digipinColor", "#672a5c"))
        self.digipinColor.setAlpha(int(qset.value("/vgrid/digipinColorOpacity", 255)))


        ### General Settings ###
        self.zoomLevel = int(qset.value("/vgrid/zoomLevel", Qt.Checked))
        self.gridLabel = int(qset.value("/vgrid/gridLabel", Qt.Checked))
        self.persistentMarker = int(qset.value("/vgrid/persistentMarker", Qt.Checked))
        self.fixAntimeridian = int(qset.value("/vgrid/fixAntimeridian", Qt.Checked))
        self.coordOrder = int(qset.value("/vgrid/coordOrder", CoordOrder.OrderYX))
        self.epsg4326Precision = int(qset.value("/vgrid/epsg4326Precision", 8))

        self.markerColor = QColor(qset.value("/vgrid/markerColor", "#ff0000"))
        self.markerColor.setAlpha(int(qset.value("/vgrid/markerColorOpacity", 255)))
        self.markerSize = int(qset.value("/vgrid/markerSize", 18))
        self.markerWidth = int(qset.value("/vgrid/markerWidth", 2))

        self.gridWidth = int(qset.value("/vgrid/gridWidth", 2))

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
        self.buttonBox.button(QDialogButtonBox.RestoreDefaults).clicked.connect(
            self.restoreDefaults
        )
        self.readSettings()

    def restoreDefaults(self):
        """Restore all settings to their default state."""
        # Follow order and default values from readSettings

        ### DGGS Settings ###
        # H3
        self.h3ResSpinBox.setValue(10)
        self.h3ColorButton.setColor(QColor("#1e54b7"))

        # S2
        self.s2ResSpinBox.setValue(16)
        self.s2ColorButton.setColor(QColor("#de6b00"))

        # A5
        self.a5ResSpinBox.setValue(15)
        self.a5ColorButton.setColor(QColor("#00aa55"))

        # rHEALPix
        self.rhealpixResSpinBox.setValue(10)
        self.rhealpixColorButton.setColor(QColor("#7b0bff"))

        # ISEA4T
        self.isea4tResSpinBox.setValue(16)
        self.isea4tColorButton.setColor(QColor("#159bc1"))

        # ISEA3H
        self.isea3hResSpinBox.setValue(20)
        self.isea3hColorButton.setColor(QColor("#159bc1"))

        # EASE
        self.easeResSpinBox.setValue(4)
        self.easeColorButton.setColor(QColor("#7a0019"))

        # DGGAL_GNOSIS
        self.dggal_gnosisResSpinBox.setValue(16)
        self.dggal_gnosisColorButton.setColor(QColor("#00008B"))

        # DGGAL_ISEA4R
        self.dggal_isea4rResSpinBox.setValue(12)
        self.dggal_isea4rColorButton.setColor(QColor("#00008B"))

        # DGGAL_ISEA9R
        self.dggal_isea9rResSpinBox.setValue(10)
        self.dggal_isea9rColorButton.setColor(QColor("#00008B"))

        # DGGAL_ISEA3H
        self.dggal_isea3hResSpinBox.setValue(21)
        self.dggal_isea3hColorButton.setColor(QColor("#00008B"))
        # DGGAL_ISEA7H
        self.dggal_isea7hResSpinBox.setValue(11)
        self.dggal_isea7hColorButton.setColor(QColor("#00008B"))
        # DGGAL_ISEA7H_Z7
        self.dggal_isea7h_z7ResSpinBox.setValue(11)
        self.dggal_isea7h_z7ColorButton.setColor(QColor("#00008B"))


        # DGGAL_IVEA4R
        self.dggal_ivea4rResSpinBox.setValue(15)
        self.dggal_ivea4rColorButton.setColor(QColor("#00008B"))
        # DGGAL_IVEA9R
        self.dggal_ivea9rResSpinBox.setValue(10)
        self.dggal_ivea9rColorButton.setColor(QColor("#00008B"))

        # DGGAL_IVEA3H
        self.dggal_ivea3hResSpinBox.setValue(21)
        self.dggal_ivea3hColorButton.setColor(QColor("#00008B"))
       
        # DGGAL_IVEA7H
        self.dggal_ivea7hResSpinBox.setValue(11)
        self.dggal_ivea7hColorButton.setColor(QColor("#00008B"))
        # DGGAL_IVEA7H_Z7
        self.dggal_ivea7h_z7ResSpinBox.setValue(11)
        self.dggal_ivea7h_z7ColorButton.setColor(QColor("#00008B"))

        # DGGAL_RTEA4R
        self.dggal_rtea4rResSpinBox.setValue(12)
        self.dggal_rtea4rColorButton.setColor(QColor("#00008B"))

        # DGGAL_RTEA9R
        self.dggal_rtea9rResSpinBox.setValue(10)
        self.dggal_rtea9rColorButton.setColor(QColor("#00008B"))

        # DGGAL_RTEA3H
        self.dggal_rtea3hResSpinBox.setValue(21)
        self.dggal_rtea3hColorButton.setColor(QColor("#00008B"))

       # DGGAL_RTEA7H
        self.dggal_rtea7hResSpinBox.setValue(11)
        self.dggal_rtea7hColorButton.setColor(QColor("#00008B"))
        # DGGAL_RTEA7H_Z7
        self.dggal_rtea7h_z7ResSpinBox.setValue(11)
        self.dggal_rtea7h_z7ColorButton.setColor(QColor("#00008B"))

        # DGGAL_HEALPix
        self.dggal_healpixResSpinBox.setValue(18)
        self.dggal_healpixColorButton.setColor(QColor("#00008B"))

        # DGGAL_RHEALPIX
        self.dggal_rhealpixResSpinBox.setValue(10)
        self.dggal_rhealpixColorButton.setColor(QColor("#00008B"))

        # QTM
        self.qtmResSpinBox.setValue(18)
        self.qtmColorButton.setColor(QColor("#672a5c"))

        # OLC
        self.olcResSpinBox.setValue(8)
        self.olcColorButton.setColor(QColor("#4285f4"))

        # Geohash
        self.geohashResSpinBox.setValue(7)
        self.geohashColorButton.setColor(QColor("#672a5c"))

        # GEOREF
        self.georefResSpinBox.setValue(3)
        self.georefColorButton.setColor(QColor("#672a5c"))

        # MGRS
        self.mgrsResSpinBox.setValue(3)
        self.mgrsColorButton.setColor(QColor("#0052b4"))

        # Tilecode
        self.tilecodeResSpinBox.setValue(18)
        self.tilecodeColorButton.setColor(QColor("#672a5c"))

        # Quadkey
        self.quadkeyResSpinBox.setValue(18)
        self.quadkeyColorButton.setColor(QColor("#672a5c"))

        # Maidenhead
        self.maidenheadResSpinBox.setValue(4)
        self.maidenheadColorButton.setColor(QColor("#672a5c"))

        # GARS
        self.garsResSpinBox.setValue(4)
        self.garsColorButton.setColor(QColor("#672a5c"))

        # DIGIPIN
        self.digipinResSpinBox.setValue(6)
        self.digipinColorButton.setColor(QColor("#672a5c"))

        ### General Settings ###
        self.zoomLevelCheckBox.setCheckState(Qt.Checked)
        self.gridLabelCheckBox.setCheckState(Qt.Checked)
        self.persistentMarkerCheckBox.setCheckState(Qt.Checked)
        self.fixAntimeridianCheckBox.setCheckState(Qt.Checked)
        self.coordOrderComboBox.setCurrentIndex(CoordOrder.OrderYX)
        self.epsg4326PrecisionSpinBox.setValue(8)

        # Marker settings
        self.markerColorButton.setColor(QColor("#ff0000"))
        self.markerSizeSpinBox.setValue(18)
        self.markerWidthSpinBox.setValue(2)

        # Grid settings
        self.gridWidthSpinBox.setValue(2)

    def readSettings(self):
        """Load the user selected settings. The settings are retained even when
        the user quits QGIS. This just loads the saved information into varialbles,
        but does not update the widgets. The widgets are updated with showEvent."""
        settings.readSettings()

    def accept(self):
        """Accept the settings and save them for next time."""
        qset = QgsSettings()

        ### DGGS Settings ###
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
            "/vgrid/dggal_isea7h_z7Color", self.dggal_isea7h_z7ColorButton.color().name()
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
            "/vgrid/dggal_ivea7h_z7Color", self.dggal_ivea7h_z7ColorButton.color().name()
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
            "/vgrid/dggal_rtea7h_z7Color", self.dggal_rtea7h_z7ColorButton.color().name()
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
        qset.setValue("/vgrid/digipinColorOpacity", self.digipinColorButton.color().alpha())


        ### General Settings ###
        qset.setValue("/vgrid/zoomLevel", int(self.zoomLevelCheckBox.checkState()))
        qset.setValue("/vgrid/gridLabel", int(self.gridLabelCheckBox.checkState()))
        qset.setValue(
            "/vgrid/persistentMarker", int(self.persistentMarkerCheckBox.checkState())
        )
        qset.setValue(
            "/vgrid/fixAntimeridian", int(self.fixAntimeridianCheckBox.checkState())
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

        ### DGGS Settings ###
        self.h3ResSpinBox.setValue(settings.h3Res)
        self.h3ColorButton.setColor(settings.h3Color)

        self.s2ResSpinBox.setValue(settings.s2Res)
        self.s2ColorButton.setColor(settings.s2Color)

        self.a5ResSpinBox.setValue(settings.a5Res)
        self.a5ColorButton.setColor(settings.a5Color)

        self.rhealpixResSpinBox.setValue(settings.rhealpixRes)
        self.rhealpixColorButton.setColor(settings.rhealpixColor)

        self.isea4tResSpinBox.setValue(settings.isea4tRes)
        self.isea4tColorButton.setColor(settings.isea4tColor)

        self.isea3hResSpinBox.setValue(settings.isea3hRes)
        self.isea3hColorButton.setColor(settings.isea3hColor)

        self.easeResSpinBox.setValue(settings.easeRes)
        self.easeColorButton.setColor(settings.easeColor)

        self.dggal_gnosisResSpinBox.setValue(settings.dggal_gnosisRes)
        self.dggal_gnosisColorButton.setColor(settings.dggal_gnosisColor)

        self.dggal_isea4rResSpinBox.setValue(settings.dggal_isea4rRes)
        self.dggal_isea4rColorButton.setColor(settings.dggal_isea4rColor)
        self.dggal_isea9rResSpinBox.setValue(settings.dggal_isea9rRes)
        self.dggal_isea9rColorButton.setColor(settings.dggal_isea9rColor)

        self.dggal_isea3hResSpinBox.setValue(settings.dggal_isea3hRes)
        self.dggal_isea3hColorButton.setColor(settings.dggal_isea3hColor)
        self.dggal_isea7hResSpinBox.setValue(settings.dggal_isea7hRes)
        self.dggal_isea7hColorButton.setColor(settings.dggal_isea7hColor)
        self.dggal_isea7h_z7ResSpinBox.setValue(settings.dggal_isea7h_z7Res)
        self.dggal_isea7h_z7ColorButton.setColor(settings.dggal_isea7h_z7Color)


        self.dggal_ivea4rResSpinBox.setValue(settings.dggal_ivea4rRes)
        self.dggal_ivea4rColorButton.setColor(settings.dggal_ivea4rColor)
        self.dggal_ivea9rResSpinBox.setValue(settings.dggal_ivea9rRes)
        self.dggal_ivea9rColorButton.setColor(settings.dggal_ivea9rColor)

        self.dggal_ivea3hResSpinBox.setValue(settings.dggal_ivea3hRes)
        self.dggal_ivea3hColorButton.setColor(settings.dggal_ivea3hColor)
        self.dggal_ivea7hResSpinBox.setValue(settings.dggal_ivea7hRes)
        self.dggal_ivea7hColorButton.setColor(settings.dggal_ivea7hColor)
        self.dggal_ivea7h_z7ResSpinBox.setValue(settings.dggal_ivea7h_z7Res)
        self.dggal_ivea7h_z7ColorButton.setColor(settings.dggal_ivea7h_z7Color)

        self.dggal_rtea4rResSpinBox.setValue(settings.dggal_rtea4rRes)
        self.dggal_rtea4rColorButton.setColor(settings.dggal_rtea4rColor)
        self.dggal_rtea9rResSpinBox.setValue(settings.dggal_rtea9rRes)
        self.dggal_rtea9rColorButton.setColor(settings.dggal_rtea9rColor)

        self.dggal_rtea3hResSpinBox.setValue(settings.dggal_rtea3hRes)
        self.dggal_rtea3hColorButton.setColor(settings.dggal_rtea3hColor)
        self.dggal_rtea7hResSpinBox.setValue(settings.dggal_rtea7hRes)
        self.dggal_rtea7hColorButton.setColor(settings.dggal_rtea7hColor)
        self.dggal_rtea7h_z7ResSpinBox.setValue(settings.dggal_rtea7h_z7Res)
        self.dggal_rtea7h_z7ColorButton.setColor(settings.dggal_rtea7h_z7Color)

        self.dggal_healpixResSpinBox.setValue(settings.dggal_healpixRes)
        self.dggal_healpixColorButton.setColor(settings.dggal_healpixColor)
        self.dggal_rhealpixResSpinBox.setValue(settings.dggal_rhealpixRes)
        self.dggal_rhealpixColorButton.setColor(settings.dggal_rhealpixColor)

        self.qtmResSpinBox.setValue(settings.qtmRes)
        self.qtmColorButton.setColor(settings.qtmColor)

        self.olcResSpinBox.setValue(settings.olcRes)
        self.olcColorButton.setColor(settings.olcColor)

        self.geohashResSpinBox.setValue(settings.geohashRes)
        self.geohashColorButton.setColor(settings.geohashColor)

        self.georefResSpinBox.setValue(settings.georefRes)
        self.georefColorButton.setColor(settings.georefColor)

        self.mgrsResSpinBox.setValue(settings.mgrsRes)
        self.mgrsColorButton.setColor(settings.mgrsColor)

        self.tilecodeResSpinBox.setValue(settings.tilecodeRes)
        self.tilecodeColorButton.setColor(settings.tilecodeColor)

        self.quadkeyResSpinBox.setValue(settings.quadkeyRes)
        self.quadkeyColorButton.setColor(settings.quadkeyColor)

        self.maidenheadResSpinBox.setValue(settings.maidenheadRes)
        self.maidenheadColorButton.setColor(settings.maidenheadColor)

        self.garsResSpinBox.setValue(settings.garsRes)
        self.garsColorButton.setColor(settings.garsColor)

        self.digipinResSpinBox.setValue(settings.digipinRes)
        self.digipinColorButton.setColor(settings.digipinColor)

        ### General Settings ###
        self.zoomLevelCheckBox.setCheckState(settings.zoomLevel)
        self.gridLabelCheckBox.setCheckState(settings.gridLabel)
        self.persistentMarkerCheckBox.setCheckState(settings.persistentMarker)
        self.fixAntimeridianCheckBox.setCheckState(settings.fixAntimeridian)
        self.coordOrderComboBox.setCurrentIndex(settings.coordOrder)
        self.epsg4326PrecisionSpinBox.setValue(settings.epsg4326Precision)

        self.markerColorButton.setColor(settings.markerColor)
        self.markerSizeSpinBox.setValue(settings.markerSize)
        self.markerWidthSpinBox.setValue(settings.markerWidth)
        self.gridWidthSpinBox.setValue(settings.gridWidth)
