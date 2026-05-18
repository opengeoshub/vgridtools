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
from collections import defaultdict
from ...utils.imgs import Imgs
from ...utils.binning.bin_helper import (
    append_bin_stat_fields,
    append_geodesic_metric_fields,
    append_stats_value,
    build_bin_feature_props,
    feature_attributes,
    get_default_stats_structure,
)
from ...settings import settings

from vgrid.conversion.latlon2dggs import latlon2rhealpix
from vgrid.dggs.rhealpixdggs.dggs import RHEALPixDGGS
from vgrid.dggs.rhealpixdggs.ellipsoids import WGS84_ELLIPSOID
from vgrid.conversion.dggs2geo.rhealpix2geo import rhealpix2geo


class rHEALPixBin(QgsProcessingAlgorithm):
    INPUT = "INPUT"
    CATEGORY_FIELD = "CATEGORY_FIELD"
    NUMERIC_FIELD = "NUMERIC_FIELD"
    STATS = "STATS"
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
        return rHEALPixBin()

    def name(self):
        return "bin_rhealpix"

    def icon(self):
        return QIcon(
            os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "../images/generator/grid_rhealpix.svg",
            )
        )

    def displayName(self):
        return self.tr("rHEALPix Bin", "rHEALPix Bin")

    def group(self):
        return self.tr("Binning", "Binning")

    def groupId(self):
        return "binning"

    def tags(self):
        return self.tr("DGGS, rHEALPix, Binning").split(",")

    txt_en = "rHEALPix Bin"
    txt_vi = "rHEALPix Bin"
    figure = "../images/tutorial/bin_rhealpix.png"

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
                type=QgsProcessingParameterField.Numeric,  # 🔥 This limits to numeric fields only
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

        min_res, max_res, default_res = settings.getResolution("rHEALPix")
        self.addParameter(
            QgsProcessingParameterNumber(
                self.RESOLUTION,
                self.tr(f"Resolution [{min_res}..{max_res}]"),
                QgsProcessingParameterNumber.Integer,
                defaultValue=default_res,
                minValue=min_res,
                maxValue=max_res,
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
        self.resolution = self.parameterAsInt(parameters, self.RESOLUTION, context)
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
        E = WGS84_ELLIPSOID
        rhealpix_dggs = RHEALPixDGGS(
            ellipsoid=E, north_square=1, south_square=3, N_side=3
        )

        rhealpix_bins = defaultdict(lambda: defaultdict(get_default_stats_structure))
        rhealpix_geometries = {}

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

            rhealpix_id = latlon2rhealpix(point.y(), point.x(), self.resolution)
            props = point_feature.attributes()
            fields = self.point_layer.fields()
            props_dict = {fields[i].name(): props[i] for i in range(len(fields))}

            append_stats_value(
                rhealpix_bins,
                rhealpix_id,
                props_dict,
                self.stats,
                self.numeric_field,
                self.category_field,
            )

            # Update progress after each point is processed
            feedback.setProgress(int((i + 1) / total_points * 100))

        # Generate geometries and update progress
        total_rhealpix_bins = len(rhealpix_bins)
        for i, rhealpix_id in enumerate(rhealpix_bins.keys()):
            cell_polygon = rhealpix2geo(rhealpix_id)
            rhealpix_geometries[rhealpix_id] = cell_polygon
            # Update progress after each geometry is generated
            feedback.setProgress(int((i + 1) / total_rhealpix_bins * 100))

        # Prepare output fields
        out_fields = QgsFields()
        out_fields.append(QgsField("rhealpix", QVariant.String))
        append_geodesic_metric_fields(out_fields)

        all_categories = set()
        for bin_data in rhealpix_bins.values():
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

        # Process each rhealpix bin and update progress
        total_rhealpix_geometries = len(rhealpix_geometries)
        for i, (rhealpix_id, geom) in enumerate(rhealpix_geometries.items()):
            props = build_bin_feature_props(
                geom,
                self.resolution,
                "rhealpix",
                rhealpix_id,
                rhealpix_bins,
                all_categories,
                self.stats,
                self.numeric_field,
                self.category_field,
                rhealpix_dggs=rhealpix_dggs,
            )
            rhealpix_feature = QgsFeature(out_fields)
            rhealpix_feature.setGeometry(QgsGeometry.fromWkt(geom.wkt))
            rhealpix_feature.setAttributes(feature_attributes(out_fields, props))
            sink.addFeature(rhealpix_feature, QgsFeatureSink.FastInsert)

            # Update progress after each rhealpix bin is processed
            feedback.setProgress(int((i + 1) / total_rhealpix_geometries * 100))

        return {self.OUTPUT: dest_id}
