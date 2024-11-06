"""
This utility is designed to generate an Extended Degree GARS grid.

##
## EXTENDED DEGREE GARS
##


# 6 DEGREE CELLS

ED-GARS divides the surface of the earth into 6-degree by 6-degree cells.
Each cell is identified by a five-character designation. (ex. D06AG)

The first character is a D to designate that it is using the extended degree system.

The next two characters designate a 6-degree wide longitudinal band.
Beginning with the 180-degree meridian and proceeding eastward,
the bands are numbered from 01 to 60, so that 180 E to 174 W is band 001;
174 W to 168 W is band 002; and so on.

The fourth and fifth characters designate a 6-degree wide latitudinal band.
Beginning at the south pole and proceeding northward, the bands are lettered
from AA to BK (using only letters ABCDEFGHJKLMNPQRSTUV) so that 90 S to 84 S is band AA;
84 S to 78 S is band AB; and so on.

# 3 DEGREE CELLS

    0  15  30
 30 ---------
    | 1 | 2 |
 15 ---------
    | 3 | 4 |
 0  ---------

The quadrants are numbered sequentially, from west to east,
starting with the northernmost band. Specifically, the northwest quadrant is 1;
the northeast quadrant is 2; the southwest quadrant is 3; the southeast quadrant is 4.

Each quadrant is identified by a six-character designation. (ex. D06AG3)
The first five characters comprise the 6-degree cell designation.
The sixth character is the quadrant number.

# 1 DEGREE CELLS

    0   5  10  15
 15 -------------
    | 1 | 2 | 3 |
 10 -------------
    | 4 | 5 | 6 |
 5  -------------
    | 7 | 8 | 9 |
 0  -------------

The areas are numbered sequentially, from west to east, starting with the northernmost band.
The graphical representation of a 3-degree quadrant with numbered 1-degree by 1-degree
areas resembles a telephone keypad

Each 1-degree by 1-degree area, or keypad key is identified by a seven-character
designation. The first six characters comprise the 3-degree quadrant designation.
The seventh character is the keypad key number. (ex. D06AG39)

"""
import math
import re
from typing import Optional

import shapely.geometry

from .garsgrid import GARSGridBase


