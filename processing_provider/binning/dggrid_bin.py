# -*- coding: utf-8 -*-
__author__ = "Thang Quach"
__date__ = "2024-11-20"
__copyright__ = "(L) 2024, Thang Quach"

import os

from qgis.core import (
    QgsApplication,
    QgsFields,
    QgsField,
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingParameterEnum,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterField,
    QgsProcessingParameterNumber,
    QgsProcessingParameterVectorDestination,
    QgsWkbTypes,
)
from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.PyQt.QtGui import QIcon
from vgrid.utils.constants import DGGRID_TYPES
from vgrid.utils.io import validate_dggrid_resolution

from ...settings import settings
from ...utils.binning.bin_helper import append_geodesic_metric_fields, dggrid_num_edges
from ...utils.binning.grid_bin_qgis import (
    TwoStepBinProgress,
    qgis_feature_source_to_gdf,
    silence_tqdm_for_qgis,
    write_vgrid_bin_to_sink,
)
from ...utils.dggrid_instance import (
    build_dggrid_options,
    dggrid_bin_qgis,
    get_plugin_dggrid_instance,
)
from ...utils.imgs import Imgs

_DGGS_TYPE_OPTIONS = list(DGGRID_TYPES.keys())
_DEFAULT_DGGS_TYPE = "ISEA3H"


class DGGRIDBin(QgsProcessingAlgorithm):
    INPUT = "INPUT"
    CATEGORY_FIELD = "CATEGORY_FIELD"
    NUMERIC_FIELD = "NUMERIC_FIELD"
    STATS = "STATS"
    DGGS_TYPE = "DGGS_TYPE"
    RESOLUTION = "RESOLUTION"
    OUTPUT = "OUTPUT"

    STATISTICS = [
        "count",
        "sum",
        "min",
        "max",
        "mean",
        "median",
        "std",
        "var",
        "range",
        "minority",
        "majority",
        "variety",
    ]

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
    figure = "../images/tutorial/bin_dggal.png"

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
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.INPUT,
                "Input point layer",
                [QgsProcessing.TypeVectorPoint],
            )
        )
        default_index = _DGGS_TYPE_OPTIONS.index(_DEFAULT_DGGS_TYPE)
        self.addParameter(
            QgsProcessingParameterEnum(
                self.DGGS_TYPE,
                self.tr("DGGS Type"),
                options=_DGGS_TYPE_OPTIONS,
                defaultValue=default_index,
            )
        )

        settings_key = f"DGGRID_{_DEFAULT_DGGS_TYPE}"
        min_res, max_res, default_res = settings.getResolution(settings_key)
        self.addParameter(
            QgsProcessingParameterNumber(
                self.RESOLUTION,
                self.tr("Resolution"),
                QgsProcessingParameterNumber.Integer,
                defaultValue=default_res,
                minValue=min_res,
                maxValue=max_res,
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
        self.dggs_type = _DGGS_TYPE_OPTIONS[dggs_type_index]

        self.resolution = self.parameterAsInt(parameters, self.RESOLUTION, context)
        self.resolution = validate_dggrid_resolution(self.dggs_type, self.resolution)

        self.numeric_field = self.parameterAsString(
            parameters, self.NUMERIC_FIELD, context
        )
        self.category_field = self.parameterAsString(
            parameters, self.CATEGORY_FIELD, context
        )

        if self.stats != "count" and not self.numeric_field:
            raise QgsProcessingException(
                "A numeric field is required for statistics other than 'count'."
            )
        return True

    def processAlgorithm(self, parameters, context, feedback):
        points_gdf = qgis_feature_source_to_gdf(self.point_layer, feedback=feedback)
        if points_gdf.empty:
            feedback.pushInfo("No point features to bin.")
            return self._empty_sink(parameters, context)

        progress = TwoStepBinProgress(feedback)
        with silence_tqdm_for_qgis():
            result_gdf = dggrid_bin_qgis(
                get_plugin_dggrid_instance(feedback=feedback),
                self.dggs_type,
                points_gdf,
                self.resolution,
                stats=self.stats,
                category=self.category_field or None,
                numeric_field=self.numeric_field or None,
                options=build_dggrid_options(settings.dggridDensificationSpinBox),
                feedback=feedback,
                progress=progress,
            )

        if result_gdf is None or result_gdf.empty:
            feedback.pushInfo("No DGGRID cells with points were found.")
            return self._empty_sink(parameters, context)

        id_field = f"dggrid_{self.dggs_type.lower()}"
        return write_vgrid_bin_to_sink(
            result_gdf,
            algorithm=self,
            parameters=parameters,
            context=context,
            output_param=self.OUTPUT,
            point_layer=self.point_layer,
            id_field=id_field,
            resolution=self.resolution,
            metric_kind="geodesic",
            num_edges_fn=lambda _cell_id, geom: dggrid_num_edges(geom),
            feedback=feedback,
            progress=progress,
        )

    def _empty_sink(self, parameters, context):
        id_field = f"dggrid_{self.dggs_type.lower()}"
        out_fields = QgsFields()
        out_fields.append(QgsField(id_field, QVariant.String))
        append_geodesic_metric_fields(out_fields)
        sink, dest_id = self.parameterAsSink(
            parameters,
            self.OUTPUT,
            context,
            out_fields,
            QgsWkbTypes.Polygon,
            self.point_layer.sourceCrs(),
        )
        return {self.OUTPUT: dest_id}
