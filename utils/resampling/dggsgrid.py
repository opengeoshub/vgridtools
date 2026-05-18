from collections import deque

from shapely import make_valid
from shapely.wkt import loads as load_wkt
from shapely.geometry import Polygon, box, shape
from shapely.ops import unary_union
import a5
from vgrid.generator.geohashgrid import expand_geohash_bbox
from qgis.core import (
    QgsVectorLayer,
    QgsFields,
    QgsField,
    QgsFeature,
    QgsGeometry,
)
from qgis.PyQt.QtCore import QVariant
import h3
from vgrid.dggs import s2, qtm, olc, mercantile
from vgrid.generator.olcgrid import olc_refine_cell
from vgrid.utils.antimeridian import fix_polygon
from vgrid.utils.geometry import (
    geodesic_dggs_metrics,
    graticule_dggs_metrics,
    graticule_dggs_to_geoseries,
)
from vgrid.utils.constants import INITIAL_GEOHASHES
from vgrid.utils.io import (
    is_full_world_bbox,
    validate_a5_resolution,
    validate_bbox,
    validate_geohash_resolution,
    validate_h3_resolution,
    validate_isea4t_resolution,
    validate_olc_resolution,
    validate_qtm_resolution,
    validate_quadkey_resolution,
    validate_rhealpix_resolution,
    validate_s2_resolution,
    validate_tilecode_resolution,
)
from vgrid.conversion.dggs2geo.a52geo import a52geo_u64
from vgrid.conversion.dggs2geo.geohash2geo import geohash2geo
from vgrid.conversion.dggs2geo.s22geo import s22geo
from vgrid.conversion.dggs2geo.h32geo import h32geo
from vgrid.conversion.dggs2geo.rhealpix2geo import rhealpix2geo
from vgrid.dggs.rhealpixdggs.dggs import RHEALPixDGGS
from vgrid.dggs.rhealpixdggs.ellipsoids import WGS84_ELLIPSOID
import platform

_RHEALPIX_DGGS = RHEALPixDGGS(
    ellipsoid=WGS84_ELLIPSOID, north_square=1, south_square=3, N_side=3
)

if platform.system() == "Windows":
    from vgrid.dggs.eaggr.enums.model import Model
    from vgrid.dggs.eaggr.eaggr import Eaggr
    from vgrid.dggs.eaggr.shapes.dggs_cell import DggsCell
    from vgrid.dggs.eaggr.enums.shape_string_format import ShapeStringFormat
    from vgrid.conversion.dggs2geo.isea4t2geo import isea4t2geo
    from vgrid.utils.constants import ISEA4T_BASE_CELLS, ISEA4T_RES_ACCURACY_DICT
    from vgrid.generator.isea4tgrid import (
        get_isea4t_children_cells,
        get_isea4t_children_cells_within_bbox,
    )

    isea4t_dggs = Eaggr(Model.ISEA4T)
    isea3h_dggs = Eaggr(Model.ISEA3H)

p90_n180, p90_n90, p90_p0, p90_p90, p90_p180 = (
    (90.0, -180.0),
    (90.0, -90.0),
    (90.0, 0.0),
    (90.0, 90.0),
    (90.0, 180.0),
)
p0_n180, p0_n90, p0_p0, p0_p90, p0_p180 = (
    (0.0, -180.0),
    (0.0, -90.0),
    (0.0, 0.0),
    (0.0, 90.0),
    (0.0, 180.0),
)
n90_n180, n90_n90, n90_p0, n90_p90, n90_p180 = (
    (-90.0, -180.0),
    (-90.0, -90.0),
    (-90.0, 0.0),
    (-90.0, 90.0),
    (-90.0, 180.0),
)


WEB_MERCATOR_BBOX = [-180.0, -85.05112878, 180.0, 85.05112878]

_SHIFT_FIX = {
    "h3": "shift_west",
    "s2": "shift_east",
    "rhealpix": "shift_east",
    "isea4t": "shift_west",
}


def _resolve_fix_antimeridian(to_dggs, shift_antimeridian=False, split_antimeridian=False):
    """Map generator-style booleans to ``fix_antimeridian`` for geo converters."""
    if split_antimeridian:
        return "split"
    if shift_antimeridian:
        key = to_dggs.lower().replace("dggal_", "")
        return _SHIFT_FIX.get(key, "shift_west")
    return None


def _use_split_antimeridian(shift_antimeridian=False, split_antimeridian=False):
    return split_antimeridian or shift_antimeridian


def _bbox_from_unified_geom(unified_geom):
    min_lon, min_lat, max_lon, max_lat = unified_geom.bounds
    try:
        return validate_bbox([min_lon, min_lat, max_lon, max_lat])
    except ValueError:
        return [-180.0, -90.0, 180.0, 90.0]


def _ensure_valid_geometry(geom):
    """Repair invalid polygons (e.g. after antimeridian shift) before set ops."""
    if geom is None or geom.is_empty:
        return geom
    if geom.is_valid:
        return geom
    fixed = make_valid(geom)
    if fixed.is_empty:
        return fixed
    if fixed.geom_type == "GeometryCollection":
        polys = [
            g
            for g in fixed.geoms
            if g.geom_type in ("Polygon", "MultiPolygon") and not g.is_empty
        ]
        if polys:
            fixed = max(polys, key=lambda g: g.area)
    if not fixed.is_valid:
        fixed = fixed.buffer(0)
    return fixed


def _safe_intersection(geom_a, geom_b):
    """Intersection with geometry repair on topological failures."""
    try:
        inter = geom_a.intersection(geom_b)
        if not inter.is_empty:
            return inter
    except Exception:
        pass
    a = _ensure_valid_geometry(geom_a)
    b = _ensure_valid_geometry(geom_b)
    return a.intersection(b)


def _unified_footprint(geometries):
    """Union footprint for intersection tests; falls back to envelope union."""
    fixed = [_ensure_valid_geometry(g) for g in geometries]
    try:
        unified = unary_union(fixed)
        if unified.is_empty:
            raise ValueError("empty union")
        return _ensure_valid_geometry(unified)
    except Exception:
        return unary_union([g.envelope for g in fixed])


