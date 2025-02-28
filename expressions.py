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
from .vgridlibrary.conversion import olc,mgrs,geohash,georef,s2, tilecode,maidenhead,gars

group_name = 'Vgrid'

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
  Convert latlon to MGRS code.
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
  Convert latlon to GEOREF code.
  <h4>Syntax</h4>    
    <li><span class = function>latlon2georef</span>(<span class = parameters>lat, long, resolution [0-->10]</span>)</li>
  <h4>Example usage</h4>

  <ul>
    <li><span class = function>latlon2georef</span>(<span class = parameters>10.775275567242561, 106.70679737574993, 5</span>)&rarr; 'VGBL4240746516'</li>
  </ul>    
  """ 
  return georef.encode(latitude, longitude, resolution) 

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
  Convert latlon to S2 code.
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

# def latlon2h3(latitude, longitude, resolution, feature, parent):
#   """<style type="text/css">
#     .function {
#     color: #05688f;
#     font-weight: bold;
#     }
#     .parameters {
#     color: red;
#     font-style:italic
#     }
#   </style>
#   Convert latlon to H3 code.
#   <h4>Syntax</h4>    
#     <li><span class = function>latlon2h3</span>(<span class = parameters>lat, long, resolution [0-15]</span>)</li>
#   <h4>Example usage</h4>

#   <ul>
#     <li><span class = function>latlon2h3</span>(<span class = parameters>10.775275567242561, 106.70679737574993, 13</span>)&rarr; ''</li>
#   </ul>    
#   """ 
#   return h3.latlng_to_cell(latitude, longitude, resolution)

@qgsfunction(args='auto', group=group_name)
def latlon2vcode(latitude, longitude, zoom, feature, parent):
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
    <li><span class = function>latlon2vcode</span>(<span class = parameters>lat, long, resolution/ zoom level [0;25]</span>)</li>
  <h4>Example usage</h4>

  <ul>
    <li><span class = function>latlon2vcode</span>(<span class = parameters>10.775275567242561, 106.70679737574993, 23</span>)&rarr; 'z23x6680752y3941728'</li>
  </ul>    
  """ 
  return tilecode.latlon2vcode(latitude, longitude, zoom) 

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
  Convert latlon to Maidenhead code.
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
  Convert latlon to GARS code.
  <h4>Syntax</h4>    
    <li><span class = function>latlon2gars</span>(<span class = parameters>lat, long, resolution [1, 5, 15, 30 (minutes)]</span>)</li>
  <h4>Example usage</h4>

  <ul>
    <li><span class = function>latlon2gars</span>(<span class = parameters>10.775275567242561, 106.70679737574993, 1</span>)&rarr; '574JK1918'</li>
  </ul>    
  """ 
  gars_grid = gars.GARSGrid.from_latlon(latitude, longitude, resolution)
  gars_code = gars_grid.gars_id
  return gars_code
