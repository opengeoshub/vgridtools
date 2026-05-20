# -*- coding: utf-8 -*-
__author__ = "Thang Quach"
__date__ = "2024-11-20"
__copyright__ = "(L) 2024, Thang Quach"

from qgis.core import (
    QgsApplication,
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterNumber,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterField,
    QgsProcessingParameterVectorDestination,
    QgsProcessingParameterEnum,
)
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtCore import QCoreApplication
import os

from vgrid.utils.constants import DGGRID_TYPES
from vgrid.utils.io import validate_dggrid_resolution

from ...settings import settings
from ...utils.binning.bin_helper import (
    BIN_STATISTICS,
    generate_dggrid_grid_qgis,
    prepare_point_bin_algorithm,
    process_point_dggs_bin,
)
from ...utils.imgs import Imgs

_DGGS_TYPE_OPTIONS = list(DGGRID_TYPES.keys())
_DEFAULT_DGGS_TYPE = "ISEA3H"


def _option_index(options, name, fallback=0):
    try:
        return options.index(name)
    except ValueError:
        return fallback


class DGGRIDBin(QgsProcessingAlgorithm):
    INPUT = "INPUT"
    CATEGORY_FIELD = "CATEGORY_FIELD"
    NUMERIC_FIELD = "NUMERIC_FIELD"
    STATS = "STATS"
    DGGS_TYPE = "DGGS_TYPE"
    RESOLUTION = "RESOLUTION"
    DENSIFICATION = "DENSIFICATION"
    OUTPUT = "OUTPUT"

    STATISTICS = BIN_STATISTICS

    LOC = QgsApplication.locale()[:2]

    def translate(self, string):
        return QCoreApplication.translate("Processing", string)

    def tr(self, *string):
        if self.LOC == "vi":
            if len(string) == 2:
                return string[1]
            return self.translate(string[0])
        return self.translate(string[0])

    def createInstance(self):
        return DGGRIDBin()

    def name(self):
        return "bin_dggrid"

    def icon(self):
        return QIcon(
            os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "../images/generator/grid_dggrid.svg",
            )
        )

    def displayName(self):
        return self.tr("DGGRID Bin", "DGGRID Bin")

    def group(self):
        return self.tr("Binning", "Binning")

    def groupId(self):
        return "binning"

    def tags(self):
        return self.tr("DGGS, DGGRID, Binning").split(",")

    txt_en = "DGGRID Bin"
    txt_vi = "DGGRID Bin"
    figure = "../images/tutorial/grid_dggrid.png"

    def shortHelpString(self):
        social_BW = Imgs().social_BW
        footer = (
            '''<div align="center">
                      <img src="'''
            + os.path.join(os.path.dirname(os.path.dirname(__file__)), self.figure)
            + """">
                    </div>
                    <div align="right">
                      <p align="right">
                      <b>"""
            + self.tr("Author: Thang Quach", "Author: Thang Quach")
            + """</b>
                      </p>"""
            + social_BW
            + """
                    </div>
                    """
        )
        return self.tr(self.txt_en, self.txt_vi) + footer

    def initAlgorithm(self, config=None):
        settings.readSettings()

        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.INPUT,
                "Input point layer",
                [QgsProcessing.TypeVectorPoint],
            )
        )
        self.addParameter(
            QgsProcessingParameterEnum(
                self.DGGS_TYPE,
                self.tr("DGGS Type"),
                options=_DGGS_TYPE_OPTIONS,
                defaultValue=_option_index(_DGGS_TYPE_OPTIONS, _DEFAULT_DGGS_TYPE),
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.RESOLUTION,
                self.tr("Resolution"),
                QgsProcessingParameterNumber.Integer,
                defaultValue=1,
                minValue=0,
                maxValue=35,
                optional=False,
            )
        )
        self.addParameter(
            QgsProcessingParameterEnum(
                self.STATS,
                "Statistic to compute",
                options=self.STATISTICS,
                defaultValue=0,
            )
        )
        self.addParameter(
            QgsProcessingParameterField(
                self.NUMERIC_FIELD,
                "Numeric field (for statistics other than 'count')",
                parentLayerParameterName=self.INPUT,
                optional=True,
                type=QgsProcessingParameterField.Numeric,
            )
        )
        self.addParameter(
            QgsProcessingParameterField(
                self.CATEGORY_FIELD,
                "Category field",
                optional=True,
                parentLayerParameterName=self.INPUT,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.DENSIFICATION,
                self.tr("Densification"),
                QgsProcessingParameterNumber.Integer,
                defaultValue=settings.dggridDensificationSpinBox,
                minValue=1,
                optional=False,
            )
        )
        self.addParameter(
            QgsProcessingParameterVectorDestination(self.OUTPUT, "DGGS_binning")
        )

    def prepareAlgorithm(self, parameters, context, feedback):
        self.point_layer = self.parameterAsSource(parameters, self.INPUT, context)
        self.stats_index = self.parameterAsEnum(parameters, self.STATS, context)
        self.stats = self.STATISTICS[self.stats_index]

        dggs_type_index = self.parameterAsEnum(parameters, self.DGGS_TYPE, context)
        if dggs_type_index < 0 or dggs_type_index >= len(_DGGS_TYPE_OPTIONS):
            dggs_type_index = _option_index(_DGGS_TYPE_OPTIONS, _DEFAULT_DGGS_TYPE)
        self.dggs_type = _DGGS_TYPE_OPTIONS[dggs_type_index]

        self.resolution = self.parameterAsInt(parameters, self.RESOLUTION, context)
        self.densification = self.parameterAsInt(
            parameters, self.DENSIFICATION, context
        )
        self.numeric_field = self.parameterAsString(
            parameters, self.NUMERIC_FIELD, context
        )
        self.category_field = self.parameterAsString(
            parameters, self.CATEGORY_FIELD, context
        )

        prepare_point_bin_algorithm(
            self.point_layer,
            self.stats,
            self.numeric_field,
            self.category_field,
        )
        return True

    def processAlgorithm(self, parameters, context, feedback):
        id_col = f"dggrid_{self.dggs_type.lower()}"
        dggs_type = self.dggs_type
        densification = self.densification

        def validate_res(resolution):
            return validate_dggrid_resolution(dggs_type, resolution)

        def generate_grid(resolution, extent_layer, fb):
            return generate_dggrid_grid_qgis(
                dggs_type,
                resolution,
                extent_layer,
                feedback=fb,
                densification=densification,
            )

        return process_point_dggs_bin(
            self,
            parameters,
            context,
            feedback,
            self.point_layer,
            self.resolution,
            self.stats,
            self.category_field,
            self.numeric_field,
            id_col,
            f"DGGRID {dggs_type}",
            validate_res,
            generate_grid,
            metric_kind="geodesic",
        )