def _unified_geom_and_bbox(qgs_features):
    geometries = []
    for feature in qgs_features.getFeatures():
        geom = load_wkt(feature.geometry().asWkt())
        if geom is None or geom.is_empty:
            continue
        geometries.append(geom)
    if not geometries:
        raise ValueError("No valid geometries in input layer.")
    unified_geom = _unified_footprint(geometries)
    footprint = box(
        min(g.bounds[0] for g in geometries),
        min(g.bounds[1] for g in geometries),
        max(g.bounds[2] for g in geometries),
        max(g.bounds[3] for g in geometries),
    )
    bbox = _bbox_from_unified_geom(footprint)
    return unified_geom, bbox


#########################
# H3
#########################

def _h3_cell_ids_full_world(resolution):
    """All H3 cell IDs at resolution (same path as vgrid ``h3_grid``)."""
    cells = []
    for cell in h3.get_res0_cells():
        cells.extend(h3.cell_to_children(cell, resolution))
    return cells


def generate_h3_grid(
    resolution,
    qgs_features,
    feedback=None,
    shift_antimeridian=False,
    split_antimeridian=False,
):
    if not qgs_features:
        raise ValueError("No features provided for H3 grid generation.")

    resolution = validate_h3_resolution(resolution)
    unified_geom, bbox = _unified_geom_and_bbox(qgs_features)
    fix = _resolve_fix_antimeridian("h3", shift_antimeridian, split_antimeridian)
    bbox_polygon = None

    if is_full_world_bbox(bbox):
        h3_cells = _h3_cell_ids_full_world(resolution)
    else:
        bbox_polygon = box(*bbox)
        h3_cells = h3.geo_to_cells(bbox_polygon, resolution)

    total = len(h3_cells)

    if feedback:
        feedback.pushInfo(
            f"Generating H3 grid at resolution {resolution} with {total} cells..."
        )

    h3_features = []
    for idx, h3_cell in enumerate(h3_cells):
        if feedback:
            if feedback.isCanceled():
                return None
            feedback.setProgress(int((idx / total) * 100))

        cell_polygon = (
            h32geo(h3_cell, fix_antimeridian=fix) if fix else h32geo(h3_cell)
        )
        if bbox_polygon is not None and not cell_polygon.intersects(bbox_polygon):
            continue
        if not cell_polygon.intersects(unified_geom):
            continue

        h3_id = str(h3_cell)
        num_edges = 6 if not h3.is_pentagon(h3_id) else 5
        center_lat, center_lon, avg_edge_len, cell_area, cell_perimeter = (
            geodesic_dggs_metrics(cell_polygon, num_edges)
        )

        qgs_feature = QgsFeature()
        qgs_feature.setGeometry(QgsGeometry.fromWkt(cell_polygon.wkt))
        qgs_feature.setAttributes(
            [
                h3_id,
                resolution,
                center_lat,
                center_lon,
                avg_edge_len,
                cell_area,
                cell_perimeter,
            ]
        )
        h3_features.append(qgs_feature)

    fields = QgsFields()
    fields.append(QgsField("h3", QVariant.String))
    fields.append(QgsField("resolution", QVariant.Int))
    fields.append(QgsField("center_lat", QVariant.Double))
    fields.append(QgsField("center_lon", QVariant.Double))
    fields.append(QgsField("avg_edge_len", QVariant.Double))
    fields.append(QgsField("cell_area", QVariant.Double))
    fields.append(QgsField("cell_perimeter", QVariant.Double))

    layer = QgsVectorLayer("Polygon?crs=EPSG:4326", f"h3_{resolution}", "memory")
    layer.startEditing()
    layer.dataProvider().addAttributes(fields)
    layer.updateFields()
    layer.dataProvider().addFeatures(h3_features)
    layer.commitChanges()

    if feedback:
        feedback.setProgress(100)
        feedback.pushInfo("H3 grid generation complete.")

    return layer


#########################
# S2
#########################
def generate_s2_grid(
    resolution,
    qgs_features,
    feedback=None,
    shift_antimeridian=False,
    split_antimeridian=False,
):
    if not qgs_features:
        raise ValueError("No features provided for S2 grid generation.")

    resolution = validate_s2_resolution(resolution)
    unified_geom, bbox = _unified_geom_and_bbox(qgs_features)
    min_lon, min_lat, max_lon, max_lat = bbox
    fix = _resolve_fix_antimeridian("s2", shift_antimeridian, split_antimeridian)

    level = resolution
    coverer = s2.RegionCoverer()
    coverer.min_level = level
    coverer.max_level = level

    region = s2.LatLngRect(
        s2.LatLng.from_degrees(min_lat, min_lon),
        s2.LatLng.from_degrees(max_lat, max_lon),
    )

    covering = coverer.get_covering(region)

    s2_features = []
    total = len(covering)

    if feedback:
        feedback.pushInfo(
            f"Generating S2 grid at resolution {resolution} with {total} cells..."
        )

    for idx, cell_id in enumerate(covering):
        if feedback:
            if feedback.isCanceled():
                return None
            feedback.setProgress(int((idx / total) * 100))

        s2_token = cell_id.to_token()
        cell_polygon = (
            s22geo(s2_token, fix_antimeridian=fix) if fix else s22geo(s2_token)
        )
        if not cell_polygon.intersects(unified_geom):
            continue
        num_edges = 4
        center_lat, center_lon, avg_edge_len, cell_area, cell_perimeter = (
            geodesic_dggs_metrics(cell_polygon, num_edges)
        )

        qgs_feature = QgsFeature()
        qgs_feature.setGeometry(QgsGeometry.fromWkt(cell_polygon.wkt))
        qgs_feature.setAttributes(
            [
                s2_token,
                resolution,
                center_lat,
                center_lon,
                avg_edge_len,
                cell_area,
                cell_perimeter,
            ]
        )
        s2_features.append(qgs_feature)

    fields = QgsFields()
    fields.append(QgsField("s2", QVariant.String))
    fields.append(QgsField("resolution", QVariant.Int))
    fields.append(QgsField("center_lat", QVariant.Double))
    fields.append(QgsField("center_lon", QVariant.Double))
    fields.append(QgsField("avg_edge_len", QVariant.Double))
    fields.append(QgsField("cell_area", QVariant.Double))
    fields.append(QgsField("cell_perimeter", QVariant.Double))
    layer = QgsVectorLayer("Polygon?crs=EPSG:4326", f"s2_{resolution}", "memory")
    layer.startEditing()
    layer.dataProvider().addAttributes(fields)
    layer.updateFields()
    layer.dataProvider().addFeatures(s2_features)
    layer.commitChanges()

    if feedback:
        feedback.pushInfo(
            f"Completed generating S2 grid with {len(s2_features)} intersecting features."
        )

    return layer


