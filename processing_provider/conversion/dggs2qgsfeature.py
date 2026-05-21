# -*- coding: utf-8 -*-
"""
dggs2qgsfeaure.py
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

from qgis.core import (
    QgsProcessing,
    QgsProcessingException,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterField,
    QgsProcessingFeatureBasedAlgorithm,
    QgsProcessingParameterEnum,
    QgsProcessingParameterNumber,
    QgsFeatureSink,
    QgsField,
    QgsFields,
    QgsWkbTypes,
    QgsCoordinateReferenceSystem,
)

from qgis.core import QgsApplication
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtCore import QCoreApplication, QVariant

import platform

from ...utils.help_footer import social_links_footer
from ...utils.conversion.dggs2qgsfeature import (
    a52qgsfeature,
    dggal2qgsfeature,
    digipin2qgsfeature,
    dggrid_batch2qgsfeatures,
    gars2qgsfeature,
    geohash2qgsfeature,
    georef2qgsfeature,
    h32qgsfeature,
    isea3h2qgsfeature,
    isea4t2qgsfeature,
    maidenhead2qgsfeature,
    mgrs2qgsfeature,
    olc2qgsfeature,
    qtm2qgsfeature,
    quadkey2qgsfeature,
    rhealpix2qgsfeature,
    s22qgsfeature,
    tilecode2qgsfeature,
)
from ...settings import settings


class CellID2DGGS(QgsProcessingFeatureBasedAlgorithm):
    """
    Algorithm to convert H3, S2, A5, rHEALPix,QTM, OLC/ OpenLocationCode/ Google Plus Code, Geohash,
        GEOREF, MGRS, Tilecode, Quadkey, Maidenhead, GARS grid cells
    """

    INPUT = "INPUT"
    CELL_ID = "CELL_ID"
    DGGS_TYPE = "DGGS_TYPE"
    RESOLUTION = "RESOLUTION"
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
        "DGGRID_SUPERFUND",
        "DGGRID_PLANETRISK",
        "DGGRID_ISEA3H",
        "DGGRID_ISEA4H",
        "DGGRID_ISEA4T",
        "DGGRID_ISEA4D",
        "DGGRID_ISEA43H",
        "DGGRID_ISEA7H",
        "DGGRID_IGEO7",
        "DGGRID_FULLER3H",
        "DGGRID_FULLER4H",
        "DGGRID_FULLER4T",
        "DGGRID_FULLER4D",
        "DGGRID_FULLER43H",
        "DGGRID_FULLER7H",
        "QTM",
        "OLC",
        "Geohash",
        "GEOREF",
        "MGRS",
        "Tilecode",
        "Quadkey",
        "Maidenhead",
        "GARS",
        "DIGIPIN",
    ]

    if platform.system() == "Windows":
        index = DGGS_TYPES.index("rHEALPix") + 1
        DGGS_TYPES[index:index] = ["ISEA4T", "ISEA3H"]

    OUTPUT = "OUTPUT"

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
        return CellID2DGGS()

    def name(self):
        return "cellid2dggs"

    def icon(self):
        return QIcon(
            os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "../images/conversion/cellid2dggs.svg",
            )
        )

    def displayName(self):
        return self.tr("Cell ID to DGGS", "Cell ID to DGGS")

    def group(self):
        return self.tr("Conversion", "Conversion")

    def groupId(self):
        return "conversion"

    def tags(self):
        return self.tr(
            "H3,S2,A5,rHEALPix,ISEA4T, ISEA3H, QTM,OLC,OpenLocationCode,Google Plus Code,Geohash,\
                        GEOREF,MGRS,Tilecode,Quadkey,Maidenhead,GARS"
        ).split(",")

    txt_en = "Cell ID to DGGS"
    txt_vi = "Cell ID to DGGS"
    figure = "../images/tutorial/cellid2dggs.png"

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
        return [QgsProcessing.TypeVector]

    def outputName(self):
        return self.tr("CellID2DGGS")

    def outputCrs(self, input_crs):
        return QgsCoordinateReferenceSystem("EPSG:4326")

    def outputWkbType(self, input_wkb_type):
        return QgsWkbTypes.Polygon

    def supportInPlaceEdit(self, layer):
        return False

    def initParameters(self, config=None):
        # Input layer
        param = QgsProcessingParameterFeatureSource(
            self.INPUT, self.tr("Input layer"), [QgsProcessing.TypeVector]
        )
        self.addParameter(param)

        # Cell ID
        param = QgsProcessingParameterField(
            self.CELL_ID,
            self.tr("Cell ID field"),
            type=QgsProcessingParameterField.String,
            parentLayerParameterName=self.INPUT,
        )
        self.addParameter(param)

        # DGGS Type
        param = QgsProcessingParameterEnum(
            self.DGGS_TYPE,
            self.tr("DGGS type"),
            options=self.DGGS_TYPES,
            defaultValue=0,
        )
        self.addParameter(param)

        default_dggs = self.DGGS_TYPES[0]
        _, _, default_res = settings.getResolution(default_dggs)
        self.addParameter(
            QgsProcessingParameterNumber(
                self.RESOLUTION,
                self.tr("Resolution (DGGRID)"),
                QgsProcessingParameterNumber.Integer,
                default_res,
                minValue=0,
                maxValue=40,
            )
        )

    def checkParameterValues(self, parameters, context):
        selected_dggs = self.DGGS_TYPES[
            self.parameterAsEnum(parameters, self.DGGS_TYPE, context)
        ]
        if not selected_dggs.startswith("DGGRID_"):
            return super().checkParameterValues(parameters, context)

        resolution_settings = settings.getResolution(selected_dggs)
        if resolution_settings is None:
            return (False, f"No resolution settings found for {selected_dggs}.")

        min_res, max_res, _ = resolution_settings
        res_value = self.parameterAsInt(parameters, self.RESOLUTION, context)
        if not (min_res <= res_value <= max_res):
            return (
                False,
                f"Resolution must be between {min_res} and {max_res} for {selected_dggs}.",
            )
        return super().checkParameterValues(parameters, context)

    def prepareAlgorithm(self, parameters, context, feedback):
        source = self.parameterAsSource(parameters, self.INPUT, context)
        self.total_features = source.featureCount()
        self.num_bad = 0

        self.cell_id_field = self.parameterAsString(parameters, self.CELL_ID, context)
        self.DGGS_TYPE_index = self.parameterAsEnum(parameters, self.DGGS_TYPE, context)
        self.resolution = self.parameterAsInt(parameters, self.RESOLUTION, context)
        self.DGGS_TYPE_functions = {
            "h3": h32qgsfeature,
            "s2": s22qgsfeature,
            "a5": a52qgsfeature,
            "rhealpix": rhealpix2qgsfeature,
            # 'ease': ease2qgsfeature, # prone to unexpected errors
            "dggal_gnosis": lambda feature, zone_id: dggal2qgsfeature(
                feature, zone_id, "gnosis"
            ),
            "dggal_isea4r": lambda feature, zone_id: dggal2qgsfeature(
                feature, zone_id, "isea4r"
            ),
            "dggal_isea9r": lambda feature, zone_id: dggal2qgsfeature(
                feature, zone_id, "isea9r"
            ),
            "dggal_isea3h": lambda feature, zone_id: dggal2qgsfeature(
                feature, zone_id, "isea3h"
            ),
            "dggal_isea7h": lambda feature, zone_id: dggal2qgsfeature(
                feature, zone_id, "isea7h"
            ),
            "dggal_isea7h_z7": lambda feature, zone_id: dggal2qgsfeature(
                feature, zone_id, "isea7h_z7"
            ),
            "dggal_ivea4r": lambda feature, zone_id: dggal2qgsfeature(
                feature, zone_id, "ivea4r"
            ),
            "dggal_ivea9r": lambda feature, zone_id: dggal2qgsfeature(
                feature, zone_id, "ivea9r"
            ),
            "dggal_ivea3h": lambda feature, zone_id: dggal2qgsfeature(
                feature, zone_id, "ivea3h"
            ),
            "dggal_ivea7h": lambda feature, zone_id: dggal2qgsfeature(
                feature, zone_id, "ivea7h"
            ),
            "dggal_ivea7h_z7": lambda feature, zone_id: dggal2qgsfeature(
                feature, zone_id, "ivea7h_z7"
            ),
            "dggal_rtea4r": lambda feature, zone_id: dggal2qgsfeature(
                feature, zone_id, "rtea4r"
            ),
            "dggal_rtea9r": lambda feature, zone_id: dggal2qgsfeature(
                feature, zone_id, "rtea9r"
            ),
            "dggal_rtea3h": lambda feature, zone_id: dggal2qgsfeature(
                feature, zone_id, "rtea3h"
            ),
            "dggal_rtea7h": lambda feature, zone_id: dggal2qgsfeature(
                feature, zone_id, "rtea7h"
            ),
            "dggal_rtea7h_z7": lambda feature, zone_id: dggal2qgsfeature(
                feature, zone_id, "rtea7h_z7"
            ),
            "dggal_healpix": lambda feature, zone_id: dggal2qgsfeature(
                feature, zone_id, "healpix"
            ),
            "dggal_rhealpix": lambda feature, zone_id: dggal2qgsfeature(
                feature, zone_id, "rhealpix"
            ),
            "qtm": qtm2qgsfeature,
            "olc": olc2qgsfeature,
            "geohash": geohash2qgsfeature,
            "georef": georef2qgsfeature,
            "mgrs": mgrs2qgsfeature,
            "tilecode": tilecode2qgsfeature,
            "quadkey": quadkey2qgsfeature,
            "maidenhead": maidenhead2qgsfeature,
            "gars": gars2qgsfeature,
            "digipin": digipin2qgsfeature,
        }

        self._dggrid_type_name = None
        dggs_key = self.DGGS_TYPES[self.DGGS_TYPE_index].lower()
        if dggs_key.startswith("dggrid_"):
            self._dggrid_type_name = self.DGGS_TYPES[self.DGGS_TYPE_index].replace(
                "DGGRID_", ""
            )

        if platform.system() == "Windows":
            self.DGGS_TYPE_functions["isea4t"] = isea4t2qgsfeature
            self.DGGS_TYPE_functions["isea3h"] = isea3h2qgsfeature

        return True

    def outputFields(self, input_fields):
        output_fields = QgsFields()

        # Preserve all original input fields
        for field in input_fields:
            output_fields.append(field)

        # Function to generate a unique field name by adding a suffix if necessary
        def get_unique_name(base_name):
            existing_names = {field.name() for field in output_fields}
            if base_name not in existing_names:
                return base_name
            i = 1
            while f"{base_name}_{i}" in existing_names:
                i += 1
            return f"{base_name}_{i}"

        dggs_type = self.DGGS_TYPES[self.DGGS_TYPE_index].lower()

        # Fields to be added
        new_fields = [
            QgsField(get_unique_name(dggs_type), QVariant.String),
            QgsField(get_unique_name("resolution"), QVariant.Int),
            QgsField(get_unique_name("center_lat"), QVariant.Double),
            QgsField(get_unique_name("center_lon"), QVariant.Double),
            QgsField(
                get_unique_name(
                    "avg_edge_len"
                    if dggs_type
                    in (
                        "h3",
                        "s2",
                        "a5",
                        "rhealpix",
                        "isea4t",
                        "isea3h",
                        "dggal_gnosis",
                        "dggal_isea4r",
                        "dggal_isea9r",
                        "dggal_isea7h",
                        "dggal_isea7h_z7",
                        "dggal_ivea4r",
                        "dggal_ivea9r",
                        "dggal_ivea3h",
                        "dggal_ivea7h",
                        "dggal_ivea7h_z7",
                        "dggal_rtea4r",
                        "dggal_rtea9r",
                        "dggal_rtea3h",
                        "dggal_rtea7h",
                        "dggal_rtea7h_z7",
                        "dggal_healpix",
                        "dggal_rhealpix",
                        "qtm",
                    )
                    or dggs_type.startswith("dggrid_")
                    else "cell_width"
                ),
                QVariant.Double,
            ),
            QgsField(get_unique_name("cell_height"), QVariant.Double)
            if dggs_type
            not in (
                "h3",
                "s2",
                "a5",
                "rhealpix",
                "isea4t",
                "isea3h",
                "dggal_gnosis",
                "dggal_isea4r",
                "dggal_isea9r",
                "dggal_isea7h",
                "dggal_isea7h_z7",
                "dggal_ivea4r",
                "dggal_ivea9r",
                "dggal_ivea3h",
                "dggal_ivea7h",
                "dggal_ivea7h_z7",
                "dggal_rtea4r",
                "dggal_rtea9r",
                "dggal_rtea3h",
                "dggal_rtea7h",
                "dggal_rtea7h_z7",
                "dggal_healpix",
                "dggal_rhealpix",
                "qtm",
            )
            and not dggs_type.startswith("dggrid_")
            else None,
            QgsField(get_unique_name("cell_area"), QVariant.Double),
            QgsField(get_unique_name("cell_perimeter"), QVariant.Double),
        ]

        # Append the fields to output_fields
        for field in new_fields:
            if field:
                output_fields.append(field)

        return output_fields

    def processFeature(self, feature, context, feedback):
        try:
            cell_id = feature[self.cell_id_field]
            DGGS_TYPE_key = self.DGGS_TYPES[self.DGGS_TYPE_index].lower()
            conversion_function = self.DGGS_TYPE_functions.get(DGGS_TYPE_key)
            cell_feature = conversion_function(feature, cell_id)
            if cell_feature:
                return [cell_feature]

        except Exception as e:
            self.num_bad += 1
            feedback.reportError(f"Error processing feature {feature.id()}: {str(e)}")
            return []

    def processAlgorithm(self, parameters, context, feedback):
        dggs_index = self.parameterAsEnum(parameters, self.DGGS_TYPE, context)
        if not self.DGGS_TYPES[dggs_index].startswith("DGGRID_"):
            return super().processAlgorithm(parameters, context, feedback)

        if not self.prepareAlgorithm(parameters, context, feedback):
            raise QgsProcessingException(self.invalidParameterTypes())

        source = self.parameterAsSource(parameters, self.INPUT, context)
        out_fields = self.outputFields(source.fields())
        input_features = []
        cell_ids = []
        for feat in source.getFeatures():
            if feedback.isCanceled():
                break
            input_features.append(feat)
            try:
                cell_ids.append(feat[self.cell_id_field])
            except Exception:
                cell_ids.append(None)

        if feedback:
            feedback.pushInfo(
                f"Read {len(input_features)} input feature(s); "
                f"cell ID field: {self.cell_id_field!r}."
            )

        out_features, batch_bad = dggrid_batch2qgsfeatures(
            input_features,
            cell_ids,
            self._dggrid_type_name,
            self.resolution,
            out_fields,
            feedback=feedback,
        )
        self.num_bad += batch_bad

        if feedback:
            feedback.pushInfo(
                f"Built {len(out_features)} output feature(s) "
                f"({batch_bad} failed to join)."
            )

        sink, dest_id = self.parameterAsSink(
            parameters,
            self.OUTPUT,
            context,
            out_fields,
            QgsWkbTypes.Polygon,
            QgsCoordinateReferenceSystem("EPSG:4326"),
        )

        for out_feat in out_features:
            if feedback.isCanceled():
                break
            sink.addFeature(out_feat, QgsFeatureSink.FastInsert)

        feedback.setProgress(100)
        return {self.OUTPUT: dest_id}

    def postProcessAlgorithm(self, context, feedback):
        if self.num_bad:
            feedback.pushInfo(
                self.tr(
                    "{} out of {} features had invalid parameters and were ignored.".format(
                        self.num_bad, self.total_features
                    )
                )
            )
        return {}
