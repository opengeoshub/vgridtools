from qgis.core import QgsProcessingAlgorithm, QgsProcessingParameterNumber, QgsSettings
from qgis.PyQt.QtCore import QCoreApplication
from qgis.PyQt.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QVBoxLayout,
    QWidget,
    QLabel,
    QSpinBox,
    QHBoxLayout,
)


class DGGSSettingsDialog(QDialog):
    def __init__(self, algorithm, parent=None):
        super().__init__(parent)
        self.algorithm = algorithm
        self.setWindowTitle("DGGS Settings")
        self.settings = QgsSettings()

        # Initialize UI
        self.initUI()
        self.loadSettings()

    def initUI(self):
        layout = QVBoxLayout()

        # Add resolution inputs for each DGGS type
        dggs_types = [
            "H3",
            "S2",
            "rHEALPix",
            "QTM",
            "OLC",
            "Geohash",
            "Tilecode",
            "Quadkey",
            "DGGAL_GNOSIS",
            "DGGAL_ISEA3H",
            "DGGAL_ISEA9R",
            "DGGAL_IVEA3H",
            "DGGAL_IVEA9R",
            "DGGAL_RTEA3H",
            "DGGAL_RTEA9R",
            "DGGAL_RHEALPIX",
        ]
        self.res_spins = {}

        for dggs_type in dggs_types:
            res_layout = QHBoxLayout()
            res_label = QLabel(f"{dggs_type} Resolution:")
            res_spin = QSpinBox()
            min_res, max_res, _ = self.algorithm.DGGS_RESOLUTION[dggs_type]
            res_spin.setRange(min_res, max_res)
            res_layout.addWidget(res_label)
            res_layout.addWidget(res_spin)
            layout.addLayout(res_layout)
            self.res_spins[dggs_type] = res_spin

        # Add buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self.setLayout(layout)

    def loadSettings(self):
        default_dggs_type = self.settings.value(
            "vgridtools/default_dggs_type", 0, type=int
        )
        default_resolution = self.settings.value(
            "vgridtools/default_resolution", 10, type=int
        )

        dggs_types = [
            "H3",
            "S2",
            "rHEALPix",
            "QTM",
            "OLC",
            "Geohash",
            "Tilecode",
            "Quadkey",
            "DGGAL_GNOSIS",
            "DGGAL_ISEA3H",
            "DGGAL_ISEA9R",
            "DGGAL_IVEA3H",
            "DGGAL_IVEA9R",
            "DGGAL_RTEA3H",
            "DGGAL_RTEA9R",
            "DGGAL_RHEALPIX",
        ]
        selected_type = dggs_types[default_dggs_type]

        for dggs_type, spin in self.res_spins.items():
            if dggs_type == selected_type:
                spin.setValue(default_resolution)
            else:
                min_res, _, _ = self.algorithm.DGGS_RESOLUTION[dggs_type]
                spin.setValue(min_res)

    def getSelectedTypeAndResolution(self):
        dggs_types = [
            "H3",
            "S2",
            "rHEALPix",
            "QTM",
            "OLC",
            "Geohash",
            "Tilecode",
            "Quadkey",
            "DGGAL_GNOSIS",
            "DGGAL_ISEA3H",
            "DGGAL_ISEA9R",
            "DGGAL_IVEA3H",
            "DGGAL_IVEA9R",
            "DGGAL_RTEA3H",
            "DGGAL_RTEA9R",
            "DGGAL_RHEALPIX",
        ]
        selected_type = None
        selected_resolution = None

        for dggs_type, spin in self.res_spins.items():
            if spin.value() != spin.minimum():
                if selected_type is not None:
                    return None, None  # Multiple types selected
                selected_type = dggs_type
                selected_resolution = spin.value()

        if selected_type is None:
            return None, None  # No type selected

        return dggs_types.index(selected_type), selected_resolution


