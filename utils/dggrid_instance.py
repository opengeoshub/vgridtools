# -*- coding: utf-8 -*-
"""Resolve DGGRID executable and create a configured DGGRIDv8 instance for QGIS."""

from __future__ import annotations

import os
import platform
from contextlib import contextmanager
from pathlib import Path

import requests
from dggrid4py import DGGRIDv8, tool
from qgis.core import QgsProcessingException

_PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DGGRID_DIR = os.path.join(_PLUGIN_ROOT, "dggrid")

# Non-geographic .prj metadata; antimeridian split/aggregate can crash PROJ in QGIS.
DGGRID_TYPES_NO_ANTIMERIDIAN = frozenset(
    {"SUPERFUND", "PLANETRISK", "ISEA4H", "ISEA43H", "FULLER4H", "FULLER43H", "FULLER7H"}
)

# DGGRID v8.43 accepts shapefile_id_field_length only in 1..50 (default 11).
_DGGRID_SHAPEFILE_ID_FIELD_LENGTH_MAX = 50


def build_dggrid_options(densification):
    """Extra kwargs for ``grid_cell_polygons_for_extent`` (densification, shapefile DBF width)."""
    return {
        "densification": densification,
        # Default 11 is too short for GEO, Z7_STRING, etc.; 50 is the DGGRID v8.43 maximum.
        "shapefile_id_field_length": _DGGRID_SHAPEFILE_ID_FIELD_LENGTH_MAX,
    }


def patch_dggrid_output_extras(dggrid_instance) -> None:
    """
    dggrid4py only writes ``output_extra_fields`` keys into the metafile.
    Register ``shapefile_id_field_length`` within the DGGRID v8.43 allowed range.
    """
    if getattr(dggrid_instance, "_vgrid_output_extras_patched", False):
        return

    extra_fields = dict(dggrid_instance.output_extra_fields)
    if "shapefile_id_field_length" not in extra_fields:
        extra_fields["shapefile_id_field_length"] = tuple(
            range(1, _DGGRID_SHAPEFILE_ID_FIELD_LENGTH_MAX + 1)
        )
    dggrid_instance.output_extra_fields = extra_fields
    dggrid_instance._vgrid_output_extras_patched = True

# dggrid4py 0.3.2 shipped portable binaries on its GitHub release; 0.5.3+ points
# Windows to DGGRID v8.43b (required for DGGRIDv8). Linux/mac URLs unchanged in 0.5.3.
_PORTABLE_RELEASE_032 = "https://github.com/allixender/dggrid4py/releases/download/v0.3.2"
_PORTABLE_URLS = {
    "linux-aarch64": f"{_PORTABLE_RELEASE_032}/dggrid-linux-aarch-gnu",
    "linux-x86_64": f"{_PORTABLE_RELEASE_032}/dggrid-linux-x64",
    "darwin-arm64": f"{_PORTABLE_RELEASE_032}/dggrid-macos-aarch",
    "windows-amd64": (
        "https://github.com/allixender/DGGRID/releases/download/v8.43b-1/dggrid-windows.exe"
    ),
}


def dggrid_work_dir() -> str:
    """Writable folder for DGGRID download and temp files (QGIS-safe substitute for '.')."""
    os.makedirs(_DGGRID_DIR, exist_ok=True)
    return _DGGRID_DIR


def _platform_key() -> str:
    uname = platform.uname()
    return f"{uname.system.lower()}-{uname.machine.lower()}"


def _portable_download_url() -> str:
    key = _platform_key()
    url = _PORTABLE_URLS.get(key)
    if not url:
        raise QgsProcessingException(
            f"No portable DGGRID build is available for {key}."
        )
    return url