#########################
# rHEALPix
#########################
def generate_rhealpix_grid(
    resolution,
    qgs_features,
    feedback=None,
    shift_antimeridian=False,
    split_antimeridian=False,
):
    if not qgs_features:
        raise ValueError("No features provided for rHEALPix grid generation.")

    resolution = validate_rhealpix_resolution(resolution)
    unified_geom, bbox = _unified_geom_and_bbox(qgs_features)
    fix = _resolve_fix_antimeridian(
        "rhealpix", shift_antimeridian, split_antimeridian
    )
    bbox_polygon = box(*bbox)
    bbox_center_lon = bbox_polygon.centroid.x
    bbox_center_lat = bbox_polygon.centroid.y
    seed_point = (bbox_center_lon, bbox_center_lat)
    seed_cell = _RHEALPIX_DGGS.cell_from_point(resolution, seed_point, plane=False)
    seed_cell_id = str(seed_cell)
    seed_cell_polygon = (
        rhealpix2geo(seed_cell_id, fix_antimeridian=fix)
        if fix
        else rhealpix2geo(seed_cell_id)
    )

    intersecting_cells = {}
    if seed_cell_polygon.contains(bbox_polygon):
        intersecting_cells[seed_cell_id] = (seed_cell, seed_cell_polygon)
    else:
        covered_cells = set()
        queue = deque([seed_cell])
        while queue:
            current_cell = queue.popleft()
            current_cell_id = str(current_cell)
            if current_cell_id in covered_cells:
                continue
            covered_cells.add(current_cell_id)

            cell_polygon = (
                rhealpix2geo(current_cell_id, fix_antimeridian=fix)
                if fix
                else rhealpix2geo(current_cell_id)
            )
            if cell_polygon.intersects(bbox_polygon):
                intersecting_cells[current_cell_id] = (current_cell, cell_polygon)
                for _, neighbor in current_cell.neighbors(plane=False).items():
                    neighbor_id = str(neighbor)
                    if neighbor_id not in covered_cells:
                        queue.append(neighbor)

    rhealpix_features = []
    cells_to_process = list(intersecting_cells.items())
    total = len(cells_to_process)

    for i, (cell_id, (cell, cell_polygon)) in enumerate(cells_to_process):
        if feedback and feedback.isCanceled():
            return None

        if not cell_polygon.intersects(unified_geom):
            continue

        num_edges = 3 if cell.ellipsoidal_shape() == "dart" else 4
        center_lat, center_lon, avg_edge_len, cell_area, cell_perimeter = (
            geodesic_dggs_metrics(cell_polygon, num_edges)
        )

        feature = QgsFeature()
        feature.setGeometry(QgsGeometry.fromWkt(cell_polygon.wkt))
        feature.setAttributes(
            [
                cell_id,
                resolution,
                center_lat,
                center_lon,
                avg_edge_len,
                cell_area,
                cell_perimeter,
            ]
        )
        rhealpix_features.append(feature)

        if feedback and total:
            feedback.setProgress(int((i + 1) / total * 100))

    fields = QgsFields()
    fields.append(QgsField("rhealpix", QVariant.String))
    fields.append(QgsField("resolution", QVariant.Int))
    fields.append(QgsField("center_lat", QVariant.Double))
    fields.append(QgsField("center_lon", QVariant.Double))
    fields.append(QgsField("avg_edge_len", QVariant.Double))
    fields.append(QgsField("cell_area", QVariant.Double))
    fields.append(QgsField("cell_perimeter", QVariant.Double))
    layer = QgsVectorLayer("Polygon?crs=EPSG:4326", f"rhealpix_{resolution}", "memory")
    layer.startEditing()
    layer.dataProvider().addAttributes(fields)
    layer.updateFields()
    layer.dataProvider().addFeatures(rhealpix_features)
    layer.commitChanges()
    layer.updateExtents()

    if feedback:
        feedback.pushInfo(
            f"Completed generating rHEALPix grid with {len(rhealpix_features)} features."
        )
        feedback.setProgress(100)

    return layer


