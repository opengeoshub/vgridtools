import h3, json
from vgrid.geocode.geocode2geojson import *

latitude, longitude = 10.775275567242561, 106.70679737574993

h3_precision = 13 #(0-15)
h3_code = h3.latlng_to_cell(latitude, longitude, h3_precision)
h3_decode = h3.cell_to_latlng(h3_code)

print(f'latitude, longitude = {latitude},{longitude}')
print(f'H3 code at precision = {h3_precision}: {h3_code}')
print(f'Decode {h3_code} to WGS84 = {h3_decode}')

data = h32geojson(h3_code)
print(data)

output_file = f'h3_{h3_precision}.geojson'
with open(output_file, 'w') as f:
    json.dump(data, f, indent=2)  # 'indent' makes the JSON output more readable
print(f'GeoJSON written to {output_file}')