def _find_cached_executable(folder: str) -> str | None:
    """Return newest dggrid* binary in *folder* (handles 0.3.2 and 0.5.3 filenames)."""
    if not os.path.isdir(folder):
        return None
    candidates = []
    for name in os.listdir(folder):
        path = os.path.join(folder, name)
        if not os.path.isfile(path) or os.path.getsize(path) == 0:
            continue
        low = name.lower()
        if low.startswith("dggrid") and (
            low.endswith(".exe")
            or low.startswith("dggrid-linux")
            or low.startswith("dggrid-macos")
        ):
            candidates.append(path)
    if not candidates:
        return None
    return os.path.abspath(max(candidates, key=os.path.getmtime))


def _download_portable_executable_fallback(folder: str) -> str:
    """Reliable download when ``tool.get_portable_executable`` fails (common on Windows/QGIS)."""
    url = _portable_download_url()
    local_path = os.path.join(folder, url.rsplit("/", 1)[-1])
    tmp_path = local_path + ".part"

    if os.path.exists(tmp_path):
        try:
            os.remove(tmp_path)
        except OSError:
            pass

    response = requests.get(url, stream=True, timeout=300)
    response.raise_for_status()

    try:
        with open(tmp_path, "wb") as handle:
            for chunk in response.iter_content(chunk_size=65536):
                if chunk:
                    handle.write(chunk)
        os.replace(tmp_path, local_path)
    except Exception:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
        raise

    return os.path.abspath(local_path)


def get_portable_executable(feedback=None) -> str:
    """
    Download or reuse the portable DGGRID binary.

    Uses ``tool.get_portable_executable`` like vgrid/notebook, with *folder* set to
    the plugin ``dggrid/`` directory instead of ``'.'`` (not writable under QGIS).
    """
    folder = dggrid_work_dir()
    cached = _find_cached_executable(folder)

    if cached:
        # dggrid4py 0.5.3 + DGGRIDv8 need DGGRID 8 (dggrid-windows.exe), not v0.3.2 x64 build.
        if _platform_key() == "windows-amd64" and cached.lower().endswith(
            "dggrid-windows-x64.exe"
        ):
            if feedback:
                feedback.pushInfo(
                    "Replacing legacy v0.3.2 portable binary with DGGRID v8.43b..."
                )
            cached = None
        else:
            if feedback:
                feedback.pushInfo(f"Using cached DGGRID executable: {cached}")
            return cached

    if feedback:
        try:
            import dggrid4py

            version = getattr(dggrid4py, "__version__", "unknown")
        except Exception:
            version = "unknown"
        feedback.pushInfo(
            f"Downloading portable DGGRID to {folder} (dggrid4py {version})..."
        )

    # On Windows/QGIS, dggrid4py's downloader often hits [Errno 9]; use fallback first.
    if _platform_key() == "windows-amd64":
        try:
            executable = _download_portable_executable_fallback(folder)
        except Exception as exc:
            try:
                executable = tool.get_portable_executable(folder)
            except Exception as tool_exc:
                raise QgsProcessingException(
                    "Failed to download the portable DGGRID executable. "
                    f"Folder: {folder}. Fallback: {exc}. dggrid4py tool: {tool_exc}"
                ) from tool_exc
    else:
        try:
            executable = tool.get_portable_executable(folder)
        except OSError:
            executable = _download_portable_executable_fallback(folder)
        except Exception as exc:
            raise QgsProcessingException(
                "Failed to download the portable DGGRID executable. "
                f"Folder: {folder}. Error: {exc}"
            ) from exc

    executable = os.path.abspath(executable)
    if not os.path.isfile(executable):
        raise QgsProcessingException(
            f"DGGRID download reported success but file is missing: {executable}"
        )

    if feedback:
        feedback.pushInfo(f"DGGRID executable ready: {executable}")
    return executable


def _is_crs_read_error(exc: BaseException) -> bool:
    message = str(exc).lower()
    name = type(exc).__name__.lower()
    return (
        "invalid ellipsoid" in message
        or "crserror" in name
        or ("proj" in message and "ellipsoid" in message)
    )


def _is_shapefile_path(path_or_buffer, driver=None) -> bool:
    path = Path(path_or_buffer)
    if path.suffix.lower() == ".shp":
        return True
    if driver and "shape" in str(driver).lower():
        return True
    return False


