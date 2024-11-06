import h3

def h3cell(h3_code):
     # Decode the GEOREF code to get the center coordinates and precision
    bbox = h3.cell_to_boundary(h3_code)
    return bbox