# import mgrs, maidenhead, geohash, georef, olc, s2
from . import olc
from .s2 import LatLng, CellId
from .gars import GARSGrid
import math

from qgis.core import QgsFeature, QgsGeometry, QgsPointXY, QgsField, QgsFields
from PyQt5.QtCore import QVariant

def haversine(lat1, lon1, lat2, lon2):
    # Radius of the Earth in meters
    R = 6371000  

    # Convert latitude and longitude from degrees to radians
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    # Haversine formula
    a = math.sin(delta_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c  # Distance in meters

def olc2qgsfeature(olc_code):
    # Decode the Open Location Code into a CodeArea object
    coord = olc.decode(olc_code)
    if coord:
        # Create the bounding box coordinates for the polygon
        min_lat, min_lon = coord.latitudeLo, coord.longitudeLo
        max_lat, max_lon = coord.latitudeHi, coord.longitudeHi

        # Create a polygon geometry from the bounding box using QgsPointXY
        ring = [
            QgsPointXY(min_lon, min_lat),  # Bottom-left corner
            QgsPointXY(max_lon, min_lat),  # Bottom-right corner
            QgsPointXY(max_lon, max_lat),  # Top-right corner
            QgsPointXY(min_lon, max_lat),  # Top-left corner
            QgsPointXY(min_lon, min_lat)   # Closing the polygon (same as the first point)
        ]
        
        # Create QgsGeometry from the ring
        geometry = QgsGeometry.fromPolygonXY([ring])

        # Create the QgsFeature and set its geometry
        feature = QgsFeature()
        feature.setGeometry(geometry)

        # Create QgsFields and add fields to it
        fields = QgsFields()
        fields.append(QgsField('olc', QVariant.String))
        fields.append(QgsField('center_lat', QVariant.Double))
        fields.append(QgsField('center_lon', QVariant.Double))
        fields.append(QgsField('bbox_height', QVariant.String))
        fields.append(QgsField('bbox_width', QVariant.String))
        fields.append(QgsField('precision', QVariant.Int))
        
        feature.setFields(fields)

        # Set the attribute values
        center_lat, center_lon = coord.latitudeCenter, coord.longitudeCenter
        precision = coord.codeLength

        # Compute bounding box dimensions
        lat_len = haversine(min_lat, min_lon, max_lat, min_lon)
        lon_len = haversine(min_lat, min_lon, min_lat, max_lon)

        # Format bbox dimensions
        bbox_width = f'{round(lon_len, 1)} m' if lon_len < 10000 else f'{round(lon_len / 1000, 1)} km'
        bbox_height = f'{round(lat_len, 1)} m' if lat_len < 10000 else f'{round(lat_len / 1000, 1)} km'

        # Set the properties
        feature.setAttribute('olc', olc_code)
        feature.setAttribute('center_lat', center_lat)
        feature.setAttribute('center_lon', center_lon)
        feature.setAttribute('bbox_height', bbox_height)
        feature.setAttribute('bbox_width', bbox_width)
        feature.setAttribute('precision', precision)

        return feature

    return None  # Return None if OLC is invalid
