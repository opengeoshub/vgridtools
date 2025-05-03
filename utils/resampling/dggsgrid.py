from shapely.wkt import loads as load_wkt
from shapely.geometry import Polygon,shape
from shapely.ops import unary_union
from qgis.core import (
    QgsVectorLayer, QgsFields, QgsField, QgsFeature, QgsGeometry, QgsWkbTypes
)
from PyQt5.QtCore import QVariant
import h3
from vgrid.utils import s2, qtm, olc, mercantile
from vgrid.generator.h3grid import geodesic_buffer, fix_h3_antimeridian_cells
from vgrid.generator.settings import geodesic_dggs_metrics, graticule_dggs_metrics
from vgrid.generator.s2grid import s2_cell_to_polygon
from vgrid.utils.rhealpixdggs.dggs import RHEALPixDGGS
from vgrid.generator.rhealpixgrid import rhealpix_cell_to_polygon
import platform
if (platform.system() == 'Windows'):
    from vgrid.utils.eaggr.eaggr import Eaggr
    from vgrid.utils.eaggr.shapes.dggs_cell import DggsCell
    from vgrid.utils.eaggr.enums.model import Model
    from vgrid.utils.eaggr.enums.shape_string_format import ShapeStringFormat
    from vgrid.generator.settings import isea4t_res_accuracy_dict
    from vgrid.generator.isea4tgrid import fix_polygon, fix_isea4t_antimeridian_cells, isea4t_cell_to_polygon, get_isea4t_children_cells_within_bbox

p90_n180, p90_n90, p90_p0, p90_p90, p90_p180 = (90.0, -180.0), (90.0, -90.0), (90.0, 0.0), (90.0, 90.0), (90.0, 180.0)
p0_n180, p0_n90, p0_p0, p0_p90, p0_p180 = (0.0, -180.0), (0.0, -90.0), (0.0, 0.0), (0.0, 90.0), (0.0, 180.0)
n90_n180, n90_n90, n90_p0, n90_p90, n90_p180 = (-90.0, -180.0), (-90.0, -90.0), (-90.0, 0.0), (-90.0, 90.0), (-90.0, 180.0)

from vgrid.generator import olcgrid, geohashgrid