#########################
# ISEA4T
#########################
def generate_isea4t_grid(
    resolution,
    qgs_features,
    feedback=None,
    shift_antimeridian=False,
    split_antimeridian=False,
):
    if not qgs_features:
        raise ValueError("No features provided for ISEA4T grid generation.")

    resolution = validate_isea4t_resolution(resolution)
    unified_geom, bbox = _unified_geom_and_bbox(qgs_features)
    fix = _resolve_fix_antimeridian(
        "isea4t", shift_antimeridian, split_antimeridian
    )

    if is_full_world_bbox(bbox):
        bounding_children = get_isea4t_children_cells(ISEA4T_BASE_CELLS, resolution)
    else:
        accuracy = ISEA4T_RES_ACCURACY_DICT.get(resolution)
        bbox_polygon = box(*bbox)
        bounding_box_wkt = bbox_polygon.wkt
        isea4t_shapes = isea4t_dggs.convert_shape_string_to_dggs_shapes(
            bounding_box_wkt, ShapeStringFormat.WKT, accuracy
        )
        isea4t_shape = isea4t_shapes[0]
        bbox_cells = isea4t_shape.get_shape().get_outer_ring().get_cells()
        bounding_cell = isea4t_dggs.get_bounding_dggs_cell(bbox_cells)
        bounding_children = get_isea4t_children_cells_within_bbox(
            bounding_cell.get_cell_id(), bbox_polygon, resolution
        )

    isea4t_features = []

    for i, child in enumerate(bounding_children):
        if feedback and feedback.isCanceled():
            return None

        isea4t_cell = DggsCell(child)
        isea4t_id = isea4t_cell.get_cell_id()
        cell_polygon = (
            isea4t2geo(isea4t_id, fix_antimeridian=fix)
            if fix
            else isea4t2geo(isea4t_id)
        )
        if not cell_polygon.intersects(unified_geom):
            continue

        num_edges = 3
        center_lat, center_lon, avg_edge_len, cell_area, cell_perimeter = (
            geodesic_dggs_metrics(cell_polygon, num_edges)
        )

        feature = QgsFeature()
        feature.setGeometry(QgsGeometry.fromWkt(cell_polygon.wkt))
        feature.setAttributes(
            [
                isea4t_id,
                resolution,
                center_lat,
                center_lon,
                avg_edge_len,
                cell_area,
                cell_perimeter,
            ]
        )
        isea4t_features.append(feature)

        if feedback:
            feedback.setProgress(int((i + 1) / len(bounding_children) * 100))

    fields = QgsFields()
    fields.append(QgsField("isea4t", QVariant.String))
    fields.append(QgsField("resolution", QVariant.Int))
    fields.append(QgsField("center_lat", QVariant.Double))
    fields.append(QgsField("center_lon", QVariant.Double))
    fields.append(QgsField("avg_edge_len", QVariant.Double))
    fields.append(QgsField("cell_area", QVariant.Double))
    fields.append(QgsField("cell_perimeter", QVariant.Double))
    layer = QgsVectorLayer("Polygon?crs=EPSG:4326", f"isea4t_{resolution}", "memory")
    layer.startEditing()
    layer.dataProvider().addAttributes(fields)
    layer.updateFields()
    layer.dataProvider().addFeatures(isea4t_features)
    layer.commitChanges()

    if feedback:
        feedback.pushInfo(
            f"Completed generating ISEA4T grid with {len(isea4t_features)} features."
        )
        feedback.setProgress(100)

    return layer


#########################
# QTM
#########################
def generate_qtm_grid(resolution, qgs_features, feedback=None):
    if not qgs_features:
        raise ValueError("No features provided for QTM grid generation.")

    resolution = validate_qtm_resolution(resolution)
    unified_geom, bbox = _unified_geom_and_bbox(qgs_features)
    min_lon, min_lat, max_lon, max_lat = bbox
    bbox_poly = Polygon(
        [
            (min_lon, min_lat),
            (max_lon, min_lat),
            (max_lon, max_lat),
            (min_lon, max_lat),
            (min_lon, min_lat),
        ]
    )

    levelFacets = {}
    QTMID = {}
    qtm_features = []

    for lvl in range(resolution):
        if feedback and feedback.isCanceled():
            return None

        if feedback:
            feedback.setProgress(int((lvl + 1) / resolution * 100))

        levelFacets[lvl] = []
        QTMID[lvl] = []

        if lvl == 0:
            initial_facets = [
                [p0_n180, p0_n90, p90_n90, p90_n180, p0_n180, True],
                [p0_n90, p0_p0, p90_p0, p90_n90, p0_n90, True],
                [p0_p0, p0_p90, p90_p90, p90_p0, p0_p0, True],
                [p0_p90, p0_p180, p90_p180, p90_p90, p0_p90, True],
                [n90_n180, n90_n90, p0_n90, p0_n180, n90_n180, False],
                [n90_n90, n90_p0, p0_p0, p0_n90, n90_n90, False],
                [n90_p0, n90_p90, p0_p90, p0_p0, n90_p0, False],
                [n90_p90, n90_p180, p0_p180, p0_p90, n90_p90, False],
            ]

            for i, facet in enumerate(initial_facets):
                QTMID[0].append(str(i + 1))
                facet_geom = qtm.constructGeometry(facet)
                levelFacets[0].append(facet)

                if shape(facet_geom).intersects(bbox_poly) and resolution == 1:
                    if not shape(facet_geom).intersects(unified_geom):
                        continue
                    qtm_id = QTMID[0][i]
                    num_edges = 3
                    center_lat, center_lon, avg_edge_len, cell_area, cell_perimeter = (
                        geodesic_dggs_metrics(facet_geom, num_edges)
                    )

                    feature = QgsFeature()
                    feature.setGeometry(QgsGeometry.fromWkt(facet_geom.wkt))
                    feature.setAttributes(
                        [
                            qtm_id,
                            resolution,
                            center_lat,
                            center_lon,
                            avg_edge_len,
                            cell_area,
                            cell_perimeter,
                        ]
                    )
                    qtm_features.append(feature)

        else:
            for i, pf in enumerate(levelFacets[lvl - 1]):
                subdivided_facets = qtm.divideFacet(pf)
                for j, subfacet in enumerate(subdivided_facets):
                    subfacet_geom = qtm.constructGeometry(subfacet)
                    if shape(subfacet_geom).intersects(bbox_poly):
                        new_id = QTMID[lvl - 1][i] + str(j)
                        QTMID[lvl].append(new_id)
                        levelFacets[lvl].append(subfacet)

                        if lvl == resolution - 1:
                            if not shape(subfacet_geom).intersects(unified_geom):
                                continue
                            num_edges = 3
                            (
                                center_lat,
                                center_lon,
                                avg_edge_len,
                                cell_area,
                                cell_perimeter,
                            ) = geodesic_dggs_metrics(subfacet_geom, num_edges)

                            feature = QgsFeature()
                            feature.setGeometry(QgsGeometry.fromWkt(subfacet_geom.wkt))
                            feature.setAttributes(
                                [
                                    new_id,
                                    resolution,
                                    center_lat,
                                    center_lon,
                                    avg_edge_len,
                                    cell_area,
                                    cell_perimeter,
                                ]
                            )
                            qtm_features.append(feature)

    fields = QgsFields()
    fields.append(QgsField("qtm", QVariant.String))
    fields.append(QgsField("resolution", QVariant.Int))
    fields.append(QgsField("center_lat", QVariant.Double))
    fields.append(QgsField("center_lon", QVariant.Double))
    fields.append(QgsField("avg_edge_len", QVariant.Double))
    fields.append(QgsField("cell_area", QVariant.Double))
    fields.append(QgsField("cell_perimeter", QVariant.Double))
    layer = QgsVectorLayer("Polygon?crs=EPSG:4326", f"qtm_{resolution}", "memory")
    layer.startEditing()
    layer.dataProvider().addAttributes(fields)
    layer.updateFields()
    layer.dataProvider().addFeatures(qtm_features)
    layer.commitChanges()
    layer.updateExtents()

    if feedback:
        feedback.pushInfo(f"Generated QTM grid with {len(qtm_features)} features.")
        feedback.setProgress(100)

    return layer