def _read_geofile_ignore_bad_crs(path_or_buffer, driver=None):
    """Read DGGRID shapefile output without parsing .prj (avoids pyogrio/PROJ crashes in QGIS)."""
    import geopandas as gpd
    from shapely.geometry import shape
    from shapely.geometry.base import BaseGeometry

    path = Path(path_or_buffer)
    read_driver = driver or "ESRI Shapefile"
    renamed_sidecars = []
    if path.suffix.lower() == ".shp":
        for ext in (".prj", ".cpg"):
            sidecar = path.with_suffix(ext)
            backup = sidecar.with_suffix(sidecar.suffix + ".bak")
            if not sidecar.exists() and backup.exists():
                backup.rename(sidecar)
            if sidecar.exists():
                sidecar.rename(backup)
                renamed_sidecars.append((sidecar, backup))

    try:
        try:
            # Without .prj, geopandas reads polygons correctly (same as the notebook).
            gdf = gpd.read_file(str(path), driver=read_driver)
            if isinstance(gdf, gpd.GeoDataFrame) and len(gdf) > 0:
                if isinstance(gdf.geometry.iloc[0], BaseGeometry):
                    gdf.crs = None
                    return gdf
        except Exception:
            pass

        import fiona

        with fiona.open(str(path), driver=read_driver) as collection:
            features = list(collection)
        if not features:
            return gpd.GeoDataFrame(geometry=[], crs=None)

        records = []
        geometries = []
        for feat in features:
            geometries.append(shape(feat["geometry"]))
            props = dict(feat.get("properties") or {})
            props.pop("geometry", None)
            records.append(props)
        return gpd.GeoDataFrame(records, geometry=geometries, crs=None)
    finally:
        for sidecar, backup in renamed_sidecars:
            if backup.exists():
                if sidecar.exists():
                    sidecar.unlink()
                backup.rename(sidecar)


@contextmanager
def patch_geopandas_read_for_dggrid():
    """Patch geopandas.read_file while dggrid4py reads DGGRID temp layers."""
    import geopandas as gpd

    original_read_file = gpd.read_file

    def read_file_with_crs_fallback(path_or_buffer, *args, **kwargs):
        driver = kwargs.get("driver")
        # Always avoid parsing .prj for DGGRID shapefiles (SUPERFUND etc. crash pyproj).
        if _is_shapefile_path(path_or_buffer, driver):
            return _read_geofile_ignore_bad_crs(path_or_buffer, driver=driver)
        try:
            return original_read_file(path_or_buffer, *args, **kwargs)
        except Exception as exc:
            if not _is_crs_read_error(exc):
                raise
            return _read_geofile_ignore_bad_crs(
                path_or_buffer, driver=driver
            )

    gpd.read_file = read_file_with_crs_fallback
    try:
        yield
    finally:
        gpd.read_file = original_read_file


def _crs_safe_for_qgis(crs):
    """Avoid pyproj/PROJ access violations inside QGIS (dggrid4py uses crs=4326)."""
    if crs is None:
        return None
    if crs == 4326 or crs == "4326" or crs == "EPSG:4326":
        return None
    return crs


@contextmanager
def patch_geopandas_for_dggrid_qgis():
    """
    Patches geopandas while dggrid4py runs inside QGIS.

    - Skips crs=4326 on GeoDataFrame creation (clip_geom path in dggrid_runner).
    - Reads DGGRID shapefile output without parsing .prj.
    """
    import geopandas as gpd

    original_gdf_init = gpd.GeoDataFrame.__init__

    def gdf_init_no_epsg4326(self, data=None, *args, crs=None, **kwargs):
        crs = _crs_safe_for_qgis(crs)
        return original_gdf_init(self, data, *args, crs=crs, **kwargs)

    gpd.GeoDataFrame.__init__ = gdf_init_no_epsg4326
    with patch_geopandas_read_for_dggrid():
        try:
            yield
        finally:
            gpd.GeoDataFrame.__init__ = original_gdf_init


