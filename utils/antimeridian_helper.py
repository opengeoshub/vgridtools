"""Map Shift/Split at Antimeridian checkboxes to *2geo converter arguments."""

_SHIFT_FIX = {
    "h3": "shift_west",
    "s2": "shift_east",
    "rhealpix": "shift_east",
    "isea4t": "shift_west",
    "isea3h": "shift_west",
}


def resolve_fix_antimeridian(
    dggs_type, shift_antimeridian=False, split_antimeridian=False
):
    """Map Shift/Split checkboxes to ``fix_antimeridian`` for *2geo converters."""
    if split_antimeridian:
        return "split"
    if shift_antimeridian:
        return _SHIFT_FIX.get(dggs_type.lower())
    return None


def use_split_antimeridian(shift_antimeridian=False, split_antimeridian=False):
    """A5/DGGAL converters only support split (shift is treated as split)."""
    return bool(split_antimeridian or shift_antimeridian)


def geo_with_fix(
    converter,
    cell_id,
    dggs_type,
    shift_antimeridian=False,
    split_antimeridian=False,
):
    fix = resolve_fix_antimeridian(
        dggs_type, shift_antimeridian, split_antimeridian
    )
    if fix:
        return converter(cell_id, fix_antimeridian=fix)
    return converter(cell_id)
