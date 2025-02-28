"""
This utility is designed to generate a Giant Extended Degree GARS grid.

##
## GIANT EXTENDED DEGREE GARS
##


# 60 DEGREE CELLS

GED-GARS divides the surface of the earth into 60-degree by 60-degree cells.
Each cell is identified by a four-character designation. (ex. GD1A)

The first two characters are GD to designate that it is using the
giant extended degree system.

The next character designate a 60-degree wide longitudinal band.
Beginning with the 180-degree meridian and proceeding eastward,
the bands are numbered from 1 to 6, so that 180 E to 120 W is band 1;
120 W to 60 W is band 2; and so on.

The fourth character designates a 60-degree wide latitudinal band.
Beginning at the south pole and proceeding northward, the bands are lettered
from A to C (using only letters ABC) so that 90 S to 30 S is band A;
30 S to 30 N is band B; and 30N to 90N is band C.

# 30 DEGREE CELLS

    0  30   60
 60 ---------
    | 1 | 2 |
 30 ---------
    | 3 | 4 |
 0  --------

The areas are numbered sequentially, from west to east, starting with the
northernmost band. The graphical representation of a 30-degree quadrant with
numbered 30-degree by 30-degree areas resembles a telephone keypad.

Each 30-degree by 30-degree area, or keypad key is identified by a five-character
designation. The first four characters comprise the 30-degree quadrant designation.
The fifth character is the keypad key number. (ex. GD6A3)

"""
import math
import re
from typing import Optional, Tuple

import shapely.geometry

from .garsgrid import GARSGridBase


class GEDGARSGrid(GARSGridBase):
    """
    This object gives the polygon of the ED-GARS grid based on the ED-GARS ID
    or the resolution and lat/lon coords for the extended version using
    degrees.

    """

    LETTERS = "ABC"
    VALID_RESOLUTIONS: Tuple[int, int] = (30, 60)
    RE_PATTERN = re.compile(
        r"^GD(?P<quadrant_60deg>\d{1}[A-C])(?P<quadrant_30deg>[1-4])?$"
    )

    def __init__(self, gars_id: str, max_resolution: Optional[int] = None):
        """
        Parameters
        ----------
        gars_id: str
            The string representing the ED-GARS grid.
        max_resolution: int, optional
            The grid resolution in degrees (30, 60).
            If not provided, it will be inferred from the `gars_id`.

        """
        super().__init__()

        max_resolution = (
            None if max_resolution is None else self.validate_resolution(max_resolution)
        )

        # truncate ED-GARS ID to match resolution
        if max_resolution == 60:
            gars_id = gars_id[:4]

        # validate ED-GARS ID
        gars_match = self.RE_PATTERN.match(gars_id)
        if not gars_match:
            raise ValueError(f'"{gars_id}" is not a valid ED-GARS grid ID.')
        self.gars_id: str = gars_id

        gars_dict = gars_match.groupdict()

        self.quadrant_60deg: str = gars_dict["quadrant_60deg"]
        self.quadrant_30deg: str = gars_dict["quadrant_30deg"]

        lon_num = int(self.quadrant_60deg[0])
        if (lon_num < 1) or (lon_num > 6):
            raise ValueError(
                f'"{gars_id}" is not a valid GED-GARS grid ID. '
                "Longitude numbers can only be between 1-6."
            )

        # determine resolution from ED-GARS ID
        self.resolution: int = 60
        if self.quadrant_30deg:
            self.resolution = 30

        # properties
        self._polygon: Optional[shapely.geometry.Polygon] = None

    def __repr__(self):
        return f"<GED-GARS(gars_id={self}, resolution={self.resolution})>"

    @property
    def utm_epsg(self) -> None:  # type: ignore
        """
        Not valid since it spans UTM Zones
        """
        return None

    @classmethod
    def from_latlon(
        cls, latitude: float, longitude: float, resolution: int
    ) -> "GEDGARSGrid":
        """Load ED-GARS grid from latitude and longitude.

        Parameters
        ----------
        latitude: float
            The latitude of the cell you want to find.
        longitude: float
            The longitude of the cell you want to find.
        resolution: int
            The grid resolution in degrees (30, 60).


        Returns
        -------
        GEDGARSGrid

        """
        resolution = cls.validate_resolution(resolution)

        # convert from (-180, 180) to (0, 360)
        longitude = (longitude + 180) % 360 if longitude != 180 else 360
        # convert from (-90, 90) to (0, 180)
        latitude = (latitude + 90) % 180 if latitude != 90 else 179.9999999999

        lon_idx = int(math.floor(longitude / 60.0))
        lat_idx = int(math.floor(latitude / 60.0))
        # 60 deg quadrant
        quadrant_60deg = str(lon_idx + 1) + cls.LETTERS[lat_idx]

        quadrant_30deg = ""
        # 30 deg quadrant
        if resolution < 60:
            lon_30deg_idx = math.floor((longitude % 60) / 30.0) + 1
            lat_30deg_idx = 2 - math.floor((latitude % 60) / 30.0)
            quadrant_30deg = str(int((lat_30deg_idx - 1) * 2 + lon_30deg_idx))

        gars_id = "".join(["GD", quadrant_60deg, quadrant_30deg])

        return cls(gars_id, max_resolution=resolution)

    @property
    def polygon(self) -> shapely.geometry.Polygon:
        """Generates the GARS bounding polygon.

        Returns
        -------
        :obj:`shapely.geometry.Polygon`

        """
        if self._polygon is not None:
            return self._polygon

        # CALCULATE 60 DEG DEGREES
        # get 60 DEG quadrant info
        longitude: float = ((int(self.quadrant_60deg[0]) - 1) * 60) - 180

        # 60 deg north/south letter, A-C
        lat_60deg_letter = self.quadrant_60deg[1]
        latitude: float = -90.0 + (self.LETTERS.index(lat_60deg_letter) * 60.0)

        # CALCULATE 30 DEG DELTA
        try:
            quad_30deg = int(self.quadrant_30deg)
        except TypeError:
            quad_30deg = None

        if quad_30deg is not None:
            if quad_30deg in (2, 4):
                longitude += 30.0

            if quad_30deg in (1, 2):
                latitude += 30.0

        # upper right coordinate
        ul_latitude = latitude + self.resolution
        ul_longitude = longitude + self.resolution

        self._polygon = shapely.geometry.box(
            longitude, latitude, ul_longitude, ul_latitude
        )

        return self._polygon
