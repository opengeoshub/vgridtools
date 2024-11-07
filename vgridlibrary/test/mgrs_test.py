from vgrid.geocode import mgrs
from vgrid.geocode.geocode2geojson import *
import json
latitude, longitude = 40.00194441, 23.99972080
latitude, longitude = 10.775275567242561, 106.70679737574993

mgrs_precision = 4 # [0 -->5]
mgrs_code = mgrs.toMgrs(latitude, longitude, mgrs_precision)
mgrs_code_to_wgs = mgrs.toWgs(mgrs_code)
print(f'MGRS Code at precision = {mgrs_precision}: {mgrs_code}')
print(f'Convert {mgrs_code} to WGS84 = {mgrs_code_to_wgs}')

data = mgrs2geojson(mgrs_code)
print(data)
output_file = f'mgrs{mgrs_precision}.geojson'
with open(output_file, 'w') as f:
    json.dump(data, f, indent=2)  # 'indent' makes the JSON output more readable
print(f'GeoJSON written to {output_file}')