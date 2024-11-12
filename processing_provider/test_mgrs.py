import mgrs
def get_unique_mgrs_codes(precision):
    # Define MGRS converter

    # Set up bounding box for the entire world
    lat_min, lat_max = -79.0, 83.0  # MGRS is valid between these latitudes
    lon_min, lon_max = -180.0, 180.0

    # Determine step size based on precision
    if precision == 0:
        step = 1    # 100 km grid cell
    if precision == 1:
        step = 0.1    # 10 km grid cell
    elif precision == 2:
        step = 0.01   # 1 km grid cell
    elif precision == 3:
        step = 0.001  # 100 m grid cell
    elif precision == 4:
        step = 0.0001 # 10 m grid cell
    elif precision == 5:
        step = 0.00001 # 1 m grid cell
    else:
        step = 1 
    
    # Set to store unique MGRS codes
    unique_mgrs_codes = set()
    
    # Iterate over latitude and longitude
    lat = lat_min
    while lat <= lat_max:
        lon = lon_min
        while lon <= lon_max:
            # Convert lat/lon to MGRS code at the desired precision
            mgrs_code = mgrs.toMgrs(lat, lon, precision)
            unique_mgrs_codes.add(mgrs_code)
            lon += step
        lat += step
    
    return unique_mgrs_codes

# Example usage
precision_level = 0 # Change this to desired precision (0 to 5)
unique_codes = get_unique_mgrs_codes(precision_level)

# Output result
print(f"Number of unique MGRS codes at precision {precision_level}: {len(unique_codes)}")
print("Sample MGRS codes:", list(unique_codes)[:10])  # Display a sample
# lat,lon = -80, 40
# print (mgrs.toMgrs(lat, lon, 0))