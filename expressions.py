# -*- coding: utf-8 -*-

"""
/***************************************************************************
                              Vgrid Expression
                              -------------------
        Date                 : 2024-11-20
        copyright            : (L) 2024 by Thang Quach
        email                : quachdongthang@gmail.com
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""

__author__ = 'Thang Quach'
__date__ = '2024-11-20'
__copyright__ = '(L) 2024 by Thang Quach'


from qgis.core import *
from qgis.gui import *
from qgis.utils import qgsfunction
from vgrid.utils import s2,qtm,olc,mgrs,geohash,georef,tilecode,maidenhead
from vgrid.utils.gars.garsgrid import GARSGrid  
from vgrid.utils.rhealpixdggs.dggs import RHEALPixDGGS
from vgrid.utils.rhealpixdggs.ellipsoids import WGS84_ELLIPSOID
import h3
import platform
if (platform.system() == 'Windows'):
    from vgrid.utils.eaggr.eaggr import Eaggr
    from vgrid.utils.eaggr.shapes.dggs_cell import DggsCell
    from vgrid.utils.eaggr.shapes.lat_long_point import LatLongPoint
    from vgrid.utils.eaggr.enums.model import Model
    from vgrid.generator.isea3hgrid import isea3h_res_accuracy_dict
    from vgrid.generator.isea4tgrid import isea4t_res_accuracy_dict

group_name = 'DGGS Vgrid'

# https://qgis.org/pyqgis/3.2/core/Expression/QgsExpression.html

LOC = QgsApplication.locale()[:2]
def tr(*string):
    # Translate to Vietnamese: arg[0] - English (translate), arg[1] - Vietnamese
    if LOC == 'vi':
        if len(string) == 2:
            return string[1]
        else:
            return string[0]
    else:
        return string[0]

@qgsfunction(args='auto', group=group_name)
def latlon2h3(latitude, longitude, resolution, feature, parent):
  """<style type="text/css">
    .function {
    color: #05688f;
    font-weight: bold;
    }
    .parameters {
    color: red;
    font-style:italic
    }
  </style>
  Convert latlon to H3 cell ID.
  <h4>Syntax</h4>    
    <li><span class = function>latlon2h3</span>(<span class = parameters>lat, long, resolution [0..15]</span>)</li>
  <h4>Example usage</h4>

  <ul>
    <li><span class = function>latlon2h3</span>(<span class = parameters>10.775275567242561, 106.70679737574993, 13</span>)&rarr; '8d65b56628e46bf'</li>
  </ul>    
  """ 
  return h3.latlng_to_cell(latitude, longitude, resolution)

@qgsfunction(args='auto', group=group_name)
def latlon2s2(latitude, longitude, resolution, feature, parent):
  """<style type="text/css">
    .function {
    color: #05688f;
    font-weight: bold;
    }
    .parameters {
    color: red;
    font-style:italic
    }
  </style>
  Convert latlon to S2 cell ID.
  <h4>Syntax</h4>    
    <li><span class = function>latlon2s2</span>(<span class = parameters>lat, long, resolution [0-->30]</span>)</li>
  <h4>Example usage</h4>

  <ul>
    <li><span class = function>latlon2s2</span>(<span class = parameters>10.775275567242561, 106.70679737574993, 21</span>)&rarr; '31752f45cc94'</li>
  </ul>    
  """ 
  lat_lng = s2.LatLng.from_degrees(latitude, longitude)
  cell_id = s2.CellId.from_lat_lng(lat_lng)
  cell_id = cell_id.parent(resolution)
  cell_id_token= s2.CellId.to_token(cell_id)
  return cell_id_token


@qgsfunction(args='auto', group=group_name)
def latlon2rhealpix(latitude, longitude, resolution, feature, parent):
  """<style type="text/css">
    .function {
    color: #05688f;
    font-weight: bold;
    }
    .parameters {
    color: red;
    font-style:italic
    }
  </style>
  Convert latlon to Rhealpix cell ID.
  <h4>Syntax</h4>    
    <li><span class = function>latlon2rhealpix</span>(<span class = parameters>lat, long, resolution [0..15]</span>)</li>
  <h4>Example usage</h4>

  <ul>
    <li><span class = function>latlon2rhealpix</span>(<span class = parameters>10.775275567242561, 106.70679737574993, 12</span>)&rarr; 'R312603625535'</li>
  </ul>    
  """ 
  E = WGS84_ELLIPSOID
  rdggs = RHEALPixDGGS(ellipsoid=E, north_square=1, south_square=3, N_side=3)
  point = (longitude, latitude)
  rhealpix_cell = rdggs.cell_from_point(resolution, point, plane=False)
  return str(rhealpix_cell)


@qgsfunction(args='auto', group=group_name)
def latlon2isea4t(latitude, longitude, resolution, feature, parent):
  """<style type="text/css">
    .function {
    color: #05688f;
    font-weight: bold;
    }
    .parameters {
    color: red;
    font-style:italic
    }
  </style>
  Convert latlon to OpenEAGGR ISEA4T cell ID.
  <h4>Syntax</h4>    
    <li><span class = function>latlon2isea4t</span>(<span class = parameters>lat, long, resolution [0..39]</span>)</li>
  <h4>Example usage</h4>

  <ul>
    <li><span class = function>latlon2isea4t</span>(<span class = parameters>10.775275567242561, 106.70679737574993, 20</span>)&rarr; '1310231333101123322130'</li>
  </ul>    
  """ 
  if (platform.system() == 'Windows'):
      # res: [0..39]
      isea4t_dggs = Eaggr(Model.ISEA4T)
      max_accuracy =  isea4t_res_accuracy_dict[39] # maximum cell_id length with 41 characters, 2.55*10**13 is min cell_id length with 2 chacracters
      lat_long_point = LatLongPoint(latitude, longitude, max_accuracy)
      isea4t_cell_max_accuracy = isea4t_dggs.convert_point_to_dggs_cell(lat_long_point)
      cell_id_len = resolution+2
      isea4t_cell = DggsCell(isea4t_cell_max_accuracy._cell_id[:cell_id_len])
      return isea4t_cell._cell_id

@qgsfunction(args='auto', group=group_name)
def latlon2isea3h(latitude, longitude, resolution, feature, parent):
  """<style type="text/css">
    .function {
    color: #05688f;
    font-weight: bold;
    }
    .parameters {
    color: red;
    font-style:italic
    }
  </style>
  Convert latlon to OpenEAGGR ISEA3H cell ID.
  <h4>Syntax</h4>    
    <li><span class = function>latlon2isea3h</span>(<span class = parameters>lat, long, resolution [0..40]</span>)</li>
  <h4>Example usage</h4>

  <ul>
    <li><span class = function>latlon2isea3h</span>(<span class = parameters>10.775275567242561, 106.70679737574993, 20</span>)&rarr; '132022636,-1020'</li>
  </ul>    
  """ 
  if (platform.system() == 'Windows'):
        isea3h_dggs = Eaggr(Model.ISEA3H)
        accuracy = isea3h_res_accuracy_dict.get(resolution)            
        lat_long_point = LatLongPoint(latitude, longitude, accuracy)
        isea3h_cell = isea3h_dggs.convert_point_to_dggs_cell(lat_long_point)
        return isea3h_cell.get_cell_id()

@qgsfunction(args='auto', group=group_name)
def latlon2qtm(latitude, longitude, resolution, feature, parent):
  """<style type="text/css">
    .function {
    color: #05688f;
    font-weight: bold;
    }
    .parameters {
    color: red;
    font-style:italic
    }
  </style>
  Convert latlon to QTM cell ID.
  <h4>Syntax</h4>    
    <li><span class = function>latlon2qtm</span>(<span class = parameters>lat, long, resolution [1..24]</span>)</li>
  <h4>Example usage</h4>

  <ul>
    <li><span class = function>latlon2qtm</span>(<span class = parameters>10.775275567242561, 106.70679737574993, 18</span>)&rarr; '420123231312110130'</li>
  </ul>    
  """
  return qtm.latlon_to_qtm_id(latitude, longitude, resolution)

# @qgsfunction(args='auto', group=group_name,usesgeometry=True)
@qgsfunction(args='auto', group=group_name)
def latlon2olc(latitude, longitude, codeLength, feature, parent):
  """<style type="text/css">
    .function {
    color: #05688f;
    font-weight: bold;
    }
    .parameters {
    color: red;
    font-style:italic
    }
  </style>
  Convert latlon to Open Location Code (OLC)/ Google Plus Code
  <h4>Syntax</h4>    
    <li><span class = function>latlon2olc</span>(<span class = parameters>lat, long, codeLength [10-->15]</span>)</li>
  <h4>Example usage</h4>

  <ul>
    <li><span class = function>latlon2olc</span>(<span class = parameters>10.775275567242561, 106.70679737574993, 11</span>)&rarr; '7P28QPG4+4P7'</li>
  </ul>    
  """ 
  return olc.encode(latitude, longitude, codeLength) 

@qgsfunction(args='auto', group=group_name)
def latlon2mgrs(latitude, longitude, resolution, feature, parent):
  """<style type="text/css">
    .function {
    color: #05688f;
    font-weight: bold;
    }
    .parameters {
    color: red;
    font-style:italic
    }
  </style>
  Convert latlon to MGRS cell ID.
  <h4>Syntax</h4>    
    <li><span class = function>latlon2mgrs</span>(<span class = parameters>lat, long, resolution [0-->5]</span>)</li>
  <h4>Example usage</h4>

  <ul>
    <li><span class = function>latlon2mgrs</span>(<span class = parameters>10.775275567242561, 106.70679737574993, 4</span>)&rarr; '48PXS86629165'</li>
  </ul>    
  """ 
  return mgrs.toMgrs(latitude, longitude, resolution) 

@qgsfunction(args='auto', group=group_name)
def latlon2geohash(latitude, longitude, resolution, feature, parent):
  """<style type="text/css">
    .function {
    color: #05688f;
    font-weight: bold;
    }
    .parameters {
    color: red;
    font-style:italic
    }
  </style>
  Convert latlon to Geohash.
  <h4>Syntax</h4>    
    <li><span class = function>latlon2geohash</span>(<span class = parameters>lat, long, resolution [1-->30]</span>)</li>
  <h4>Example usage</h4>

  <ul>
    <li><span class = function>latlon2geohash</span>(<span class = parameters>10.775275567242561, 106.70679737574993, 9</span>)&rarr; 'w3gvk1td8'</li>
  </ul>    
  """ 
  return geohash.encode(latitude, longitude, resolution) 

@qgsfunction(args='auto', group=group_name)
def latlon2georef(latitude, longitude, resolution, feature, parent):
  """<style type="text/css">
    .function {
    color: #05688f;
    font-weight: bold;
    }
    .parameters {
    color: red;
    font-style:italic
    }
  </style>
  Convert latlon to GEOREF cell ID.
  <h4>Syntax</h4>    
    <li><span class = function>latlon2georef</span>(<span class = parameters>lat, long, resolution [0-->10]</span>)</li>
  <h4>Example usage</h4>

  <ul>
    <li><span class = function>latlon2georef</span>(<span class = parameters>10.775275567242561, 106.70679737574993, 5</span>)&rarr; 'VGBL4240746516'</li>
  </ul>    
  """ 
  return georef.encode(latitude, longitude, resolution) 

@qgsfunction(args='auto', group=group_name)
def latlon2tilecode(latitude, longitude, zoom, feature, parent):
  """<style type="text/css">
    .function {
    color: #05688f;
    font-weight: bold;
    }
    .parameters {
    color: red;
    font-style:italic
    }
  </style>
  Convert latlon to Vcode.
  <h4>Syntax</h4>    
    <li><span class = function>latlon2tilecode</span>(<span class = parameters>lat, long, resolution/ zoom level [0;25]</span>)</li>
  <h4>Example usage</h4>

  <ul>
    <li><span class = function>latlon2tilecode</span>(<span class = parameters>10.775275567242561, 106.70679737574993, 23</span>)&rarr; 'z23x6680752y3941728'</li>
  </ul>    
  """ 
  return tilecode.latlon2tilecode(latitude, longitude, zoom) 

@qgsfunction(args='auto', group=group_name)
def latlon2maidenhead(latitude, longitude, resolution, feature, parent):
  """<style type="text/css">
    .function {
    color: #05688f;
    font-weight: bold;
    }
    .parameters {
    color: red;
    font-style:italic
    }
  </style>
  Convert latlon to Maidenhead cell ID.
  <h4>Syntax</h4>    
    <li><span class = function>latlon2maidenhead</span>(<span class = parameters>lat, long, resolution [1-->4]</span>)</li>
  <h4>Example usage</h4>

  <ul>
    <li><span class = function>latlon2maidenhead</span>(<span class = parameters>10.775275567242561, 106.70679737574993, 4</span>)&rarr; 'OK30is46'</li>
  </ul>    
  """ 
  return maidenhead.toMaiden(latitude, longitude, resolution)

@qgsfunction(args='auto', group=group_name)
def latlon2gars(latitude, longitude, resolution, feature, parent):
  """<style type="text/css">
    .function {
    color: #05688f;
    font-weight: bold;
    }
    .parameters {
    color: red;
    font-style:italic
    }
  </style>
  Convert latlon to GARS cell ID.
  <h4>Syntax</h4>    
    <li><span class = function>latlon2gars</span>(<span class = parameters>lat, long, resolution [1, 5, 15, 30 (minutes)]</span>)</li>
  <h4>Example usage</h4>

  <ul>
    <li><span class = function>latlon2gars</span>(<span class = parameters>10.775275567242561, 106.70679737574993, 1</span>)&rarr; '574JK1918'</li>
  </ul>    
  """ 
  gars_grid = GARSGrid.from_latlon(latitude, longitude, resolution)
  gars_code = gars_grid.gars_id
  return gars_code
