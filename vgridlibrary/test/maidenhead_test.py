from vgrid.geocode import maidenhead
from vgrid.geocode.geocode2geojson import *
import json
latitude, longitude = 10.775275567242561, 106.70679737574993

maidenhead_precision = 4 #[1-->4]
maidenhead_code = maidenhead.toMaiden(latitude, longitude, maidenhead_precision)
maidenGrid = maidenhead.maidenGrid(maidenhead_code)
print(f'Maidenhead Code at precision = {maidenhead_precision}: {maidenhead_code}')
print(f'Convert {maidenhead_code} to center and cell in WGS84 = {maidenGrid}')

data = maidenhead2geojson(maidenhead_code)
print(data)
output_file = f'maidenhead{maidenhead_precision}.geojson'

with open(output_file, 'w') as f:
    json.dump(data, f, indent=2)  # 'indent' makes the JSON output more readable
print(f'GeoJSON written to {output_file}')