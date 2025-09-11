from qgis.core import QgsCoordinateReferenceSystem
import re

epsg4326 = QgsCoordinateReferenceSystem("EPSG:4326")


def parseDMS(str, hemisphere):
    """Parse a DMS formatted string."""
    str = re.sub(r"[^\d.]+", " ", str).strip()
    parts = re.split(r"[\s]+", str)
    dmslen = len(parts)
    if dmslen == 3:
        deg = float(parts[0]) + float(parts[1]) / 60.0 + float(parts[2]) / 3600.0
    elif dmslen == 2:
        deg = float(parts[0]) + float(parts[1]) / 60.0
    elif dmslen == 1:
        dms = parts[0]
        if hemisphere == "N" or hemisphere == "S":
            dms = "0" + dms
        # Find the length up to the first decimal
        ll = dms.find(".")
        if ll == -1:
            # No decimal point found so just return the length of the string
            ll = len(dms)
        if ll >= 7:
            deg = float(dms[0:3]) + float(dms[3:5]) / 60.0 + float(dms[5:]) / 3600.0
        elif ll == 6:  # A leading 0 was left off but we can still work with 6 digits
            deg = float(dms[0:2]) + float(dms[2:4]) / 60.0 + float(dms[4:]) / 3600.0
        elif ll == 5:
            deg = float(dms[0:3]) + float(dms[3:]) / 60.0
        elif ll == 4:  # Leading 0's were left off
            deg = float(dms[0:2]) + float(dms[2:]) / 60.0
        else:
            deg = float(dms)
    else:
        raise ValueError("Invalid DMS Coordinate")
    if hemisphere == "S" or hemisphere == "W":
        deg = -deg
    return deg


def parseDMSString(str, order=0):
    """Parses a pair of coordinates that are in the order of
    "latitude, longitude". The string can be in DMS or decimal
    degree notation. If order is 0 then then decimal coordinates are assumed to
    be in Lat Lon order otherwise they are in Lon Lat order. For DMS coordinates
    it does not matter the order."""
    str = str.strip().upper()  # Make it all upper case
    try:
        if re.search(r"[NSEW]", str) is None:
            # There were no annotated dms coordinates so assume decimal degrees
            # Remove any characters that are not digits and decimal
            str = re.sub(r"[^\d.+-]+", " ", str).strip()
            coords = re.split(r"\s+", str, 1)
            if len(coords) != 2:
                raise ValueError("Invalid Coordinates")
            if order == 0:
                lat = float(coords[0])
                lon = float(coords[1])
            else:
                lon = float(coords[0])
                lat = float(coords[1])
        else:
            # We should have a DMS coordinate
            if re.search(r"[NSEW]\s*\d+.+[NSEW]\s*\d+", str) is None:
                # We assume that the cardinal directions occur after the digits
                m = re.findall(r"(.+)\s*([NS])[\s,;:]*(.+)\s*([EW])", str)
                if len(m) != 1 or len(m[0]) != 4:
                    # This is either invalid or the coordinates are ordered by lon lat
                    m = re.findall(r"(.+)\s*([EW])[\s,;:]*(.+)\s*([NS])", str)
                    if len(m) != 1 or len(m[0]) != 4:
                        # Now we know it is invalid
                        raise ValueError("Invalid DMS Coordinate")
                    else:
                        # The coordinates were in lon, lat order
                        lon = parseDMS(m[0][0], m[0][1])
                        lat = parseDMS(m[0][2], m[0][3])
                else:
                    # The coordinates are in lat, lon order
                    lat = parseDMS(m[0][0], m[0][1])
                    lon = parseDMS(m[0][2], m[0][3])
            else:
                # The cardinal directions occur at the beginning of the digits
                m = re.findall(r"([NS])\s*(\d+.*?)[\s,;:]*([EW])(.+)", str)
                if len(m) != 1 or len(m[0]) != 4:
                    # This is either invalid or the coordinates are ordered by lon lat
                    m = re.findall(r"([EW])\s*(\d+.*?)[\s,;:]*([NS])(.+)", str)
                    if len(m) != 1 or len(m[0]) != 4:
                        # Now we know it is invalid
                        raise ValueError("Invalid DMS Coordinate")
                    else:
                        # The coordinates were in lon, lat order
                        lon = parseDMS(m[0][1], m[0][0])
                        lat = parseDMS(m[0][3], m[0][2])
                else:
                    # The coordinates are in lat, lon order
                    lat = parseDMS(m[0][1], m[0][0])
                    lon = parseDMS(m[0][3], m[0][2])

    except Exception:
        raise ValueError("Invalid Coordinates")

    return lat, lon
