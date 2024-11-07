import vgrid.geocode.olc as olc

def generate_all_olcs(length):
    """Generate all OLC codes of a given length."""
    olc_chars = '23456789CFGHJMPQRVWX'
    if length < 2:
        raise ValueError("OLC length should be at least 2.")

    def olc_generator(prefix, depth):
        if depth == length:
            yield prefix
        else:
            for char in olc_chars:
                yield from olc_generator(prefix + char, depth + 1)

    return olc_generator("", 0)

def to_full_olc(short_code):
    # Decode the short OLC code into latitude and longitude
    latitude, longitude = olc.decode(short_code)
    
    # Re-encode to get the full OLC code
    return olc.encode(latitude, longitude)

for olc_code in generate_all_olcs(2):
    print(olc_code)
    full_code = olc.encode(to_full_olc(olc_code))
    print(full_code)
    # print (olc.decode(olc_code))