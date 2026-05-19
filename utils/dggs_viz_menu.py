# -*- coding: utf-8 -*-
"""Build the merged DGGS Viz menu and submenus."""

from __future__ import annotations

import os

from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QCheckBox, QMenu, QWidgetAction

from vgrid.utils.constants import DGGRID_TYPES

from ..dggsgrid.dggridgrid import DGGRIDGrid

DGGRID_MENU_EXCLUDE = frozenset(
    {"SUPERFUND", "PLANETRISK", "ISEA4H", "ISEA43H", "FULLER4H", "FULLER43H", "FULLER7H"}
)

DGGAL_VIZ_ENTRIES = [
    ("gnosis", "dggal_gnosisgrid", "GNOSIS"),
    ("isea4r", "dggal_isea4rgrid", "ISEA4R"),
    ("isea9r", "dggal_isea9rgrid", "ISEA9R"),
    ("isea3h", "dggal_isea3hgrid", "ISEA3H"),
    ("isea7h", "dggal_isea7hgrid", "ISEA7H"),
    ("isea7h_z7", "dggal_isea7h_z7grid", "ISEA7H_Z7"),
    ("ivea4r", "dggal_ivea4rgrid", "IVEA4R"),
    ("ivea9r", "dggal_ivea9rgrid", "IVEA9R"),
    ("ivea3h", "dggal_ivea3hgrid", "IVEA3H"),
    ("ivea7h", "dggal_ivea7hgrid", "IVEA7H"),
    ("ivea7h_z7", "dggal_ivea7h_z7grid", "IVEA7H_Z7"),
    ("rtea4r", "dggal_rtea4rgrid", "RTEA4R"),
    ("rtea9r", "dggal_rtea9rgrid", "RTEA9R"),
    ("rtea3h", "dggal_rtea3hgrid", "RTEA3H"),
    ("rtea7h", "dggal_rtea7hgrid", "RTEA7H"),
    ("rtea7h_z7", "dggal_rtea7h_z7grid", "RTEA7H_Z7"),
    ("healpix", "dggal_healpixgrid", "HEALPix"),
    ("rhealpix", "dggal_rhealpixgrid", "rHEALPix"),
]


def _plugin_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _icon(name: str) -> QIcon:
    return QIcon(os.path.join(_plugin_root(), "images", "generator", name))


def _add_checkbox(menu: QMenu, label: str, icon: QIcon, on_toggle) -> QWidgetAction:
    action = QWidgetAction(menu)
    checkbox = QCheckBox(label)
    checkbox.setIcon(icon)
    checkbox.setChecked(False)
    checkbox.toggled.connect(on_toggle)
    action.setDefaultWidget(checkbox)
    menu.addAction(action)
    return action


def _grid_toggle(enable_fn, grid_fn):
    return lambda checked: (enable_fn(checked), grid_fn()) if checked else enable_fn(False)


def _dggrid_viz_toggle(plugin, dggs_type: str, grid, checked: bool) -> None:
    """Only one DGGRID type active at a time; refresh grid on check like DGGAL Viz."""
    if checked:
        for other_type, (other_grid, other_cb) in plugin.dggrid_viz_items.items():
            if other_type != dggs_type:
                other_cb.blockSignals(True)
                other_cb.setChecked(False)
                other_cb.blockSignals(False)
                other_grid.enable_dggrid(False)
        grid.enable_dggrid(True)
        grid.dggrid_grid()
    else:
        grid.enable_dggrid(False)