#########################
# H3
#########################
def generate_h3_grid(resolution, qgs_features, feedback=None):
    if not qgs_features:
        raise ValueError("No features provided for H3 grid generation.")

    geometries = [load_wkt(f.geometry().asWkt()) for f in qgs_features.getFeatures()]
    unified_geom = unary_union(geometries)

    distance = h3.average_hexagon_edge_length(resolution, unit='m') * 2
    buffered_geom = geodesic_buffer(unified_geom, distance)

    h3_cells = h3.geo_to_cells(buffered_geom, resolution)
    total = len(h3_cells)

    if feedback:
        feedback.pushInfo(f"Generating H3 grid at resolution {resolution} with {total} cells...")

    h3_features = []
    for idx, h3_cell in enumerate(h3_cells):
        if feedback:
            if feedback.isCanceled():
                return None
            feedback.setProgress(int((idx / total) * 100))

        hex_boundary = h3.cell_to_boundary(h3_cell)
        filtered_boundary = fix_h3_antimeridian_cells(hex_boundary)
        reversed_boundary = [(lon, lat) for lat, lon in filtered_boundary]
        cell_polygon = Polygon(reversed_boundary)

        if not cell_polygon.intersects(unified_geom):
            continue

        h3_id = str(h3_cell)
        num_edges = 6 if not h3.is_pentagon(h3_id) else 5
        center_lat, center_lon, avg_edge_len, cell_area = geodesic_dggs_metrics(cell_polygon, num_edges)

        qgs_feature = QgsFeature()
        qgs_feature.setGeometry(QgsGeometry.fromWkt(cell_polygon.wkt))
        qgs_feature.setAttributes([h3_id, resolution, center_lat, center_lon, avg_edge_len, cell_area])
        h3_features.append(qgs_feature)

    fields = QgsFields()
    fields.append(QgsField("h3", QVariant.String))
    fields.append(QgsField("resolution", QVariant.Int))
    fields.append(QgsField("center_lat", QVariant.Double))
    fields.append(QgsField("center_lon", QVariant.Double))
    fields.append(QgsField("avg_edge_len", QVariant.Double))
    fields.append(QgsField("cell_area", QVariant.Double))

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
def generate_s2_grid(resolution, qgs_features, feedback=None):
    if not qgs_features:
        raise ValueError("No features provided for S2 grid generation.")

    geometries = [load_wkt(f.geometry().asWkt()) for f in qgs_features.getFeatures()]
    unified_geom = unary_union(geometries)

    min_lng, min_lat, max_lng, max_lat = unified_geom.bounds

    level = resolution
    coverer = s2.RegionCoverer()
    coverer.min_level = level
    coverer.max_level = level

    region = s2.LatLngRect(
        s2.LatLng.from_degrees(min_lat, min_lng),
        s2.LatLng.from_degrees(max_lat, max_lng)
    )

    covering = coverer.get_covering(region)

    s2_features = []
    total = len(covering)

    if feedback:
        feedback.pushInfo(f"Generating S2 grid at resolution {resolution} with {total} cells...")

    for idx, cell_id in enumerate(covering):
        if feedback:
            if feedback.isCanceled():
                return None
            feedback.setProgress(int((idx / total) * 100))

        cell_polygon = s2_cell_to_polygon(cell_id)
        if not cell_polygon.intersects(unified_geom):
            continue

        s2_token = cell_id.to_token()
        num_edges = 4
        center_lat, center_lon, avg_edge_len, cell_area = geodesic_dggs_metrics(cell_polygon, num_edges)

        qgs_feature = QgsFeature()
        qgs_feature.setGeometry(QgsGeometry.fromWkt(cell_polygon.wkt))
        qgs_feature.setAttributes([s2_token, resolution, center_lat, center_lon, avg_edge_len, cell_area])
        s2_features.append(qgs_feature)

    fields = QgsFields()
    fields.append(QgsField("s2", QVariant.String))
    fields.append(QgsField("resolution", QVariant.Int))
    fields.append(QgsField("center_lat", QVariant.Double))
    fields.append(QgsField("center_lon", QVariant.Double))
    fields.append(QgsField("avg_edge_len", QVariant.Double))
    fields.append(QgsField("cell_area", QVariant.Double))

    layer = QgsVectorLayer("Polygon?crs=EPSG:4326", f"s2_{resolution}", "memory")
    layer.startEditing()
    layer.dataProvider().addAttributes(fields)
    layer.updateFields()
    layer.dataProvider().addFeatures(s2_features)
    layer.commitChanges()

    if feedback:
        feedback.pushInfo(f"Completed generating S2 grid with {len(s2_features)} intersecting features.")

    return layer

