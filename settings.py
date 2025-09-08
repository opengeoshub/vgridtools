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


FORM_CLASS, _ = loadUiType(os.path.join(
    os.path.dirname(__file__), 'ui/settings.ui'))

@enum.unique
class CoordOrder(enum.IntEnum):
    OrderYX = 0
    OrderXY = 1

class Settings():
    def __init__(self):
        self.readSettings()

    def readSettings(self):
        '''Load the user selected settings. The settings are retained even when
        the user quits QGIS. This just loads the saved information into variables,
        but does not update the widgets. The widgets are updated with showEvent.'''
        qset = QgsSettings()
        
        self.coordOrder = int(qset.value('/vgrid/coordOrder', CoordOrder.OrderYX))
        self.h3Res = int(qset.value('/vgrid/h3Res', 14))
        self.s2Res = int(qset.value('/vgrid/s2Res', 22))
        self.a5Res = int(qset.value('/vgrid/a5Res', 14))
        self.rhealpixRes = int(qset.value('/vgrid/rhealpixRes', 14))
        self.isea4tRes = int(qset.value('/vgrid/isea4tRes', 21))
        self.isea3hRes = int(qset.value('/vgrid/isea3hRes', 27))
        self.easeRes = int(qset.value('/vgrid/easeRes', 5))

        self.dggal_gnosisRes = int(qset.value('/vgrid/dggal_gnosisRes', 22))
        self.dggal_isea3hRes = int(qset.value('/vgrid/dggal_isea3hRes', 27))
        self.dggal_isea9rRes = int(qset.value('/vgrid/dggal_isea9rRes', 13))
        self.dggal_ivea3hRes = int(qset.value('/vgrid/dggal_ivea3hRes', 27))
        self.dggal_ivea9rRes = int(qset.value('/vgrid/dggal_ivea9rRes', 13))
        self.dggal_rtea3hRes = int(qset.value('/vgrid/dggal_rtea3hRes', 27))
        self.dggal_rtea9rRes = int(qset.value('/vgrid/dggal_rtea9rRes', 13))
        self.dggal_rhealpixRes = int(qset.value('/vgrid/dggal_rhealpixRes', 11))

        self.qtmRes = int(qset.value('/vgrid/qtmRes', 24))
        self.olcRes = int(qset.value('/vgrid/olcRes', 11))
        self.geohashRes = int(qset.value('/vgrid/geohashRes', 9))
        self.georefRes = int(qset.value('/vgrid/georefRes', 4))
        self.mgrsRes = int(qset.value('/vgrid/mgrsRes', 4))
        self.tilecodeRes = int(qset.value('/vgrid/tilecodeRes', 23))
        self.quadkeyRes = int(qset.value('/vgrid/quadkeyRes', 23))
        self.maidenheadRes = int(qset.value('/vgrid/maidenheadRes', 4))
        self.garsRes = int(qset.value('/vgrid/garsRes', 4))


settings = Settings()


