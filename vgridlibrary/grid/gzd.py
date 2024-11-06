
# Reference: https://github.com/pistell/Leaflet.DumbMGRS
# https://mgrs-mapper.com/app, https://military-history.fandom.com/wiki/Military_Grid_Reference_System
# https://codesandbox.io/s/how-to-toggle-react-leaflet-layer-control-and-rectangle-grid-f43xi?file=/src/App.js:1057-1309
# https://github.com/GeoSpark/gridoverlay/tree/d66ed86636c7ec3f02ca2e9298ac3086c2023f1d
# https://help.arcgis.com/en/arcgisdesktop/10.0/help/index.html#//00700000001n000000
# https://storymaps.arcgis.com/stories/842edf2b4381438b9a4edefed124775b
# https://github.com/dnlbaldwin/React-Leaflet-MGRS-Graticule
# https://dnlbaldwin.github.io/React-Leaflet-MGRS-Graticule/
# https://earth-info.nga.mil/index.php?dir=coordsys&action=mgrs-100km-polyline-dloads
# https://mgrs-data.org/metadata/
# https://ufl.maps.arcgis.com/apps/dashboards/2539764e24e74bd78f265f49c7adc2d1
# https://earth-info.nga.mil/index.php?dir=coordsys&action=gars-20x20-dloads

from vgrid.geocode import mgrs
# mgrs_code = mgrs.toMgrs(10.63038542, 106.12923131,3)
# # mgrs_code = mgrs.toMgrs(-84.65698112, -80.69068228,3)


# print('mgrs_code: ', mgrs_code)
# mgrs_encode = mgrs.toWgs(mgrs_code)
# original point: WGS84 (10.83114203, 106.79186584), UTM(48N 695891 1197885)
mgrs_encode = mgrs.toWgs('48PXS99') # p = 1 10.760174227850744, 106.73758927416272
mgrs_encode = mgrs.toWgs('48PXS9597') # p = 2 10.823192907438367, 106.78367326848301
mgrs_encode = mgrs.toWgs('48PXS958978') # p = 3 10.830382261828017, 106.79103139219501
mgrs_encode = mgrs.toWgs('48PXS95899788') # p = 4 10.831100652944578, 106.79185866548592
mgrs_encode = mgrs.toWgs('48PXS9589197885') # p = 5 10.8311457980804, 106.79186807843304

# mgrs_encode = mgrs._mgrsToUtm('48PXS99') # p = 1  (48, 'N', 690000.0, 1190000.0)
# mgrs_encode = mgrs._mgrsToUtm('48PXS9597') # p = 2 (48, 'N', 695000.0, 1197000.0)
# mgrs_encode = mgrs._mgrsToUtm('48PXS958978') # p = 3  (48, 'N', 695800.0, 1197800.0)
# mgrs_encode = mgrs._mgrsToUtm('48PXS95899788') # p = 4 (48, 'N', 695890.0, 1197880.0)
# mgrs_encode = mgrs._mgrsToUtm('48PXS9589197885') # p = 5  (48, 'N', 695891.0, 1197885.0)


# print('mgrs_encode: ', mgrs_encode)
# 10.83114203, 106.79186584
import argparse
import geopandas as gpd
from shapely.geometry import box
from tqdm import tqdm

bands = ['C', 'D', 'E', 'F', 'G', 'H', 'J', 'K', 'L', 'M', 'N', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X']

def generate_mgrs_grid(polar=True):
    features = []

    def export_polygon(lon, lat, width, height, mgrs):
        rect = box(lon, lat, lon + width, lat + height)
        features.append({
            'geometry': rect,
            'mgrs': mgrs
        })

    if polar:
        export_polygon(-180, -90, 180, 10, 'A')
        export_polygon(0, -90, 180, 10, 'B')

    lat = -80
    for b in tqdm(bands, desc="Generating Bands"):
        if b == 'X':
            height = 12
            lon = -180
            for i in range(1, 31):
                mgrs = '{:02d}{}'.format(i, b)
                width = 6
                export_polygon(lon, lat, width, height, mgrs)
                lon += width
            export_polygon(lon, lat, 9, height, '31X')
            lon += 9
            export_polygon(lon, lat, 12, height, '33X')
            lon += 12
            export_polygon(lon, lat, 12, height, '35X')
            lon += 12
            export_polygon(lon, lat, 9, height, '37X')
            lon += 9
            for i in range(38, 61):
                mgrs = '{:02d}{}'.format(i, b)
                width = 6
                export_polygon(lon, lat, width, height, mgrs)
                lon += width
        else:
            height = 8
            lon = -180
            for i in range(1, 61):
                mgrs = '{:02d}{}'.format(i, b)
                if b == 'V' and i == 31:
                    width = 3
                elif b == 'V' and i == 32:
                    width = 9
                else:
                    width = 6
                export_polygon(lon, lat, width, height, mgrs)
                lon += width
        lat += height

    if polar:
        export_polygon(-180, 84, 180, 6, 'Y')
        export_polygon(0, 84, 180, 6, 'Z')

    # Create a GeoDataFrame
    gdf = gpd.GeoDataFrame(features, crs="EPSG:4326")
    return gdf


def main():
    parser = argparse.ArgumentParser(description="Generate MGRS Grid Zone Designators and save as Shapefile.")
    parser.add_argument('-o', '--output', type=str, required=True, help="Output Shapefile path, e.g., output.shp.")
    args = parser.parse_args()

    try:
        # Generate MGRS grid
        gdf = generate_mgrs_grid()

        # Save to Shapefile
        gdf.to_file(args.output, driver='ESRI Shapefile')
        print(f"Shapefile saved to {args.output}")

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == '__main__':
    main()