def setup_dggs_visualization_menus(plugin) -> None:
    """
    Create DGGS Viz menu on *plugin* with ordered entries and submenus.
    Sets ``plugin.dggs_viz_menu``, ``plugin.dggal_menu``, ``plugin.dggrid_grids``.
    """
    viz_menu = QMenu("DGGS Viz")
    hex_icon = _icon("grid_hex.svg")
    plugin.Vgrid_add_submenu2(viz_menu, hex_icon)

    plugin.dggs_viz_menu = viz_menu
    plugin.dggrid_grids = {}
    plugin.dggrid_viz_items = {}

    _add_checkbox(
        viz_menu,
        "H3",
        _icon("grid_h3.svg"),
        _grid_toggle(plugin.h3grid.enable_h3, plugin.h3grid.h3_grid),
    )
    _add_checkbox(
        viz_menu,
        "S2",
        _icon("grid_s2.svg"),
        _grid_toggle(plugin.s2grid.enable_s2, plugin.s2grid.s2_grid),
    )
    _add_checkbox(
        viz_menu,
        "A5",
        _icon("grid_a5.svg"),
        _grid_toggle(plugin.a5grid.enable_a5, plugin.a5grid.a5_grid),
    )
    _add_checkbox(
        viz_menu,
        "rHEALPix",
        _icon("grid_rhealpix.svg"),
        _grid_toggle(plugin.rhealpixgrid.enable_rhealpix, plugin.rhealpixgrid.rhealpix_grid),
    )
    _add_checkbox(
        viz_menu,
        "ISEA4T",
        _icon("grid_triangle.svg"),
        _grid_toggle(plugin.isea4tgrid.enable_isea4t, plugin.isea4tgrid.isea4t_grid),
    )
    _add_checkbox(
        viz_menu,
        "ISEA3H",
        hex_icon,
        _grid_toggle(plugin.isea3hgrid.enable_isea3h, plugin.isea3hgrid.isea3h_grid),
    )

    dggal_menu = QMenu("DGGAL")
    dggal_menu.setIcon(_icon("grid_dggal.svg"))
    viz_menu.addMenu(dggal_menu)
    plugin.dggal_menu = dggal_menu

    for _key, attr, label in DGGAL_VIZ_ENTRIES:
        grid = getattr(plugin, attr)
        _add_checkbox(
            dggal_menu,
            label,
            _icon("grid_dggal.svg"),
            _grid_toggle(grid.enable_dggal, grid.dggal_grid),
        )

    dggrid_menu = QMenu("DGGRID")
    dggrid_menu.setIcon(_icon("grid_dggrid.svg"))
    viz_menu.addMenu(dggrid_menu)
    plugin.dggrid_menu = dggrid_menu

    for dggs_type in DGGRID_TYPES:
        if dggs_type in DGGRID_MENU_EXCLUDE:
            continue
        grid = DGGRIDGrid(plugin, plugin.canvas, plugin.iface, dggs_type)
        plugin.dggrid_grids[dggs_type] = grid
        action = QWidgetAction(dggrid_menu)
        checkbox = QCheckBox(dggs_type)
        checkbox.setIcon(_icon("grid_dggrid.svg"))
        checkbox.setChecked(False)
        checkbox.toggled.connect(
            lambda checked, t=dggs_type, g=grid: _dggrid_viz_toggle(plugin, t, g, checked)
        )
        action.setDefaultWidget(checkbox)
        dggrid_menu.addAction(action)
        plugin.dggrid_viz_items[dggs_type] = (grid, checkbox)

    _add_checkbox(
        viz_menu,
        "OLC",
        _icon("grid_olc.svg"),
        _grid_toggle(plugin.olcgrid.enable_olc, plugin.olcgrid.olc_grid),
    )
    _add_checkbox(
        viz_menu,
        "Geohash",
        _icon("grid_quad.svg"),
        _grid_toggle(plugin.geohashgrid.enable_geohash, plugin.geohashgrid.geohash_grid),
    )
    _add_checkbox(
        viz_menu,
        "GEOREF",
        _icon("grid_quad.svg"),
        _grid_toggle(plugin.georefgrid.enable_georef, plugin.georefgrid.georef_grid),
    )
    _add_checkbox(
        viz_menu,
        "Tilecode",
        _icon("grid_quad.svg"),
        _grid_toggle(plugin.tilecodegrid.enable_tilecode, plugin.tilecodegrid.tilecode_grid),
    )
    _add_checkbox(
        viz_menu,
        "Maidenhead",
        _icon("grid_quad.svg"),
        _grid_toggle(
            plugin.maidenheadgrid.enable_maidenhead, plugin.maidenheadgrid.maidenhead_grid
        ),
    )
    _add_checkbox(
        viz_menu,
        "GARS",
        _icon("grid_quad.svg"),
        _grid_toggle(plugin.garsgrid.enable_gars, plugin.garsgrid.gars_grid),
    )
    _add_checkbox(
        viz_menu,
        "DIGIPIN",
        _icon("grid_quad.svg"),
        _grid_toggle(plugin.digipingrid.enable_digipin, plugin.digipingrid.digipin_grid),
    )
