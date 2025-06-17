from qgis.PyQt.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QSpinBox,
    QPushButton,
    QDialogButtonBox
)
from qgis.PyQt.QtCore import QSettings
from qgis.core import QgsSettings

class DGGSSettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("DGGS Settings")
        self.settings = QgsSettings()
        
        # Initialize UI
        self.initUI()
        self.loadSettings()
        
    def initUI(self):
        layout = QVBoxLayout()
        
        # DGGS Type selection
        dggs_layout = QHBoxLayout()
        dggs_label = QLabel("Default DGGS Type:")
        self.dggs_combo = QComboBox()
        self.dggs_combo.addItems([
            'H3', 'S2', 'rHEALPix', 'QTM', 'OLC', 'Geohash',
            'Tilecode', 'Quadkey'
        ])
        dggs_layout.addWidget(dggs_label)
        dggs_layout.addWidget(self.dggs_combo)
        layout.addLayout(dggs_layout)
        
        # Resolution selection
        res_layout = QHBoxLayout()
        res_label = QLabel("Default Resolution:")
        self.res_spin = QSpinBox()
        self.res_spin.setRange(0, 30)  # Will be updated based on DGGS type
        res_layout.addWidget(res_label)
        res_layout.addWidget(self.res_spin)
        layout.addLayout(res_layout)
        
        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
        self.setLayout(layout)
        
        # Connect signals
        self.dggs_combo.currentIndexChanged.connect(self.updateResolutionRange)
        
    def loadSettings(self):
        # Load saved settings
        dggs_type = self.settings.value('vgridtools/default_dggs_type', 0, type=int)
        resolution = self.settings.value('vgridtools/default_resolution', 10, type=int)
        
        self.dggs_combo.setCurrentIndex(dggs_type)
        self.updateResolutionRange(dggs_type)
        self.res_spin.setValue(resolution)
        
    def updateResolutionRange(self, dggs_type):
        # Define resolution ranges for each DGGS type
        resolution_ranges = {
            'H3': (0, 15),
            'S2': (0, 30),
            'rHEALPix': (1, 15),
            'QTM': (1, 24),
            'OLC': (2, 15),
            'Geohash': (1, 10),
            'Tilecode': (0, 29),
            'Quadkey': (0, 29)
        }
        
        dggs_name = self.dggs_combo.currentText()
        min_res, max_res = resolution_ranges.get(dggs_name, (0, 30))
        
        self.res_spin.setRange(min_res, max_res)
        
    def accept(self):
        # Save settings
        self.settings.setValue('vgridtools/default_dggs_type', self.dggs_combo.currentIndex())
        self.settings.setValue('vgridtools/default_resolution', self.res_spin.value())
        super().accept() 