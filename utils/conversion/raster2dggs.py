"""
QGIS raster-to-DGGS conversion (binning or nearest_neighbour), aligned with vgrid logic.
"""

from __future__ import annotations

import platform

import h3

from vgrid.dggs import s2, tilecode
from vgrid.conversion.latlon2dggs import (
    latlon2a5,
    latlon2digipin,
    latlon2dggal,
    latlon2geohash,
    latlon2olc,
    latlon2qtm,
    latlon2rhealpix,
)
from vgrid.conversion.dggs2geo.a52geo import a52geo
from vgrid.conversion.dggs2geo.dggal2geo import dggal2geo
from vgrid.conversion.dggs2geo.digipin2geo import digipin2geo
from vgrid.conversion.dggs2geo.geohash2geo import geohash2geo
from vgrid.conversion.dggs2geo.h32geo import h32geo
from vgrid.conversion.dggs2geo.olc2geo import olc2geo
from vgrid.conversion.dggs2geo.qtm2geo import qtm2geo
from vgrid.conversion.dggs2geo.quadkey2geo import quadkey2geo
from vgrid.conversion.dggs2geo.rhealpix2geo import rhealpix2geo
from vgrid.conversion.dggs2geo.s22geo import s22geo
from vgrid.conversion.dggs2geo.tilecode2geo import tilecode2geo
from vgrid.dggs.rhealpixdggs.dggs import RHEALPixDGGS
from vgrid.dggs.rhealpixdggs.ellipsoids import WGS84_ELLIPSOID
from vgrid.utils.constants import DGGAL_TYPES
from vgrid.utils.geometry import geodesic_dggs_metrics, graticule_dggs_metrics

from dggal import *
from ...utils.resampling import dggsgrid
from .raster2dggs_helper import (
    gdf_to_qgs_vector_layer,
    run_raster2,
)

E = WGS84_ELLIPSOID
_RHEALPIX_DGGS = RHEALPixDGGS(ellipsoid=E, north_square=1, south_square=3, N_side=3)

_dggal_app = Application(appGlobals=globals())
pydggal_setup(_dggal_app)

if platform.system() == "Windows":
    from vgrid.conversion.dggs2geo.isea4t2geo import isea4t2geo
    from vgrid.conversion.latlon2dggs import latlon2isea4t
    from vgrid.dggs.eaggr.eaggr import Eaggr
    from vgrid.dggs.eaggr.enums.model import Model

    _isea4t_dggs = Eaggr(Model.ISEA4T)


def _geodesic_meta(cell_polygon, num_edges, cell_id, resolution):
    center_lat, center_lon, avg_edge_len, cell_area, cell_perimeter = (
        geodesic_dggs_metrics(cell_polygon, num_edges)
    )
    return {
        "id": cell_id,
        "resolution": resolution,
        "center_lat": center_lat,
        "center_lon": center_lon,
        "avg_edge_len": avg_edge_len,
        "cell_area": cell_area,
        "cell_perimeter": cell_perimeter,
    }


def _h3_cell_builder(cell_id, resolution):
    cell_polygon = h32geo(cell_id)
    if not cell_polygon:
        return None
    num_edges = 5 if h3.is_pentagon(cell_id) else 6
    return cell_polygon, _geodesic_meta(cell_polygon, num_edges, cell_id, resolution)


def _s2_cell_builder(cell_id, resolution):
    cell_polygon = s22geo(cell_id)
    if not cell_polygon:
        return None
    return cell_polygon, _geodesic_meta(cell_polygon, 4, cell_id, resolution)


def raster2h3(raster_layer, resolution, feedback=None, method="nearest", stats="mean"):
    return run_raster2(
        raster_layer,
        resolution,
        method,
        stats,
        "h3",
        lambda lat, lon: h3.latlng_to_cell(lat, lon, resolution),
        lambda res, feat, fb: dggsgrid.generate_h3_grid(res, feat, fb),
        lambda cid, res: _h3_cell_builder(cid, res),
        feedback=feedback,
        layer_name="H3",
    )


def raster2s2(raster_layer, resolution, feedback=None, method="nearest", stats="mean"):
    def cell_id(lat, lon):
        lat_lng = s2.LatLng.from_degrees(lat, lon)
        return s2.CellId.to_token(s2.CellId.from_lat_lng(lat_lng).parent(resolution))

    return run_raster2(
        raster_layer,
        resolution,
        method,
        stats,
        "s2",
        cell_id,
        lambda res, feat, fb: dggsgrid.generate_s2_grid(res, feat, fb),
        lambda cid, res: _s2_cell_builder(cid, res),
        feedback=feedback,
        layer_name="S2",
    )


