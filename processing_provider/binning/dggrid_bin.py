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

from vgrid.utils.constants import DGGRID_TYPES
from vgrid.utils.io import validate_dggrid_resolution

from ...settings import settings
from ...utils.dggrid_instance import DGGRID_TYPES_NO_ANTIMERIDIAN
from ...utils.binning.bin_helper import (
    load_wgs84_feature_source,
    AGGREGATE,
    BIN_AGG,
    SPLIT_ANTIMERIDIAN,
    add_dggrid_antimeridian_parameters,
    apply_loaded_layer_name,
    generate_dggrid_grid_qgis,
    prepare_point_bin_algorithm,
    process_point_dggs_bin,
    set_output_layer_name,
)
from ...utils.help_footer import social_links_footer

_DGGS_TYPE_OPTIONS = list(DGGRID_TYPES.keys())
_DEFAULT_DGGS_TYPE = "ISEA3H"


def _option_index(options, name, fallback=0):
    try:
        return options.index(name)
    except ValueError:
        return fallback


class DGGRIDBin(QgsProcessingFeatureBasedAlgorithm):
    INPUT = "INPUT"
    CATEGORY_FIELD = "CATEGORY_FIELD"
    NUMERIC_FIELD = "NUMERIC_FIELD"
    AGG = "AGG"
    DGGS_TYPE = "DGGS_TYPE"
    RESOLUTION = "RESOLUTION"
    DENSIFICATION = "DENSIFICATION"
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
        return [QgsProcessing.SourceType.TypeVectorPoint]

    def inputParameterDescription(self):
        return self.tr("Input point layer")

    def outputName(self):
        return self.tr("DGGS_binning")

    def outputWkbType(self, input_wkb_type):
        return QgsWkbTypes.Type.Polygon

    def outputCrs(self, input_crs):
        return QgsCoordinateReferenceSystem("EPSG:4326")

    def supportInPlaceEdit(self, layer):
        return False

    def initParameters(self, config=None):
        # INPUT is provided by QgsProcessingFeatureBasedAlgorithm
        # (includes native "Selected features only").
        settings.readSettings()

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
                QgsProcessingParameterNumber.Type.Integer,
                defaultValue=1,
                minValue=0,
                maxValue=35,
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
                type=QgsProcessingParameterField.DataType.Numeric,
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
        add_dggrid_antimeridian_parameters(self)
        self.addParameter(
            QgsProcessingParameterNumber(
                self.DENSIFICATION,
                self.tr("Densification"),
                QgsProcessingParameterNumber.Type.Integer,
                defaultValue=settings.dggridDensificationSpinBox,
                minValue=1,
                optional=False,
            )
        )

    def prepareAlgorithm(self, parameters, context, feedback):
        self.agg_index = self.parameterAsEnum(parameters, self.AGG, context)
        self.agg = self.AGG_OPTIONS[self.agg_index]

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
        self.split_antimeridian = self.parameterAsBoolean(
            parameters, SPLIT_ANTIMERIDIAN, context
        )
        self.aggregate = self.parameterAsBoolean(parameters, AGGREGATE, context)

        prepare_point_bin_algorithm(
            None,
            self.agg,
            self.numeric_field,
            self.category_field,
        )

        if self.dggs_type in DGGRID_TYPES_NO_ANTIMERIDIAN:
            if self.split_antimeridian:
                feedback.reportError(
                    f"Split at Antimeridian is not supported for {self.dggs_type} due to the current DGGRIDv8 bugs. "
                    "Disable Split at Antimeridian or choose another DGGS type."
                )
                return False
            if self.aggregate:
                feedback.reportWarning(
                    f"Aggregate is ignored for {self.dggs_type} "
                    "(antimeridian splitting is not available for this type)."
                )
                self.aggregate = False
        elif self.aggregate and not self.split_antimeridian:
            feedback.reportWarning(
                "Aggregate split cells requires Split at Antimeridian; "
                "Aggregate will be ignored."
            )
            self.aggregate = False

        return True

    def processAlgorithm(self, parameters, context, feedback):
        id_col = f"dggrid_{self.dggs_type.lower()}"
        dggs_type = self.dggs_type
        densification = self.densification
        layer_name = f"DGGRID_{dggs_type.upper()}"
        set_output_layer_name(parameters, self.OUTPUT, "DGGS_binning", layer_name)

        def validate_res(resolution):
            return validate_dggrid_resolution(dggs_type, resolution)

        def generate_grid(resolution, extent_layer, fb, **kwargs):
            return generate_dggrid_grid_qgis(
                dggs_type,
                resolution,
                extent_layer,
                feedback=fb,
                densification=densification,
                **kwargs,
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
            f"DGGRID {dggs_type}",
            validate_res,
            generate_grid,
            metric_kind="geodesic",
            grid_kwargs={
                "split_antimeridian": self.split_antimeridian,
                "aggregate": self.aggregate,
            },
        )
        apply_loaded_layer_name(
            context, result.get(self.OUTPUT), "DGGS_binning", layer_name
        )
        return result
