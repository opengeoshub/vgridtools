"""Shared rHEALPix N_side helpers for the vgridtools plugin."""

from __future__ import annotations


def resolve_rhealpix_n_side(N_side=None) -> int:
    """Return validated N_side (2 or 3), defaulting to plugin settings."""
    if N_side is None:
        try:
            from ..settings import settings

            N_side = getattr(settings, "rhealpixNSide", 3)
        except Exception:
            N_side = 3
    from vgrid.utils.io import validate_rhealpix_n_side

    return validate_rhealpix_n_side(int(N_side))


def get_plugin_rhealpix_dggs(N_side=None):
    """Build native rHEALPix DGGS using plugin settings when N_side is omitted."""
    from vgrid.utils.io import get_rhealpix_dggs

    return get_rhealpix_dggs(N_side=resolve_rhealpix_n_side(N_side))