#########################
# rHEALPix
#########################
def generate_rhealpix_grid(rhealpix_dggs, resolution, qgs_features, feedback=None):
    if not qgs_features:
        raise ValueError("No features provided for rHEALPix grid generation.")
    
    geometries = [load_wkt(f.geometry().asWkt()) for f in qgs_features.getFeatures()]
    unified_geom = unary_union(geometries)

    seed_point = (unified_geom.centroid.x, unified_geom.centroid.y)
    seed_cell = rhealpix_dggs.cell_from_point(resolution, seed_point, plane=False)
    seed_cell_polygon = rhealpix_cell_to_polygon(seed_cell)

    cells_to_process = []
    if seed_cell_polygon.contains(unified_geom):
        cells_to_process = [seed_cell]
    else:
        covered = set()
        queue = [seed_cell]
        while queue:
            current = queue.pop()
            cid = str(current)
            if cid in covered:
                continue
            covered.add(cid)

            poly = rhealpix_cell_to_polygon(current)
            if not poly.intersects(unified_geom):
                continue

            neighbors = current.neighbors(plane=False)
            for _, neighbor in neighbors.items():
                nid = str(neighbor)
                if nid not in covered:
                    queue.append(neighbor)

        cells_to_process = [
            rhealpix_dggs.cell((cid[0],) + tuple(map(int, cid[1:]))) for cid in covered
        ]

    rhealpix_features = []

    for i, cell in enumerate(cells_to_process):
        if feedback and feedback.isCanceled():
            return None

        cell_polygon = rhealpix_cell_to_polygon(cell)
        if not cell_polygon.intersects(unified_geom):
            continue

        num_edges = 3 if cell.ellipsoidal_shape() == 'dart' else 4
        center_lat, center_lon, avg_edge_len, cell_area = geodesic_dggs_metrics(cell_polygon, num_edges)

        feature = QgsFeature()
        feature.setGeometry(QgsGeometry.fromWkt(cell_polygon.wkt))
        feature.setAttributes([
            str(cell), resolution, center_lat, center_lon, avg_edge_len, cell_area
        ])
        rhealpix_features.append(feature)

        if feedback:
            feedback.setProgress(int((i + 1) / len(cells_to_process) * 100))

    fields = QgsFields()
    fields.append(QgsField("rhealpix", QVariant.String))
    fields.append(QgsField("resolution", QVariant.Int))
    fields.append(QgsField("center_lat", QVariant.Double))
    fields.append(QgsField("center_lon", QVariant.Double))
    fields.append(QgsField("avg_edge_len", QVariant.Double))
    fields.append(QgsField("cell_area", QVariant.Double))

    layer = QgsVectorLayer("Polygon?crs=EPSG:4326", f"rhealpix_{resolution}", "memory")
    layer.startEditing()
    layer.dataProvider().addAttributes(fields)
    layer.updateFields()
    layer.dataProvider().addFeatures(rhealpix_features)
    layer.commitChanges()
    layer.updateExtents()

    if feedback:
        feedback.pushInfo(f"Completed generating rHEALPix grid with {len(rhealpix_features)} features.")
        feedback.setProgress(100)

    return layer

#########################
# ISEA4T
#########################
def generate_isea4t_grid(isea4t_dggs, resolution, qgs_features, feedback=None):
    if not qgs_features:
        raise ValueError("No features provided for ISEA4T grid generation.")
    
    accuracy = isea4t_res_accuracy_dict.get(resolution)

    geometries = [load_wkt(f.geometry().asWkt()) for f in qgs_features.getFeatures()]
    unified_geom = unary_union(geometries)
    unified_geom_wkt = unified_geom.wkt

    isea4t_shapes = isea4t_dggs.convert_shape_string_to_dggs_shapes(unified_geom_wkt, ShapeStringFormat.WKT, accuracy)
    isea4t_shape = isea4t_shapes[0]
    bbox_cells = isea4t_shape.get_shape().get_outer_ring().get_cells()
    bounding_cell = isea4t_dggs.get_bounding_dggs_cell(bbox_cells)

    bounding_children = get_isea4t_children_cells_within_bbox(
        isea4t_dggs, bounding_cell.get_cell_id(), unified_geom, resolution
    )

    isea4t_features = []

    for i, child in enumerate(bounding_children):
        if feedback and feedback.isCanceled():
            return None

        isea4t_cell = DggsCell(child)
        cell_polygon = isea4t_cell_to_polygon(isea4t_dggs, isea4t_cell)
        isea4t_id = isea4t_cell.get_cell_id()

        if resolution == 0:
            cell_polygon = fix_polygon(cell_polygon)
        elif isea4t_id.startswith(('00', '09', '14', '04', '19')):
            cell_polygon = fix_isea4t_antimeridian_cells(cell_polygon)

        if not cell_polygon.intersects(unified_geom):
            continue

        num_edges = 3
        center_lat, center_lon, avg_edge_len, cell_area = geodesic_dggs_metrics(cell_polygon, num_edges)

        feature = QgsFeature()
        feature.setGeometry(QgsGeometry.fromWkt(cell_polygon.wkt))
        feature.setAttributes([
            isea4t_id, resolution, center_lat, center_lon, avg_edge_len, cell_area
        ])
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

    layer = QgsVectorLayer("Polygon?crs=EPSG:4326", f"isea4t_{resolution}", "memory")
    layer.startEditing()
    layer.dataProvider().addAttributes(fields)
    layer.updateFields()
    layer.dataProvider().addFeatures(isea4t_features)
    layer.commitChanges()

    if feedback:
        feedback.pushInfo(f"Completed generating ISEA4T grid with {len(isea4t_features)} features.")
        feedback.setProgress(100)

    return layer