#########################
# OLC
#########################
def _olc_world_cell_records(resolution, feedback=None):
    """Global OLC cells as flat dict records (no GeoPandas — safe inside QGIS)."""
    resolution = validate_olc_resolution(resolution)
    sw_lat, sw_lng = -90, -180
    ne_lat, ne_lng = 90, 180

    area = olc.decode(olc.encode(sw_lat, sw_lng, resolution))
    lat_step = area.latitudeHi - area.latitudeLo
    lng_step = area.longitudeHi - area.longitudeLo

    total_lat = int((ne_lat - sw_lat) / lat_step)
    total_lng = int((ne_lng - sw_lng) / lng_step)
    total_steps = max(total_lat * total_lng, 1)

    records = []
    step = 0
    lat = sw_lat
    while lat < ne_lat:
        lng = sw_lng
        while lng < ne_lng:
            center_lat = lat + lat_step / 2
            center_lon = lng + lng_step / 2
            olc_id = olc.encode(center_lat, center_lon, resolution)
            code_len = olc.decode(olc_id).codeLength
            cell_polygon = Polygon(
                [
                    [lng, lat],
                    [lng, lat + lat_step],
                    [lng + lng_step, lat + lat_step],
                    [lng + lng_step, lat],
                    [lng, lat],
                ]
            )
            records.append(
                graticule_dggs_to_geoseries("olc", olc_id, code_len, cell_polygon)
            )
            lng += lng_step
            step += 1
            if feedback and step % 32 == 0:
                feedback.setProgress(int(step / total_steps * 100))
        lat += lat_step
    return records


def generate_base_grid(resolution):
    sw_lat, sw_lng = -90, -180
    ne_lat, ne_lng = 90, 180

    area = olc.decode(olc.encode(sw_lat, sw_lng, resolution))
    lat_step = area.latitudeHi - area.latitudeLo
    lng_step = area.longitudeHi - area.longitudeLo

    olc_features = []

    lat = sw_lat
    while lat < ne_lat:
        lng = sw_lng
        while lng < ne_lng:
            # Generate the Plus Code for the center of the cell
            center_lat = lat + lat_step / 2
            center_lon = lng + lng_step / 2
            olc_id = olc.encode(center_lat, center_lon, resolution)

            # Create the polygon for the cell
            cell_polygon = Polygon(
                [
                    [lng, lat],  # SW
                    [lng, lat + lat_step],  # NW
                    [lng + lng_step, lat + lat_step],  # NE
                    [lng + lng_step, lat],  # SE
                    [lng, lat],  # Close the polygon
                ]
            )
            # center_lat, center_lon, cell_width, cell_height, cell_area = graticule_dggs_metrics(cell_polygon)

            # Create the QgsFeature and set the geometry and attributes
            qgis_feature = QgsFeature()
            qgis_feature.setGeometry(QgsGeometry.fromWkt(cell_polygon.wkt))
            qgis_feature.setAttributes([olc_id])

            # Add feature to the list
            olc_features.append(qgis_feature)

            lng += lng_step
        lat += lat_step

    # Create a QgsVectorLayer to hold the features
    fields = QgsFields()
    fields.append(QgsField("olc", QVariant.String))
    fields.append(QgsField("cell_perimeter", QVariant.Double))
    layer = QgsVectorLayer("Polygon?crs=EPSG:4326", f"olc_grid_{resolution}", "memory")
    layer.startEditing()
    layer.dataProvider().addAttributes(fields)
    layer.updateFields()
    layer.dataProvider().addFeatures(olc_features)
    layer.commitChanges()

    return layer


def _olc_record_resolution(record):
    if isinstance(record, QgsFeature):
        field_names = record.fields().names()
        if "resolution" in field_names:
            return int(record["resolution"])
        return olc.decode(_olc_record_id(record)).codeLength
    return int(record["resolution"])


def _olc_record_id(record):
    if isinstance(record, QgsFeature):
        field_names = record.fields().names()
        return str(record["olc"] if "olc" in field_names else record[0])
    return str(record["olc"])


def _olc_record_to_qgs_feature(record):
    if isinstance(record, QgsFeature):
        field_names = record.fields().names()
        if "center_lat" in field_names:
            return record
        olc_id = _olc_record_id(record)
        cell_geom = record.geometry()
        cell_polygon = load_wkt(cell_geom.asWkt())
        (
            center_lat,
            center_lon,
            cell_width,
            cell_height,
            cell_area,
            cell_perimeter,
        ) = graticule_dggs_metrics(cell_polygon)
        feat = QgsFeature()
        feat.setGeometry(cell_geom)
        feat.setAttributes(
            [
                olc_id,
                olc.decode(olc_id).codeLength,
                center_lat,
                center_lon,
                cell_width,
                cell_height,
                cell_area,
                cell_perimeter,
            ]
        )
        return feat

    cell_polygon = record["geometry"]
    feat = QgsFeature()
    feat.setGeometry(QgsGeometry.fromWkt(cell_polygon.wkt))
    feat.setAttributes(
        [
            str(record["olc"]),
            int(record["resolution"]),
            record["center_lat"],
            record["center_lon"],
            record["cell_width"],
            record["cell_height"],
            record["cell_area"],
            record["cell_perimeter"],
        ]
    )
    return feat