class DGGSSettingsAlgorithm(QgsProcessingAlgorithm):
    """Algorithm to configure DGGS settings."""

    # DGGS type parameters
    H3 = "H3"
    S2 = "S2"
    RHEALPIX = "RHEALPIX"
    QTM = "QTM"
    OLC = "OLC"
    GEOHASH = "GEOHASH"
    TILECODE = "TILECODE"
    QUADKEY = "QUADKEY"
    DGGAL_GNOSIS = "DGGAL_GNOSIS"
    DGGAL_ISEA3H = "DGGAL_ISEA3H"
    DGGAL_ISEA9R = "DGGAL_ISEA9R"
    DGGAL_IVEA3H = "DGGAL_IVEA3H"
    DGGAL_IVEA9R = "DGGAL_IVEA9R"
    DGGAL_RTEA3H = "DGGAL_RTEA3H"
    DGGAL_RTEA9R = "DGGAL_RTEA9R"
    DGGAL_RHEALPIX = "DGGAL_RHEALPIX"
    DGGS_RESOLUTION = {
        "H3": (0, 15, 10),
        "S2": (0, 30, 16),
        "rHEALPix": (1, 15, 11),
        "QTM": (1, 24, 12),
        "OLC": (2, 15, 10),
        "Geohash": (1, 10, 9),
        "Tilecode": (0, 29, 15),
        "Quadkey": (0, 29, 15),
        "DGGAL_GNOSIS": (0, 28, 18),
        "DGGAL_ISEA3H": (0, 33, 22),
        "DGGAL_ISEA9R": (0, 16, 11),
        "DGGAL_IVEA3H": (0, 33, 22),
        "DGGAL_IVEA9R": (0, 16, 11),
        "DGGAL_RTEA3H": (0, 33, 22),
        "DGGAL_RTEA9R": (0, 16, 11),
        "DGGAL_RHEALPIX": (0, 16, 11),
    }

    def tr(self, string):
        return QCoreApplication.translate("Processing", string)

    def createInstance(self):
        return DGGSSettingsAlgorithm()

    def name(self):
        return "settings"

    def displayName(self):
        return self.tr("Settings")

    def shortHelpString(self):
        return self.tr("Configure default DGGS type and resolution settings.")

    def createCustomDialog(self, parent=None):
        return DGGSSettingsDialog(self, parent)

    def initAlgorithm(self, config=None):
        # Get default values from settings
        settings = QgsSettings()
        default_dggs_type = settings.value("vgridtools/default_dggs_type", 0, type=int)
        default_resolution = settings.value(
            "vgridtools/default_resolution", 10, type=int
        )

        # Add individual DGGS type parameters with their resolution ranges
        dggs_types = [
            "H3",
            "S2",
            "rHEALPix",
            "QTM",
            "OLC",
            "Geohash",
            "Tilecode",
            "Quadkey",
            "DGGAL_GNOSIS",
            "DGGAL_ISEA3H",
            "DGGAL_ISEA9R",
            "DGGAL_IVEA3H",
            "DGGAL_IVEA9R",
            "DGGAL_RTEA3H",
            "DGGAL_RTEA9R",
            "DGGAL_RHEALPIX",
        ]
        dggs_params = [
            self.H3,
            self.S2,
            self.RHEALPIX,
            self.QTM,
            self.OLC,
            self.GEOHASH,
            self.TILECODE,
            self.QUADKEY,
            self.DGGAL_GNOSIS,
            self.DGGAL_ISEA3H,
            self.DGGAL_ISEA9R,
            self.DGGAL_IVEA3H,
            self.DGGAL_IVEA9R,
            self.DGGAL_RTEA3H,
            self.DGGAL_RTEA9R,
            self.DGGAL_RHEALPIX,
        ]

        for i, (dggs_type, param) in enumerate(zip(dggs_types, dggs_params)):
            min_res, max_res, default_res = self.DGGS_RESOLUTION[dggs_type]
            self.addParameter(
                QgsProcessingParameterNumber(
                    param,
                    self.tr(f"{dggs_type} Resolution"),
                    QgsProcessingParameterNumber.Integer,
                    default_res if i == default_dggs_type else min_res,
                    minValue=min_res,
                    maxValue=max_res,
                )
            )

    def processAlgorithm(self, parameters, context, feedback):
        # Get selected DGGS type and resolution from dialog
        dialog = self.createCustomDialog()
        if not dialog.exec_():
            return {}  # User cancelled

        selected_index, selected_resolution = dialog.getSelectedTypeAndResolution()
        if selected_index is None:
            feedback.reportError("Please set resolution for one DGGS type")
            return {}

        # Save settings
        settings = QgsSettings()
        settings.setValue("vgridtools/default_dggs_type", selected_index)
        settings.setValue("vgridtools/default_resolution", selected_resolution)

        dggs_types = [
            "H3",
            "S2",
            "rHEALPix",
            "QTM",
            "OLC",
            "Geohash",
            "Tilecode",
            "Quadkey",
            "DGGAL_GNOSIS",
            "DGGAL_ISEA3H",
            "DGGAL_ISEA9R",
            "DGGAL_IVEA3H",
            "DGGAL_IVEA9R",
            "DGGAL_RTEA3H",
            "DGGAL_RTEA9R",
            "DGGAL_RHEALPIX",
        ]
        feedback.pushInfo(
            f"Settings saved: DGGS Type = {dggs_types[selected_index]}, Resolution = {selected_resolution}"
        )
        return {}
