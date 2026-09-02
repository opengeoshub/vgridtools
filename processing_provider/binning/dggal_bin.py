# -*- coding: utf-8 -*-
__author__ = "Thang Quach"
__date__ = "2024-11-20"
__copyright__ = "(L) 2024, Thang Quach"

from qgis.core import (
    QgsApplication,
    QgsCoordinateReferenceSystem,
    QgsProcessing,
    QgsProcessingFeatureBasedAlgorithm,
    QgsProcessingParameterNumber,
    QgsProcessingParameterField,
    QgsProcessingParameterEnum,
    QgsWkbTypes,
)
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtCore import QCoreApplication
import os

from vgrid.utils.constants import DGGAL_TYPES
from vgrid.utils.io import validate_dggal_resolution

from ...utils.binning.bin_helper import (
    load_wgs84_feature_source,
    BIN_AGG,
    add_shift_split_parameters,
    apply_loaded_layer_name,
    prepare_point_bin_algorithm,
    process_point_dggs_bin,
    read_shift_split,
    set_output_layer_name,
)
from ...utils.help_footer import social_links_footer
from ...utils.resampling.dggsgrid import generate_dggal_grid


class DGGALBin(QgsProcessingFeatureBasedAlgorithm):
    INPUT = "INPUT"
    CATEGORY_FIELD = "CATEGORY_FIELD"
    NUMERIC_FIELD = "NUMERIC_FIELD"
    AGG = "AGG"
    DGGS_TYPE = "DGGS_TYPE"
    RESOLUTION = "RESOLUTION"
    OUTPUT = "OUTPUT"

    AGG_OPTIONS = BIN_AGG

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


    def inputLayerTypes(self):
        return [QgsProcessing.TypeVectorPoint]

    def inputParameterDescription(self):
        return self.tr("Input point layer")

    def outputName(self):
        return self.tr("DGGS_binning")

    def outputWkbType(self, input_wkb_type):
        return QgsWkbTypes.Polygon

    def outputCrs(self, input_crs):
        return QgsCoordinateReferenceSystem("EPSG:4326")

    def supportInPlaceEdit(self, layer):
        return False

    def initParameters(self, config=None):
        # INPUT is provided by QgsProcessingFeatureBasedAlgorithm
        # (includes native "Selected features only").
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
                self.AGG,
                "Aggregate function",
                options=self.AGG_OPTIONS,
                defaultValue=0,
            )
        )
        self.addParameter(
            QgsProcessingParameterField(
                self.NUMERIC_FIELD,
                "Numeric field (for aggregate function other than 'count')",
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
        add_shift_split_parameters(self, shift=False)

    def prepareAlgorithm(self, parameters, context, feedback):
        self.agg_index = self.parameterAsEnum(parameters, self.AGG, context)
        self.agg = self.AGG_OPTIONS[self.agg_index]

        dggs_type_index = self.parameterAsEnum(parameters, self.DGGS_TYPE, context)
        self.dggs_type = list(DGGAL_TYPES.keys())[dggs_type_index]

        self.resolution = self.parameterAsInt(parameters, self.RESOLUTION, context)
        self.numeric_field = self.parameterAsString(
            parameters, self.NUMERIC_FIELD, context
        )
        self.category_field = self.parameterAsString(
            parameters, self.CATEGORY_FIELD, context
        )
        _, self.split_antimeridian = read_shift_split(
            self, parameters, context, shift=False
        )

        prepare_point_bin_algorithm(
            None,
            self.agg,
            self.numeric_field,
            self.category_field,
        )
        return True

    def processAlgorithm(self, parameters, context, feedback):
        id_col = f"dggal_{self.dggs_type}"
        dggs_type = self.dggs_type
        layer_name = f"DGGAL_{dggs_type.upper()}"
        set_output_layer_name(parameters, self.OUTPUT, "DGGS_binning", layer_name)

        def validate_res(resolution):
            return validate_dggal_resolution(dggs_type, resolution)

        def generate_grid(resolution, extent_layer, fb, **kwargs):
            return generate_dggal_grid(
                dggs_type, resolution, extent_layer, feedback=fb, **kwargs
            )

        point_layer = load_wgs84_feature_source(
            self,
            parameters,
            context,
            feedback,
            self.INPUT,
            layer_name="bin_points_wgs84",
            error="Invalid input point layer.",
        )
        result = process_point_dggs_bin(
            self,
            parameters,
            context,
            feedback,
            point_layer,
            self.resolution,
            self.agg,
            self.category_field,
            self.numeric_field,
            id_col,
            f"DGGAL {dggs_type}",
            validate_res,
            generate_grid,
            metric_kind="geodesic",
            grid_kwargs={
                "split_antimeridian": self.split_antimeridian,
            },
        )
        apply_loaded_layer_name(
            context, result.get(self.OUTPUT), "DGGS_binning", layer_name
        )
        return result
