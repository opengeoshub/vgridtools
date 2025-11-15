# -*- coding: utf-8 -*-
__author__ = "Thang Quach"
__date__ = "2024-11-20"
__copyright__ = "(L) 2024, Thang Quach"

import os

from qgis.core import (
    QgsProcessing,
    QgsProcessingParameterFeatureSource,
    QgsProcessingFeatureBasedAlgorithm,
    QgsProcessingParameterBoolean,
    QgsCoordinateReferenceSystem,
)

from qgis.core import QgsApplication
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtCore import QCoreApplication

from ...utils.imgs import Imgs
from vgrid.utils.geometry import check_crossing_geom
from vgrid.utils.antimeridian import fix_shape
from shapely.geometry import shape
from qgis.core import QgsGeometry


class SplitAltimeridian(QgsProcessingFeatureBasedAlgorithm):
    """
    Split at antimeridian for (multi)polylines and (multi)polygons
    """

    INPUT = "INPUT"
    OUTPUT = "OUTPUT"
    FORCE_NORTH_POLE = "FORCE_NORTH_POLE"
    FORCE_SOUTH_POLE = "FORCE_SOUTH_POLE"
    FIX_WINDING = "FIX_WINDING"

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
        return SplitAltimeridian()

    def name(self):
        return "splitantimeridian"

    def icon(self):
        return QIcon(
            os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "../images/utils/antimeridian.svg",
            )
        )

    def displayName(self):
        return self.tr("Split at Antimeridian", "Split at Antimeridian")

    def group(self):
        return self.tr("Utils", "Utils")

    def groupId(self):
        return "utils"

    def tags(self):
        return self.tr(
            "antimeridian, fix, split"
        ).split(",")

    txt_en = "Split at Antimeridian"
    txt_vi = "Split at Antimeridian"
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
        return [QgsProcessing.TypeVectorPolygon]

    def outputName(self):
        return self.tr("split_antimeridian")

    def outputWkbType(self, input_wkb_type):
        return input_wkb_type

    def supportInPlaceEdit(self, layer):
        return False

    def initParameters(self, config=None):
        # Input vector layer
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.INPUT, self.tr("Input (multi)polygon layer with EPSG:4326 CRS"), [QgsProcessing.TypeVectorPolygon]
            )
        )
        
        # Fix winding
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.FIX_WINDING,
                self.tr("Fix winding", "Fix winding"),
                defaultValue=True,  
            )
        )

        # Force north pole parameter
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.FORCE_NORTH_POLE,
                self.tr("Force North pole", "Force North pole"),
                defaultValue=False,
            )
        )
        
        # Force south pole parameter
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.FORCE_SOUTH_POLE,
                self.tr("Force South pole", "Force South pole"),
                defaultValue=False,
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
        
        # Get boolean parameters
        self.force_north_pole = self.parameterAsBool(parameters, self.FORCE_NORTH_POLE, context)
        self.force_south_pole = self.parameterAsBool(parameters, self.FORCE_SOUTH_POLE, context)
        self.fix_winding = self.parameterAsBool(parameters, self.FIX_WINDING, context)
        
        # Initialize counters
        self.num_bad = 0
        self.total_features = source.featureCount()
        
        return True

    def processFeature(self, feature, context, feedback):
        try:
            feature_geom = feature.geometry()
            
            # Convert QgsGeometry to shapely geometry for checking and fixing
            shapely_geom = shape(feature_geom.__geo_interface__)
            
            # No need toheck if geometry crosses the antimeridian
            # if check_crossing_geom(shapely_geom):
                # Fix the geometry (returns a dict)
            fixed_shape_dict = fix_shape(
                shapely_geom,
                force_north_pole=self.force_north_pole,
                force_south_pole=self.force_south_pole,
                fix_winding=self.fix_winding
            )
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