class EDGARSGrid(GARSGridBase):
    """
    This object gives the polygon of the ED-GARS grid based on the ED-GARS ID
    or the resolution and lat/lon coords for the extended version using
    degrees.

    """

    LETTERS = "ABCDEFGHJKLMNPQRSTUV"
    VALID_RESOLUTIONS = (1, 3, 6)
    RE_PATTERN = re.compile(
        r"^D(?P<quadrant_6deg>\d{2}[A-B][A-HJ-NP-V])"
        r"((?P<quadrant_3deg>[1-9])"
        r"(?P<quadrant_1deg>[1-9])?)?$"
    )

    def __init__(self, gars_id: str, max_resolution: Optional[int] = None) -> None:
        """
        Parameters
        ----------
        gars_id: str
            The string representing the ED-GARS grid.
        max_resolution: int, optional
            The grid resolution in degrees (1, 3, 6).
            If not provided, it will be inferred from the `gars_id`.

        """
        super().__init__()

        max_resolution = (
            None if max_resolution is None else self.validate_resolution(max_resolution)
        )

        # truncate ED-GARS ID to match resolution
        if max_resolution == 6:
            gars_id = gars_id[:5]
        elif max_resolution == 3:
            gars_id = gars_id[:6]

        # validate ED-GARS ID
        gars_match = self.RE_PATTERN.match(gars_id)
        if not gars_match:
            raise ValueError(f'"{gars_id}" is not a valid ED-GARS grid ID.')
        self.gars_id: str = gars_id

        gars_dict = gars_match.groupdict()

        self.quadrant_1deg: str = gars_dict["quadrant_1deg"]
        self.quadrant_3deg: str = gars_dict["quadrant_3deg"]
        self.quadrant_6deg: str = gars_dict["quadrant_6deg"]

        lon_num = int(self.quadrant_6deg[:2])
        if (lon_num < 1) or (lon_num > 60):
            raise ValueError(
                f'"{gars_id}" is not a valid ED-GARS grid ID. '
                "Longitude numbers can only be between 01-60."
            )

        if self.quadrant_6deg[2] == "B" and self.quadrant_6deg[3] > "K":
            raise ValueError(
                f'"{gars_id}" is not a valid ED-GARS grid ID. '
                "Latitude letters cannot exceed BK."
            )

        # determine resolution from ED-GARS ID
        self.resolution: int = 6
        if self.quadrant_1deg:
            self.resolution = 1
        elif self.quadrant_3deg:
            self.resolution = 3

        # properties
        self._polygon: Optional[shapely.geometry.Polygon] = None

    def __repr__(self) -> str:
        return f"<ED-GARS(gars_id={self}, resolution={self.resolution})>"

    @classmethod
    def from_latlon(
        cls, latitude: float, longitude: float, resolution: int
    ) -> "EDGARSGrid":
        """Load ED-GARS grid from latitude and longitude.

        Parameters
        ----------
        latitude: float
            The latitude of the cell you want to find.
        longitude: float
            The longitude of the cell you want to find.
        resolution: int
            The grid resolution in degrees (1, 3, 6).


        Returns
        -------
        EDGARSGrid

        """
        resolution = cls.validate_resolution(resolution)

        # convert from (-180, 180) to (0, 360)
        longitude = (longitude + 180) % 360 if longitude != 180 else 360
        # convert from (-90, 90) to (0, 180)
        latitude = (latitude + 90) % 180 if latitude != 90 else 179.9999999999

        lon_idx = longitude / 6.0
        lat_idx = latitude / 6.0
        # 6 deg quadrant
        quadrant_6deg = (
            f"{int(lon_idx + 1):02d}"
            + cls.LETTERS[int(math.floor(lat_idx // 20))]
            + cls.LETTERS[int(math.floor(lat_idx % 20))]
        )

        quadrant_3deg = ""
        quadrant_1deg = ""
        # 3 deg quadrant
        if resolution < 6:
            lon_3deg_idx = math.floor((longitude % 6) / 3.0) + 1
            lat_3deg_idx = 2 - math.floor((latitude % 6) / 3.0)
            quadrant_3deg = str(int((lat_3deg_idx - 1) * 2 + lon_3deg_idx))

            # 1 deg quadrant
            if resolution < 3:
                lon_1deg_idx = math.floor(longitude % 3) + 1
                lat_1deg_idx = 3 - math.floor(latitude % 3)
                quadrant_1deg = str(int((lat_1deg_idx - 1) * 3 + lon_1deg_idx))

        gars_id = "".join(["D", quadrant_6deg, quadrant_3deg, quadrant_1deg])

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

        # CALCULATE 6 DEG DEGREES
        # get 6 DEG quadrant info
        longitude: float = ((int(self.quadrant_6deg[:2]) - 1) * 6) - 180

        # first 6 deg north/south letter, A-B
        lat_6deg_letter1 = self.quadrant_6deg[2]

        # second 6 deg north/south letter, A-V
        lat_6deg_letter2 = self.quadrant_6deg[3]

        latitude: float = (-90.0 + (self.LETTERS.index(lat_6deg_letter1) * 120.0)) + (
            self.LETTERS.index(lat_6deg_letter2) * 6.0
        )

        # CALCULATE 3 DEG DELTA
        try:
            quad_3deg = int(self.quadrant_3deg)
        except TypeError:
            quad_3deg = None

        if quad_3deg is not None:
            if quad_3deg in (1, 2):
                latitude += 3.0
            if quad_3deg in (2, 4):
                longitude += 3.0

        # CALCULATE 1 DEG DELTA
        try:
            quad_1deg = int(self.quadrant_1deg)
        except TypeError:
            quad_1deg = None

        if quad_1deg is not None:
            if quad_1deg in (2, 5, 8):
                longitude += 1.0
            elif quad_1deg in (3, 6, 9):
                longitude += 2.0

            if quad_1deg in (4, 5, 6):
                latitude += 1.0
            elif quad_1deg in (1, 2, 3):
                latitude += 2.0

        # upper right coordinate
        ul_latitude = latitude + self.resolution
        ul_longitude = longitude + self.resolution

        self._polygon = shapely.geometry.box(
            longitude, latitude, ul_longitude, ul_latitude
        )

        return self._polygon
