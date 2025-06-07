# -*- coding: utf-8 -*-

"""
/***************************************************************************
                              Vgrid Expression
                              -------------------
        Date                 : 2024-11-20
        copyright            : (L) 2024 by Thang Quach
        email                : quachdongthang@gmail.com
 ***************************************************************************/

 """

__author__ = 'Thang Quach'
__date__ = '2024-11-20'
__copyright__ = '(L) 2024 by Thang Quach'


from qgis.core import *
from qgis.gui import *
from qgis.utils import qgsfunction
from vgrid.conversion import latlon2dggs

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
  Convert (lat, long) to H3 ID.
  <h4>Syntax</h4>    
    <li><span class = function>latlon2h3</span>(<span class = parameters>lat, long, resolution [0..15]</span>)</li>
  <h4>Example usage</h4>

  <ul>
    <li><span class = function>latlon2h3</span>(<span class = parameters>10.775275567242561, 106.70679737574993, 13</span>)&rarr; '8d65b56628e46bf'</li>
  </ul>    
  """ 
  return latlon2dggs.latlon2h3(latitude, longitude, resolution)

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
  Convert (lat, long) to S2 ID.
  <h4>Syntax</h4>    
    <li><span class = function>latlon2s2</span>(<span class = parameters>lat, long, resolution [0-..30]</span>)</li>
  <h4>Example usage</h4>

  <ul>
    <li><span class = function>latlon2s2</span>(<span class = parameters>10.775275567242561, 106.70679737574993, 21</span>)&rarr; '31752f45cc94'</li>
  </ul>    
  """ 
  return latlon2dggs.latlon2s2(latitude, longitude, resolution)


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
  Convert (lat, long) to rHEALPix ID.
  <h4>Syntax</h4>    
    <li><span class = function>latlon2rhealpix</span>(<span class = parameters>lat, long, resolution [0..15]</span>)</li>
  <h4>Example usage</h4>

  <ul>
    <li><span class = function>latlon2rhealpix</span>(<span class = parameters>10.775275567242561, 106.70679737574993, 12</span>)&rarr; 'R312603625535'</li>
  </ul>    
  """ 
  return latlon2dggs.latlon2rhealpix(latitude, longitude, resolution)


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
  Convert (lat, long) to OpenEAGGR ISEA4T ID.
  <h4>Syntax</h4>    
    <li><span class = function>latlon2isea4t</span>(<span class = parameters>lat, long, resolution [0..39]</span>)</li>
  <h4>Example usage</h4>

  <ul>
    <li><span class = function>latlon2isea4t</span>(<span class = parameters>10.775275567242561, 106.70679737574993, 20</span>)&rarr; '1310231333101123322130'</li>
  </ul>    
  """ 
  return latlon2dggs.latlon2isea4t(latitude, longitude, resolution)

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
  Convert (lat, long) to OpenEAGGR ISEA3H ID.
  <h4>Syntax</h4>    
    <li><span class = function>latlon2isea3h</span>(<span class = parameters>lat, long, resolution [0..40]</span>)</li>
  <h4>Example usage</h4>

  <ul>
    <li><span class = function>latlon2isea3h</span>(<span class = parameters>10.775275567242561, 106.70679737574993, 20</span>)&rarr; '132022636,-1020'</li>
  </ul>    
  """ 
  return latlon2dggs.latlon2isea3h(latitude, longitude, resolution)


# @qgsfunction(args='auto', group=group_name)
# def latlon2ease(latitude, longitude, resolution, feature, parent):
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
#   Convert (lat, long) to EASE-DGGS.
#   <h4>Syntax</h4>    
#     <li><span class = function>latlon2ease</span>(<span class = parameters>lat, long, resolution [0..6]</span>)</li>
#   <h4>Example usage</h4>

#   <ul>
#     <li><span class = function>latlon2ease</span>(<span class = parameters>10.775275567242561, 106.70679737574993, 5</span>)&rarr; 'L5.165767.02.02.22.45.63'</li>
#   </ul>    
#   """ 
#   return latlon2dggs.latlon2ease(latitude, longitude, resolution)
  
  
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
  Convert (lat, long) to QTM ID.
  <h4>Syntax</h4>    
    <li><span class = function>latlon2qtm</span>(<span class = parameters>lat, long, resolution [1..24]</span>)</li>
  <h4>Example usage</h4>

  <ul>
    <li><span class = function>latlon2qtm</span>(<span class = parameters>10.775275567242561, 106.70679737574993, 18</span>)&rarr; '420123231312110130'</li>
  </ul>    
  """
  return latlon2dggs.latlon2qtm(latitude, longitude, resolution)

# @qgsfunction(args='auto', group=group_name,usesgeometry=True)
@qgsfunction(args='auto', group=group_name)
def latlon2olc(latitude, longitude, resolution, feature, parent):
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
  Convert (lat, long) to Open Location Code (OLC)/ Google Plus Code
  <h4>Syntax</h4>    
    <li><span class = function>latlon2olc</span>(<span class = parameters>lat, long, resolution [2,4,6,8,10,11..15]</span>)</li>
  <h4>Example usage</h4>

  <ul>
    <li><span class = function>latlon2olc</span>(<span class = parameters>10.775275567242561, 106.70679737574993, 11</span>)&rarr; '7P28QPG4+4P7'</li>
  </ul>    
  """ 
  return latlon2dggs.latlon2olc(latitude, longitude, resolution) 

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
  Convert (lat, long) to MGRS ID.
  <h4>Syntax</h4>    
    <li><span class = function>latlon2mgrs</span>(<span class = parameters>lat, long, resolution [0..5]</span>)</li>
  <h4>Example usage</h4>

  <ul>
    <li><span class = function>latlon2mgrs</span>(<span class = parameters>10.775275567242561, 106.70679737574993, 4</span>)&rarr; '48PXS86629165'</li>
  </ul>    
  """ 
  return latlon2dggs.latlon2mgrs(latitude, longitude, resolution)  

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
  Convert (lat, long) to Geohash ID.
  <h4>Syntax</h4>    
    <li><span class = function>latlon2geohash</span>(<span class = parameters>lat, long, resolution [1..30]</span>)</li>
  <h4>Example usage</h4>

  <ul>
    <li><span class = function>latlon2geohash</span>(<span class = parameters>10.775275567242561, 106.70679737574993, 9</span>)&rarr; 'w3gvk1td8'</li>
  </ul>    
  """ 
  return latlon2dggs.latlon2geohash(latitude, longitude, resolution) 

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
  Convert (lat, long) to GEOREF ID.
  <h4>Syntax</h4>    
    <li><span class = function>latlon2georef</span>(<span class = parameters>lat, long, resolution [0..10]</span>)</li>
  <h4>Example usage</h4>

  <ul>
    <li><span class = function>latlon2georef</span>(<span class = parameters>10.775275567242561, 106.70679737574993, 5</span>)&rarr; 'VGBL4240746516'</li>
  </ul>    
  """ 
  return latlon2dggs.latlon2georef(latitude, longitude, resolution)  

@qgsfunction(args='auto', group=group_name)
def latlon2tilecode(latitude, longitude, resolution, feature, parent):
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
  Convert (lat, long) to Tilecode ID.
  <h4>Syntax</h4>    
    <li><span class = function>latlon2tilecode</span>(<span class = parameters>lat, long, resolution [0..29]</span>)</li>
  <h4>Example usage</h4>

  <ul>
    <li><span class = function>latlon2tilecode</span>(<span class = parameters>10.775275567242561, 106.70679737574993, 23</span>)&rarr; 'z23x6680752y3941728'</li>
  </ul>    
  """ 
  return latlon2dggs.latlon2tilecode(latitude, longitude, resolution) 