def _ensure_active_geometry_qgis(gdf):
    """Ensure GeoDataFrame has a valid geometry column (no pyproj set_crs)."""
    import geopandas as gpd
    from shapely.geometry.base import BaseGeometry

    if not isinstance(gdf, gpd.GeoDataFrame):
        gdf = gpd.GeoDataFrame(gdf, crs=None)

    if len(gdf) == 0:
        return gdf

    if isinstance(gdf.geometry, gpd.GeoSeries) and isinstance(
        gdf.geometry.iloc[0], BaseGeometry
    ):
        return gdf

    for col in gdf.columns:
        if len(gdf) > 0 and isinstance(gdf[col].iloc[0], BaseGeometry):
            return gdf.set_geometry(col, crs=None)

    return gdf


def generate_grid_qgis(
    dggrid_instance,
    dggs_type,
    resolution,
    bbox,
    output_address_type="SEQNUM",
    split_antimeridian=False,
    aggregate=False,
    options=None,
):
    """Same logic as vgrid.generator.dggridgen.generate_grid, without pyproj set_crs."""
    from shapely.geometry import box

    from vgrid.utils.io import (
        is_full_world_bbox,
        validate_bbox,
        validate_dggrid_resolution,
        validate_dggrid_type,
    )

    dggs_type = validate_dggrid_type(dggs_type)
    resolution = validate_dggrid_resolution(dggs_type, resolution)
    bbox = validate_bbox(bbox)
    if bbox and is_full_world_bbox(bbox):
        bbox = None

    if dggs_type in DGGRID_TYPES_NO_ANTIMERIDIAN:
        split_antimeridian = False
        aggregate = False

    with patch_geopandas_for_dggrid_qgis():
        if bbox:
            bounding_box = box(*bbox)
            kwargs = {
                "split_dateline": False,
                "output_address_type": output_address_type,
            }
            if options:
                kwargs.update(options)
            dggrid_gdf = dggrid_instance.grid_cell_polygons_for_extent(
                dggs_type,
                resolution,
                clip_geom=bounding_box,
                **kwargs,
            )
        else:
            kwargs = {
                "split_dateline": split_antimeridian,
                "output_address_type": output_address_type,
            }
            if options:
                kwargs.update(options)
            dggrid_gdf = dggrid_instance.grid_cell_polygons_for_extent(
                dggs_type,
                resolution,
                **kwargs,
            )

    dggrid_gdf = _ensure_active_geometry_qgis(dggrid_gdf)

    if split_antimeridian and aggregate:
        dggrid_gdf = dggrid_gdf.dissolve(by="global_id", as_index=False)
        dggrid_gdf = _ensure_active_geometry_qgis(dggrid_gdf)

    return dggrid_gdf



def _ensure_dggrid_global_id_column(grid_gdf):
    """Normalize DGGRID grid output to a ``global_id`` column for joins."""
    import geopandas as gpd

    gdf = grid_gdf.copy()
    if "global_id" in gdf.columns:
        gdf["global_id"] = gdf["global_id"].map(
            lambda v: normalize_dggrid_cell_id(v) if v is not None else None
        )
        return gdf, "global_id"

    for col in ("name", "seqnum"):
        if col in gdf.columns:
            gdf["global_id"] = gdf[col].map(
                lambda v: normalize_dggrid_cell_id(v) if v is not None else None
            )
            return gdf, "global_id"

    raise ValueError("DGGRID grid output has no cell ID column (global_id, name, seqnum).")


