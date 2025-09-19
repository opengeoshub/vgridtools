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
    QgsFields,
    QgsField,
    QgsFeature,
    QgsWkbTypes,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterVectorDestination,
    QgsProcessingParameterEnum,
    QgsProcessingException,
)
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtCore import QCoreApplication, QVariant
import os
import statistics
from collections import defaultdict, Counter
from shapely.geometry import shape
import json
from ...utils.imgs import Imgs
from ...utils.binning.bin_helper import append_stats_value, get_default_stats_structure


class PolygonBin(QgsProcessingAlgorithm):
    POINT_INPUT = "POINT_INPUT"
    POLYGON_INPUT = "POLYGON_INPUT"
    CATEGORY_FIELD = "CATEGORY_FIELD"
    NUMERIC_FIELD = "NUMERIC_FIELD"
    STATS = "STATS"
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
            return string[1] if len(string) == 2 else self.translate(string[0])
        else:
            return self.translate(string[0])

    def createInstance(self):
        return PolygonBin()

    def name(self):
        return "bin_polygon"

    def icon(self):
        return QIcon(
            os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "../images/binning/bin_polygon.svg",
            )
        )

    def displayName(self):
        return self.tr("Polygon Bin", "Polygon Bin")

    def group(self):
        return self.tr("Binning", "Binning")

    def groupId(self):
        return "binning"

    def tags(self):
        return self.tr("DGGS, Polygon, Binning").split(",")

    txt_en = "Polygon Bin"
    txt_vi = "Polygon Bin"
    figure = "../images/tutorial/bin_h3.png"

    def shortHelpString(self):
        social_BW = Imgs().social_BW
        footer = f'''
        <div align="center">
          <img src="{os.path.join(os.path.dirname(os.path.dirname(__file__)), self.figure)}">
        </div>
        <div align="right">
          <p align="right">
          <b>{self.tr("Author: Thang Quach", "Author: Thang Quach")}</b>
          </p>{social_BW}
        </div>
        '''
        return self.tr(self.txt_en, self.txt_vi) + footer

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.POINT_INPUT, "Input point layer", [QgsProcessing.TypeVectorPoint]
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.POLYGON_INPUT,
                "Input polygon layer",
                [QgsProcessing.TypeVectorPolygon],
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
                parentLayerParameterName=self.POINT_INPUT,
                optional=True,
                type=QgsProcessingParameterField.Numeric,
            )
        )
        self.addParameter(
            QgsProcessingParameterField(
                self.CATEGORY_FIELD,
                "Category field",
                optional=True,
                parentLayerParameterName=self.POINT_INPUT,
            )
        )
        self.addParameter(
            QgsProcessingParameterVectorDestination(self.OUTPUT, "Polygon_binning")
        )

    def prepareAlgorithm(self, parameters, context, feedback):
        self.point_layer = self.parameterAsSource(parameters, self.POINT_INPUT, context)
        self.polygon_layer = self.parameterAsSource(
            parameters, self.POLYGON_INPUT, context
        )
        self.stats_index = self.parameterAsEnum(parameters, self.STATS, context)
        self.stats = self.STATISTICS[self.stats_index]
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
        polygon_fields = self.polygon_layer.fields()
        fields = QgsFields(polygon_fields)

        all_categories = set()
        bin_results = {}

        total_polygons = self.polygon_layer.featureCount()
        feedback.setProgress(0)

        for i, polygon_feature in enumerate(self.polygon_layer.getFeatures()):
            try:
                poly_geom = shape(json.loads(polygon_feature.geometry().asJson()))
            except:
                feedback.pushInfo(
                    f"Polygon feature {polygon_feature.id()} has invalid geometry and will be skipped"
                )
                continue

            bin_key = polygon_feature.id()
            bin_results[bin_key] = defaultdict(get_default_stats_structure)

            progress = int((i / total_polygons) * 100)
            feedback.setProgress(progress)

            for point_feature in self.point_layer.getFeatures():
                try:
                    pt_geom = shape(json.loads(point_feature.geometry().asJson()))
                except:
                    feedback.pushInfo(
                        f"Point feature {point_feature.id()} has invalid geometry and will be skipped"
                    )
                    continue

                if poly_geom.contains(pt_geom):
                    props = point_feature.attributes()
                    props_dict = {
                        self.point_layer.fields().at(i).name(): props[i]
                        for i in range(len(props))
                    }
                    append_stats_value(
                        bin_results,
                        bin_key,
                        props_dict,
                        self.stats,
                        self.numeric_field,
                        self.category_field,
                    )

            for cat in bin_results[bin_key].keys():
                all_categories.add(cat)

        for cat in sorted(all_categories):
            prefix = "" if not self.category_field else f"{cat}_"
            if self.stats == "count":
                fields.append(QgsField(f"{prefix}count", QVariant.Int))
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
                fields.append(QgsField(f"{prefix}{self.stats}", QVariant.Double))
            elif self.stats in ["minority", "majority"]:
                fields.append(QgsField(f"{prefix}{self.stats}", QVariant.String))
            elif self.stats == "variety":
                fields.append(QgsField(f"{prefix}variety", QVariant.Int))

        (sink, dest_id) = self.parameterAsSink(
            parameters,
            self.OUTPUT,
            context,
            fields,
            QgsWkbTypes.Polygon,
            self.polygon_layer.sourceCrs(),
        )

        for i, polygon_feature in enumerate(self.polygon_layer.getFeatures()):
            geom = polygon_feature.geometry()
            bin_key = polygon_feature.id()
            props = polygon_feature.attributes()
            attr_dict = {f.name(): props[i] for i, f in enumerate(polygon_fields)}

            for cat in sorted(all_categories):
                prefix = "" if not self.category_field else f"{cat}_"
                values = bin_results.get(bin_key, {}).get(
                    cat, get_default_stats_structure()
                )

                if self.stats == "count":
                    attr_dict[f"{prefix}count"] = values["count"]
                elif self.stats == "sum":
                    attr_dict[f"{prefix}sum"] = (
                        sum(values["sum"]) if values["sum"] else None
                    )
                elif self.stats == "min":
                    attr_dict[f"{prefix}min"] = (
                        min(values["min"]) if values["min"] else None
                    )
                elif self.stats == "max":
                    attr_dict[f"{prefix}max"] = (
                        max(values["max"]) if values["max"] else None
                    )
                elif self.stats == "mean":
                    attr_dict[f"{prefix}mean"] = (
                        statistics.mean(values["mean"]) if values["mean"] else None
                    )
                elif self.stats == "median":
                    attr_dict[f"{prefix}median"] = (
                        statistics.median(values["median"])
                        if values["median"]
                        else None
                    )
                elif self.stats == "std":
                    attr_dict[f"{prefix}std"] = (
                        statistics.stdev(values["std"]) if len(values["std"]) > 1 else 0
                    )
                elif self.stats == "var":
                    attr_dict[f"{prefix}var"] = (
                        statistics.variance(values["var"])
                        if len(values["var"]) > 1
                        else 0
                    )
                elif self.stats == "range":
                    attr_dict[f"{prefix}range"] = (
                        max(values["range"]) - min(values["range"])
                        if values["range"]
                        else 0
                    )
                elif self.stats == "minority":
                    freq = Counter(values["values"])
                    attr_dict[f"{prefix}minority"] = (
                        min(freq.items(), key=lambda x: x[1])[0] if freq else None
                    )
                elif self.stats == "majority":
                    freq = Counter(values["values"])
                    attr_dict[f"{prefix}majority"] = (
                        max(freq.items(), key=lambda x: x[1])[0] if freq else None
                    )
                elif self.stats == "variety":
                    attr_dict[f"{prefix}variety"] = len(set(values["values"]))

            out_feature = QgsFeature(fields)
            out_feature.setGeometry(geom)
            out_feature.setAttributes([attr_dict.get(f.name(), None) for f in fields])
            sink.addFeature(out_feature, QgsFeatureSink.FastInsert)

        return {self.OUTPUT: dest_id}
