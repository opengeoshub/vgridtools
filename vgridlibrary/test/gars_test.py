
from vgrid.geocode.gars import GARSGrid
from vgrid.geocode.geocode2geojson import *
import json 

latitude, longitude = 10.775275567242561, 106.70679737574993# GARS encoding
gars_precision = 1 # 1, 5, 15, 30 minutes
gars_grid = GARSGrid.from_latlon(latitude, longitude, gars_precision)
gars_code = gars_grid.gars_id
print(gars_code)

data = gars2geojson(gars_code)
print(data)
output_file = f'gars_{gars_precision}.geojson'
with open(output_file, 'w') as f:
    json.dump(data, f, indent=2)  
print(f'GeoJSON written to {output_file}')