def dggrid_bin_qgis(
    dggrid_instance,
    dggs_type,
    points_gdf,
    resolution,
    stats="count",
    category=None,
    numeric_field=None,
    options=None,
    feedback=None,
):
    """
    Bin points into DGGRID cells by generating a grid over the point extent,
    spatial join (within), and aggregation — same logic as vgrid ``dggrid_bin``.
    """
    import geopandas as gpd
    from vgrid.utils.io import aggregate_joined, validate_dggrid_resolution, validate_dggrid_type

    dggs_type = validate_dggrid_type(dggs_type)
    resolution = validate_dggrid_resolution(dggs_type, resolution)

    if stats != "count" and not numeric_field:
        raise ValueError(
            "A numeric_field is required for statistics other than 'count'"
        )

    if points_gdf is None or points_gdf.empty:
        return gpd.GeoDataFrame(crs="EPSG:4326")

    points_gdf = points_gdf[
        points_gdf.geometry.geom_type.isin(["Point", "MultiPoint"])
    ].copy()
    if "MultiPoint" in set(points_gdf.geometry.geom_type.unique()):
        points_gdf = points_gdf.explode(index_parts=False, ignore_index=True)

    if points_gdf.empty:
        return gpd.GeoDataFrame(crs="EPSG:4326")

    minx, miny, maxx, maxy = points_gdf.total_bounds
    bbox = (minx, miny, maxx, maxy)

    if feedback:
        feedback.pushInfo(
            f"Generating DGGRID {dggs_type} grid for point layer extent..."
        )

    grid_gdf = generate_grid_qgis(
        dggrid_instance,
        dggs_type,
        resolution,
        bbox,
        output_address_type="SEQNUM",
        split_antimeridian=False,
        aggregate=False,
        options=options,
    )
    grid_gdf, id_col = _ensure_dggrid_global_id_column(grid_gdf)

    if grid_gdf.crs is None:
        grid_gdf = grid_gdf.set_crs(points_gdf.crs or "EPSG:4326")
    elif points_gdf.crs is not None and grid_gdf.crs != points_gdf.crs:
        grid_gdf = grid_gdf.to_crs(points_gdf.crs)

    join_cols = []
    if category and category in points_gdf.columns:
        join_cols.append(category)
    if stats != "count" and numeric_field:
        if numeric_field not in points_gdf.columns:
            raise ValueError(f"numeric_field '{numeric_field}' not found in input layer")
        join_cols.append(numeric_field)

    left = points_gdf[[c for c in ["geometry", *join_cols] if c]]
    joined = gpd.sjoin(
        left,
        grid_gdf[[id_col, "geometry"]],
        how="inner",
        predicate="within",
    )

    if feedback:
        feedback.pushInfo(
            f"Aggregating {len(joined)} point-in-cell match(es) ({stats})..."
        )

    grouped = aggregate_joined(
        joined, id_col, stats=stats, category=category, numeric_field=numeric_field
    )
    grouped = grouped.reset_index()

    out = grid_gdf.merge(grouped, on=id_col, how="inner")
    out = out.rename(columns={id_col: f"dggrid_{dggs_type.lower()}"})
    if "resolution" not in out.columns:
        out["resolution"] = resolution

    return gpd.GeoDataFrame(out, geometry="geometry", crs=grid_gdf.crs or "EPSG:4326")


