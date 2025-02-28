"""
This module contains tools to generate
 a set of GARS grids (field) based on:
- the bounding area of interest
- the desired resolution.

"""
import itertools
from typing import List, Optional, Tuple, Type

import shapely

from .edgarsgrid import EDGARSGrid
from .garsgrid import GARSGrid, GARSGridBase
from .gedgarsgrid import GEDGARSGrid


class GARSField:
    """
    Given a Shapely shape object and an GARS grid resolution, return a set of
    GARSGrid objects which intersect.
    """

    # pylint: disable=too-many-instance-attributes
    def __init__(self, bounding_geom: shapely.geometry.base.BaseGeometry) -> None:
        """
        Parameters
        ----------
        bounding_geom: :obj:`shapely.geometry.base.BaseGeometry`
            The geometry to retrieve grids from.

        """
        self.bounding_geom = bounding_geom

        self._gars_60deg: Optional[List[GEDGARSGrid]] = None
        self._gars_30deg: Optional[List[GEDGARSGrid]] = None

        self._gars_6deg: Optional[List[EDGARSGrid]] = None
        self._gars_3deg: Optional[List[EDGARSGrid]] = None
        self._gars_1deg: Optional[List[EDGARSGrid]] = None

        self._gars_30min: Optional[List[GARSGrid]] = None
        self._gars_15min: Optional[List[GARSGrid]] = None
        self._gars_5min: Optional[List[GARSGrid]] = None
        self._gars_1min: Optional[List[GARSGrid]] = None

    def _get_bounds(self) -> Tuple[float, float, float, float]:
        """
        Retrieve the bounding coordinates of the input geometry

        Returns:
        --------
        tuple:
            min_lon, min_lat, max_lon, max_lat
        """
        min_lon, min_lat, max_lon, max_lat = self.bounding_geom.bounds

        if min_lon < -180:
            min_lon = -180
        if max_lon >= 180:
            max_lon = 179.999999999999

        return min_lon, min_lat, max_lon, max_lat

    @staticmethod
    def _get_lat_letter_range(
        gars_grid: Type[GARSGridBase],
        ll_lat1: str,
        ll_lat2: str,
        ur_lat1: str,
        ur_lat2: str,
    ) -> List[str]:
        """
        Retrieve the latitude letter range for the bounding box.
        """
        # ignoring types due to: https://github.com/python/mypy/issues/4125

        # first north/south letter,  GARSGrid (A-Q), EDGARSGRid (A-B)
        lat_letter1_range: str = gars_grid.LETTERS[  # type: ignore
            gars_grid.LETTERS.index(ll_lat1) : gars_grid.LETTERS.index(ur_lat1) + 1  # type: ignore
        ]

        # second north/south letter, A-Z
        lat_letter2_range: str = gars_grid.LETTERS[  # type: ignore
            gars_grid.LETTERS.index(ll_lat2) : gars_grid.LETTERS.index(ur_lat2) + 1  # type: ignore
        ]

        lat_letter_range: List[str] = []
        if ll_lat1 != ur_lat1:
            # part 1: using first letter1 and all from first letter2 to end of all LETTERS
            for letter2 in gars_grid.LETTERS[gars_grid.LETTERS.index(ll_lat2) :]:  # type: ignore
                lat_letter_range.append("".join([ll_lat1, letter2]))

            # part 2: from second letter1 to next to last letter2 with all LETTERS
            for letter1, letter2 in itertools.product(
                lat_letter1_range[1:-1], gars_grid.LETTERS  # type: ignore
            ):
                lat_letter_range.append("".join([letter1, letter2]))

            # part 3: using last letter1 and all from beginning of all LETTERS to last last letter2
            for letter2 in gars_grid.LETTERS[: gars_grid.LETTERS.index(ur_lat2) + 1]:  # type: ignore
                lat_letter_range.append("".join([ur_lat1, letter2]))

        else:
            for letter1, letter2 in itertools.product(
                lat_letter1_range, lat_letter2_range
            ):
                lat_letter_range.append("".join([letter1, letter2]))
        return lat_letter_range

    @property
    def gars_60deg(self) -> List[GEDGARSGrid]:
        """list: The 36deg GEDGARSGrid objects that intersect the bounding geometry."""
        if self._gars_60deg is not None:
            return self._gars_60deg

        # handle multi geometry
        if self.bounding_geom.geom_type.startswith("Multi"):
            self._gars_60deg = []
            for bounding_geom in self.bounding_geom.geoms:
                self._gars_60deg += GARSField(bounding_geom).gars_60deg
            # make sure unique
            self._gars_60deg = sorted(set(self._gars_60deg))
            return self._gars_60deg

        # generate the list of 36 degree GED-GARS grids
        self._gars_60deg = []
        for lon_num_60deg, lat_60deg_letter in itertools.product(
            range(1, 7), GEDGARSGrid.LETTERS
        ):
            g60deg = GEDGARSGrid("".join(["GD", str(lon_num_60deg), lat_60deg_letter]))
            if g60deg.polygon.intersects(self.bounding_geom):
                self._gars_60deg.append(g60deg)

        return self._gars_60deg

    @property
    def gars_30deg(self) -> List[GEDGARSGrid]:
        """list: The 30deg GEDGARSGrid objects that intersect the bounding geometry."""
        if self._gars_30deg is not None:
            return self._gars_30deg

        # handle multi geometry
        if self.bounding_geom.geom_type.startswith("Multi"):
            self._gars_30deg = []
            for bounding_geom in self.bounding_geom.geoms:
                self._gars_30deg += GARSField(bounding_geom).gars_30deg
            # make sure unique
            self._gars_30deg = sorted(set(self._gars_30deg))
            return self._gars_30deg

        # generate the list of 3 degree ED-GARS grids
        self._gars_30deg = []
        for gars_60deg, quadrant_30deg in itertools.product(
            self.gars_60deg, range(1, 5)
        ):
            g30deg = GEDGARSGrid("".join([str(gars_60deg), str(quadrant_30deg)]))
            if g30deg.polygon.intersects(self.bounding_geom):
                self._gars_30deg.append(g30deg)
        return self._gars_30deg

    def _get_6deg_ranges(self) -> Tuple[List[str], List[str]]:
        """Retrieves the latitude numeric range and longitude letter range
        within the bounds.
        """
        min_lon, min_lat, max_lon, max_lat = self._get_bounds()

        ll_gars = str(EDGARSGrid.from_latlon(min_lat, min_lon, resolution=6))
        ur_gars = str(EDGARSGrid.from_latlon(max_lat, max_lon, resolution=6))

        lon_num_range = [
            f"{lon_num:02d}"
            for lon_num in range(int(ll_gars[1:3]), int(ur_gars[1:3]) + 1)
        ]

        lat_letter_range = self._get_lat_letter_range(
            EDGARSGrid, ll_gars[3], ll_gars[4], ur_gars[3], ur_gars[4]
        )

        return lon_num_range, lat_letter_range

    @property
    def gars_6deg(self) -> List[EDGARSGrid]:
        """list: The 6deg EDGARSGrid objects that intersect the bounding geometry."""
        if self._gars_6deg is not None:
            return self._gars_6deg

        # handle multi geometry
        if self.bounding_geom.geom_type.startswith("Multi"):
            self._gars_6deg = []
            for bounding_geom in self.bounding_geom.geoms:
                self._gars_6deg += GARSField(bounding_geom).gars_6deg
            # make sure unique
            self._gars_6deg = sorted(set(self._gars_6deg))
            return self._gars_6deg

        # generate the list of 6 degree ED-GARS grids
        self._gars_6deg = []
        for lon_num_6deg, lat_6deg_letter in itertools.product(
            *self._get_6deg_ranges()
        ):
            try:
                g6deg = EDGARSGrid("".join(["D", lon_num_6deg, lat_6deg_letter]))
            except ValueError:
                continue
            if g6deg.polygon.intersects(self.bounding_geom):
                self._gars_6deg.append(g6deg)

        return self._gars_6deg

    @property
    def gars_3deg(self) -> List[EDGARSGrid]:
        """list: The 3deg EDGARSGrid objects that intersect the bounding geometry."""
        if self._gars_3deg is not None:
            return self._gars_3deg

        # handle multi geometry
        if self.bounding_geom.geom_type.startswith("Multi"):
            self._gars_3deg = []
            for bounding_geom in self.bounding_geom.geoms:
                self._gars_3deg += GARSField(bounding_geom).gars_3deg
            # make sure unique
            self._gars_3deg = sorted(set(self._gars_3deg))
            return self._gars_3deg

        # generate the list of 3 degree ED-GARS grids
        self._gars_3deg = []
        for gars_6deg, quadrant_3deg in itertools.product(self.gars_6deg, range(1, 5)):
            g3deg = EDGARSGrid("".join([str(gars_6deg), str(quadrant_3deg)]))
            if g3deg.polygon.intersects(self.bounding_geom):
                self._gars_3deg.append(g3deg)
        return self._gars_3deg

    @property
    def gars_1deg(self) -> List[EDGARSGrid]:
        """list: The 1deg EDGARSGrid objects that intersect the bounding geometry."""
        if self._gars_1deg is not None:
            return self._gars_1deg

        # handle multi geometry
        if self.bounding_geom.geom_type.startswith("Multi"):
            self._gars_1deg = []
            for bounding_geom in self.bounding_geom.geoms:
                self._gars_1deg += GARSField(bounding_geom).gars_1deg
            # make sure unique
            self._gars_1deg = sorted(set(self._gars_1deg))
            return self._gars_1deg

        # generate the list of 1 degree ED-GARS grids
        self._gars_1deg = []
        for gars_3deg, quadrant_1deg in itertools.product(self.gars_3deg, range(1, 10)):
            g1deg = EDGARSGrid("".join([str(gars_3deg), str(quadrant_1deg)]))
            if g1deg.polygon.intersects(self.bounding_geom):
                self._gars_1deg.append(g1deg)
        return self._gars_1deg

    def _get_30min_ranges(self) -> Tuple[List[str], List[str]]:
        """Retrieves the latitude numeric range and longitude letter range
        within the bounds.
        """
        min_lon, min_lat, max_lon, max_lat = self._get_bounds()

        ll_gars = str(GARSGrid.from_latlon(min_lat, min_lon, resolution=30))
        ur_gars = str(GARSGrid.from_latlon(max_lat, max_lon, resolution=30))

        lon_num_range = [
            f"{lon_num:03d}"
            for lon_num in range(int(ll_gars[:3]), int(ur_gars[:3]) + 1)
        ]

        lat_letter_range = self._get_lat_letter_range(
            GARSGrid, ll_gars[3], ll_gars[4], ur_gars[3], ur_gars[4]
        )

        return lon_num_range, lat_letter_range

    @property
    def gars_30min(self) -> List[GARSGrid]:
        """list: The 30min GARSGrid objects that intersect the bounding geometry."""
        if self._gars_30min is not None:
            return self._gars_30min

        # handle multi geometry
        if self.bounding_geom.geom_type.startswith("Multi"):
            self._gars_30min = []
            for bounding_geom in self.bounding_geom.geoms:
                self._gars_30min += GARSField(bounding_geom).gars_30min
            # make sure unique
            self._gars_30min = sorted(set(self._gars_30min))
            return self._gars_30min

        # generate the list of 30 minute GARS grids
        self._gars_30min = []
        for lon_num_30min, lat_30min_letter in itertools.product(
            *self._get_30min_ranges()
        ):
            try:
                g30min = GARSGrid("".join([lon_num_30min, lat_30min_letter]))
            except ValueError:
                continue
            if g30min.polygon.intersects(self.bounding_geom):
                self._gars_30min.append(g30min)

        return self._gars_30min

    @property
    def gars_15min(self) -> List[GARSGrid]:
        """list: The 15min GARSGrid objects that intersect the bounding geometry."""
        if self._gars_15min is not None:
            return self._gars_15min

        # handle multi geometry
        if self.bounding_geom.geom_type.startswith("Multi"):
            self._gars_15min = []
            for bounding_geom in self.bounding_geom.geoms:
                self._gars_15min += GARSField(bounding_geom).gars_15min
            # make sure unique
            self._gars_15min = sorted(set(self._gars_15min))
            return self._gars_15min

        # generate the list of 15 minute GARS grids
        self._gars_15min = []
        for gars_30min, quadrant_15min in itertools.product(
            self.gars_30min, range(1, 5)
        ):
            g15min = GARSGrid("".join([str(gars_30min), str(quadrant_15min)]))
            if g15min.polygon.intersects(self.bounding_geom):
                self._gars_15min.append(g15min)
        return self._gars_15min

    @property
    def gars_5min(self) -> List[GARSGrid]:
        """list: The 5min GARSGrid objects that intersect the bounding geometry."""
        if self._gars_5min is not None:
            return self._gars_5min

        # handle multi geometry
        if self.bounding_geom.geom_type.startswith("Multi"):
            self._gars_5min = []
            for bounding_geom in self.bounding_geom.geoms:
                self._gars_5min += GARSField(bounding_geom).gars_5min
            # make sure unique
            self._gars_5min = sorted(set(self._gars_5min))
            return self._gars_5min

        # generate the list of 5 minute GARS grids
        self._gars_5min = []
        for gars_15min, quadrant_5min in itertools.product(
            self.gars_15min, range(1, 10)
        ):
            g5min = GARSGrid("".join([str(gars_15min), str(quadrant_5min)]))
            if g5min.polygon.intersects(self.bounding_geom):
                self._gars_5min.append(g5min)
        return self._gars_5min

    @property
    def gars_1min(self) -> List[GARSGrid]:
        """list: The 1min GARSGrid objects that intersect the bounding geometry."""
        if self._gars_1min is not None:
            return self._gars_1min

        # handle multi geometry
        if self.bounding_geom.geom_type.startswith("Multi"):
            self._gars_1min = []
            for bounding_geom in self.bounding_geom.geoms:
                self._gars_1min += GARSField(bounding_geom).gars_1min
            # make sure unique
            self._gars_1min = sorted(set(self._gars_1min))
            return self._gars_1min

        # generate the list of 1 minute GARS grids
        self._gars_1min = []
        for gars_5min, quadrant_1min in itertools.product(self.gars_5min, range(1, 26)):
            g1min = GARSGrid("".join([str(gars_5min), f"{quadrant_1min:02d}"]))
            if g1min.polygon.intersects(self.bounding_geom):
                self._gars_1min.append(g1min)
        return self._gars_1min
