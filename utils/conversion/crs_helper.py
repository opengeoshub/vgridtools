"""CRS checks for DGGS tools that require WGS84 input."""

from qgis.core import QgsCoordinateReferenceSystem

WGS84 = QgsCoordinateReferenceSystem("EPSG:4326")

WGS84_REQUIRED_MSG = (
    "Input must use WGS84 (EPSG:4326). "
    "Please reproject the layer to EPSG:4326 and run the tool again."
)


def is_wgs84(crs) -> bool:
    return crs is not None and crs.isValid() and crs.authid() == "EPSG:4326"
