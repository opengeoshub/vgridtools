import os
from qgis.PyQt.uic import loadUiType
from qgis.PyQt.QtWidgets import QDialog, QDialogButtonBox
from qgis.PyQt.QtCore import QSettings, Qt

FORM_CLASS, _ = loadUiType(
    os.path.join(os.path.dirname(__file__), "ui/dggs_settings.ui")
)


class DGGSettings:
    def __init__(self):
        self.readSettings()

    def readSettings(self):
        """Load the user selected settings."""
        qset = QSettings()

        # Default values from the original DGGS_RESOLUTION
        self.default_resolutions = {
            "H3": (0, 15, 10),
            "S2": (0, 30, 16),
            "A5": (0, 29, 15),
            "rHEALPix": (1, 15, 11),
            "QTM": (1, 24, 12),
            "OLC": (2, 15, 10),
            "Geohash": (1, 10, 9),
            "Tilecode": (0, 29, 15),
            "Quadkey": (0, 29, 15),
            "ISEA4T": (0, 25, 17),
            "ISEA3H": (0, 32, 17),
            "DGGAL_GNOSIS": (0, 28, 18),
            "DGGAL_ISEA3H": (0, 33, 22),
            "DGGAL_ISEA9R": (0, 16, 11),
            "DGGAL_IVEA3H": (0, 33, 22),
            "DGGAL_IVEA9R": (0, 16, 11),
            "DGGAL_RTEA3H": (0, 33, 22),
            "DGGAL_RTEA9R": (0, 16, 11),
        }

        # Load settings for each DGGS type
        self.resolutions = {}
        for dggs_type, (min_res, max_res, default) in self.default_resolutions.items():
            min_key = f"/DGGS/{dggs_type}/MinRes"
            max_key = f"/DGGS/{dggs_type}/MaxRes"
            default_key = f"/DGGS/{dggs_type}/DefaultRes"

            self.resolutions[dggs_type] = (
                int(qset.value(min_key, min_res)),
                int(qset.value(max_key, max_res)),
                int(qset.value(default_key, default)),
            )

    def getResolution(self, dggs_type):
        """Get resolution settings for a specific DGGS type."""
        return self.resolutions.get(dggs_type, self.default_resolutions.get(dggs_type))

    def setResolution(self, dggs_type, min_res, max_res, default_res):
        """Set resolution settings for a specific DGGS type."""
        qset = QSettings()
        qset.setValue(f"/DGGS/{dggs_type}/MinRes", min_res)
        qset.setValue(f"/DGGS/{dggs_type}/MaxRes", max_res)
        qset.setValue(f"/DGGS/{dggs_type}/DefaultRes", default_res)
        self.resolutions[dggs_type] = (min_res, max_res, default_res)

    def restoreDefaults(self):
        """Restore all settings to their default values."""
        self.resolutions = self.default_resolutions.copy()
        qset = QSettings()
        for dggs_type, (min_res, max_res, default) in self.default_resolutions.items():
            qset.setValue(f"/DGGS/{dggs_type}/MinRes", min_res)
            qset.setValue(f"/DGGS/{dggs_type}/MaxRes", max_res)
            qset.setValue(f"/DGGS/{dggs_type}/DefaultRes", default)


settings = DGGSettings()


class DGGSettingsDialog(QDialog, FORM_CLASS):
    """Settings Dialog box."""

    def __init__(self, iface):
        super(DGGSettingsDialog, self).__init__(iface.mainWindow())
        self.setupUi(self)
        self.iface = iface

        # Connect signals
        self.buttonBox.button(QDialogButtonBox.RestoreDefaults).clicked.connect(
            self.restoreDefaults
        )
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

        # Load current settings
        self.loadSettings()

    def loadSettings(self):
        """Load current settings into the dialog."""
        for dggs_type, (min_res, max_res, _) in settings.resolutions.items():
            min_spin = getattr(self, f"{dggs_type.lower()}MinRes")
            max_spin = getattr(self, f"{dggs_type.lower()}MaxRes")
            min_spin.setValue(min_res)
            max_spin.setValue(max_res)

    def restoreDefaults(self):
        """Restore all settings to their default state."""
        settings.restoreDefaults()
        self.loadSettings()

    def accept(self):
        """Accept the settings and save them."""
        # Save settings for each DGGS type
        for dggs_type in settings.resolutions.keys():
            min_spin = getattr(self, f"{dggs_type.lower()}MinRes")
            max_spin = getattr(self, f"{dggs_type.lower()}MaxRes")
            min_res = min_spin.value()
            max_res = max_spin.value()
            default_res = (min_res + max_res) // 2  # Use middle value as default
            settings.setResolution(dggs_type, min_res, max_res, default_res)

        self.close()
