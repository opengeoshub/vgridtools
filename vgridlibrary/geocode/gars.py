"""
This utility is designed to generate a GARS grid.

Code Based on:
- https://github.com/mil-oss/GARSutils
- https://github.com/Moustikitos/gryd/blob/c79edde94f19d46e3b3532ae14eb351e91d55322/Gryd/geodesy.py

Design Information From:
- http://earth-info.nga.mil/GandG/coordsys/grids/gars.html

# 30 MINUTE CELLS
GARS divides the surface of the earth into 30-minute by 30-minute cells.
Each cell is identified by a five-character designation. (ex. 006AG)

The first three characters designate a 30-minute wide longitudinal band.
Beginning with the 180-degree meridian and proceeding eastward,
the bands are numbered from 001 to 720, so that 180 E to 179 30 W is band 001;
179 30 W to 179 00 W is band 002; and so on.

The fourth and fifth characters designate a 30-minute wide latitudinal band.
Beginning at the south pole and proceeding northward, the bands are lettered
from AA to QZ (omitting I and O) so that 90 00 S to 89 30 S is band AA;
89 30 S to 89 00 S is band AB; and so on.

# 15 MINUTE CELLS

    0  15  30
 30 ---------
    | 1 | 2 |
 15 ---------
    | 3 | 4 |
 0  ---------

The quadrants are numbered sequentially, from west to east,
starting with the northernmost band. Specifically, the northwest quadrant is 1;
the northeast quadrant is 2; the southwest quadrant is 3; the southeast quadrant is 4.

Each quadrant is identified by a six-character designation. (ex. 006AG3)
The first five characters comprise the 30-minute cell designation.
The sixth character is the quadrant number.

# 5 MINUTE CELLS

    0   5  10  15
 15 -------------
    | 1 | 2 | 3 |
 10 -------------
    | 4 | 5 | 6 |
 5  -------------
    | 7 | 8 | 9 |
 0  -------------

The areas are numbered sequentially, from west to east, starting with the northernmost band.
The graphical representation of a 15-minute quadrant with numbered 5-minute by 5-minute
areas resembles a telephone keypad

Each 5-minute by 5-minute area, or keypad key is identified by a seven-character
designation. The first six characters comprise the 15-minute quadrant designation.
The seventh character is the keypad key number. (ex.006AG39)


# 1 MINUTE CELLS (CUSTOM EXTENSION)

    0   1   2   3   4   5
 5  ---------------------
    | 01| 02| 03| 04| 05|
 4  ---------------------
    | 06| 07| 08| 09| 10|
 3  ---------------------
    | 11| 12| 13| 14| 15|
 2  ---------------------
    | 16| 17| 18| 19| 20|
 1  ---------------------
    | 21| 22| 23| 24| 25|
 0  ---------------------

The areas are numbered sequentially, from west to east, starting with the northernmost band.
The graphical representation of a 5-minute quadrant with numbered 1-minute by 1-minute
areas resembles a telephone keypad

Each 1-minute by 1-minute area, or keypad key is identified by a seven-character
designation. The first seven characters comprise the 5-minute quadrant designation.
The eighth and ninth characters are the keypad key number. (ex.006AG3901)

"""
import math
import re
from abc import abstractmethod
from typing import Optional, Tuple

import shapely.geometry
from pyproj.aoi import AreaOfInterest
from pyproj.database import (  # type: ignore  # pylint: disable=no-name-in-module
    query_utm_crs_info,
)


