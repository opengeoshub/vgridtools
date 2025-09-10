# -*- coding: utf-8 -*-
__author__ = "Thang Quach"
__date__ = "2024-11-20"
__copyright__ = "(L) 2024, Thang Quach"

from qgis.core import (
    QgsApplication,
    QgsFeatureSink,
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterField,
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
from qgis.PyQt.QtCore import QCoreApplication, QSettings, Qt
from PyQt5.QtCore import QVariant
import os, statistics
from shapely.geometry import Polygon
from ...utils.imgs import Imgs
from collections import defaultdict, Counter
from ...utils.binning.bin_helper import append_stats_value, get_default_stats_structure
from ...settings import settings
from vgrid.dggs import olc
from vgrid.conversion.latlon2dggs import latlon2olc


class OLCBin(QgsProcessingAlgorithm):
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
        return OLCBin()

    def name(self):
        return "bin_olc"

    def icon(self):
        return QIcon(
            os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "../images/generator/grid_olc.svg",
            )
        )

    def displayName(self):
        return self.tr("OLC Bin", "OLC Bin")

    def group(self):
        return self.tr("Binning", "Binning")

    def groupId(self):
        return "binning"

    def tags(self):
        return self.tr("DGGS, OLC, Binning").split(",")

    txt_en = "OLC Bin"
    txt_vi = "OLC Bin"
    figure = "../images/tutorial/bin_olc.png"

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

        min_res, max_res, default_res = settings.getResolution("OLC")
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

        if self.resolution not in [2, 4, 6, 8, 10, 11, 12, 13, 14, 15]:
            feedback.reportError(
                "Please select a resolution in [2, 4, 6, 8, 10..15] and try again."
            )
            return False

        if self.stats != "count" and not self.numeric_field:
            raise QgsProcessingException(
                "A numeric field is required for statistics other than 'count'."
            )

        return True

    def processAlgorithm(self, parameters, context, feedback):
        olc_bins = defaultdict(lambda: defaultdict(get_default_stats_structure))
        olc_geometries = {}

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

            olc_id = latlon2olc(point.y(), point.x(), self.resolution)
            props = point_feature.attributes()
            fields = self.point_layer.fields()
            props_dict = {fields[i].name(): props[i] for i in range(len(fields))}

            append_stats_value(
                olc_bins,
                olc_id,
                props_dict,
                self.stats,
                self.numeric_field,
                self.category_field,
            )

            # Update progress after each point is processed
            feedback.setProgress(int((i + 1) / total_points * 100))

        # Generate geometries and update progress
        total_olc_bins = len(olc_bins)
        for i, olc_id in enumerate(olc_bins.keys()):
            coord = olc.decode(olc_id)
            # Create the bounding box coordinates for the polygon
            min_lat, min_lon = coord.latitudeLo, coord.longitudeLo
            max_lat, max_lon = coord.latitudeHi, coord.longitudeHi
            # Define the polygon based on the bounding box
            cell_polygon = Polygon(
                [
                    [min_lon, min_lat],  # Bottom-left corner
                    [max_lon, min_lat],  # Bottom-right corner
                    [max_lon, max_lat],  # Top-right corner
                    [min_lon, max_lat],  # Top-left corner
                    [min_lon, min_lat],  # Closing the polygon (same as the first point)
                ]
            )

            olc_geometries[olc_id] = cell_polygon

            # Update progress after each geometry is generated
            feedback.setProgress(int((i + 1) / total_olc_bins * 100))

        # Prepare output fields
        out_fields = QgsFields()
        out_fields.append(QgsField("olc", QVariant.String))

        all_categories = set()
        for bin_data in olc_bins.values():
            all_categories.update(bin_data.keys())

        for cat in sorted(all_categories):
            prefix = "" if not self.category_field else f"{cat}_"

            if self.stats == "count":
                out_fields.append(QgsField(f"{prefix}count", QVariant.Int))
            elif self.stats in [
                "sum",
                "mean",
                "min",
                "max",
                "median",
                "std",
                "var",
                "range",
            ]:
                out_fields.append(QgsField(f"{prefix}{self.stats}", QVariant.Double))
            elif self.stats in ["minority", "majority"]:
                out_fields.append(QgsField(f"{prefix}{self.stats}", QVariant.String))
            elif self.stats == "variety":
                out_fields.append(QgsField(f"{prefix}variety", QVariant.Int))

        # Create the sink for the output
        (sink, dest_id) = self.parameterAsSink(
            parameters,
            self.OUTPUT,
            context,
            out_fields,
            QgsWkbTypes.Polygon,
            self.point_layer.sourceCrs(),
        )

        # Process each olc bin and update progress
        total_olc_geometries = len(olc_geometries)
        for i, (olc_id, geom) in enumerate(olc_geometries.items()):
            props = {}
            for cat in sorted(all_categories):
                prefix = "" if not self.category_field else f"{cat}_"
                values = olc_bins[olc_id].get(cat, get_default_stats_structure())

                if self.stats == "count":
                    props[f"{prefix}count"] = values["count"]
                elif self.stats == "sum":
                    props[f"{prefix}sum"] = (
                        sum(values["sum"]) if values["sum"] else None
                    )
                elif self.stats == "min":
                    props[f"{prefix}min"] = (
                        min(values["min"]) if values["min"] else None
                    )
                elif self.stats == "max":
                    props[f"{prefix}max"] = (
                        max(values["max"]) if values["max"] else None
                    )
                elif self.stats == "mean":
                    props[f"{prefix}mean"] = (
                        statistics.mean(values["mean"]) if values["mean"] else None
                    )
                elif self.stats == "median":
                    props[f"{prefix}median"] = (
                        statistics.median(values["median"])
                        if values["median"]
                        else None
                    )
                elif self.stats == "std":
                    props[f"{prefix}std"] = (
                        statistics.stdev(values["std"]) if len(values["std"]) > 1 else 0
                    )
                elif self.stats == "var":
                    props[f"{prefix}var"] = (
                        statistics.variance(values["var"])
                        if len(values["var"]) > 1
                        else 0
                    )
                elif self.stats == "range":
                    props[f"{prefix}range"] = (
                        max(values["range"]) - min(values["range"])
                        if values["range"]
                        else 0
                    )
                elif self.stats == "minority":
                    freq = Counter(values["values"])
                    props[f"{prefix}minority"] = (
                        min(freq.items(), key=lambda x: x[1])[0] if freq else None
                    )
                elif self.stats == "majority":
                    freq = Counter(values["values"])
                    props[f"{prefix}majority"] = (
                        max(freq.items(), key=lambda x: x[1])[0] if freq else None
                    )
                elif self.stats == "variety":
                    props[f"{prefix}variety"] = len(set(values["values"]))

            olc_feature = QgsFeature(out_fields)
            olc_feature.setGeometry(QgsGeometry.fromWkt(geom.wkt))
            olc_feature.setAttributes(
                [
                    props.get(f.name(), None) if f.name() != "olc" else olc_id
                    for f in out_fields
                ]
            )
            sink.addFeature(olc_feature, QgsFeatureSink.FastInsert)

            # Update progress after each olc bin is processed
            feedback.setProgress(int((i + 1) / total_olc_geometries * 100))

        return {self.OUTPUT: dest_id}