def vector_geom_to_dggrid_gdf_qgis(
    dggrid_instance,
    dggs_type,
    shapely_geom,
    resolution,
    predicate=None,
    output_address_type="SEQNUM",
    options=None,
):
    """
    DGGRID cells for one Shapely geometry (point/line/polygon).

    Uses ``generate_grid_qgis`` / cached cell lookup instead of vgrid
    ``vector2dggrid`` so pyproj is never invoked with EPSG:4326 inside QGIS.
    """
    import geopandas as gpd

    from vgrid.utils.geometry import check_predicate
    from vgrid.utils.io import validate_dggrid_resolution, validate_dggrid_type

    dggs_type = validate_dggrid_type(dggs_type)
    resolution = validate_dggrid_resolution(dggs_type, resolution)
    geom_type = shapely_geom.geom_type

    if geom_type == "Point":
        cell_id = cached_latlon2dggrid(
            dggrid_instance,
            dggs_type,
            float(shapely_geom.y),
            float(shapely_geom.x),
            resolution,
            output_address_type,
        )
        cell_geom = cached_dggrid_cell_geometry(
            dggrid_instance,
            dggs_type,
            cell_id,
            resolution,
            split_antimeridian=dggs_type not in DGGRID_TYPES_NO_ANTIMERIDIAN,
            options=options,
        )
        id_col = "seqnum" if output_address_type == "SEQNUM" else output_address_type.lower()
        return gpd.GeoDataFrame(
            {id_col: [str(cell_id)], "geometry": [cell_geom]},
            geometry="geometry",
            crs=None,
        )

    gdf = generate_grid_qgis(
        dggrid_instance,
        dggs_type,
        resolution,
        shapely_geom.bounds,
        output_address_type=output_address_type,
        split_antimeridian=False,
        aggregate=False,
        options=options,
    )

    if gdf is None or gdf.empty:
        return gdf

    if output_address_type == "SEQNUM" and "name" in gdf.columns and "seqnum" not in gdf.columns:
        gdf = gdf.rename(columns={"name": "seqnum"})

    if geom_type in ("LineString", "LinearRing"):
        gdf = gdf[gdf.intersects(shapely_geom)]
    elif geom_type == "Polygon":
        if predicate:
            gdf = gdf[
                gdf.geometry.apply(
                    lambda cell: check_predicate(cell, shapely_geom, predicate)
                )
            ]
        else:
            gdf = gdf[gdf.intersects(shapely_geom)]

    return _ensure_active_geometry_qgis(gdf)


def create_dggrid_instance(executable=None, feedback=None, **kwargs) -> DGGRIDv8:
    """
    Create a DGGRIDv8 instance (same options as vgrid notebook ``09_dggrid.ipynb``).

    Download uses ``tool.get_portable_executable(folder)`` with *folder* =
    ``<plugin>/dggrid`` instead of ``'.'``, which is not reliable inside QGIS.
    """
    work_dir = dggrid_work_dir()

    if executable is None:
        executable = get_portable_executable(feedback=feedback)

    dggrid_instance = DGGRIDv8(
        executable=executable,
        working_dir=work_dir,
        capture_logs=True,
        silent=True,
        has_gdal=False,
        tmp_geo_out_legacy=True,
        debug=False,
        **kwargs,
    )
    patch_dggrid_output_extras(dggrid_instance)
    return dggrid_instance


_plugin_dggrid_instance: DGGRIDv8 | None = None

# In-memory cache: each DGGRID subprocess is slow (~1–3s). Reuse results for repeated lookups.
_DGGRID_LATLON_CACHE: dict = {}
_DGGRID_GEO_WKT_CACHE: dict = {}
_DGGRID_CACHE_MAX = 512


def clear_dggrid_conversion_cache() -> None:
    """Drop cached lat/lon and cell-id → polygon conversions."""
    _DGGRID_LATLON_CACHE.clear()
    _DGGRID_GEO_WKT_CACHE.clear()


def _dggrid_cache_put(cache: dict, key, value) -> None:
    if len(cache) >= _DGGRID_CACHE_MAX:
        cache.pop(next(iter(cache)))
    cache[key] = value


def dggrid_latlon_cell_options():
    """DGGRID options for single-cell polygon lookup (low densification = faster)."""
    return build_dggrid_options(0)


def cached_latlon2dggrid(
    dggrid_instance,
    dggs_type,
    lat,
    lon,
    res,
    output_address_type="SEQNUM",
):
    """Cached wrapper around vgrid ``latlon2dggrid`` (one DGGRID run per unique point/type/res)."""
    from vgrid.conversion.latlon2dggs import latlon2dggrid

    key = (round(lat, 6), round(lon, 6), dggs_type, res, output_address_type)
    if key in _DGGRID_LATLON_CACHE:
        return _DGGRID_LATLON_CACHE[key]
    value = latlon2dggrid(
        dggrid_instance,
        dggs_type,
        lat,
        lon,
        res,
        output_address_type=output_address_type,
    )
    _dggrid_cache_put(_DGGRID_LATLON_CACHE, key, value)
    return value