#########################
# QTM
#########################
def generate_qtm_grid(resolution, qgs_features, feedback=None):
    if not qgs_features:
        raise ValueError("No features provided for ISEA4T grid generation.")    
    
    levelFacets = {}
    QTMID = {}
    qtm_features = []

    geometries = [load_wkt(f.geometry().asWkt()) for f in qgs_features.getFeatures()]
    unified_geom = unary_union(geometries)

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

                if shape(facet_geom).intersects(unified_geom) and resolution == 1:
                    qtm_id = QTMID[0][i]
                    num_edges = 3
                    center_lat, center_lon, avg_edge_len, cell_area = geodesic_dggs_metrics(facet_geom, num_edges)

                    feature = QgsFeature()
                    feature.setGeometry(QgsGeometry.fromWkt(facet_geom.wkt))
                    feature.setAttributes([
                        qtm_id, resolution, center_lat, center_lon, avg_edge_len, cell_area
                    ])
                    qtm_features.append(feature)

        else:
            for i, pf in enumerate(levelFacets[lvl - 1]):
                subdivided_facets = qtm.divideFacet(pf)
                for j, subfacet in enumerate(subdivided_facets):
                    subfacet_geom = qtm.constructGeometry(subfacet)
                    if shape(subfacet_geom).intersects(unified_geom):
                        new_id = QTMID[lvl - 1][i] + str(j)
                        QTMID[lvl].append(new_id)
                        levelFacets[lvl].append(subfacet)

                        if lvl == resolution - 1:
                            num_edges = 3
                            center_lat, center_lon, avg_edge_len, cell_area = geodesic_dggs_metrics(subfacet_geom, num_edges)

                            feature = QgsFeature()
                            feature.setGeometry(QgsGeometry.fromWkt(subfacet_geom.wkt))
                            feature.setAttributes([
                                new_id, resolution, center_lat, center_lon, avg_edge_len, cell_area
                            ])
                            qtm_features.append(feature)

    fields = QgsFields()
    fields.append(QgsField("qtm", QVariant.String))
    fields.append(QgsField("resolution", QVariant.Int))
    fields.append(QgsField("center_lat", QVariant.Double))
    fields.append(QgsField("center_lon", QVariant.Double))
    fields.append(QgsField("avg_edge_len", QVariant.Double))
    fields.append(QgsField("cell_area", QVariant.Double))

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
            cell_polygon = Polygon([
                [lng, lat],  # SW
                [lng, lat + lat_step],  # NW
                [lng + lng_step, lat + lat_step],  # NE
                [lng + lng_step, lat],  # SE
                [lng, lat]  # Close the polygon
            ])
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

    layer = QgsVectorLayer("Polygon?crs=EPSG:4326", f"olc_grid_{resolution}", "memory")
    layer.startEditing()
    layer.dataProvider().addAttributes(fields)
    layer.updateFields()
    layer.dataProvider().addFeatures(olc_features)
    layer.commitChanges()

    return layer

