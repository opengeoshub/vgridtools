# -*- coding: utf-8 -*-
"""
dggsagg.py
***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 2 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************
"""

__author__ = "Thang Quach"
__date__ = "2026-10-01"
__copyright__ = "(L) 2026, Thang Quach"

import os
import platform

from qgis.core import (
    QgsApplication,
    QgsFeatureSink,
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingParameterBoolean,
    QgsProcessingParameterEnum,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterField,
    QgsProcessingParameterNumber,
    QgsVectorLayer,
)
from qgis.PyQt.QtCore import QCoreApplication
from qgis.PyQt.QtGui import QIcon

from ...settings import settings
from ...utils.help_footer import social_links_footer
from ...utils.crs_helper import attributes_only_source
from ...utils.binning.bin_helper import (
    BIN_AGG,
    apply_loaded_layer_name,
    set_output_layer_name,
)
from ...utils.conversion.dggsagg import (
    a5agg,
    dggalagg,
    digipinagg,
    easeagg,
    geohashagg,
    h3agg,
    isea3hagg,
    isea4tagg,
    olcagg,
    qtmagg,
    quadkeyagg,
    rhealpixagg,
    s2agg,
    tilecodeagg,
)


class DGGSAggregate(QgsProcessingAlgorithm):
    """Roll DGGS cells up to a parent resolution and aggregate values there."""

    INPUT = "INPUT"
    CELL_ID = "CELL_ID"
    DGGS_TYPE = "DGGS_TYPE"
    RESOLUTION = "RESOLUTION"
    AGG = "AGG"
    NUMERIC_FIELD = "NUMERIC_FIELD"
    SHIFT_ANTIMERIDIAN = "SHIFT_ANTIMERIDIAN"
    SPLIT_ANTIMERIDIAN = "SPLIT_ANTIMERIDIAN"
    CELL_METRICS = "CELL_METRICS"
    OUTPUT = "OUTPUT"

    AGG_OPTIONS = BIN_AGG

    DGGS_TYPES = [
        "H3",
        "S2",
        "A5",
        "rHEALPix",
        "EASE",
        "DGGAL_GNOSIS",
        "DGGAL_ISEA4R",
        "DGGAL_ISEA9R",
        "DGGAL_ISEA3H",
        "DGGAL_ISEA7H",
        "DGGAL_ISEA7H_Z7",
        "DGGAL_IVEA4R",
        "DGGAL_IVEA9R",
        "DGGAL_IVEA3H",
        "DGGAL_IVEA7H",
        "DGGAL_IVEA7H_Z7",
        "DGGAL_RTEA4R",
        "DGGAL_RTEA9R",
        "DGGAL_RTEA3H",
        "DGGAL_RTEA7H",
        "DGGAL_RTEA7H_Z7",
        "DGGAL_HEALPix",
        "DGGAL_rHEALPix",
        "QTM",
        "OLC",
        "Geohash",
        "Tilecode",
        "Quadkey",
        "DIGIPIN",
    ]

    if platform.system() == "Windows":
        index = DGGS_TYPES.index("rHEALPix") + 1
        DGGS_TYPES[index:index] = ["ISEA4T", "ISEA3H"]

    LOC = QgsApplication.locale()[:2]

    def translate(self, string):
        return QCoreApplication.translate("Processing", string)

    def tr(self, *string):
        if self.LOC == "vi":
            return string[1] if len(string) == 2 else self.translate(string[0])
        return self.translate(string[0])

    def createInstance(self):
        return DGGSAggregate()

    def name(self):
        return "dggsagg"

    def displayName(self):
        return self.tr("DGGS Aggregate", "DGGS Aggregate")

    def group(self):
        return self.tr("Conversion", "Conversion")

    def groupId(self):
        return "conversion"

    def icon(self):
        return QIcon(
            os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "../images/conversion/aggregate.svg",
            )
        )

    def tags(self):
        return self.tr(
            "DGGS, aggregate, parent, roll up, H3, S2, A5, rHEALPix, ISEA4T, ISEA3H, "
            "EASE, DGGAL, QTM, OLC, Geohash, Tilecode, Quadkey, DIGIPIN"
        ).split(",")

    txt_en = (
        "Roll DGGS cells up to a parent resolution and aggregate values there. "
        "Every cell is assigned to its parent, even when sibling cells are missing "
        "(a group-by parent, not compaction)."
    )
    txt_vi = txt_en
    figure = "../images/tutorial/aggregate.png"

    def shortHelpString(self):
        footer = f"""<div align="center">
                      <img src="{os.path.join(os.path.dirname(os.path.dirname(__file__)), self.figure)}">
                    </div>
                    <div align="right">
                      <p><b>{self.tr("Author: Thang Quach", "Author: Thang Quach")}</b></p>
                      {social_links_footer()}
                    </div>"""
        return self.tr(self.txt_en, self.txt_vi) + footer

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.INPUT,
                self.tr("Input layer"),
                [QgsProcessing.SourceType.TypeVector],
            )
        )

        self.addParameter(
            QgsProcessingParameterField(
                self.CELL_ID,
                self.tr("Cell ID field"),
                type=QgsProcessingParameterField.DataType.String,
                parentLayerParameterName=self.INPUT,
            )
        )

        self.addParameter(
            QgsProcessingParameterEnum(
                self.DGGS_TYPE,
                self.tr("DGGS type"),
                options=self.DGGS_TYPES,
                defaultValue=0,
            )
        )

        self.addParameter(
            QgsProcessingParameterNumber(
                self.RESOLUTION,
                self.tr("Parent resolution"),
                QgsProcessingParameterNumber.Type.Integer,
                defaultValue=0,
                minValue=0,
                maxValue=40,
            )
        )

        self.addParameter(
            QgsProcessingParameterEnum(
                self.AGG,
                self.tr("Aggregate function"),
                options=self.AGG_OPTIONS,
                defaultValue=self.AGG_OPTIONS.index("count"),
            )
        )

        self.addParameter(
            QgsProcessingParameterField(
                self.NUMERIC_FIELD,
                self.tr("Numeric field (required when aggregate is not 'count')"),
                parentLayerParameterName=self.INPUT,
                optional=True,
                type=QgsProcessingParameterField.DataType.Numeric,
            )
        )

        self.addParameter(
            QgsProcessingParameterBoolean(
                self.SHIFT_ANTIMERIDIAN,
                self.tr("Shift at Antimeridian"),
                defaultValue=False,
            )
        )

        self.addParameter(
            QgsProcessingParameterBoolean(
                self.SPLIT_ANTIMERIDIAN,
                self.tr("Split at Antimeridian"),
                defaultValue=False,
            )
        )

        self.addParameter(
            QgsProcessingParameterBoolean(
                self.CELL_METRICS,
                self.tr("Compute cell metrics"),
                defaultValue=False,
            )
        )

        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT,
                self.tr("DGGS_aggregated"),
                QgsProcessing.SourceType.TypeVectorPolygon,
            )
        )

    def checkParameterValues(self, parameters, context):
        selected_dggs = self.DGGS_TYPES[
            self.parameterAsEnum(parameters, self.DGGS_TYPE, context)
        ]
        resolution_settings = settings.getResolution(selected_dggs)
        if resolution_settings is not None:
            min_res, max_res, _ = resolution_settings
            res_value = self.parameterAsInt(parameters, self.RESOLUTION, context)
            if not (min_res <= res_value <= max_res):
                return (
                    False,
                    f"Parent resolution must be between {min_res} and {max_res} "
                    f"for {selected_dggs}.",
                )

        agg = self.AGG_OPTIONS[self.parameterAsEnum(parameters, self.AGG, context)]
        numeric_field = self.parameterAsString(parameters, self.NUMERIC_FIELD, context)
        if agg != "count" and not numeric_field:
            return (
                False,
                "A numeric field is required for aggregate function other than 'count'.",
            )
        return super().checkParameterValues(parameters, context)

    def prepareAlgorithm(self, parameters, context, feedback):
        self.DGGS_TYPE_index = self.parameterAsEnum(parameters, self.DGGS_TYPE, context)
        self.dggs_type = self.DGGS_TYPES[self.DGGS_TYPE_index].lower()
        self.cell_id_field = self.parameterAsString(parameters, self.CELL_ID, context)
        self.resolution = self.parameterAsInt(parameters, self.RESOLUTION, context)
        self.agg = self.AGG_OPTIONS[self.parameterAsEnum(parameters, self.AGG, context)]
        self.numeric_field = (
            self.parameterAsString(parameters, self.NUMERIC_FIELD, context) or None
        )
        self.shift_antimeridian = self.parameterAsBoolean(
            parameters, self.SHIFT_ANTIMERIDIAN, context
        )
        self.split_antimeridian = self.parameterAsBoolean(
            parameters, self.SPLIT_ANTIMERIDIAN, context
        )
        self.cell_metrics = self.parameterAsBoolean(
            parameters, self.CELL_METRICS, context
        )
        def _dggal_fn(dggal_type):
            return lambda layer, field, resolution, feedback, **kwargs: dggalagg(
                layer, field, resolution, feedback, dggal_type, **kwargs
            )

        self.DGGS_TYPE_functions = {
            "h3": h3agg,
            "s2": s2agg,
            "a5": a5agg,
            "rhealpix": rhealpixagg,
            "isea4t": isea4tagg,
            "isea3h": isea3hagg,
            "ease": easeagg,
            "qtm": qtmagg,
            "olc": olcagg,
            "geohash": geohashagg,
            "tilecode": tilecodeagg,
            "quadkey": quadkeyagg,
            "digipin": digipinagg,
        }
        for dggs_name in self.DGGS_TYPES:
            if dggs_name.startswith("DGGAL_"):
                dggal_type = dggs_name[len("DGGAL_"):].lower()
                self.DGGS_TYPE_functions[f"dggal_{dggal_type}"] = _dggal_fn(dggal_type)
        return True

    def processAlgorithm(self, parameters, context, feedback):
        source = self.parameterAsSource(parameters, self.INPUT, context)
        if source is None:
            raise QgsProcessingException(self.invalidSourceError(parameters, self.INPUT))

        source = attributes_only_source(
            source, feedback=feedback, layer_name="dggs_agg_ids"
        )

        agg_function = self.DGGS_TYPE_functions.get(self.dggs_type)
        if agg_function is None:
            raise QgsProcessingException(
                f"No aggregate function for DGGS type: {self.dggs_type}"
            )

        feedback.pushInfo(
            f"Aggregating {self.dggs_type.upper()} to parent resolution {self.resolution}"
        )

        memory_layer = agg_function(
            source,
            self.cell_id_field,
            self.resolution,
            feedback,
            agg=self.agg,
            numeric_col=self.numeric_field,
            shift_antimeridian=self.shift_antimeridian,
            split_antimeridian=self.split_antimeridian,
            cell_metrics=self.cell_metrics,
            N_side=getattr(settings, "rhealpixNSide", 3),
        )

        if not isinstance(memory_layer, QgsVectorLayer) or not memory_layer.isValid():
            raise QgsProcessingException(
                "Invalid output layer returned from aggregate function."
            )

        layer_name = f"{self.DGGS_TYPES[self.DGGS_TYPE_index]}_{self.resolution}_agg"
        set_output_layer_name(parameters, self.OUTPUT, "DGGS_aggregated", layer_name)

        (sink, sink_id) = self.parameterAsSink(
            parameters,
            self.OUTPUT,
            context,
            memory_layer.fields(),
            memory_layer.wkbType(),
            memory_layer.crs(),
        )
        if sink is None:
            raise QgsProcessingException(self.invalidSinkError(parameters, self.OUTPUT))

        for feature in memory_layer.getFeatures():
            sink.addFeature(feature, QgsFeatureSink.Flag.FastInsert)

        apply_loaded_layer_name(context, sink_id, "DGGS_aggregated", layer_name)
        return {self.OUTPUT: sink_id}
