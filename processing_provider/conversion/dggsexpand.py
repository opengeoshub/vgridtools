# -*- coding: utf-8 -*-
__author__ = "Thang Quach"
__date__ = "2024-11-20"
__copyright__ = "(L) 2024, Thang Quach"

import os

from qgis.core import (
    Qgis,
    QgsProcessing,
    QgsProcessingParameterField,
    QgsProcessingParameterEnum,
    QgsProcessingParameterNumber,
    QgsProcessingParameterBoolean,
    QgsProcessingFeatureBasedAlgorithm,
    QgsProcessingException,
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
from ...utils.binning.bin_helper import apply_loaded_layer_name, set_output_layer_name
from ...utils.conversion.dggsexpand import *


class DGGSExpand(QgsProcessingFeatureBasedAlgorithm):
    INPUT = "INPUT"
    DGGS_FIELD = "DGGS_FIELD"
    DGGS_TYPE = "DGGS_TYPE"
    RESOLUTION = "RESOLUTION"
    DEPTH = "DEPTH"
    SHIFT_ANTIMERIDIAN = "SHIFT_ANTIMERIDIAN"
    SPLIT_ANTIMERIDIAN = "SPLIT_ANTIMERIDIAN"
    OUTPUT = "OUTPUT"

    DGGS_TYPES = [
        "H3",
        "S2",
        "A5",
        "rHEALPix",
        "ISEA4T",
        "ISEA3H",
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

    LOC = QgsApplication.locale()[:2]

    def translate(self, string):
        return QCoreApplication.translate("Processing", string)

    def tr(self, *string):
        if self.LOC == "vi":
            return string[1] if len(string) == 2 else self.translate(string[0])
        return self.translate(string[0])

    def name(self):
        return "dggsexpand"

    def displayName(self):
        return self.tr("DGGS Expand", "DGGS Expand")

    def group(self):
        return self.tr("Conversion", "Conversion")

    def groupId(self):
        return "conversion"

    def icon(self):
        return QIcon(
            os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "../images/conversion/dggsexpand.png",
            )
        )

    def tags(self):
        return self.tr(
            "DGGS, expand, H3,S2, A5, rHEALPix, ISEA4T, ISEA3H, QTM,OLC,Geohash,Tilecode,Quadkey,DIGIPIN,DGGAL_GNOSIS,DGGAL_ISEA4R,DGGAL_ISEA9R,DGGAL_ISEA3H,DGGAL_ISEA7H,DGGAL_ISEA7H_Z7,DGGAL_IVEA4R,DGGAL_IVEA9R,DGGAL_IVEA3H,DGGAL_IVEA7H,DGGAL_IVEA7H_Z7,DGGAL_RTEA4R,DGGAL_RTEA9R,DGGAL_RTEA3H,DGGAL_RTEA7H,DGGAL_RTEA7H_Z7,DGGAL_HEALPix,DGGAL_rHEALPix"
        ).split(",")

    txt_en = "DGGS Expand"
    txt_vi = "DGGS Expand"
    figure = "../images/tutorial/dggsexpand.png"

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
        return [QgsProcessing.TypeVector]

    def sourceFlags(self):
        # DGGS ID is the only input used; skip validity checks on input geometry.
        return Qgis.ProcessingFeatureSourceFlag.SkipGeometryValidityChecks

    def request(self):
        return QgsFeatureRequest().setFlags(Qgis.FeatureRequestFlag.NoGeometry)

    def inputParameterDescription(self):
        return self.tr("Input DGGS")

    def outputName(self):
        return self.tr("DGGS_expanded")

    def outputWkbType(self, input_wkb_type):
        return QgsWkbTypes.Polygon

    def supportInPlaceEdit(self, layer):
        return False

    def createInstance(self):
        return DGGSExpand()

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
                type=QgsProcessingParameterField.String,
            )
        )

        self.addParameter(
            QgsProcessingParameterNumber(
                self.RESOLUTION,
                self.tr(
                    "Resolution (if set, depth is ignored; -1 to use depth)"
                ),
                QgsProcessingParameterNumber.Integer,
                5,
                minValue=-1,
                maxValue=40,
            )
        )

        self.addParameter(
            QgsProcessingParameterNumber(
                self.DEPTH,
                self.tr(
                    "Expand depth (-1: unused, "
                    "1: children, 2: grandchildren,...)"
                ),
                QgsProcessingParameterNumber.Integer,
                defaultValue=-1,
                minValue=-1,
                maxValue=40,
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
        self.parameterAsEnum(parameters, self.DGGS_TYPE, context)
        resolution = self.parameterAsInt(parameters, self.RESOLUTION, context)
        depth = self.parameterAsInt(parameters, self.DEPTH, context)
        self.resolution = None if resolution < 0 else resolution
        self.depth = None if depth < 1 else depth
        if self.resolution is None and self.depth is None:
            raise QgsProcessingException(
                "Specify Resolution (>= 0) or Expand depth (>= 1). "
                "When Resolution is set, depth is ignored."
            )

        self.DGGS_TYPE_index = self.parameterAsEnum(parameters, self.DGGS_TYPE, context)
        self.dggs_type = self.DGGS_TYPES[self.DGGS_TYPE_index].lower()
        self.dggs_field = self.parameterAsString(parameters, self.DGGS_FIELD, context)
        self.shift_antimeridian = self.parameterAsBoolean(
            parameters, self.SHIFT_ANTIMERIDIAN, context
        )
        self.split_antimeridian = self.parameterAsBoolean(
            parameters, self.SPLIT_ANTIMERIDIAN, context
        )

        def _dggal_fn(dggal_type):
            return lambda layer, resolution, field, feedback, **kwargs: dggalexpand(
                layer, resolution, field, feedback, dggal_type, **kwargs
            )

        self.DGGS_TYPE_functions = {
            "h3": h3expand,
            "s2": s2expand,
            "a5": a5expand,
            "rhealpix": rhealpixexpand,
            "isea4t": isea4texpand,
            "isea3h": isea3hexpand,
            "qtm": qtmexpand,
            "olc": olcexpand,
            "geohash": geohashexpand,
            "tilecode": tilecodeexpand,
            "quadkey": quadkeyexpand,
            "digipin": digipinexpand,
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
        }

        return True

    def processAlgorithm(self, parameters, context, feedback):
        dggs_layer = self.parameterAsSource(parameters, self.INPUT, context)
        if dggs_layer is None:
            raise QgsProcessingException("Invalid input DGGS layer.")

        dggs_layer = attributes_only_source(
            dggs_layer, feedback=feedback, layer_name="dggs_expand_ids"
        )

        conversion_function = self.DGGS_TYPE_functions.get(self.dggs_type)

        if conversion_function is None:
            raise QgsProcessingException(
                f"No conversion function for DGGS type: {self.dggs_type}"
            )

        if self.resolution is not None:
            feedback.pushInfo(
                f"Expanding {self.dggs_type.upper()} to resolution {self.resolution}"
            )
        else:
            feedback.pushInfo(
                f"Expanding {self.dggs_type.upper()} by depth {self.depth}"
            )

        memory_layer = conversion_function(
            dggs_layer,
            self.resolution,
            self.dggs_field,
            feedback,
            shift_antimeridian=self.shift_antimeridian,
            split_antimeridian=self.split_antimeridian,
            depth=self.depth,
        )

        if not isinstance(memory_layer, QgsVectorLayer) or not memory_layer.isValid():
            raise QgsProcessingException(
                "Invalid output layer returned from conversion function."
            )

        layer_name = f"{self.DGGS_TYPES[self.DGGS_TYPE_index]}_expanded"
        set_output_layer_name(parameters, self.OUTPUT, "DGGS_expanded", layer_name)

        (sink, sink_id) = self.parameterAsSink(
            parameters,
            self.OUTPUT,
            context,
            memory_layer.fields(),
            memory_layer.wkbType(),
            memory_layer.crs(),
        )

        for feature in memory_layer.getFeatures():
            sink.addFeature(feature, QgsFeatureSink.FastInsert)

        apply_loaded_layer_name(context, sink_id, "DGGS_expanded", layer_name)
        return {self.OUTPUT: sink_id}
