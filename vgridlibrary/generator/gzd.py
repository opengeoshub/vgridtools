import geopandas as gpd
from shapely.geometry import box
from qgis.core import QgsProject, QgsVectorLayer, QgsField, QgsFeature, QgsGeometry
from PyQt5.QtCore import QVariant
from PyQt5.QtWidgets import QProgressBar
from qgis.utils import iface

bands = ['C', 'D', 'E', 'F', 'G', 'H', 'J', 'K', 'L', 'M', 'N', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X']

def generate_mgrs_grid(progress_bar, polar=True):
    features = []
    total_steps = len(bands)  # Total bands for the progress bar

    def export_polygon(lon, lat, width, height, gzd):
        rect = box(lon, lat, lon + width, lat + height)
        features.append({
            'geometry': rect,
            'gzd': gzd
        })

    if polar:
        export_polygon(-180, -90, 180, 10, 'A')
        export_polygon(0, -90, 180, 10, 'B')

    lat = -80
    for index, b in enumerate(bands):
        # Update the progress bar
        progress_bar.setValue((index + 1) * 100 // total_steps)
        
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
                gzd = '{:02d}{}'.format(i, b)
                width = 6
                export_polygon(lon, lat, width, height, gzd)
                lon += width
        else:
            height = 8
            lon = -180
            for i in range(1, 61):
                gzd = '{:02d}{}'.format(i, b)
                if b == 'V' and i == 31:
                    width = 3
                elif b == 'V' and i == 32:
                    width = 9
                else:
                    width = 6
                export_polygon(lon, lat, width, height, gzd)
                lon += width
        lat += height

    if polar:
        export_polygon(-180, 84, 180, 6, 'Y')
        export_polygon(0, 84, 180, 6, 'Z')

    # Create a GeoDataFrame
    gdf = gpd.GeoDataFrame(features, crs="EPSG:4326")
    return gdf


def main():
    # Create a progress bar and add it to the QGIS status bar
    progress_bar = QProgressBar()
    progress_bar.setMaximum(100)
    progress_bar.setValue(0)
    iface.mainWindow().statusBar().addWidget(progress_bar)
    
    # Generate GZD grid with progress bar
    gdf = generate_mgrs_grid(progress_bar)

    # Create a temporary layer in QGIS
    layer = QgsVectorLayer("Polygon?crs=EPSG:4326", "GZD", "memory")
    provider = layer.dataProvider()
    
    # Add an attribute for the MGRS code
    provider.addAttributes([QgsField("GZD", QVariant.String)])
    layer.updateFields()

    # Add features from GeoDataFrame to QGIS layer
    for _, row in gdf.iterrows():
        feature = QgsFeature()
        feature.setGeometry(QgsGeometry.fromWkt(row['geometry'].wkt))
        feature.setAttributes([row['gzd']])
        provider.addFeature(feature)

    # Add the layer to the QGIS project
    QgsProject.instance().addMapLayer(layer)

    # Remove the progress bar from the status bar
    iface.mainWindow().statusBar().removeWidget(progress_bar)


if __name__ == '__main__':
    main()