def generate_olc_grid(resolution, qgs_features, feedback=None):
    if not qgs_features:
        raise ValueError("No features provided for OLC grid generation.")    

    geometries = [load_wkt(f.geometry().asWkt()) for f in qgs_features.getFeatures()]
    unified_geom = unary_union(geometries)

    base_resolution = 2
    base_cells = generate_base_grid(base_resolution)  # Create base grid

    seed_cells = []
    base_cells_list = list(base_cells.getFeatures())
    total_base = len(base_cells_list)

    # Step 1: Identify seed cells with intersection
    for idx, base_cell in enumerate(base_cells_list):
        ring = base_cell.geometry().asPolygon()[0]  # outer ring
        coords = [(pt.x(), pt.y()) for pt in ring]
        base_cell_poly = Polygon(coords)

        if unified_geom.intersects(base_cell_poly):
            seed_cells.append(base_cell)

        if feedback:
            progress = int((idx + 1) / total_base * 33)
            feedback.setProgress(progress)

    # Step 2: Refine seed cells to the desired resolution
    refined_features = []
    total_seeds = len(seed_cells)

    for idx, seed_cell in enumerate(seed_cells):
        ring = seed_cell.geometry().asPolygon()[0]
        coords = [(pt.x(), pt.y()) for pt in ring]
        seed_cell_poly = Polygon(coords)

        if seed_cell_poly.contains(unified_geom) and resolution == base_resolution:
            refined_features.append(seed_cell)
        else:
            refined_features.extend(
                olcgrid.refine_cell(seed_cell_poly.bounds, base_resolution, resolution, unified_geom)
            )

        if feedback:
            progress = 33 + int((idx + 1) / total_seeds * 33)
            feedback.setProgress(progress)

    resolution_features = [
        feature for feature in refined_features if feature["properties"]["resolution"] == resolution
    ]

    final_features = []
    seen_olc_ids = set()

    for idx, feature in enumerate(resolution_features):
        olc_id = feature["properties"]["olc"]
        if olc_id not in seen_olc_ids:
            final_features.append(feature)
            seen_olc_ids.add(olc_id)

        if feedback and len(resolution_features) > 0:
            progress = 66 + int((idx + 1) / len(resolution_features) * 33)
            feedback.setProgress(progress)

    fields = QgsFields()
    fields.append(QgsField("olc", QVariant.String))
    fields.append(QgsField("resolution", QVariant.Int))
    fields.append(QgsField("center_lat", QVariant.Double))
    fields.append(QgsField("center_lon", QVariant.Double))
    fields.append(QgsField("cell_width", QVariant.Double))
    fields.append(QgsField("cell_height", QVariant.Double))
    fields.append(QgsField("cell_area", QVariant.Double))

    qgis_features = []

    for feature in final_features:
        props = feature["properties"]
        cell_geom = QgsGeometry.fromWkt(shape(feature["geometry"]).wkt)

        qgis_feature = QgsFeature()
        qgis_feature.setGeometry(cell_geom)
        qgis_feature.setAttributes([
            props["olc"], props["resolution"], props["center_lat"], props["center_lon"],
            props["cell_width"], props["cell_height"], props["cell_area"]
        ])
        qgis_features.append(qgis_feature)

    layer = QgsVectorLayer("Polygon?crs=EPSG:4326", f"olc_grid_{resolution}", "memory")
    layer.startEditing()
    layer.dataProvider().addAttributes(fields)
    layer.updateFields()
    layer.dataProvider().addFeatures(qgis_features)
    layer.commitChanges()

    if feedback:
        feedback.pushInfo(f"Generated OLC grid with {len(final_features)} features.")
        feedback.setProgress(100)

    return layer