def _olc_build_layer(records, resolution, feedback=None):
    """Build a memory layer from OLC grid records (GeoDataFrame rows or refine dicts)."""
    fields = QgsFields()
    fields.append(QgsField("olc", QVariant.String))
    fields.append(QgsField("resolution", QVariant.Int))
    fields.append(QgsField("center_lat", QVariant.Double))
    fields.append(QgsField("center_lon", QVariant.Double))
    fields.append(QgsField("cell_width", QVariant.Double))
    fields.append(QgsField("cell_height", QVariant.Double))
    fields.append(QgsField("cell_area", QVariant.Double))
    fields.append(QgsField("cell_perimeter", QVariant.Double))

    seen_olc_ids = set()
    qgis_features = []
    total = len(records)
    for idx, record in enumerate(records):
        if _olc_record_resolution(record) != resolution:
            continue
        olc_id = _olc_record_id(record)
        if olc_id in seen_olc_ids:
            continue
        seen_olc_ids.add(olc_id)
        qgis_features.append(_olc_record_to_qgs_feature(record))
        if feedback and total:
            feedback.setProgress(int((idx + 1) / total * 100))

    layer = QgsVectorLayer("Polygon?crs=EPSG:4326", f"olc_grid_{resolution}", "memory")
    layer.startEditing()
    layer.dataProvider().addAttributes(fields)
    layer.updateFields()
    layer.dataProvider().addFeatures(qgis_features)
    layer.commitChanges()

    if feedback:
        feedback.pushInfo(f"Generated OLC grid with {len(qgis_features)} features.")
        feedback.setProgress(100)
    return layer


def generate_olc_grid(resolution, qgs_features, feedback=None):
    """Match ``olc_grid_within_bbox``: bbox-scoped seeds, refine, filter by resolution."""
    if not qgs_features:
        raise ValueError("No features provided for OLC grid generation.")

    resolution = validate_olc_resolution(resolution)
    _, bbox = _unified_geom_and_bbox(qgs_features)
    bbox = validate_bbox(list(bbox))

    if is_full_world_bbox(bbox):
        return _olc_build_layer(
            _olc_world_cell_records(resolution, feedback), resolution, feedback
        )

    bbox_polygon = box(*bbox)
    base_resolution = 2
    seed_cells = [
        record
        for record in _olc_world_cell_records(base_resolution)
        if bbox_polygon.intersects(record["geometry"])
    ]

    refined_records = []
    total_seeds = len(seed_cells)
    for idx, seed_cell in enumerate(seed_cells):
        seed_cell_poly = seed_cell["geometry"]

        if resolution == base_resolution:
            refined_records.append(seed_cell)
        else:
            refined_records.extend(
                olc_refine_cell(
                    seed_cell_poly.bounds, base_resolution, resolution, bbox_polygon
                )
            )

        if feedback and total_seeds:
            feedback.setProgress(33 + int((idx + 1) / total_seeds * 67))

    return _olc_build_layer(refined_records, resolution, feedback)


#########################
# Geohash
#########################
def generate_geohash_grid(resolution, qgs_features, feedback=None):
    if not qgs_features:
        raise ValueError("No features provided for Geohash grid generation.")

    resolution = validate_geohash_resolution(resolution)
    _, bbox = _unified_geom_and_bbox(qgs_features)
    min_lon, min_lat, max_lon, max_lat = validate_bbox(list(bbox))
    bbox_polygon = Polygon.from_bounds(min_lon, min_lat, max_lon, max_lat)

    intersected_geohashes = {
        gh for gh in INITIAL_GEOHASHES if geohash2geo(gh).intersects(bbox_polygon)
    }

    geohashes_geom = set()
    for gh in intersected_geohashes:
        expand_geohash_bbox(gh, resolution, geohashes_geom, bbox_polygon)

    # Create QGIS features
    fields = QgsFields()
    fields.append(QgsField("geohash", QVariant.String))
    fields.append(QgsField("resolution", QVariant.Int))
    fields.append(QgsField("center_lat", QVariant.Double))
    fields.append(QgsField("center_lon", QVariant.Double))
    fields.append(QgsField("cell_width", QVariant.Double))
    fields.append(QgsField("cell_height", QVariant.Double))
    fields.append(QgsField("cell_area", QVariant.Double))
    fields.append(QgsField("cell_perimeter", QVariant.Double))
    qgis_features = []
    for i, gh in enumerate(geohashes_geom):
        cell_polygon = geohash2geo(gh)
        (
            center_lat,
            center_lon,
            cell_width,
            cell_height,
            cell_area,
            cell_perimeter,
        ) = graticule_dggs_metrics(cell_polygon)
        cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)
        feat = QgsFeature()
        feat.setGeometry(cell_geometry)
        feat.setAttributes(
            [
                gh,
                resolution,
                center_lat,
                center_lon,
                cell_width,
                cell_height,
                cell_area,
                cell_perimeter,
            ]
        )
        qgis_features.append(feat)

        if feedback:
            feedback.setProgress(int((i + 1) / len(geohashes_geom) * 100))

    layer = QgsVectorLayer(
        "Polygon?crs=EPSG:4326", f"geohash_grid_{resolution}", "memory"
    )
    layer.startEditing()
    layer.dataProvider().addAttributes(fields)
    layer.updateFields()
    layer.dataProvider().addFeatures(qgis_features)
    layer.commitChanges()

    if feedback:
        feedback.pushInfo(f"Generated {len(qgis_features)} Geohash cells.")
        feedback.setProgress(100)

    return layer


