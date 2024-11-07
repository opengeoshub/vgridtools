from vgrid.geocode import mgrs
from vgrid.geocode.geocode2geojson import *
import json
latitude, longitude = 10.775275567242561, 106.70679737574993

georef_precision = 4 # [0 -->10]
georef_code = georef.encode(latitude, longitude, georef_precision)
georef_decode = georef.decode(georef_code, True)
print(f'latitude, longitude = {latitude},{longitude}')

print(f'GEOREF Code at precision = {georef_precision}: {georef_code}')
print(f'Decode {georef_code} to WGS84 = {georef_decode}')

data = georef2geojson(georef_code)
print(data)
output_file = f'georef{georef_precision}.geojson'
with open(output_file, 'w') as f:
    json.dump(data, f, indent=2)  # 'indent' makes the JSON output more readable
print(f'GeoJSON written to {output_file}')
