# -*- coding: utf-8 -*-
__author__ = "Thang Quach"
__date__ = "2024-11-20"
__copyright__ = "(L) 2024, Thang Quach"

import os

from qgis.core import (
    QgsProcessing,
    QgsProcessingParameterFeatureSource,
    QgsProcessingFeatureBasedAlgorithm,
    QgsProcessingParameterEnum,
    QgsProcessingParameterNumber,
    QgsCoordinateReferenceSystem,
)

from qgis.core import QgsApplication
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtCore import QCoreApplication

from ...utils.imgs import Imgs
from vgrid.utils.geometry import shift_west, shift_east, shift_balanced
from shapely.geometry import shape
from qgis.core import QgsGeometry


class ShiftAntimeridian(QgsProcessingFeatureBasedAlgorithm):
    """
    Shift at antimeridian for (multi)polylines and (multi)polygons
    """

    INPUT = "INPUT"
    OUTPUT = "OUTPUT"
    WEST_SHIFT = "WEST_SHIFT"
    EAST_SHIFT = "EAST_SHIFT"
    BALANCED_SHIFT = "BALANCED_SHIFT"
    WEST_THRESHOLD = "WEST_THRESHOLD"
    EAST_THRESHOLD = "EAST_THRESHOLD"

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
        return ShiftAntimeridian()

    def name(self):
        return "shiftantimeridian"

    def icon(self):
        return QIcon(
            os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "../images/utils/shift_antimeridian.png",
            )
        )

    def displayName(self):
        return self.tr("Shift at Antimeridian", "Shift at Antimeridian")

    def group(self):
        return self.tr("Utils", "Utils")

    def groupId(self):
        return "utils"

    def tags(self):
        return self.tr(
            "antimeridian, fix, shift"
        ).split(",")

    txt_en = "Shift at Antimeridian"
    txt_vi = "Shift at Antimeridian"
    figure = "../images/tutorial/antimeridian.png"

    def shortHelpString(self):
        social_BW = Imgs().social_BW
        reference = (
            '''<div>
                      <p><b>'''
            + self.tr("Reference:", "Reference:")
            + '''</b> <a href="https://github.com/gadomski/antimeridian">antimeridian</a></p>
                    </div>'''
        )
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
        return self.tr(self.txt_en, self.txt_vi) + reference + footer

    def inputLayerTypes(self):
        return [QgsProcessing.TypeVectorPolygon, QgsProcessing.TypeVectorLine]

    def outputName(self):
        return self.tr("shift_antimeridian")

    def outputWkbType(self, input_wkb_type):
        return input_wkb_type

    def supportInPlaceEdit(self, layer):
        return False

    def initParameters(self, config=None):
        # Input vector layer
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.INPUT, self.tr("Input (multi)polygon layer with EPSG:4326 CRS"),[QgsProcessing.TypeVectorPolygon, QgsProcessing.TypeVectorLine]
            )
        )
        
        # Shift type parameter
        self.addParameter(
            QgsProcessingParameterEnum(
                self.WEST_SHIFT,
                self.tr("Shift Type", "Shift Type"),
                options=[
                    self.tr("West Shift", "West Shift"),
                    self.tr("East Shift", "East Shift"),
                    self.tr("Balanced Shift", "Balanced Shift")
                ],
                defaultValue=0,  # Default to West Shift
            )
        )
        
        # West threshold parameter
        self.addParameter(
            QgsProcessingParameterNumber(
                self.WEST_THRESHOLD,
                self.tr("West Threshold (degrees)", "West Threshold (degrees)"),
                type=QgsProcessingParameterNumber.Double,
                defaultValue=-130.0,
                minValue=-180.0,
                maxValue=180.0,
            )
        )
        
        # East threshold parameter
        self.addParameter(
            QgsProcessingParameterNumber(
                self.EAST_THRESHOLD,
                self.tr("East Threshold (degrees)", "East Threshold (degrees)"),
                type=QgsProcessingParameterNumber.Double,
                defaultValue=146.0,
                minValue=-180.0,
                maxValue=180.0,
            )
        )

    def prepareAlgorithm(self, parameters, context, feedback):
        source = self.parameterAsSource(parameters, self.INPUT, context)
        # Check CRS
        crs = source.sourceCrs() if hasattr(source, "sourceCrs") else None
        if crs is None:
            feedback.reportError(
                "Input layer CRS must be EPSG:4326."
            )
            return False
        wgs84 = QgsCoordinateReferenceSystem("EPSG:4326")
        if crs.authid() != wgs84.authid():
            feedback.reportError(
                "Input layer CRS must be EPSG:4326."
            )
            return False
        
        # Get shift type parameter
        self.shift_type = self.parameterAsEnum(parameters, self.WEST_SHIFT, context)
        
        # Get threshold parameters
        self.west_threshold = self.parameterAsDouble(parameters, self.WEST_THRESHOLD, context)
        self.east_threshold = self.parameterAsDouble(parameters, self.EAST_THRESHOLD, context)
        
        # Initialize counters
        self.num_bad = 0
        self.total_features = source.featureCount()
        
        return True

    def processFeature(self, feature, context, feedback):
        try:
            feature_geom = feature.geometry()
            
            shapely_geom = shape(feature_geom.__geo_interface__)
            
            # Apply shift based on shift type
            # 0 = WEST_SHIFT, 1 = EAST_SHIFT, 2 = BALANCED_SHIFT
            if self.shift_type == 0:  # WEST_SHIFT
                fixed_shape_dict = shift_west(shapely_geom, threshold=self.west_threshold)
            elif self.shift_type == 1:  # EAST_SHIFT
                fixed_shape_dict = shift_east(shapely_geom, threshold=self.east_threshold)
            else:  # BALANCED_SHIFT
                fixed_shape_dict = shift_balanced(shapely_geom, threshold_west=self.west_threshold, threshold_east=self.east_threshold)
            
            # Convert dict back to shapely geometry, then to QgsGeometry
            fixed_shapely_geom = shape(fixed_shape_dict)
            fixed_geom = QgsGeometry.fromWkt(fixed_shapely_geom.wkt)
            feature.setGeometry(fixed_geom)
        
            return [feature]

        except Exception as e:
            self.num_bad += 1
            feedback.reportError(f"Error processing feature {feature.id()}: {str(e)}")
            return []

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