class GARSGridBase:
    """
    Base class for all GARS Grid classes.
    """

    def __init__(self):
        self._utm_epsg: Optional[str] = None
        self.gars_id: str = ""

    @property
    @abstractmethod
    def polygon(self) -> shapely.geometry.Polygon:
        """
        Returns the polygon boundary for the GARS tile.

        Returns
        -------
        :obj:`shapely.geometry.Polygon`
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def VALID_RESOLUTIONS(self) -> Tuple[int, ...]:  # pylint: disable=invalid-name
        """
        List of supported resolutions.

        Returns
        -------
        tuple
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def LETTERS(self) -> str:  # pylint: disable=invalid-name
        """
        String of letters for the grid system

        Returns
        -------
        str
        """
        raise NotImplementedError

    @property
    def utm_epsg(self) -> str:
        """This returns the UTM zone EPSG code for this GARS grid.

        Returns
        -------
        str:
            UTM zone EPSG code
        """
        if self._utm_epsg is not None:
            return self._utm_epsg

        latitude = self.polygon.centroid.y
        if latitude <= -80:
            # UPS South
            self._utm_epsg = "EPSG:32761"
        elif latitude >= 84:
            # UPS North
            self._utm_epsg = "EPSG:32661"
        else:
            longitude = self.polygon.centroid.x
            utm_crs_list = query_utm_crs_info(
                datum_name="WGS 84",
                area_of_interest=AreaOfInterest(
                    west_lon_degree=longitude,
                    south_lat_degree=latitude,
                    east_lon_degree=longitude,
                    north_lat_degree=latitude,
                ),
            )
            self._utm_epsg = f"EPSG:{utm_crs_list[0].code}"
        return self._utm_epsg

    def __str__(self) -> str:
        return self.gars_id

    def __eq__(self, other) -> bool:
        return str(self) == str(other)

    def __hash__(self) -> int:
        return hash(self.gars_id)

    def __lt__(self, other) -> bool:
        return self.gars_id < other.gars_id

    @classmethod
    def validate_resolution(cls, resolution: int) -> int:
        """Validate the resolution input.

        Returns
        -------
        int: Valid resolution.

        Raises
        ------
        ValueError

        """
        if resolution not in cls.VALID_RESOLUTIONS:  # type: ignore
            raise ValueError(
                f"Invalid resolution {resolution}. "
                f"Only {cls.VALID_RESOLUTIONS} are allowed."
            )
        return int(resolution)