#########################
# Geohash
#########################
def generate_geohash_grid(resolution, qgs_features, feedback=None):
    if not qgs_features:
        raise ValueError("No features provided for Geohash grid generation.")    

    geometries = [load_wkt(f.geometry().asWkt()) for f in qgs_features.getFeatures()]
    unified_geom = unary_union(geometries)

    intersected_geohashes = {
        gh for gh in geohashgrid.initial_geohashes
        if geohashgrid.geohash_to_polygon(gh).intersects(unified_geom)
    }

    geohashes_geom = set()
    for gh in intersected_geohashes:
        geohashgrid.expand_geohash_bbox(gh, resolution, geohashes_geom, unified_geom)

    # Create QGIS features
    fields = QgsFields()
    fields.append(QgsField("geohash", QVariant.String))
    fields.append(QgsField("resolution", QVariant.Int))
    fields.append(QgsField("center_lat", QVariant.Double))
    fields.append(QgsField("center_lon", QVariant.Double))
    fields.append(QgsField("cell_width", QVariant.Double))
    fields.append(QgsField("cell_height", QVariant.Double))
    fields.append(QgsField("cell_area", QVariant.Double))

    qgis_features = []
    for i, gh in enumerate(geohashes_geom):
        cell_polygon = geohashgrid.geohash_to_polygon(gh)
        center_lat, center_lon, cell_width, cell_width, cell_area = graticule_dggs_metrics(cell_polygon)
        cell_geometry = QgsGeometry.fromWkt(cell_polygon.wkt)
        feat = QgsFeature()
        feat.setGeometry(cell_geometry)
        feat.setAttributes([gh, resolution, center_lat, center_lon, cell_width, cell_width, cell_area])
        qgis_features.append(feat)

        if feedback:
            feedback.setProgress(int((i + 1) / len(geohashes_geom) * 100))

    layer = QgsVectorLayer("Polygon?crs=EPSG:4326", f"geohash_grid_{resolution}", "memory")
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

    geometries = [load_wkt(f.geometry().asWkt()) for f in qgs_features.getFeatures()]
    unified_geom = unary_union(geometries)

    min_lon, min_lat, max_lon, max_lat = unified_geom.bounds
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

    qgis_features = []

    # Step 4: Iterate over tiles and test intersection
    for i, tile in enumerate(tiles):
        z, x, y = tile.z, tile.x, tile.y
        tilecode_id = f"z{z}x{x}y{y}"
        bounds = mercantile.bounds(x, y, z)

        cell_polygon = Polygon([
            [bounds.west, bounds.south],
            [bounds.east, bounds.south],
            [bounds.east, bounds.north],
            [bounds.west, bounds.north],
            [bounds.west, bounds.south]
        ])

        if cell_polygon.intersects(unified_geom):
            cell_geom = QgsGeometry.fromWkt(cell_polygon.wkt)
            center_lat, center_lon, cell_width, cell_width, cell_area = graticule_dggs_metrics(cell_polygon)
            feature = QgsFeature()
            feature.setGeometry(cell_geom)
            feature.setAttributes([tilecode_id, resolution,center_lat, center_lon, cell_width, cell_width, cell_area])
            qgis_features.append(feature)

        if feedback:
            feedback.setProgress(int(i / total * 100))

    layer = QgsVectorLayer("Polygon?crs=EPSG:4326", f"tilecode_grid_{resolution}", "memory")
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

    geometries = [load_wkt(f.geometry().asWkt()) for f in qgs_features.getFeatures()]
    unified_geom = unary_union(geometries)

    min_lon, min_lat, max_lon, max_lat = unified_geom.bounds
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

    qgis_features = []

    # Step 4: Iterate over tiles and test intersection
    for i, tile in enumerate(tiles):
        z, x, y = tile.z, tile.x, tile.y
        quadkey_id = mercantile.quadkey(tile)
        bounds = mercantile.bounds(x, y, z)

        cell_polygon = Polygon([
            [bounds.west, bounds.south],
            [bounds.east, bounds.south],
            [bounds.east, bounds.north],
            [bounds.west, bounds.north],
            [bounds.west, bounds.south]
        ])

        if cell_polygon.intersects(unified_geom):
            cell_geom = QgsGeometry.fromWkt(cell_polygon.wkt)
            center_lat, center_lon, cell_width, cell_width, cell_area = graticule_dggs_metrics(cell_polygon)
            feature = QgsFeature()
            feature.setGeometry(cell_geom)
            feature.setAttributes([quadkey_id, resolution,center_lat, center_lon, cell_width, cell_width, cell_area])
            qgis_features.append(feature)

        if feedback:
            feedback.setProgress(int(i / total * 100))

    layer = QgsVectorLayer("Polygon?crs=EPSG:4326", f"quadkey_grid_{resolution}", "memory")
    layer.startEditing()
    layer.dataProvider().addAttributes(fields)
    layer.updateFields()
    layer.dataProvider().addFeatures(qgis_features)
    layer.commitChanges()

    if feedback:
        feedback.pushInfo(f"Generated {len(qgis_features)} Quadkey cells.")
        feedback.setProgress(100)

    return layer