def raster2a5(raster_layer, resolution, feedback=None, method="nearest", stats="mean"):
    def cell_id(lat, lon):
        try:
            return latlon2a5(lat, lon, resolution)
        except Exception:
            return None

    def builder(cid, res):
        cell_polygon = a52geo(cid)
        if not cell_polygon:
            return None
        return cell_polygon, _geodesic_meta(cell_polygon, 5, cid, res)

    return run_raster2(
        raster_layer,
        resolution,
        method,
        stats,
        "a5",
        cell_id,
        lambda res, feat, fb: dggsgrid.generate_a5_grid(res, feat, fb),
        builder,
        feedback=feedback,
        layer_name="A5",
    )


def raster2rhealpix(
    raster_layer, resolution, feedback=None, method="nearest", stats="mean"
):
    def cell_id(lat, lon):
        try:
            return latlon2rhealpix(lat, lon, resolution)
        except Exception:
            return None

    def builder(cid, res):
        cell_polygon = rhealpix2geo(cid)
        if not cell_polygon:
            return None
        uids = (cid[0],) + tuple(map(int, cid[1:]))
        cell = _RHEALPIX_DGGS.cell(uids)
        num_edges = 3 if cell.ellipsoidal_shape() == "dart" else 4
        return cell_polygon, _geodesic_meta(cell_polygon, num_edges, cid, res)

    return run_raster2(
        raster_layer,
        resolution,
        method,
        stats,
        "rhealpix",
        cell_id,
        lambda res, feat, fb: dggsgrid.generate_rhealpix_grid(res, feat, fb),
        builder,
        feedback=feedback,
        layer_name="rHEALPix",
    )


def raster2qtm(raster_layer, resolution, feedback=None, method="nearest", stats="mean"):
    def cell_id(lat, lon):
        try:
            return latlon2qtm(lat, lon, resolution)
        except Exception:
            return None

    def builder(cid, res):
        cell_polygon = qtm2geo(cid)
        if not cell_polygon:
            return None
        return cell_polygon, _geodesic_meta(cell_polygon, 3, cid, res)

    return run_raster2(
        raster_layer,
        resolution,
        method,
        stats,
        "qtm",
        cell_id,
        lambda res, feat, fb: dggsgrid.generate_qtm_grid(res, feat, fb),
        builder,
        feedback=feedback,
        layer_name="QTM",
    )


def raster2olc(raster_layer, resolution, feedback=None, method="nearest", stats="mean"):
    def cell_id(lat, lon):
        try:
            return latlon2olc(lat, lon, resolution)
        except Exception:
            return None

    def builder(cid, res):
        cell_polygon = olc2geo(cid)
        if not cell_polygon:
            return None
        return cell_polygon, _geodesic_meta(cell_polygon, 4, cid, res)

    return run_raster2(
        raster_layer,
        resolution,
        method,
        stats,
        "olc",
        cell_id,
        lambda res, feat, fb: dggsgrid.generate_olc_grid(res, feat, fb),
        builder,
        feedback=feedback,
        layer_name="OLC",
    )


def raster2geohash(
    raster_layer, resolution, feedback=None, method="nearest", stats="mean"
):
    def cell_id(lat, lon):
        try:
            return latlon2geohash(lat, lon, resolution)
        except Exception:
            return None

    def builder(cid, res):
        cell_polygon = geohash2geo(cid)
        if not cell_polygon:
            return None
        return cell_polygon, _geodesic_meta(cell_polygon, 4, cid, res)

    return run_raster2(
        raster_layer,
        resolution,
        method,
        stats,
        "geohash",
        cell_id,
        lambda res, feat, fb: dggsgrid.generate_geohash_grid(res, feat, fb),
        builder,
        feedback=feedback,
        layer_name="Geohash",
    )


def raster2tilecode(
    raster_layer, resolution, feedback=None, method="nearest", stats="mean"
):
    def cell_id(lat, lon):
        try:
            return tilecode.latlon2tilecode(lat, lon, resolution)
        except Exception:
            return None

    def builder(cid, res):
        cell_polygon = tilecode2geo(cid)
        if not cell_polygon:
            return None
        return cell_polygon, _geodesic_meta(cell_polygon, 4, cid, res)

    return run_raster2(
        raster_layer,
        resolution,
        method,
        stats,
        "tilecode",
        cell_id,
        lambda res, feat, fb: dggsgrid.generate_tilecode_grid(res, feat, fb),
        builder,
        feedback=feedback,
        layer_name="Tilecode",
    )