def normalize_dggrid_cell_id(cell_id):
    """Normalize attribute/csv cell IDs so joins match DGGRID output (e.g. 1.0 -> 1)."""
    if cell_id is None:
        return None
    if isinstance(cell_id, bool):
        return str(cell_id)
    if isinstance(cell_id, int):
        return str(cell_id)
    if isinstance(cell_id, float):
        if cell_id == int(cell_id):
            return str(int(cell_id))
        return str(cell_id).strip()
    text = str(cell_id).strip()
    if not text:
        return None
    try:
        number = float(text)
        if number == int(number):
            return str(int(number))
    except ValueError:
        pass
    return text


def _dggrid_row_cell_id(row, id_col):
    for col in (id_col, "seqnum", "global_id", "name"):
        if col in row.index:
            val = row[col]
            if val is not None:
                return normalize_dggrid_cell_id(val)
    return None


def batch_dggrid_cells_qgis(
    dggrid_instance,
    dggs_type,
    cell_ids,
    resolution,
    output_address_type="SEQNUM",
    options=None,
    feedback=None,
):
    """
    Convert many DGGRID cell IDs in one ``dggrid2geo`` call.

    Returns a dict ``{cell_id_str: cell_info}`` where *cell_info* has geometry,
    metrics, and resolution. Also seeds the geometry WKT cache for reuse.
    """
    from vgrid.conversion.dggs2geo.dggrid2geo import dggrid2geo
    from vgrid.utils.geometry import geodesic_dggs_metrics
    from vgrid.utils.io import validate_dggrid_resolution, validate_dggrid_type

    dggs_type = validate_dggrid_type(dggs_type)
    resolution = validate_dggrid_resolution(dggs_type, resolution)
    split_antimeridian = dggs_type not in DGGRID_TYPES_NO_ANTIMERIDIAN
    id_col = f"dggrid_{dggs_type.lower()}"

    batch_ids = []
    for cell_id in cell_ids:
        cell_id_str = normalize_dggrid_cell_id(cell_id)
        if cell_id_str:
            batch_ids.append(cell_id_str)

    if not batch_ids:
        return {}

    if feedback:
        feedback.pushInfo(
            f"Converting {len(batch_ids)} DGGRID cell ID(s) in one batch..."
        )

    with patch_geopandas_for_dggrid_qgis():
        gdf = dggrid2geo(
            dggrid_instance,
            dggs_type,
            batch_ids,
            resolution,
            input_address_type=output_address_type,
            split_antimeridian=split_antimeridian,
            aggregate=False,
            options=options,
        )

    if gdf is None or gdf.empty:
        return {}

    lookup = {}
    opt_key = tuple(sorted((options or {}).items()))
    total = len(gdf)
    gdf = gdf.reset_index(drop=True)
    use_input_order = len(gdf) == len(batch_ids)

    if feedback and use_input_order:
        feedback.pushInfo(
            "Indexing DGGRID polygons by input cell ID order (shapefile IDs may differ)."
        )

    from vgrid.utils.geometry import dggrid_num_edges

    num_edges = dggrid_num_edges(dggs_type)
    for idx in range(len(gdf)):
        if feedback and feedback.isCanceled():
            break

        row = gdf.iloc[idx]
        geom = row.geometry
        if geom is None or geom.is_empty:
            continue

        if use_input_order:
            cell_id_str = batch_ids[idx]
        else:
            cell_id_str = _dggrid_row_cell_id(row, id_col)
        if not cell_id_str:
            continue

        center_lat, center_lon, avg_edge_len, cell_area, cell_perimeter = (
            geodesic_dggs_metrics(geom, num_edges)
        )
        cell_info = {
            "geometry": geom,
            "cell_id": cell_id_str,
            "resolution": resolution,
            "center_lat": center_lat,
            "center_lon": center_lon,
            "avg_edge_len": avg_edge_len,
            "cell_area": cell_area,
            "cell_perimeter": cell_perimeter,
        }
        lookup[cell_id_str] = cell_info

        row_id = _dggrid_row_cell_id(row, id_col)
        if row_id and row_id != cell_id_str:
            lookup[row_id] = cell_info

        cache_key = (dggs_type, cell_id_str, resolution, split_antimeridian, opt_key)
        _dggrid_cache_put(_DGGRID_GEO_WKT_CACHE, cache_key, geom.wkt)

        if feedback and total and idx % 100 == 0:
            feedback.setProgress(int(40 * idx / total))

    if feedback:
        feedback.setProgress(50)

    return lookup


