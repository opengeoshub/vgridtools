from vgrid.geocode import olc
from vgrid.geocode.geocode2geojson import *
latitude, longitude = 10.775275567242561, 106.70679737574993

olc_precision = 11 #[10-->15]
olc_code = olc.encode(latitude, longitude, olc_precision)
olc_decode = olc.decode(olc_code)
print(f'OLC at precision = {olc_precision}: {olc_code}')
print(f'Decode {olc_code} to center and cell in WGS84 = {olc_decode}')

data = olc2geojson(olc_code)
print(data)
output_file = f'olc{olc_precision}.geojson'
with open(output_file, 'w') as f:
    json.dump(data, f, indent=2)  # 'indent' makes the JSON output more readable
print(f'GeoJSON written to {output_file}')