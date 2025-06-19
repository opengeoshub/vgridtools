import h3
from shapely.geometry import LineString, Polygon
import numpy as np

# Example Shapely LineString
line = LineString([(-122.055323, 37.361559), (-122.055223, 37.370000)])
polygon = Polygon([
    (-122.056, 37.354),
    (-122.053, 37.354),
    (-122.053, 37.357),
    (-122.056, 37.357),
    (-122.056, 37.354)
])
h3_cells = h3.geo_to_cells(line, 15)
print(h3_cells)
# Function to sample points along the line
# def sample_line(line, step=100):
#     length = line.length
#     distances = np.linspace(0, length, int(length / step) + 1)
#     return [line.interpolate(d) for d in distances]

# # Convert sampled points to H3
# def line_to_h3(line, resolution=9, step=100):
#     points = sample_line(line, step)
#     print(points)
#     h3_indexes = set()
#     for pt in points:
#         h3_index = h3.latlng_to_cell(pt.y, pt.x, resolution)
#         h3_indexes.add(h3_index)
#     return list(h3_indexes)

# # Convert line to H3 indexes
# h3_cells = line_to_h3(line, resolution=9, step=100)
# print(h3_cells)

