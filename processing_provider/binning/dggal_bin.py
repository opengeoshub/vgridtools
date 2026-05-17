# -*- coding: utf-8 -*-
__author__ = "Thang Quach"
__date__ = "2024-11-20"
__copyright__ = "(L) 2024, Thang Quach"

from qgis.core import (
    QgsApplication,
    QgsFeatureSink,
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterNumber,
    QgsFields,
    QgsField,
    QgsFeature,
    QgsGeometry,
    QgsWkbTypes,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterField,
    QgsProcessingParameterVectorDestination,
    QgsProcessingParameterEnum,
    QgsProcessingException,
)
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtCore import QCoreApplication
from qgis.PyQt.QtCore import QVariant
import os
from vgrid.utils.geometry import dggal_to_geo
from vgrid.utils.constants import DGGAL_TYPES
from vgrid.utils.io import validate_dggal_resolution
from vgrid.conversion.latlon2dggs import latlon2dggal
from ...utils.imgs import Imgs
from collections import defaultdict
from ...utils.binning.bin_helper import (
    append_bin_stat_fields,
    append_stats_value,
    get_default_stats_structure,
    stat_props_for_category,
)


class DGGALBin(QgsProcessingAlgorithm):
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
        # Translate to Vietnamese: arg[0] - English (translate), arg[1] - Vietnamese
        if self.LOC == "vi":
            if len(string) == 2:
                return string[1]
            else:
                return self.translate(string[0])
        else:
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
                [
                    QgsProcessing.TypeVectorPoint
                ],  # Ensures only point geometries are selectable
            )
        )
        param = QgsProcessingParameterEnum(
            self.DGGS_TYPE,
            self.tr("DGGS Type"),
            options=[key for key in DGGAL_TYPES.keys()],
            defaultValue="gnosis",
        )
        self.addParameter(param)

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
                type=QgsProcessingParameterField.Numeric,  # This limits to numeric fields only
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

        # Validate resolution for the selected DGGS type
        self.resolution = validate_dggal_resolution(self.dggs_type, self.resolution)

        if self.stats != "count" and not self.numeric_field:
            raise QgsProcessingException(
                "A numeric field is required for statistics other than 'count'."
            )
        return True

    def processAlgorithm(self, parameters, context, feedback):
        dggal_bins = defaultdict(lambda: defaultdict(get_default_stats_structure))
        dggal_geometries = {}

        total_points = self.point_layer.featureCount()
        feedback.setProgress(0)  # Initial progress value

        # Process each point and update progress
        for i, point_feature in enumerate(self.point_layer.getFeatures()):
            try:
                point = point_feature.geometry().asPoint()
            except:
                feedback.pushInfo(
                    f"Point feature {point_feature.id()} has invalid geometry and will be skipped"
                )
                continue

            dggal_id = latlon2dggal(
                self.dggs_type, point.y(), point.x(), self.resolution
            )
            props = point_feature.attributes()
            fields = self.point_layer.fields()
            props_dict = {fields[i].name(): props[i] for i in range(len(fields))}

            append_stats_value(
                dggal_bins,
                dggal_id,
                props_dict,
                self.stats,
                self.numeric_field,
                self.category_field,
            )

            # Update progress after each point is processed
            feedback.setProgress(int((i + 1) / total_points * 100))

        # Generate geometries and update progress
        total_dggal_bins = len(dggal_bins)
        for i, dggal_id in enumerate(dggal_bins.keys()):
            cell_polygon = dggal_to_geo(self.dggs_type, dggal_id)
            dggal_geometries[dggal_id] = cell_polygon

            # Update progress after each geometry is generated
            feedback.setProgress(int((i + 1) / total_dggal_bins * 100))

        # Prepare output fields
        out_fields = QgsFields()
        out_fields.append(QgsField(f"dggal_{self.dggs_type}", QVariant.String))

        all_categories = set()
        for bin_data in dggal_bins.values():
            all_categories.update(bin_data.keys())

        append_bin_stat_fields(
            out_fields,
            all_categories,
            self.stats,
            self.numeric_field,
            self.category_field,
        )

        # Create the sink for the output
        (sink, dest_id) = self.parameterAsSink(
            parameters,
            self.OUTPUT,
            context,
            out_fields,
            QgsWkbTypes.Polygon,
            self.point_layer.sourceCrs(),
        )

        # Process each dggal bin and update progress
        total_dggal_geometries = len(dggal_geometries)
        for i, (dggal_id, geom) in enumerate(dggal_geometries.items()):
            props = {}
            for cat in sorted(all_categories):
                values = dggal_bins[dggal_id].get(cat, get_default_stats_structure())
                props.update(
                    stat_props_for_category(
                        values,
                        self.stats,
                        self.numeric_field,
                        self.category_field,
                        cat,
                    )
                )

            dggal_feature = QgsFeature(out_fields)
            dggal_feature.setGeometry(QgsGeometry.fromWkt(geom.wkt))
            dggal_feature.setAttributes(
                [
                    props.get(f.name(), None)
                    if f.name() != f"dggal_{self.dggs_type}"
                    else dggal_id
                    for f in out_fields
                ]
            )
            sink.addFeature(dggal_feature, QgsFeatureSink.FastInsert)

            # Update progress after each dggal bin is processed
            feedback.setProgress(int((i + 1) / total_dggal_geometries * 100))

        return {self.OUTPUT: dest_id}