class GARSGrid(GARSGridBase):
    """
    This object gives the polygon of the GARS grid based on the GARS ID
    or the resolution and lat/lon coords.
    """

    LETTERS: str = "ABCDEFGHJKLMNPQRSTUVWXYZ"
    VALID_RESOLUTIONS: Tuple[int, int, int, int] = (1, 5, 15, 30)
    RE_PATTERN = re.compile(
        r"^(?P<quadrant_30min>\d{3}[A-HJ-NP-Q][A-HJ-NP-Z])"
        r"((?P<quadrant_15min>[1-4])"
        r"((?P<quadrant_5min>[1-9])"
        r"(?P<quadrant_1min>\d{2})?)?)?$"
    )

    def __init__(self, gars_id: str, max_resolution: Optional[int] = None):
        """
        Parameters
        ----------
        gars_id: str
            The string representing the GARS grid.
        max_resolution: int, optional
            The grid resolution in seconds (1, 5, 15, 30).
            If not provided, it will be inferred from the `gars_id`.

        """
        super().__init__()

        max_resolution = (
            None if max_resolution is None else self.validate_resolution(max_resolution)
        )

        # truncate GARS ID to match resolution
        if max_resolution == 30:
            gars_id = gars_id[:5]
        elif max_resolution == 15:
            gars_id = gars_id[:6]
        elif max_resolution == 5:
            gars_id = gars_id[:7]

        # validate GARS ID
        gars_match = self.RE_PATTERN.match(gars_id)
        if not gars_match:
            raise ValueError(f'"{gars_id}" is not a valid GARS grid ID.')
        self.gars_id = gars_id

        gars_dict = gars_match.groupdict()

        self.quadrant_1min = gars_dict["quadrant_1min"]
        self.quadrant_5min = gars_dict["quadrant_5min"]
        self.quadrant_15min = gars_dict["quadrant_15min"]
        self.quadrant_30min = gars_dict["quadrant_30min"]

        lon_num = int(self.quadrant_30min[:3])
        if (lon_num < 1) or (lon_num > 720):
            raise ValueError(
                f'"{gars_id}" is not a valid GARS grid ID. '
                "Longitude numbers can only be between 001-720."
            )

        # determine resolution from GARS ID
        self.resolution = 30
        if self.quadrant_1min:
            if int(self.quadrant_1min) < 1 or int(self.quadrant_1min) > 25:
                raise ValueError(
                    f'"{gars_id}" is not a valid GARS grid ID. '
                    "1 min quadrant number can only be between 01-25."
                )

            self.resolution = 1
        elif self.quadrant_5min:
            self.resolution = 5
        elif self.quadrant_15min:
            self.resolution = 15

        # properties
        self._polygon = None

    def __repr__(self) -> str:
        return f"<GARS(gars_id={self}, resolution={self.resolution})>"

    @classmethod
    def from_latlon(
        cls, latitude: float, longitude: float, resolution: int
    ) -> "GARSGrid":
        # pylint: disable=too-many-locals
        """Load GARS grid from latitude and longitude.

        Parameters
        ----------
        latitude: float
            The latitude of the cell you want to find.
        longitude: float
            The longitude of the cell you want to find.
        resolution: int
            The grid resolution in minutes (5, 15, 30).


        Returns
        -------
        GARSGrid

        """
        resolution = cls.validate_resolution(resolution)

        # convert from (-180, 180) to (0, 360)
        longitude = (longitude + 180) % 360 if longitude != 180 else 360
        # convert from (-90, 90) to (0, 180)
        latitude = (latitude + 90) % 180 if latitude != 90 else 179.9999999999

        lon_idx = longitude * 2.0
        lat_idx = latitude * 2.0

        # 30 minute quadrant
        quadrant_30min = (
            f"{int(lon_idx + 1):03d}"
            + cls.LETTERS[int(math.floor(lat_idx // 24))]
            + cls.LETTERS[int(math.floor(lat_idx % 24))]
        )

        quadrant_15min = ""
        quadrant_5min = ""
        quadrant_1min = ""
        # 15 minute quadrant
        if resolution < 30:

            def index_from_degrees(
                num_degrees: float, inverse: bool = False
            ) -> Tuple[int, int, int]:
                minutes = (num_degrees - math.floor(num_degrees)) * 60
                minutes_30 = minutes % 30
                minutes_15 = minutes % 15
                minutes_5 = minutes % 5
                idx_15 = math.floor(minutes_30 / 15.0) + 1
                idx_5 = math.floor(minutes_15 / 5.0) + 1
                idx_1 = math.floor(minutes_5) + 1
                if inverse:
                    idx_15 = 3 - idx_15
                    idx_5 = 4 - idx_5
                    idx_1 = 6 - idx_1
                return idx_15, idx_5, idx_1

            lon_15min_idx, lon_5min_idx, lon_1min_idx = index_from_degrees(longitude)
            lat_15min_idx, lat_5min_idx, lat_1min_idx = index_from_degrees(
                latitude, inverse=True
            )
            quadrant_15min = str(int((lat_15min_idx - 1) * 2 + lon_15min_idx))

            # 5 minute quadrant
            if resolution < 15:
                quadrant_5min = str(int((lat_5min_idx - 1) * 3 + lon_5min_idx))

            # 1 minute quadrant
            if resolution < 5:
                quadrant_1min = f"{int((lat_1min_idx - 1) * 5 + lon_1min_idx):02d}"

        gars_id = "".join(
            [quadrant_30min, quadrant_15min, quadrant_5min, quadrant_1min]
        )

        return cls(gars_id, max_resolution=resolution)

    def _15_minute_delta(self) -> Tuple[float, float]:
        """
        Calculate 15 minute delta

        Returns
        -------
        tuple:
            lon_minutes, lat_minutes
        """
        lat_minutes = 0.0
        lon_minutes = 0.0

        try:
            quad_15min = int(self.quadrant_15min)
        except TypeError:
            return lon_minutes, lat_minutes

        if quad_15min in (1, 2):
            lat_minutes = 15.0
        if quad_15min in (2, 4):
            lon_minutes = 15.0
        return lon_minutes, lat_minutes

    def _5_minute_delta(self) -> Tuple[float, float]:
        """
        Calculate 5 minute delta

        Returns
        -------
        tuple:
            lon_minutes, lat_minutes
        """
        lat_minutes = 0.0
        lon_minutes = 0.0

        try:
            quad_5min = int(self.quadrant_5min)
        except TypeError:
            return lon_minutes, lat_minutes

        if quad_5min in (2, 5, 8):
            lon_minutes = 5.0
        elif quad_5min in (3, 6, 9):
            lon_minutes = 10.0

        if quad_5min in (4, 5, 6):
            lat_minutes = 5.0
        elif quad_5min in (1, 2, 3):
            lat_minutes = 10.0
        return lon_minutes, lat_minutes

    def _1_minute_delta(self) -> Tuple[float, float]:
        """
        Calculate 1 minute delta

        Returns
        -------
        tuple:
            lon_minutes, lat_minutes
        """
        lat_minutes = 0.0
        lon_minutes = 0.0

        try:
            quad_1min = int(self.quadrant_1min)
        except TypeError:
            return lon_minutes, lat_minutes

        if quad_1min in (2, 7, 12, 17, 22):
            lon_minutes = 1.0
        elif quad_1min in (3, 8, 13, 18, 23):
            lon_minutes = 2.0
        elif quad_1min in (4, 9, 14, 19, 24):
            lon_minutes = 3.0
        elif quad_1min in (5, 10, 15, 20, 25):
            lon_minutes = 4.0

        if quad_1min <= 5:
            lat_minutes = 4.0
        elif 6 <= quad_1min <= 10:
            lat_minutes = 3.0
        elif 11 <= quad_1min <= 15:
            lat_minutes = 2.0
        elif 16 <= quad_1min <= 20:
            lat_minutes = 1.0
        return lon_minutes, lat_minutes

    @property
    def polygon(self) -> shapely.geometry.Polygon:
        """Generates the GARS bounding polygon.

        Returns
        -------
        :obj:`shapely.geometry.Polygon`

        """
        if self._polygon is not None:
            return self._polygon

        # CALCULATE 30 MIN DEGREES
        # get 30 minute quadrant info
        longitude = ((int(self.quadrant_30min[:3]) - 1) / 2.0) - 180

        # first 30 minute north/south letter, A-Q
        lat_30min_letter1 = self.quadrant_30min[3]

        # second 30 minute north/south letter, A-Z
        lat_30min_letter2 = self.quadrant_30min[4]

        latitude = (-90.0 + (self.LETTERS.index(lat_30min_letter1) * 12.0)) + (
            self.LETTERS.index(lat_30min_letter2) / 2.0
        )

        lon_minutes_15, lat_minutes_15 = self._15_minute_delta()
        lon_minutes_5, lat_minutes_5 = self._5_minute_delta()
        lon_minutes_1, lat_minutes_1 = self._1_minute_delta()

        # lower left coordinate
        ll_latitude = latitude + (lat_minutes_15 + lat_minutes_5 + lat_minutes_1) / 60.0
        ll_longitude = (
            longitude + (lon_minutes_15 + lon_minutes_5 + lon_minutes_1) / 60.0
        )

        # upper right coordinate
        ul_latitude = ll_latitude + self.resolution / 60.0
        ul_longitude = ll_longitude + self.resolution / 60.0

        self._polygon = shapely.geometry.box(
            ll_longitude, ll_latitude, ul_longitude, ul_latitude
        )

        return self._polygon