def cached_dggrid_cell_geometry(
    dggrid_instance,
    dggs_type,
    cell_id,
    res,
    split_antimeridian=False,
    options=None,
):
    """Cached wrapper around vgrid ``dggrid2geo`` returning a Shapely geometry."""
    from shapely import wkt

    cell_id_str = str(cell_id).strip()
    opt_key = tuple(sorted((options or {}).items()))
    key = (dggs_type, cell_id_str, res, split_antimeridian, opt_key)
    if key in _DGGRID_GEO_WKT_CACHE:
        return wkt.loads(_DGGRID_GEO_WKT_CACHE[key])

    lookup = batch_dggrid_cells_qgis(
        dggrid_instance,
        dggs_type,
        [cell_id_str],
        res,
        split_antimeridian=split_antimeridian,
        options=options,
    )
    info = lookup.get(cell_id_str)
    if not info:
        raise ValueError("empty DGGRID cell")
    return info["geometry"]


def plugin_dggrid_instance_initialized() -> bool:
    return _plugin_dggrid_instance is not None


def reset_plugin_dggrid_instance() -> None:
    """Drop the shared plugin DGGRID instance (e.g. after cache clear or plugin unload)."""
    global _plugin_dggrid_instance
    _plugin_dggrid_instance = None
    clear_dggrid_conversion_cache()


def get_plugin_dggrid_instance(feedback=None, force_new: bool = False) -> DGGRIDv8:
    """
    Return the single shared DGGRIDv8 instance for Generator, Viz, and other plugin code.

    Created on first use, or replaced when *force_new* is True (Utils → Create DGGRID Instance).
    """
    global _plugin_dggrid_instance
    if force_new:
        reset_plugin_dggrid_instance()
    if _plugin_dggrid_instance is None:
        _plugin_dggrid_instance = create_dggrid_instance(feedback=feedback)
    return _plugin_dggrid_instance


def _is_dggrid_cache_artifact(name: str) -> bool:
    """True for DGGRID run leftovers (not the portable executable)."""
    low = name.lower()
    return (
        low.endswith(".txt")
        or low.startswith("meta")
        or low.startswith("temp")
    )


def clear_dggrid_cache_files() -> tuple[list[str], list[tuple[str, str]]]:
    """
    Delete DGGRID cache artifacts under the plugin ``dggrid/`` folder:
    ``*.txt``, names starting with ``meta``, and names starting with ``temp``.

    Returns ``(removed_names, [(name, error), ...])``.
    """
    folder = dggrid_work_dir()
    removed: list[str] = []
    errors: list[tuple[str, str]] = []
    if not os.path.isdir(folder):
        return removed, errors

    for name in os.listdir(folder):
        if not _is_dggrid_cache_artifact(name):
            continue
        path = os.path.join(folder, name)
        try:
            if os.path.isfile(path) or os.path.islink(path):
                os.remove(path)
                removed.append(name)
        except OSError as exc:
            errors.append((name, str(exc)))
    clear_dggrid_conversion_cache()
    return removed, errors


def create_plugin_dggrid_instance(feedback=None, **kwargs) -> DGGRIDv8:
    """Return the shared plugin instance (or create it). Pass extra *kwargs* only for a one-off instance."""
    if kwargs:
        return create_dggrid_instance(feedback=feedback, **kwargs)
    return get_plugin_dggrid_instance(feedback=feedback)
