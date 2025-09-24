# Vgridtools
**Vgridtools -  Vgrid DGGS Plugin for QGIS**

Vgridtools supports a wide range of popular geodesic DGGS, including H3, S2, A5, rHEALPix, Open-EAGGR ISEA4T, ISEA3H, DGGRID, DGGAL, EASE-DGGS, QTM, along with graticule-based DGGS such as OLC, Geohash, MGRS, GEOREF, TileCode, Quadkey, Maidenhead, and GARS.

[![logo](https://raw.githubusercontent.com/opengeoshub/vgridtools/refs/heads/main/images/vgridqgis.svg)](https://github.com/opengeoshub/vgridtools/blob/main/images/vgridqgis.svg)


Full Vgridtools DGGS documentation is available at [vgridtools document](https://vgridtools.gishub.vn).

To work with Vgrid DGGS directly in Python or CLI, install [vgrid](https://pypi.org/project/vgrid/). Full Vgrid  Python documentation is available at [vgrid document](https://vgrid.gishub.vn).

To work with Vgrid DGGS directly in GeoPandas and Pandas, use the [vgridpandas](https://pypi.org/project/vgridpandas/) package. Full Vgridpandas DGGS documentation is available at [vgridpandas document](https://vgridpandas.gishub.vn).

To visualize DGGS in Maplibre GL JS, try the [vgrid-maplibre](https://www.npmjs.com/package/vgrid-maplibre) library.

For an interactive demo, visit the [Vgrid Homepage](https://vgrid.vn).


[![image](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

<!-- TABLE OF CONTENTS -->
<details open="open">
  <summary>Vgrid DGGS Tools for QGIS</summary>  
  <ol>
    <li>
      <a href="#vgridtools-installation">Vgridtools installation</a>     
    </li>
    <li><a href="#dggs-visualization">DGGS Visualization</a></li>
    <li><a href="#latlon-to-dggs">Latlon to DGGS</a></li>
    <li><a href="#dggs-conversion">DGGS Conversion</a></li>
    <li><a href="#dggs-binning">DGGS Binning</a></li>
    <li><a href="#dggs-resampling">DGGS Resampling</a></li>
    <li><a href="#dggs-generator">DGGS Generator</a></li>
    <li><a href="#expressions">Expressions</a></li>
    <li><a href="#settings">Settings</a></li>
  </ol>
</details>

## Vgridtools installation
### After installing `vgridtools`, a dialog will appear prompting you to install `vgrid`. Copy the following commands:
```python
import pip  
pip.main(['install', 'vgrid','--upgrade'])
```
### Use the same command after upgrading vgridtools

<div align="center">
  <img src="https://raw.githubusercontent.com/opengeoshub/vgridtools/main/images/readme/vgriddialog.png">
</div>

### When QGIS starts, navigate to Plugins → Python Console, select ***Show Editor***, paste the copied commands, and click ***Run Script***.
<div align="center">
<img src="https://raw.githubusercontent.com/opengeoshub/vgridtools/main/images/readme/vgridinstall.png">
</div>

### Restart QGIS, and you'll see DGGS Vgrid in the Processing Toolbox.
<div align="center">
<img src="https://raw.githubusercontent.com/opengeoshub/vgridtools/main/images/readme/vgridtools.png">
</div>

## DGGS Visualization
### Visualize DGGSs interactively.

<div align="center">
  <img src="https://raw.githubusercontent.com/opengeoshub/vgridtools/main/images/readme/dggsvisualization.png">
</div>

## Latlon to DGGS
### Click and zoom to DGGS cells.

<div align="center">
  <img src="https://raw.githubusercontent.com/opengeoshub/vgridtools/main/images/readme/latlon2dggstool.png">
</div> 

## DGGS Conversion

- Cell ID to DGGS: see [Cell ID to DGGS](manual/conversion/cellid2dggs.md)
- Vector to DGGS: see [Vector to DGGS](manual/conversion/vector2dggs.md)
- Raster to DGGS: see [Raster to DGGS](manual/conversion/raster2dggs.md)
- DGGS Compact: see [DGGS Compact](manual/conversion/dggscompact.md)
- DGGS Expand: see [DGGS Expand](manual/conversion/dggsexpand.md)

## DGGS Binning
### Bin/ aggregate point layer into DGGS at a specified resolution.
<div align="center">
  <img src="https://raw.githubusercontent.com/opengeoshub/vgridtools/main/images/readme/dggsbinning_h3.png">
</div>

## DGGS Resampling
### Resample accross different DGGSs.
<div align="center">
  <img src="https://raw.githubusercontent.com/opengeoshub/vgridtools/main/images/readme/dggsresampling_h32s2.png">
</div>


## DGGS Generator
### Generate DGGS at a specified resolution within a bounding box.
<div align="center">
  <img src="https://raw.githubusercontent.com/opengeoshub/vgridtools/main/images/readme/dggsgenerator_h3.png">
</div>

## Expressions

See [Expressions](manual/expressions.md)

## Settings
### Configure default resolution, stroke color, and other DGGS cartographic options.

<div align="center">
  <img src="https://raw.githubusercontent.com/opengeoshub/vgridtools/main/images/readme/settings.png">
</div>
