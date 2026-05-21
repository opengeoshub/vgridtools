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

from vgrid.utils.constants import DGGAL_TYPES
from vgrid.utils.io import validate_dggal_resolution

from ...utils.binning.bin_helper import (
    BIN_STATISTICS,
    prepare_point_bin_algorithm,
    process_point_dggs_bin,
)
from ...utils.help_footer import social_links_footer
from ...utils.resampling.dggsgrid import generate_dggal_grid


class DGGALBin(QgsProcessingAlgorithm):
    INPUT = "INPUT"
    CATEGORY_FIELD = "CATEGORY_FIELD"
    NUMERIC_FIELD = "NUMERIC_FIELD"
    STATS = "STATS"
    DGGS_TYPE = "DGGS_TYPE"
    RESOLUTION = "RESOLUTION"
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
        return DGGALBin()

    def name(self):
        return "bin_dggal"

    def icon(self):
        return QIcon(
            os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "../images/generator/grid_dggal.svg",
            )
        )

    def displayName(self):
        return self.tr("DGGAL Bin", "DGGAL Bin")

    def group(self):
        return self.tr("Binning", "Binning")

    def groupId(self):
        return "binning"

    def tags(self):
        return self.tr("DGGS, DGGAL, Binning").split(",")

    txt_en = "DGGAL Bin"
    txt_vi = "DGGAL Bin"
    figure = "../images/tutorial/bin_dggal.png"

    def shortHelpString(self):
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
            + social_links_footer()
            + """
                    </div>
                    """
        )
        return self.tr(self.txt_en, self.txt_vi) + footer

    def initAlgorithm(self, config=None):
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
                options=[key for key in DGGAL_TYPES.keys()],
                defaultValue="gnosis",
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.RESOLUTION,
                self.tr("Resolution"),
                QgsProcessingParameterNumber.Integer,
                defaultValue=1,
                minValue=0,
                maxValue=33,
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
            QgsProcessingParameterVectorDestination(self.OUTPUT, "DGGS_binning")
        )

    def prepareAlgorithm(self, parameters, context, feedback):
        self.point_layer = self.parameterAsSource(parameters, self.INPUT, context)
        self.stats_index = self.parameterAsEnum(parameters, self.STATS, context)
        self.stats = self.STATISTICS[self.stats_index]

        dggs_type_index = self.parameterAsEnum(parameters, self.DGGS_TYPE, context)
        self.dggs_type = list(DGGAL_TYPES.keys())[dggs_type_index]

        self.resolution = self.parameterAsInt(parameters, self.RESOLUTION, context)
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
        id_col = f"dggal_{self.dggs_type}"
        dggs_type = self.dggs_type

        def validate_res(resolution):
            return validate_dggal_resolution(dggs_type, resolution)

        def generate_grid(resolution, extent_layer, fb):
            return generate_dggal_grid(dggs_type, resolution, extent_layer, feedback=fb)

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
            f"DGGAL {dggs_type}",
            validate_res,
            generate_grid,
            metric_kind="geodesic",
        )