@qgsfunction(args='auto', group=group_name)
def latlon2quadkey(latitude, longitude, resolution, feature, parent):
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
  Convert (lat, long) to Quadkey ID.
  <h4>Syntax</h4>    
    <li><span class = function>latlon2quadkey</span>(<span class = parameters>lat, long, resolution [0..29]</span>)</li>
  <h4>Example usage</h4>

  <ul>
    <li><span class = function>latlon2quadkey</span>(<span class = parameters>10.775275567242561, 106.70679737574993, 23</span>)&rarr; '13223011131020212310000'</li>
  </ul>    
  """ 
  return latlon2dggs.latlon2quadkey(latitude, longitude, resolution) 

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
  Convert (lat, long) to Maidenhead ID.
  <h4>Syntax</h4>    
    <li><span class = function>latlon2maidenhead</span>(<span class = parameters>lat, long, resolution [1..4]</span>)</li>
  <h4>Example usage</h4>

  <ul>
    <li><span class = function>latlon2maidenhead</span>(<span class = parameters>10.775275567242561, 106.70679737574993, 4</span>)&rarr; 'OK30is46'</li>
  </ul>    
  """ 
  return latlon2dggs.latlon2maidenhead(latitude, longitude, resolution) 

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
   Convert (lat, long) to GARS ID.
  <h4>Syntax</h4>    
    <li><span class = function>latlon2gars</span>(<span class = parameters>lat, long, resolution [1..4] (30, 15, 5, 1 minutes)</span>)</li>
  <h4>Example usage</h4>

  <ul>
    <li><span class = function>latlon2gars</span>(<span class = parameters>10.775275567242561, 106.70679737574993, 4</span>)&rarr; '574JK1918'</li>
  </ul>      
  """ 
  return latlon2dggs.latlon2gars(latitude, longitude, resolution) 