#########################
# Tilecode
#########################
def generate_tilecode_grid(resolution, qgs_features, feedback=None):
    if not qgs_features:
        raise ValueError("No features provided for Tilecode grid generation.")

    resolution = validate_tilecode_resolution(resolution)
    _, bbox = _unified_geom_and_bbox(qgs_features)
    if is_full_world_bbox(bbox):
        bbox = WEB_MERCATOR_BBOX
    min_lon, min_lat, max_lon, max_lat = bbox
    tiles = list(mercantile.tiles(min_lon, min_lat, max_lon, max_lat, resolution))
    total = len(tiles)

    fields = QgsFields()
    fields.append(QgsField("tilecode", QVariant.String))
    fields.append(QgsField("resolution", QVariant.Int))
    fields.append(QgsField("center_lat", QVariant.Double))
    fields.append(QgsField("center_lon", QVariant.Double))
    fields.append(QgsField("cell_width", QVariant.Double))
    fields.append(QgsField("cell_height", QVariant.Double))
    fields.append(QgsField("cell_area", QVariant.Double))
    fields.append(QgsField("cell_perimeter", QVariant.Double))
    qgis_features = []

    # Step 4: Iterate over tiles and test intersection
    for i, tile in enumerate(tiles):
        z, x, y = tile.z, tile.x, tile.y
        tilecode_id = f"z{z}x{x}y{y}"
        bounds = mercantile.bounds(x, y, z)

        cell_polygon = Polygon(
            [
                [bounds.west, bounds.south],
                [bounds.east, bounds.south],
                [bounds.east, bounds.north],
                [bounds.west, bounds.north],
                [bounds.west, bounds.south],
            ]
        )

        cell_geom = QgsGeometry.fromWkt(cell_polygon.wkt)
        (
            center_lat,
            center_lon,
            cell_width,
            cell_height,
            cell_area,
            cell_perimeter,
        ) = graticule_dggs_metrics(cell_polygon)
        feature = QgsFeature()
        feature.setGeometry(cell_geom)
        feature.setAttributes(
            [
                tilecode_id,
                resolution,
                center_lat,
                center_lon,
                cell_width,
                cell_height,
                cell_area,
                cell_perimeter,
            ]
        )
        qgis_features.append(feature)

        if feedback:
            feedback.setProgress(int(i / total * 100))

    layer = QgsVectorLayer(
        "Polygon?crs=EPSG:4326", f"tilecode_grid_{resolution}", "memory"
    )
    layer.startEditing()
    layer.dataProvider().addAttributes(fields)
    layer.updateFields()
    layer.dataProvider().addFeatures(qgis_features)
    layer.commitChanges()

    if feedback:
        feedback.pushInfo(f"Generated {len(qgis_features)} Tilecode cells.")
        feedback.setProgress(100)

    return layer


#########################
# Quadkey
#########################
def generate_quadkey_grid(resolution, qgs_features, feedback=None):
    if not qgs_features:
        raise ValueError("No features provided for Quadkey grid generation.")

    resolution = validate_quadkey_resolution(resolution)
    _, bbox = _unified_geom_and_bbox(qgs_features)
    if is_full_world_bbox(bbox):
        bbox = WEB_MERCATOR_BBOX
    min_lon, min_lat, max_lon, max_lat = bbox
    tiles = list(mercantile.tiles(min_lon, min_lat, max_lon, max_lat, resolution))
    total = len(tiles)

    fields = QgsFields()
    fields.append(QgsField("quadkey", QVariant.String))
    fields.append(QgsField("resolution", QVariant.Int))
    fields.append(QgsField("center_lat", QVariant.Double))
    fields.append(QgsField("center_lon", QVariant.Double))
    fields.append(QgsField("cell_width", QVariant.Double))
    fields.append(QgsField("cell_height", QVariant.Double))
    fields.append(QgsField("cell_area", QVariant.Double))
    fields.append(QgsField("cell_perimeter", QVariant.Double))
    qgis_features = []

    # Step 4: Iterate over tiles and test intersection
    for i, tile in enumerate(tiles):
        z, x, y = tile.z, tile.x, tile.y
        quadkey_id = mercantile.quadkey(tile)
        bounds = mercantile.bounds(x, y, z)

        cell_polygon = Polygon(
            [
                [bounds.west, bounds.south],
                [bounds.east, bounds.south],
                [bounds.east, bounds.north],
                [bounds.west, bounds.north],
                [bounds.west, bounds.south],
            ]
        )

        cell_geom = QgsGeometry.fromWkt(cell_polygon.wkt)
        (
            center_lat,
            center_lon,
            cell_width,
            cell_height,
            cell_area,
            cell_perimeter,
        ) = graticule_dggs_metrics(cell_polygon)
        feature = QgsFeature()
        feature.setGeometry(cell_geom)
        feature.setAttributes(
            [
                quadkey_id,
                resolution,
                center_lat,
                center_lon,
                cell_width,
                cell_height,
                cell_area,
                cell_perimeter,
            ]
        )
        qgis_features.append(feature)

        if feedback:
            feedback.setProgress(int(i / total * 100))

    layer = QgsVectorLayer(
        "Polygon?crs=EPSG:4326", f"quadkey_grid_{resolution}", "memory"
    )
    layer.startEditing()
    layer.dataProvider().addAttributes(fields)
    layer.updateFields()
    layer.dataProvider().addFeatures(qgis_features)
    layer.commitChanges()

    if feedback:
        feedback.pushInfo(f"Generated {len(qgis_features)} Quadkey cells.")
        feedback.setProgress(100)

    return layer