def raster2quadkey(
    raster_layer, resolution, feedback=None, method="nearest", stats="mean"
):
    def cell_id(lat, lon):
        try:
            return tilecode.latlon2quadkey(lat, lon, resolution)
        except Exception:
            return None

    def builder(cid, res):
        cell_polygon = quadkey2geo(cid)
        if not cell_polygon:
            return None
        return cell_polygon, _geodesic_meta(cell_polygon, 4, cid, res)

    return run_raster2(
        raster_layer,
        resolution,
        method,
        stats,
        "quadkey",
        cell_id,
        lambda res, feat, fb: dggsgrid.generate_quadkey_grid(res, feat, fb),
        builder,
        feedback=feedback,
        layer_name="Quadkey",
    )


def raster2digipin(
    raster_layer, resolution, feedback=None, method="nearest", stats="mean"
):
    def cell_id(lat, lon):
        try:
            return latlon2digipin(lat, lon, resolution)
        except Exception:
            return None

    def builder(cid, res):
        cell_polygon = digipin2geo(cid)
        if not cell_polygon or isinstance(cell_polygon, str):
            return None
        clat, clon, cw, ch, carea, cperi = graticule_dggs_metrics(cell_polygon)
        return cell_polygon, {
            "id": cid,
            "resolution": res,
            "center_lat": clat,
            "center_lon": clon,
            "cell_width": cw,
            "cell_height": ch,
            "cell_area": carea,
            "cell_perimeter": cperi,
        }

    def digipin_grid_gen(res, feat, fb):
        from vgrid.generator.digipingrid import digipin_grid

        ext = feat.extent()
        bbox = (
            ext.xMinimum(),
            ext.yMinimum(),
            ext.xMaximum(),
            ext.yMaximum(),
        )
        gdf = digipin_grid(res, bbox)
        return gdf_to_qgs_vector_layer(gdf, "DIGIPIN")

    return run_raster2(
        raster_layer,
        resolution,
        method,
        stats,
        "digipin",
        cell_id,
        digipin_grid_gen,
        builder,
        feedback=feedback,
        layer_name="DIGIPIN",
        digipin_metrics_fn=True,
    )


def raster2dggal(
    raster_layer,
    resolution,
    feedback=None,
    dggal_type="gnosis",
    method="nearest",
    stats="mean",
):
    id_field = f"dggal_{dggal_type}"

    def cell_id(lat, lon):
        try:
            return latlon2dggal(dggal_type, lat, lon, resolution)
        except Exception:
            return None

    def builder(zone_id, res):
        try:
            cell_polygon = dggal2geo(dggal_type, zone_id)
            if not cell_polygon:
                return None
            cls_name = DGGAL_TYPES[dggal_type]["class_name"]
            dggrs = globals()[cls_name]()
            zone = dggrs.getZoneFromTextID(zone_id)
            num_edges = dggrs.countZoneEdges(zone)
            meta = _geodesic_meta(cell_polygon, num_edges, zone_id, res)
            return cell_polygon, meta
        except Exception:
            return None

    return run_raster2(
        raster_layer,
        resolution,
        method,
        stats,
        id_field,
        cell_id,
        lambda res, feat, fb: dggsgrid.generate_dggal_grid(dggal_type, res, feat, fb),
        builder,
        feedback=feedback,
        layer_name=f"DGGAL_{dggal_type}",
    )


if platform.system() == "Windows":

    def raster2isea4t(
        raster_layer, resolution, feedback=None, method="nearest", stats="mean"
    ):
        def cell_id(lat, lon):
            try:
                return latlon2isea4t(lat, lon, resolution)
            except Exception:
                return None

        def builder(cid, res):
            cell_polygon = isea4t2geo(cid)
            if not cell_polygon:
                return None
            return cell_polygon, _geodesic_meta(cell_polygon, 3, cid, res)

        return run_raster2(
            raster_layer,
            resolution,
            method,
            stats,
            "isea4t",
            cell_id,
            lambda res, feat, fb: dggsgrid.generate_isea4t_grid(res, feat, fb),
            builder,
            feedback=feedback,
            layer_name="ISEA4T",
        )

else:

    def raster2isea4t(
        raster_layer, resolution, feedback=None, method="nearest", stats="mean"
    ):
        raise RuntimeError("ISEA4T raster conversion requires Windows.")
