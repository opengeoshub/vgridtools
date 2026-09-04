# -*- coding: utf-8 -*-
"""
dggscompact.py
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
__date__ = "2024-11-20"
__copyright__ = "(L) 2024, Thang Quach"

import os
import platform

from qgis.core import (
    Qgis,
    QgsProcessing,
    QgsProcessingParameterEnum,
    QgsProcessingParameterField,
    QgsProcessingParameterNumber,
    QgsProcessingParameterBoolean,
    QgsProcessingFeatureBasedAlgorithm,
    QgsProcessingException,
    NULL,
    QgsFeatureRequest,
    QgsWkbTypes,
    QgsApplication,
    QgsVectorLayer,
    QgsFeatureSink,
)

from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtCore import QCoreApplication

from ...utils.help_footer import social_links_footer
from ...utils.crs_helper import attributes_only_source
from ...utils.binning.bin_helper import (
    BIN_AGG,
    apply_loaded_layer_name,
    set_output_layer_name,
)
from ...utils.conversion.dggscompact import *


class DGGSCompact(QgsProcessingFeatureBasedAlgorithm):
    INPUT = "INPUT"
    DGGS_FIELD = "DGGS_FIELD"
    DGGS_TYPE = "DGGS_TYPE"
    DEPTH = "DEPTH"
    AGG = "AGG"
    NUMERIC_FIELD = "NUMERIC_FIELD"
    SHIFT_ANTIMERIDIAN = "SHIFT_ANTIMERIDIAN"
    SPLIT_ANTIMERIDIAN = "SPLIT_ANTIMERIDIAN"
    OUTPUT = "OUTPUT"

    AGG_OPTIONS = BIN_AGG

    DGGS_TYPES = [
        "H3",
        "S2",
        "A5",
        "rHEALPix",
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

    def name(self):
        return "dggscompact"

    def displayName(self):
        return self.tr("DGGS Compact", "DGGS Compact")

    def group(self):
        return self.tr("Conversion", "Conversion")

    def groupId(self):
        return "conversion"

    def icon(self):
        return QIcon(
            os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "../images/conversion/dggscompact.png",
            )
        )

    def tags(self):
        return self.tr(
            "DGGS, compact, H3,S2, rHEALPix, ISEA4T, ISEA3H, QTM,OLC,Geohash,Tilecode,Quadkey,DGGAL_GNOSIS,DGGAL_ISEA3H,DGGAL_ISEA9R,DGGAL_IVEA3H,DGGAL_IVEA9R,DGGAL_RTEA3H,DGGAL_RTEA9R"
        ).split(",")

    txt_en = "DGGS Compact"
    txt_vi = "DGGS Compact"
    figure = "../images/tutorial/dggscompact.png"

    def shortHelpString(self):
        footer = f'''<div align="center">
                      <img src="{os.path.join(os.path.dirname(os.path.dirname(__file__)), self.figure)}">
                    </div>
                    <div align="right">
                      <p><b>{self.tr("Author: Thang Quach", "Author: Thang Quach")}</b></p>
                      {social_links_footer()}
                    </div>'''
        return self.tr(self.txt_en, self.txt_vi) + footer

    def inputLayerTypes(self):
        return [QgsProcessing.SourceType.TypeVector]

    def sourceFlags(self):
        # DGGS ID is the only input used; skip validity checks on input geometry.
        return Qgis.ProcessingFeatureSourceFlag.SkipGeometryValidityChecks

    def request(self):
        return QgsFeatureRequest().setFlags(Qgis.FeatureRequestFlag.NoGeometry)

    def inputParameterDescription(self):
        return self.tr("Input DGGS")

    def outputName(self):
        return self.tr("DGGS_compacted")

    def outputWkbType(self, input_wkb_type):
        return QgsWkbTypes.Type.Polygon

    def supportInPlaceEdit(self, layer):
        return False

    def createInstance(self):
        return DGGSCompact()

    def initParameters(self, config=None):
        # INPUT is provided by QgsProcessingFeatureBasedAlgorithm
        # (includes native "Selected features only").
        self.addParameter(
            QgsProcessingParameterEnum(
                self.DGGS_TYPE, "DGGS Type", options=self.DGGS_TYPES, defaultValue=0
            )
        )

        self.addParameter(
            QgsProcessingParameterField(
                self.DGGS_FIELD,
                "DGGS ID",
                parentLayerParameterName=self.INPUT,
                type=QgsProcessingParameterField.DataType.String,
            )
        )

        self.addParameter(
            QgsProcessingParameterNumber(
                self.DEPTH,
                self.tr(
                    "Compact depth (-1: full compact, "
                    "1: parent, 2: grandparent,...)"
                ),
                QgsProcessingParameterNumber.Type.Integer,
                defaultValue=-1,
                minValue=-1,
                maxValue=40,
            )
        )

        self.addParameter(
            QgsProcessingParameterEnum(
                self.AGG,
                self.tr(
                    "Aggregate function (optional; leave unset to compact without aggregating)"
                ),
                options=self.AGG_OPTIONS,
                optional=True,
                defaultValue=None,
            )
        )

        self.addParameter(
            QgsProcessingParameterField(
                self.NUMERIC_FIELD,
                self.tr(
                    "Numeric field (required when aggregate is not 'count')"
                ),
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

    def prepareAlgorithm(self, parameters, context, feedback):
        self.DGGS_TYPE_index = self.parameterAsEnum(parameters, self.DGGS_TYPE, context)
        self.dggs_type = self.DGGS_TYPES[self.DGGS_TYPE_index].lower()
        self.dggs_field = self.parameterAsString(parameters, self.DGGS_FIELD, context)
        self.depth = self.parameterAsInt(parameters, self.DEPTH, context)
        raw_agg = parameters.get(self.AGG)
        if raw_agg is None or raw_agg == NULL or raw_agg == "" or raw_agg == -1:
            self.agg = None
        else:
            agg_idx = self.parameterAsEnum(parameters, self.AGG, context)
            self.agg = (
                self.AGG_OPTIONS[agg_idx]
                if 0 <= agg_idx < len(self.AGG_OPTIONS)
                else None
            )
        self.numeric_field = (
            self.parameterAsString(parameters, self.NUMERIC_FIELD, context) or None
        )
        if self.agg and self.agg != "count" and not self.numeric_field:
            raise QgsProcessingException(
                "A numeric field is required for aggregate function other than 'count'."
            )
        self.shift_antimeridian = self.parameterAsBoolean(
            parameters, self.SHIFT_ANTIMERIDIAN, context
        )
        self.split_antimeridian = self.parameterAsBoolean(
            parameters, self.SPLIT_ANTIMERIDIAN, context
        )

        def _dggal_fn(dggal_type):
            return lambda layer, field, feedback, **kwargs: dggalcompact(
                layer, field, feedback, dggal_type, **kwargs
            )

        self.DGGS_TYPE_functions = {
            "h3": h3compact,
            "s2": s2compact,
            "a5": a5compact,
            "rhealpix": rhealpixcompact,
            "qtm": qtmcompact,
            "olc": olccompact,
            "geohash": geohashcompact,
            "tilecode": tilecodecompact,
            "quadkey": quadkeycompact,
            "dggal_gnosis": _dggal_fn("gnosis"),
            "dggal_isea4r": _dggal_fn("isea4r"),
            "dggal_isea9r": _dggal_fn("isea9r"),
            "dggal_isea3h": _dggal_fn("isea3h"),
            "dggal_isea7h": _dggal_fn("isea7h"),
            "dggal_isea7h_z7": _dggal_fn("isea7h_z7"),
            "dggal_ivea4r": _dggal_fn("ivea4r"),
            "dggal_ivea9r": _dggal_fn("ivea9r"),
            "dggal_ivea3h": _dggal_fn("ivea3h"),
            "dggal_ivea7h": _dggal_fn("ivea7h"),
            "dggal_ivea7h_z7": _dggal_fn("ivea7h_z7"),
            "dggal_rtea4r": _dggal_fn("rtea4r"),
            "dggal_rtea9r": _dggal_fn("rtea9r"),
            "dggal_rtea3h": _dggal_fn("rtea3h"),
            "dggal_rtea7h": _dggal_fn("rtea7h"),
            "dggal_rtea7h_z7": _dggal_fn("rtea7h_z7"),
            "dggal_healpix": _dggal_fn("healpix"),
            "dggal_rhealpix": _dggal_fn("rhealpix"),
            "digipin": digipincompact,
        }
        if platform.system() == "Windows":
            self.DGGS_TYPE_functions["isea4t"] = isea4tcompact
            self.DGGS_TYPE_functions["isea3h"] = isea3hcompact
        return True

    def processAlgorithm(self, parameters, context, feedback):
        dggs_layer = self.parameterAsSource(parameters, self.INPUT, context)
        if dggs_layer is None:
            raise QgsProcessingException("Invalid input DGGS layer.")

        dggs_layer = attributes_only_source(
            dggs_layer, feedback=feedback, layer_name="dggs_compact_ids"
        )

        conversion_function = self.DGGS_TYPE_functions.get(self.dggs_type)

        if conversion_function is None:
            raise QgsProcessingException(
                f"No compact function for DGGS type: {self.dggs_type}"
            )

        feedback.pushInfo(f"Compacting {self.dggs_type.upper()}")

        memory_layer = conversion_function(
            dggs_layer,
            self.dggs_field,
            feedback,
            depth=self.depth,
            agg=self.agg,
            numeric_col=self.numeric_field,
            shift_antimeridian=self.shift_antimeridian,
            split_antimeridian=self.split_antimeridian,
        )

        if not isinstance(memory_layer, QgsVectorLayer) or not memory_layer.isValid():
            raise QgsProcessingException(
                "Invalid output layer returned from compact function."
            )

        layer_name = f"{self.DGGS_TYPES[self.DGGS_TYPE_index]}_compacted"
        set_output_layer_name(parameters, self.OUTPUT, "DGGS_compacted", layer_name)

        (sink, sink_id) = self.parameterAsSink(
            parameters,
            self.OUTPUT,
            context,
            memory_layer.fields(),
            memory_layer.wkbType(),
            memory_layer.crs(),
        )

        for feature in memory_layer.getFeatures():
            sink.addFeature(feature, QgsFeatureSink.Flag.FastInsert)

        apply_loaded_layer_name(context, sink_id, "DGGS_compacted", layer_name)
        return {self.OUTPUT: sink_id}