class SettingsWidget(QDialog, FORM_CLASS):
    def __init__(self, lltools, iface, parent):
        super(SettingsWidget, self).__init__(parent)
        self.setupUi(self)
        self.lltools = lltools
        self.iface = iface

        self.buttonBox.button(QDialogButtonBox.RestoreDefaults).clicked.connect(self.restoreDefaults)
        self.readSettings()

    def restoreDefaults(self):
        '''Restore all settings to their default state.'''
        # Follow order and default values from readSettings
        self.coordOrder = coordOrder.OrderYX
        self.h3ResSpinBox.setValue(14)
        self.s2ResSpinBox.setValue(22)
        self.a5ResSpinBox.setValue(14)
        self.rhealpixResSpinBox.setValue(14)
        self.isea4tResSpinBox.setValue(21)
        self.isea3hResSpinBox.setValue(27)
        self.easeResSpinBox.setValue(5)

        self.dggal_gnosisResSpinBox.setValue(22)
        self.dggal_isea3hResSpinBox.setValue(27)
        self.dggal_isea9rResSpinBox.setValue(13)
        self.dggal_ivea3hResSpinBox.setValue(27)
        self.dggal_ivea9rResSpinBox.setValue(13)
        self.dggal_rtea3hResSpinBox.setValue(27)
        self.dggal_rtea9rResSpinBox.setValue(13)
        self.dggal_rhealpixResSpinBox.setValue(14)

        self.qtmResSpinBox.setValue(24)
        self.olcResSpinBox.setValue(11)
        self.geohashResSpinBox.setValue(9)
        self.georefResSpinBox.setValue(4)
        self.mgrsResSpinBox.setValue(4)
        self.tilecodeResSpinBox.setValue(23)
        self.quadkeyResSpinBox.setValue(23)
        self.maidenheadResSpinBox.setValue(4)
        self.garsResSpinBox.setValue(4)

    def readSettings(self):
        '''Load the user selected settings. The settings are retained even when
        the user quits QGIS. This just loads the saved information into varialbles,
        but does not update the widgets. The widgets are updated with showEvent.'''
        settings.readSettings()
        # self.setEnabled()

    def accept(self):
        '''Accept the settings and save them for next time.'''
        qset = QgsSettings()
        
        
        qset.setValue('/vgrid/h3Res', int(self.h3ResSpinBox.value()))
        qset.setValue('/vgrid/s2Res', int(self.s2ResSpinBox.value()))
        qset.setValue('/vgrid/a5Res', int(self.a5ResSpinBox.value()))
        qset.setValue('/vgrid/rhealpixRes', int(self.rhealpixResSpinBox.value()))
        qset.setValue('/vgrid/isea4tRes', int(self.isea4tResSpinBox.value()))
        qset.setValue('/vgrid/isea3hRes', int(self.isea3hResSpinBox.value()))
        qset.setValue('/vgrid/easeRes', int(self.easeResSpinBox.value()))

        qset.setValue('/vgrid/dggal_gnosisRes', int(self.dggal_gnosisResSpinBox.value()))
        qset.setValue('/vgrid/dggal_isea3hRes', int(self.dggal_isea3hResSpinBox.value()))
        qset.setValue('/vgrid/dggal_isea9rRes', int(self.dggal_isea9rResSpinBox.value()))
        qset.setValue('/vgrid/dggal_ivea3hRes', int(self.dggal_ivea3hResSpinBox.value()))
        qset.setValue('/vgrid/dggal_ivea9rRes', int(self.dggal_ivea9rResSpinBox.value()))
        qset.setValue('/vgrid/dggal_rtea3hRes', int(self.dggal_rtea3hResSpinBox.value()))
        qset.setValue('/vgrid/dggal_rtea9rRes', int(self.dggal_rtea9rResSpinBox.value()))
        qset.setValue('/vgrid/dggal_rhealpixRes', int(self.dggal_rhealpixResSpinBox.value()))

        qset.setValue('/vgrid/qtmRes', int(self.qtmResSpinBox.value()))
        qset.setValue('/vgrid/olcRes', int(self.olcResSpinBox.value()))
        qset.setValue('/vgrid/geohashRes', int(self.geohashResSpinBox.value()))
        qset.setValue('/vgrid/georefRes', int(self.georefResSpinBox.value()))
        qset.setValue('/vgrid/mgrsRes', int(self.mgrsResSpinBox.value()))
        qset.setValue('/vgrid/tilecodeRes', int(self.tilecodeResSpinBox.value()))
        qset.setValue('/vgrid/quadkeyRes', int(self.quadkeyResSpinBox.value()))
        qset.setValue('/vgrid/maidenheadRes', int(self.maidenheadResSpinBox.value()))
        qset.setValue('/vgrid/garsRes', int(self.garsResSpinBox.value()))
        qset.setValue('/vgrid/ConverterDelimiter', self.converterDelimiterLineEdit.text())
        qset.setValue('/vgrid/ConverterDdmmssDelimiter', self.converterDdmmssDelimiterLineEdit.text())
        qset.setValue('/vgrid/converterPadZeroes', self.converterPadZeroesCheckBox.checkState())
        qset.setValue('/vgrid/converterNsewBeginning', self.converterNsewBeginningCheckBox.checkState())
        qset.setValue('/vgrid/ConverterMgrsAddSpaces', self.converterMgrsAddSpacesCheckBox.checkState())
        qset.setValue('/vgrid/ConverterMgrsPrecision', int(self.converterMgrsPrecisionSpinBox.value()))

        # The values have been read from the widgets and saved to the registry.
        # Now we will read them back to the variables.
        self.readSettings()
        self.lltools.settingsChanged()
        self.close()
        
    def showTab(self, tab):
        self.tabWidget.setCurrentIndex(tab)
        self.show()

    def showEvent(self, e):
        '''The user has selected the settings dialog box so we need to
        read the settings and update the dialog box with the previously
        selected settings.'''
        self.readSettings()
    
        self.h3ResSpinBox.setValue(settings.h3Res)
        self.s2ResSpinBox.setValue(settings.s2Res)
        self.a5ResSpinBox.setValue(settings.a5Res)
        self.rhealpixResSpinBox.setValue(settings.rhealpixRes)
        
               
        self.qtmResSpinBox.setValue(settings.qtmRes)
        self.olcResSpinBox.setValue(settings.olcRes)
        self.geohashResSpinBox.setValue(settings.geohashRes)
        self.tilecodeResSpinBox.setValue(settings.tilecodeRes)
        self.quadkeyResSpinBox.setValue(settings.quadkeyRes)
        self.isea4tResSpinBox.setValue(settings.isea4tRes)
        self.isea3hResSpinBox.setValue(settings.isea3hRes)
        self.dggal_gnosisResSpinBox.setValue(settings.dggal_gnosisRes)

        self.dggal_isea3hResSpinBox.setValue(settings.dggal_isea3hRes)
        self.dggal_isea9rResSpinBox.setValue(settings.dggal_isea9rRes)
        self.dggal_ivea3hResSpinBox.setValue(settings.dggal_ivea3hRes)
        self.dggal_ivea9rResSpinBox.setValue(settings.dggal_ivea9rRes)
        self.dggal_rtea3hResSpinBox.setValue(settings.dggal_rtea3hRes)
        self.dggal_rtea9rResSpinBox.setValue(settings.dggal_rtea9rRes)
        self.dggal_rhealpixResSpinBox.setValue(settings.dggal_rhealpixRes)