#########################
# A5
#########################
def generate_a5_grid(
    resolution,
    qgs_features,
    feedback=None,
    shift_antimeridian=False,
    split_antimeridian=False,
):
    if not qgs_features:
        raise ValueError("No features provided for A5 grid generation.")

    resolution = validate_a5_resolution(resolution)
    unified_geom, bbox = _unified_geom_and_bbox(qgs_features)
    full_world = is_full_world_bbox(bbox)
    if full_world:
        min_lon, min_lat, max_lon, max_lat = -180.0, -90.0, 180.0, 90.0
    else:
        min_lon, min_lat, max_lon, max_lat = bbox

    use_split = _use_split_antimeridian(shift_antimeridian, split_antimeridian)
    bbox_polygon = box(min_lon, min_lat, max_lon, max_lat)
    bbox_center_lon = bbox_polygon.centroid.x
    bbox_center_lat = bbox_polygon.centroid.y

    seed_cell_id = a5.lonlat_to_cell((bbox_center_lon, bbox_center_lat), resolution)
    seed_cell_polygon = a52geo_u64(
        seed_cell_id, split_antimeridian=use_split
    )

    intersecting_cells = {}
    if seed_cell_polygon.contains(bbox_polygon):
        intersecting_cells[seed_cell_id] = seed_cell_polygon
    else:
        covered_cells = set()
        queue = deque([seed_cell_id])
        while queue:
            current_cell_id = queue.popleft()
            if current_cell_id in covered_cells:
                continue
            covered_cells.add(current_cell_id)

            cell_polygon = a52geo_u64(
                current_cell_id, split_antimeridian=use_split
            )
            if full_world or cell_polygon.intersects(unified_geom):
                intersecting_cells[current_cell_id] = cell_polygon
                neighbors = a5.uncompact(
                    a5.grid_disk_vertex(current_cell_id, 1), resolution
                )
                for neighbor_id in neighbors:
                    if neighbor_id not in covered_cells:
                        queue.append(neighbor_id)

    fields = QgsFields()
    fields.append(QgsField("a5", QVariant.String))
    fields.append(QgsField("resolution", QVariant.Int))
    fields.append(QgsField("center_lat", QVariant.Double))
    fields.append(QgsField("center_lon", QVariant.Double))
    fields.append(QgsField("avg_edge_len", QVariant.Double))
    fields.append(QgsField("cell_area", QVariant.Double))
    fields.append(QgsField("cell_perimeter", QVariant.Double))
    a5_features = []
    total = len(intersecting_cells)

    if feedback:
        feedback.pushInfo(f"Generating A5 grid at resolution {resolution}...")

    for i, (cell_id, cell_polygon) in enumerate(intersecting_cells.items()):
        if feedback:
            if feedback.isCanceled():
                return None
            if total:
                feedback.setProgress(int((i + 1) / total * 100))

        a5_hex = a5.u64_to_hex(cell_id)
        num_edges = 5
        if a5.get_resolution(cell_id) == 1:
            num_edges = 3
        center_lat, center_lon, avg_edge_len, cell_area, cell_perimeter = (
            geodesic_dggs_metrics(cell_polygon, num_edges)
        )

        qgs_feature = QgsFeature()
        qgs_feature.setGeometry(QgsGeometry.fromWkt(cell_polygon.wkt))
        qgs_feature.setAttributes(
            [
                a5_hex,
                resolution,
                center_lat,
                center_lon,
                avg_edge_len,
                cell_area,
                cell_perimeter,
            ]
        )
        a5_features.append(qgs_feature)

    if not a5_features:
        raise ValueError(
            "No A5 cells were generated. Check the input parameters and A5 library functions."
        )

    layer = QgsVectorLayer("Polygon?crs=EPSG:4326", f"a5_grid_{resolution}", "memory")
    layer.startEditing()
    layer.dataProvider().addAttributes(fields)
    layer.updateFields()
    layer.dataProvider().addFeatures(a5_features)
    layer.commitChanges()

    if feedback:
        feedback.pushInfo(f"Generated {len(a5_features)} A5 cells.")
        feedback.setProgress(100)

    return layer


#########################
# DGGAL
#########################
from dggal import *
from vgrid.utils.constants import DGGAL_TYPES
from vgrid.utils.geometry import dggal_to_geo
from vgrid.utils.io import validate_dggal_resolution

_dggal_app = Application(appGlobals=globals())
pydggal_setup(_dggal_app)


def generate_dggal_grid(
    dggal_type,
    resolution,
    qgs_features,
    feedback=None,
    shift_antimeridian=False,
    split_antimeridian=False,
):
    if not qgs_features:
        raise ValueError("No features provided for DGGAL grid generation.")

    resolution = validate_dggal_resolution(dggal_type, resolution)
    unified_geom, bbox = _unified_geom_and_bbox(qgs_features)
    use_split = _use_split_antimeridian(shift_antimeridian, split_antimeridian)

    dggs_class_name = DGGAL_TYPES[dggal_type]["class_name"]
    dggrs = globals()[dggs_class_name]()
    if is_full_world_bbox(bbox):
        geo_extent = wholeWorld
    else:
        min_lon, min_lat, max_lon, max_lat = bbox
        valid_lat = (-90 < min_lat < 90) and (-90 < max_lat < 90)
        if valid_lat:
            ll = GeoPoint(min_lat, min_lon)
            ur = GeoPoint(max_lat, max_lon)
            geo_extent = GeoExtent(ll, ur)
        else:
            geo_extent = wholeWorld
    zones = dggrs.listZones(resolution, geo_extent)

    total = len(zones)
    if feedback:
        feedback.pushInfo(
            f"Generating DGGAL {dggal_type} grid at resolution {resolution} "
            f"with {total} cells..."
        )

    field_name = f"dggal_{dggal_type}"
    fields = QgsFields()
    fields.append(QgsField(field_name, QVariant.String))
    fields.append(QgsField("resolution", QVariant.Int))
    fields.append(QgsField("center_lat", QVariant.Double))
    fields.append(QgsField("center_lon", QVariant.Double))
    fields.append(QgsField("avg_edge_len", QVariant.Double))
    fields.append(QgsField("cell_area", QVariant.Double))
    fields.append(QgsField("cell_perimeter", QVariant.Double))

    dggal_features = []
    for idx, zone in enumerate(zones):
        if feedback:
            if feedback.isCanceled():
                return None
            feedback.setProgress(int((idx / total) * 100))

        zone_id = dggrs.getZoneTextID(zone)
        cell_polygon = dggal_to_geo(dggal_type, zone_id)
        if use_split:
            cell_polygon = fix_polygon(cell_polygon)
        if not cell_polygon.intersects(unified_geom):
            continue

        num_edges = dggrs.countZoneEdges(zone)
        cell_resolution = dggrs.getZoneLevel(zone)
        center_lat, center_lon, avg_edge_len, cell_area, cell_perimeter = (
            geodesic_dggs_metrics(cell_polygon, num_edges)
        )

        qgs_feature = QgsFeature()
        qgs_feature.setGeometry(QgsGeometry.fromWkt(cell_polygon.wkt))
        qgs_feature.setAttributes(
            [
                zone_id,
                cell_resolution,
                center_lat,
                center_lon,
                avg_edge_len,
                cell_area,
                cell_perimeter,
            ]
        )
        dggal_features.append(qgs_feature)

    if not dggal_features:
        raise ValueError(
            f"No DGGAL cells generated for type {dggal_type!r} at resolution {resolution}."
        )

    layer = QgsVectorLayer(
        "Polygon?crs=EPSG:4326", f"dggal_{dggal_type}_{resolution}", "memory"
    )
    layer.startEditing()
    layer.dataProvider().addAttributes(fields)
    layer.updateFields()
    layer.dataProvider().addFeatures(dggal_features)
    layer.commitChanges()

    if feedback:
        feedback.setProgress(100)
        feedback.pushInfo(f"DGGAL {dggal_type} grid generation complete.")

    return layer
