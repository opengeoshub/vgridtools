import argparse
import os
from vgrid.utils.mapbox_vector_tile import encode
import vgrid.utils.mercantile as mercantile
from shapely.geometry import box, mapping
import sqlite3
import gzip
from tqdm import tqdm

def create_mbtiles(output_mbtiles, min_latitude, min_longitude, max_latitude, max_longitude, min_zoom, max_zoom):
    if os.path.exists(output_mbtiles):
        os.remove(output_mbtiles)
    conn = sqlite3.connect(output_mbtiles)
    cursor = conn.cursor()

    try:           
        cursor.execute('''CREATE TABLE metadata (name TEXT, value TEXT);''')
        cursor.execute('''CREATE UNIQUE INDEX name ON metadata (name);''')
        cursor.execute('''CREATE TABLE tiles (zoom_level INTEGER, tile_column INTEGER, tile_row INTEGER, tile_data BLOB);''')
        cursor.execute('''CREATE UNIQUE INDEX tile_index ON tiles(zoom_level, tile_column, tile_row);''')

        cursor.execute("INSERT INTO metadata (name, value) VALUES ('name', 'vgrid');")
        cursor.execute("INSERT INTO metadata (name, value) VALUES ('description', 'Vgrid MBTiles created by vgrid.vgrid');")
        cursor.execute("INSERT INTO metadata (name, value) VALUES ('type', 'overlay');")
        cursor.execute("INSERT INTO metadata (name, value) VALUES ('version', '1');")
        cursor.execute("INSERT INTO metadata (name, value) VALUES ('format', 'pbf');")
        cursor.execute(f"INSERT INTO metadata (name, value) VALUES ('minzoom', '{min_zoom}');")
        cursor.execute(f"INSERT INTO metadata (name, value) VALUES ('maxzoom', '{max_zoom}');")
        cursor.execute(f"INSERT INTO metadata (name, value) VALUES ('bounds', '{min_latitude},{min_longitude},{max_latitude},{max_longitude}');")

        conn.commit()        

    except Exception as e:
        print(f"Error creating MBTiles: {e}")
    finally:
        print(f"Creating MBTiles done!")
        conn.close()

def create_tile(z, x, y):
    try:
        flip_y = (2 ** z - 1) - y
        tile_geometry = box(0, 0, 4096, 4096)
        quadkey = mercantile.quadkey(x, y, z)
        properties = {
            'vcode': f'z{z}x{x}y{y}',
            'tmscode': f'z{z}x{x}y{flip_y}',
            'vname': f'{z}/{x}/{y}',
            'tmsname': f'{z}/{x}/{flip_y}',
            'quadkey': quadkey
        }

        feature = {
            'geometry': mapping(tile_geometry),
            'properties': properties
        }

        tile_data = {
            'name': 'vgrid',
            'features': [feature]
        }

        tile_data_encoded = encode(tile_data)
        tile_data_encoded_gzipped = gzip.compress(tile_data_encoded)
        return tile_data_encoded_gzipped
    except Exception as e:
        print(f"Error creating tile: {e}")
        raise

def create_tiles(tiles, output_mbtiles, current_zoom):
    try:
        conn = sqlite3.connect(output_mbtiles)
        cursor = conn.cursor()        
        for tile in tqdm(tiles, desc=f"Creating tiles at zoom level {current_zoom}: "):
            z, x, y = tile.z, tile.x, tile.y
            flip_y = (2 ** z - 1) - y
            tile_data = create_tile(z, x, y)
            cursor.execute('INSERT INTO tiles (zoom_level, tile_column, tile_row, tile_data) VALUES (?, ?, ?, ?);', 
                            (z, x, y, tile_data))
        conn.commit()
    except Exception as e:
        print(f"Error creating tiles: {e}")
    finally:
        conn.close()

def chunk_list(input_list, chunk_size):
    """Yield successive chunks from input_list."""
    for i in range(0, len(input_list), chunk_size):
        yield input_list[i:i + chunk_size]

def main():
    parser = argparse.ArgumentParser(description='Create a debug grid representing the XYZ vector tile scheme as an MBTiles file.')
    parser.add_argument('-o', '--output', required=True, help='Output MBTiles file')
    parser.add_argument('-minzoom', '--minzoom', type=int, required=True, help='Minimum zoom level')
    parser.add_argument('-maxzoom', '--maxzoom', type=int, required=True, help='Maximum zoom level')
    parser.add_argument('-chunksize', '--chunksize', type=int, default=10000, help='Number of tiles to process in each chunk')
    parser.add_argument('-bounds', '--bounds', type=float, nargs=4, metavar=('min_lat', 'min_lon', 'max_lat', 'max_lon'),
                        help='Bounding box coordinates (min_lat, min_lon, max_lat, max_lon)', 
                        default=[-85.05112878, -180.0, 85.05112878, 180.0])
    # Vietnam bounds: 8.34,101.85,23.81,109.74
    args = parser.parse_args()

    if args.minzoom < 0 or args.maxzoom < args.minzoom:
        raise ValueError("minzoom must be non-negative and maxzoom must be greater than or equal to minzoom")

    min_latitude, min_longitude, max_latitude, max_longitude = args.bounds

    create_mbtiles(args.output, min_latitude, min_longitude, max_latitude, max_longitude, args.minzoom, args.maxzoom)

    for zoom_level in range(args.minzoom, args.maxzoom + 1):
    # Use an iterator to process tiles without loading them all into memory
        tile_iterator = mercantile.tiles(min_longitude, min_latitude, max_longitude, max_latitude, zoom_level)
        
        tile_chunk = []
        for tile in tile_iterator:
            tile_chunk.append(tile)
            
            # When the chunk reaches the specified size, process it
            if len(tile_chunk) == args.chunksize:
                create_tiles(tile_chunk, args.output, zoom_level)
                tile_chunk = []  # Reset chunk for the next set of tiles
        
        # Process any remaining tiles in the chunk
        if tile_chunk:
            create_tiles(tile_chunk, args.output, zoom_level)
    print(f"Creating tiles done!")

if __name__ == '__main__':
    main()