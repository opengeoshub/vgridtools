import json
from vgrid.geocode import s2
from vgrid.geocode.geocode2geojson import *
from vgrid.geocode.s2 import LatLng, CellId

latitude, longitude = 10.775275567242561, 106.70679737574993

s2_precision = 21 #[0 -->30]
lat_lng = LatLng.from_degrees(latitude, longitude)
cell_id = CellId.from_lat_lng(lat_lng)
cell_id = cell_id.parent(s2_precision)
cell_id_token= CellId.to_token(cell_id)
print(cell_id_token)

data = s22geojson(cell_id_token)
print(data)

output_file = f's2_{s2_precision}.geojson'
with open(output_file, 'w') as f:
    json.dump(data, f, indent=2)  # 'indent' makes the JSON output more readable
print(f'GeoJSON written to {output_file}')