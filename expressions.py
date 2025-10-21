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

__author__ = "Thang Quach"
__date__ = "2024-11-20"
__copyright__ = "(L) 2024 by Thang Quach"


from qgis.core import  Qgis, qgsfunction, QgsGeometry, QgsCircle, QgsGeos, QgsPointXY
from vgrid.conversion import latlon2dggs
from math import tau, pi, sqrt
FOUR_PI = 4 * pi
try:
  from shapely import maximum_inscribed_circle
except ImportError:
  from shapely.experimental import maximum_inscribed_circle

group_name = "DGGS Vgrid"

def maximum_inscribed_circle(geometry: QgsGeometry) -> QgsGeometry:
    # geos_geo = QgsGeos(geometry.get())
    # epsilon = 0.00000001
    # line_string = geos_geo.maximumInscribedCircle(epsilon)[0]
    line_string = maximum_inscribed_circle(geometry)

    return QgsGeometry(
        QgsCircle.fromCenterPoint(
            line_string.pointN(0), line_string.pointN(-1)
        ).toPolygon()
    )

@qgsfunction(args="auto", group=group_name)
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
    <h4>Arguments</h4>
    <ul>
      <li><span class = parameters>lat</span>: latitude coordinate</li>
      <li><span class = parameters>long</span>: longitude coordinate</li>
      <li><span class = parameters>resolution</span>: H3 resolution [0..15]</li>
    </ul>
    <h4>Example usage</h4>
    <ul>
      <li><span class = function>latlon2h3</span>(<span class = parameters>10.775275567242561, 106.70679737574993, 13</span>)&rarr; '8d65b56628e46bf'</li>
      <li>Point features: <span class = function>latlon2h3</span>(<span class = parameters>$y,$x,13</span>)</li>
    </ul>
    """
    return latlon2dggs.latlon2h3(latitude, longitude, resolution)


@qgsfunction(args="auto", group=group_name)
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
    Convert (lat, long) to S2 Token.
    <h4>Syntax</h4>
      <li><span class = function>latlon2s2</span>(<span class = parameters>lat, long, resolution</span>)</li>   
    <h4>Arguments</h4>
    <ul>
      <li><span class = parameters>lat</span>: latitude coordinate field or value</li>
      <li><span class = parameters>long</span>: longitude coordinate field or value</li>
      <li><span class = parameters>resolution</span>: S2 resolution [0..30]</li>    
    </ul>
    <h4>Example usage</h4>

    <ul>
      <li><span class = function>latlon2s2</span>(<span class = parameters>10.775275567242561, 106.70679737574993, 21</span>)&rarr; '31752f45cc94'</li>
      <li>Point features: <span class = function>latlon2s2</span>(<span class = parameters>$y,$x,21</span>)</li>
    </ul> 
    """
    return latlon2dggs.latlon2s2(latitude, longitude, resolution)


@qgsfunction(args="auto", group=group_name)
def latlon2a5(latitude, longitude, resolution, feature, parent):
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
    Convert (lat, long) to A5 Hex Code.
    <h4>Syntax</h4>
      <li><span class = function>latlon2a5</span>(<span class = parameters>lat, long, resolution</span>)</li>
    <h4>Arguments</h4>
    <ul>
      <li><span class = parameters>lat</span>: latitude coordinate field or value</li>
      <li><span class = parameters>long</span>: longitude coordinate field or value</li>
      <li><span class = parameters>resolution</span>: A5 resolution [0..29]</li>      
    </ul>
    <h4>Example usage</h4>

    <ul>
      <li><span class = function>latlon2a5</span>(<span class = parameters>10.775275567242561, 106.70679737574993, 16</span>)&rarr; '7a9408e938000000'</li>
      <li>Point features: <span class = function>latlon2a5</span>(<span class = parameters>$y,$x,16</span>)</li>
    </ul>
    """
    return latlon2dggs.latlon2a5(latitude, longitude, resolution)


@qgsfunction(args="auto", group=group_name)
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
      <li><span class = function>latlon2rhealpix</span>(<span class = parameters>lat, long, resolution</span>)</li>
    <h4>Arguments</h4>
    <ul>
      <li><span class = parameters>lat</span>: latitude coordinate field or value</li>
      <li><span class = parameters>long</span>: longitude coordinate field or value</li>
      <li><span class = parameters>resolution</span>: rHEALPix resolution [0..15]</li>
    </ul>
    <h4>Example usage</h4>

    <ul>
      <li><span class = function>latlon2rhealpix</span>(<span class = parameters>10.775275567242561, 106.70679737574993, 12</span>)&rarr; 'R312603625535'</li>
      <li>Point features: <span class = function>latlon2rhealpix</span>(<span class = parameters>$y,$x,12</span>)</li>
    </ul>
    """
    return latlon2dggs.latlon2rhealpix(latitude, longitude, resolution)


@qgsfunction(args="auto", group=group_name)
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
      <li><span class = function>latlon2isea4t</span>(<span class = parameters>lat, long, resolution</span>)</li>
    <h4>Arguments</h4>
    <ul>
      <li><span class = parameters>lat</span>: latitude coordinate field or value</li>
      <li><span class = parameters>long</span>: longitude coordinate field or value</li>
      <li><span class = parameters>resolution</span>: ISEA4T resolution [0..39]</li>
    </ul>
    <h4>Example usage</h4>

    <ul>
      <li><span class = function>latlon2isea4t</span>(<span class = parameters>10.775275567242561, 106.70679737574993, 20</span>)&rarr; '1310231333101123322130'</li>
      <li>Point features: <span class = function>latlon2isea4t</span>(<span class = parameters>$y,$x,20</span>)</li>
    </ul>
    """
    return latlon2dggs.latlon2isea4t(latitude, longitude, resolution)


@qgsfunction(args="auto", group=group_name)
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
      <li><span class = function>latlon2isea3h</span>(<span class = parameters>lat, long, resolution</span>)</li>
    <h4>Arguments</h4>
    <ul>
      <li><span class = parameters>lat</span>: latitude coordinate field or value</li>
      <li><span class = parameters>long</span>: longitude coordinate field or value</li>
      <li><span class = parameters>resolution</span>: ISEA3H resolution [0..40]</li>
    </ul>
    <h4>Example usage</h4>

    <ul>
      <li><span class = function>latlon2isea3h</span>(<span class = parameters>10.775275567242561, 106.70679737574993, 20</span>)&rarr; '132022636,-1020'</li>
      <li>Point features: <span class = function>latlon2isea3h</span>(<span class = parameters>$y,$x,20</span>)</li>
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
#     <li><span class = function>latlon2ease</span>(<span class = parameters>lat, long, resolution</span>)</li>
#   <h4>Example usage</h4>

#   <ul>
#     <li><span class = function>latlon2ease</span>(<span class = parameters>10.775275567242561, 106.70679737574993, 5</span>)&rarr; 'L5.165767.02.02.22.45.63'</li>
#   </ul>
#   """
#   return latlon2dggs.latlon2ease(latitude, longitude, resolution)


@qgsfunction(args="auto", group=group_name)
def latlon2dggal(dggs_type, latitude, longitude, resolution, feature, parent):
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
    Convert (lat, long) to DGGAL ID.
    <h4>Syntax</h4>
      <li><span class = function>latlon2dggal</span>(<span class = parameters>dggs_type, lat, long, resolution</span>)</li>
    <h4>Arguments</h4>
    <ul>
      <li><span class = parameters>dggs_type</span>: DGGS type (e.g., 'gnosis','isea3h','isea9r','ivea3h','ivea9r','rtea3h','rtea9r','rhealpix')</li>
      <li><span class = parameters>lat</span>: latitude coordinate field or value</li>
      <li><span class = parameters>long</span>: longitude coordinate field or value</li>
      <li><span class = parameters>resolution</span>: DGGS resolution</li>
    </ul>
    <h4>Example usage</h4>

    <ul>
      <li><span class = function>latlon2dggal</span>(<span class = parameters>'isea9r', 10.775276, 106.706797, 7</span>)&rarr; 'H7-629F2'</li>
      <li>Point features: <span class = function>latlon2dggal</span>(<span class = parameters>'isea9r', $y, $x, 7</span>)</li>
    </ul>
    """
    return latlon2dggs.latlon2dggal(dggs_type, latitude, longitude, resolution)


@qgsfunction(args="auto", group=group_name)
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
      <li><span class = function>latlon2qtm</span>(<span class = parameters>lat, long, resolution</span>)</li>
    <h4>Arguments</h4>
    <ul>
      <li><span class = parameters>lat</span>: latitude coordinate field or value</li>
      <li><span class = parameters>long</span>: longitude coordinate field or value</li>
      <li><span class = parameters>resolution</span>: QTM resolution [1..24]</li>
    </ul>
    <h4>Example usage</h4>

    <ul>
      <li><span class = function>latlon2qtm</span>(<span class = parameters>10.775275567242561, 106.70679737574993, 18</span>)&rarr; '420123231312110130'</li>
      <li>Point features: <span class = function>latlon2qtm</span>(<span class = parameters>$y,$x,18</span>)</li>
    </ul>
    """
    return latlon2dggs.latlon2qtm(latitude, longitude, resolution)


# @qgsfunction(args='auto', group=group_name,usesgeometry=True)
@qgsfunction(args="auto", group=group_name)
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
      <li><span class = function>latlon2olc</span>(<span class = parameters>lat, long, resolution</span>)</li>
    <h4>Arguments</h4>
    <ul>
      <li><span class = parameters>lat</span>: latitude coordinate field or value</li>
      <li><span class = parameters>long</span>: longitude coordinate field or value</li>
      <li><span class = parameters>resolution</span>: OLC resolution [2,4,6,8,10,11..15]</li>
    </ul>
    <h4>Example usage</h4>

    <ul>
      <li><span class = function>latlon2olc</span>(<span class = parameters>10.775275567242561, 106.70679737574993, 11</span>)&rarr; '7P28QPG4+4P7'</li>
      <li>Point features: <span class = function>latlon2olc</span>(<span class = parameters>$y,$x,11</span>)</li>
    </ul>
    """
    return latlon2dggs.latlon2olc(latitude, longitude, resolution)


@qgsfunction(args="auto", group=group_name)
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
      <li><span class = function>latlon2mgrs</span>(<span class = parameters>lat, long, resolution</span>)</li>
    <h4>Arguments</h4>
    <ul>
      <li><span class = parameters>lat</span>: latitude coordinate field or value</li>
      <li><span class = parameters>long</span>: longitude coordinate field or value</li>
      <li><span class = parameters>resolution</span>: MGRS resolution [0..5]</li>
    </ul>
    <h4>Example usage</h4>

    <ul>
      <li><span class = function>latlon2mgrs</span>(<span class = parameters>10.775275567242561, 106.70679737574993, 4</span>)&rarr; '48PXS86629165'</li>
      <li>Point features: <span class = function>latlon2mgrs</span>(<span class = parameters>$y,$x,4</span>)</li>
    </ul>
    """
    return latlon2dggs.latlon2mgrs(latitude, longitude, resolution)


@qgsfunction(args="auto", group=group_name)
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
      <li><span class = function>latlon2geohash</span>(<span class = parameters>lat, long, resolution</span>)</li>
    <h4>Arguments</h4>
    <ul>
      <li><span class = parameters>lat</span>: latitude coordinate field or value</li>
      <li><span class = parameters>long</span>: longitude coordinate field or value</li>
      <li><span class = parameters>resolution</span>: Geohash resolution [1..30]</li>
    </ul>
    <h4>Example usage</h4>

    <ul>
      <li><span class = function>latlon2geohash</span>(<span class = parameters>10.775275567242561, 106.70679737574993, 9</span>)&rarr; 'w3gvk1td8'</li>
      <li>Point features: <span class = function>latlon2geohash</span>(<span class = parameters>$y,$x,9</span>)</li>
    </ul>
    """
    return latlon2dggs.latlon2geohash(latitude, longitude, resolution)


@qgsfunction(args="auto", group=group_name)
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
      <li><span class = function>latlon2georef</span>(<span class = parameters>lat, long, resolution</span>)</li>
    <h4>Arguments</h4>
    <ul>
      <li><span class = parameters>lat</span>: latitude coordinate field or value</li>
      <li><span class = parameters>long</span>: longitude coordinate field or value</li>
      <li><span class = parameters>resolution</span>: GEOREF resolution [0..10]</li>
    </ul>
    <h4>Example usage</h4>

    <ul>
      <li><span class = function>latlon2georef</span>(<span class = parameters>10.775275567242561, 106.70679737574993, 5</span>)&rarr; 'VGBL4240746516'</li>
      <li>Point features: <span class = function>latlon2georef</span>(<span class = parameters>$y,$x,5</span>)</li>
    </ul>
    """
    return latlon2dggs.latlon2georef(latitude, longitude, resolution)


@qgsfunction(args="auto", group=group_name)
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
      <li><span class = function>latlon2tilecode</span>(<span class = parameters>lat, long, resolution</span>)</li>
    <h4>Arguments</h4>
    <ul>
      <li><span class = parameters>lat</span>: latitude coordinate field or value</li>
      <li><span class = parameters>long</span>: longitude coordinate field or value</li>
      <li><span class = parameters>resolution</span>: Tilecode resolution [0..29]</li>
    </ul>
    <h4>Example usage</h4>

    <ul>
      <li><span class = function>latlon2tilecode</span>(<span class = parameters>10.775275567242561, 106.70679737574993, 23</span>)&rarr; 'z23x6680752y3941728'</li>
      <li>Point features: <span class = function>latlon2tilecode</span>(<span class = parameters>$y,$x,23</span>)</li>
    </ul>
    """
    return latlon2dggs.latlon2tilecode(latitude, longitude, resolution)


@qgsfunction(args="auto", group=group_name)
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
      <li><span class = function>latlon2quadkey</span>(<span class = parameters>lat, long, resolution</span>)</li>
    <h4>Arguments</h4>
    <ul>
      <li><span class = parameters>lat</span>: latitude coordinate field or value</li>
      <li><span class = parameters>long</span>: longitude coordinate field or value</li>
      <li><span class = parameters>resolution</span>: Quadkey resolution [0..29]</li>
    </ul>
    <h4>Example usage</h4>

    <ul>
      <li><span class = function>latlon2quadkey</span>(<span class = parameters>10.775275567242561, 106.70679737574993, 23</span>)&rarr; '13223011131020212310000'</li>
      <li>Point features: <span class = function>latlon2quadkey</span>(<span class = parameters>$y,$x,23</span>)</li>
    </ul> 
    """
    return latlon2dggs.latlon2quadkey(latitude, longitude, resolution)


@qgsfunction(args="auto", group=group_name)
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
      <li><span class = function>latlon2maidenhead</span>(<span class = parameters>lat, long, resolution</span>)</li>
    <h4>Arguments</h4>
    <ul>
      <li><span class = parameters>lat</span>: latitude coordinate field or value</li>
      <li><span class = parameters>long</span>: longitude coordinate field or value</li>
      <li><span class = parameters>resolution</span>: Maidenhead resolution [1..4]</li>
    </ul>
    <h4>Example usage</h4>

    <ul>
      <li><span class = function>latlon2maidenhead</span>(<span class = parameters>10.775275567242561, 106.70679737574993, 4</span>)&rarr; 'OK30is46'</li>
      <li>Point features: <span class = function>latlon2maidenhead</span>(<span class = parameters>$y,$x,4</span>)</li>
    </ul>
    """
    return latlon2dggs.latlon2maidenhead(latitude, longitude, resolution)


@qgsfunction(args="auto", group=group_name)
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
      <li><span class = function>latlon2gars</span>(<span class = parameters>lat, long, resolution</span>)</li>
    <h4>Arguments</h4>
    <ul>
      <li><span class = parameters>lat</span>: latitude coordinate field or value</li>
      <li><span class = parameters>long</span>: longitude coordinate field or value</li>
      <li><span class = parameters>resolution</span>: GARS resolution [1..4] (30, 15, 5, 1 minutes)</li>  
    </ul>
    <h4>Example usage</h4>

    <ul>
      <li><span class = function>latlon2gars</span>(<span class = parameters>10.775275567242561, 106.70679737574993, 4</span>)&rarr; '574JK1918'</li>
      <li>Point features: <span class = function>latlon2gars</span>(<span class = parameters>$y,$x,4</span>)</li>
    </ul>
    """
    return latlon2dggs.latlon2gars(latitude, longitude, resolution)


@qgsfunction(args="auto", group=group_name)
def latlon2digipin(latitude, longitude, resolution, feature, parent):
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
     Convert (lat, long) to DIGIPIN ID.
    <h4>Syntax</h4>
      <li><span class = function>latlon2digipin</span>(<span class = parameters>lat, long, resolution</span>)</li>
    <h4>Arguments</h4>
    <ul>
      <li><span class = parameters>lat</span>: latitude coordinate field or value</li>
      <li><span class = parameters>long</span>: longitude coordinate field or value</li>
      <li><span class = parameters>resolution</span>: DIGIPIN resolution [1..10]</li>  
    </ul>
    <h4>Example usage</h4>

    <ul>
      <li><span class = function>latlon2digipin</span>(<span class = parameters>17.414718, 78.482992, 10</span>)&rarr; '422-2PL-9857'</li>
      <li>Point features: <span class = function>latlon2digipin</span>(<span class = parameters>$y,$x,10</span>)</li>
    </ul>
    """
    return latlon2dggs.latlon2digipin(latitude, longitude, resolution)


@qgsfunction(args="auto", group=group_name)
def comp_skew(geometry: QgsGeometry, parent):
        """
        <style type="text/css">
        .function {
        color: #05688f;
        font-weight: bold;
        }
        .parameters {
        color: red;
        font-style:italic
        }
        </style>
        Calculate Skew Compactness

        <p> Skew Compactness is the ratio of the area <b>A<sub>mic<sub></b> of the maximum inscribed circle to the area of the minimum bounding circle <b>A<sub>mbc<sub></b>. </p>

        <p style="text-align: center;">
        <b>comp_skew</b> = <b>A<sub>mic</sub></b> / <b>A<sub>mbc</sub></b>
        </p>
        Where:
        <ul>
            <li> <b>A<sub>mic</sub></b> is the area of the maximum inscribed circle of the geometry. </li>
            <li> <b>A<sub>mbc</sub></b> is the area of the minimum bounding circle of the geometry. </li>
        </ul>

        Scores range from 0 to 1, where 0 is the least compact and 1 is the most compact.

        <h4>Syntax</h4>
        <p><b>comp_skew</b>( <i>geometry</i> )</p>

        <h4>Arguments</h4>
        <p><i>geometry</i>: a polygon geometry</p>

        <h4>Example usage</h4>
        <ul>
        <li><b>comp_skew</b>( $geometry )  &rarr; [0..1]</li>
        </ul>
        """
        if geometry.type() != Qgis.GeometryType.Polygon:
            parent.setEvalErrorString(
                "Only polygon geometry are supported for function `comp_skew`"
            )
            return

        # mic = maximum inscribed circle
        A_mic = maximum_inscribed_circle(geometry).area()
        # mbc = minimal bounding circle
        A_mbc = geometry.minimalEnclosingCircle()[0].area()

        return A_mic / A_mbc

@qgsfunction(args="auto", group=group_name)
def comp_pp(geometry: QgsGeometry, parent):
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
    Calculate Polsby-Popper(PP) Compactness

    <p>
      Polsby-Popper Compactness is the ratio of the area <b>A</b> of the geometry to the area of a circle whose circumference is equal to the perimeter <b>P</b> of the geometry.
    </p>

    <p style="text-align: center;">
    <b>comp_pp</b> = 4 * π * (<b>A</b> / <b>P</b>²)
    </p>
    Where:
    <ul>
      <li> <b>A</b> is the area of the geometry. </li>
      <li> <b>P</b> is the perimeter of the geometry. </li>
    </ul>

    Scores range from 0 to 1, where 0 is the least compact and 1 is the most compact. Only a perfectly round geometry will reach a Polsby–Popper score of 1.

    <h4>Syntax</h4>
    <p><span class = function>comp_pp</span>( <span class = parameters>geometry</span> )</p>

    <h4>Arguments</h4>
    <p><span class = parameters>geometry</span>: a polygon geometry</p>

    <h4>Example usage</h4>
    <ul>
      <li><span class = function>comp_pp</span>( <span class = parameters>$geometry</span> )  &rarr; [0..1]</li>
    </ul>
    """
    if geometry.type() != Qgis.GeometryType.Polygon:
        parent.setEvalErrorString(
            "Only polygon geometry are supported for function `comp_pp`"
        )
        return

    A = geometry.area()
    P = geometry.length()

    return (FOUR_PI * A) / (P * P)

@qgsfunction(args="auto", group=group_name)
def comp_schwartz(geometry: QgsGeometry, parent):
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
    Calculate Schwartzberg Compactness
    <p>
        Schwartzberg Compactness is the ratio of the perimeter <b>P</b> of the geometry to the circumference of a circle whose area is equal to the area of the geometry.
    </p>
    <p style="text-align: center;">
    <b>comp_schwartz</b> = 1 / (<b>P</b> / (2π * √(<b>A</b> / π)))
    </p>
    Where:
    <ul>
      <li> <b>A</b> is the area of the geometry. </li>
      <li> <b>P</b> is the perimeter of the geometry. </li>
    </ul>


    Scores range from 0 to 1, where 0 is the least compact and 1 is the most compact.

    <h4>Syntax</h4>
    <p><span class = function>comp_schwartz</span>( <span class = parameters>geometry</span> )</p>

    <h4>Arguments</h4>
    <p><span class = parameters>geometry</span>: a polygon geometry</p>

    <h4>Example usage</h4>
    <ul>
      <li><span class = function>comp_schwartz</span>( <span class = parameters>$geometry</span> )  &rarr; [0..1]</li>
    </ul>
    """
    if geometry.type() != Qgis.GeometryType.Polygon:
        parent.setEvalErrorString(
            "Only polygon geometry are supported for function `comp_schwartz`"
        )
        return

    A = geometry.area()
    P = geometry.length()

    return 1 / (P / (tau * sqrt(A / pi)))

@qgsfunction(args="auto", group=group_name)
def comp_reock(geometry: QgsGeometry, parent):
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
    Calculate Reock Compactness

    <p> Reock Compactness is the ratio between the area <b>A</b> of the geometry to the area of the minimum bounding circle <b>A<sub>mbc</sub></b></p>

    <p style="text-align: center;">
    <b>comp_reock</b> = <b>A</b> / <b>A<sub>mbc</sub></b>
    </p>
    Where:
    <ul>
      <li> <b>A</b> is the area of the geometry. </li>
      <li> <b>A<sub>mbc</sub></b> is the area of the minimum bounding circle of the geometry. </li>
    </ul>

    Scores range from 0 to 1, where 0 is the least compact and 1 is the most compact.

    <h4>Syntax</h4>
    <p><span class = function>comp_reock</span>( <span class = parameters>geometry</span> )</p>

    <h4>Arguments</h4>
    <p><span class = parameters>geometry</span>: a polygon geometry</p>

    <h4>Example usage</h4>
    <ul>
      <li><span class = function>comp_reock</span>( <span class = parameters>$geometry</span> )  &rarr; [0..1]</li>
    </ul>
    """
    if geometry.type() != Qgis.GeometryType.Polygon:
        parent.setEvalErrorString(
            "Only polygon geometry are supported for function `comp_reock`"
        )
        return

    A = geometry.area()
    A_mbc = geometry.minimalEnclosingCircle()[0].area()

    return A / A_mbc

@qgsfunction(args="auto", group=group_name)
def comp_box_reock(geometry: QgsGeometry, parent):
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
    Calculate Box Reock Compactness

    <p> Box Reock Compactness is the ratio between the area <b>A</b> of the geometry to the area of its minimum bounding rectangle <b>A<sub>mbr</sub></b>.</p>

    <p style="text-align: center;">
    <b>comp_box_reock</b> = <b>A</b> / <b>A<sub>mbr</sub></b>
    </p>
    Where:
    <ul>
      <li> <b>A</b> is the area of the geometry. </li>
      <li> <b>A<sub>mbr</sub></b> is the area of the minimum bounding rectangle of the geometry. </li>
    </ul>

    Scores range from 0 to 1, where 0 is the least compact and 1 is the most compact.

    <h4>Syntax</h4>
    <p><span class = function>comp_box_reock</span>( <span class = parameters>geometry</span> )</p>

    <h4>Arguments</h4>
    <p><span class = parameters>geometry</span>: a polygon geometry</p>

    <h4>Example usage</h4>
    <ul>
      <li><span class = function>comp_box_reock</span>( <span class = parameters>$geometry</span> )  &rarr; [0..1]</li>
    </ul>
    """
    if geometry.type() != Qgis.GeometryType.Polygon:
        parent.setEvalErrorString(
            "Only polygon geometry are supported for function `comp_box_reock`"
        )
        return

    A = geometry.area()
    A_mbr = geometry.boundingBox().area()

    return A / A_mbr


@qgsfunction(args="auto", group=group_name)
def comp_lw(geometry: QgsGeometry, parent):
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
    Calculate Length-Width Compactness

    <p>Length-Width Compactness is the ratio between the width <b>W<sub>mbr</sub></b> to the length <b>L<sub>mbr</sub></b> of the minimum bounding rectangle of the geometry</p>

    <p style="text-align: center;">
    <b>comp_lw</b> = <b>W<sub>mbr</sub></b> / <b>L<sub>mbr</sub></b>
    </p>
    Where:
    <ul>
      <li> <b>W<sub>mbr</sub></b> is the width of the minimum bounding rectangle of the geometry. </li>
      <li> <b>L<sub>mbr</sub></b> is the length of the minimum bounding rectangle of the geometry. </li>
    </ul>

    Scores range from 0 to 1, where 0 is the least compact and 1 is the most compact.

    <h4>Syntax</h4>
    <p><span class = function>comp_lw</span>( <span class = parameters>geometry</span> )</p>

    <h4>Arguments</h4>
    <p><span class = parameters>geometry</span>: a polygon geometry</p>

    <h4>Example usage</h4>
    <ul>
      <li><span class = function>comp_lw</span>( <span class = parameters>$geometry</span> )  &rarr; [0..1]</li>
    </ul>
    """
    if geometry.type() != Qgis.GeometryType.Polygon:
        parent.setEvalErrorString(
            "Only polygon geometry are supported for function `comp_lw`"
        )
        return

    bbox = geometry.boundingBox()

    # We define width as the shortest side
    width = min(bbox.height(), bbox.width())
    length = max(bbox.height(), bbox.width())

    return width / length


@qgsfunction(args="auto", group=group_name)
def comp_cvh(geometry: QgsGeometry, parent):
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
    Calculate Convex Hull Compactness

    <p>Convex Hull Compactness is the ratio between the area <b>A</b> of the geometry to the area of its convex hull <b>A<sub>cvh</sub></b></p>

    <p style="text-align: center;">
    <b>comp_cvh</b> = <b>A</b> / <b>A<sub>cvh</sub></b>
    </p>
    Where:
    <ul>
      <li> <b>A</b> is the area of the geometry. </li>
      <li> <b>A<sub>cvh</sub></b> is the area of the convex hull of the geometry. </li>
    </ul>

    Scores range from 0 to 1, where 0 is the least compact and 1 is the most compact. Only a convex geometry will reach a Convex Hull Compactness score of 1. 

    <h4>Syntax</h4>
    <p><span class = function>comp_cvh</span>( <span class = parameters>geometry</span> )</p>

    <h4>Arguments</h4>
    <p><span class = parameters>geometry</span>: a polygon geometry</p>

    <h4>Example usage</h4>
    <ul>
      <li><span class = function>comp_cvh</span>( <span class = parameters>$geometry</span> )  &rarr; [0..1]</li>
    </ul>
    """
    if geometry.type() != Qgis.GeometryType.Polygon:
        parent.setEvalErrorString(
            "Only polygon geometry are supported for function `comp_cvh`"
        )
        return

    A = geometry.area()
    A_cvh = geometry.convexHull().area()

    if A_cvh == 0:
        return None

    return A / A_cvh


@qgsfunction(args="auto", group=group_name)
def comp_x_sym(geometry: QgsGeometry, parent):
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

    Calculate X-Symmetry compactness

    <p> X-Symmetry compactness is calculated by dividing the intersection area <b>A(I(G, G<sup>X</sup>))</b> of the geometry with its reflection across the horizontal axis (x-axis) by the area of the original geometry <b>A</b>. </p>
    <p style="text-align: center;">
    <b>comp_x_sym</b> = <b>A(I(G, G<sup>X</sup>))/A</b>
    </p>
    Where:
    <ul>
      <li> <b>A(I(G, G<sup>X</sup>))</b> is the intersection area of the original geometry with its reflection across the horizontal axis (x-axis). </li>
      <li> <b>A</b> is the area of the original geometry. </li>
    </ul>

    Scores range from 0 to 1, where 0 is the least compact and 1 is the most compact. 

    <h4>Syntax</h4>
          <li><span class = function>comp_x_sym</span>(<span class = parameters>geometry</span>)</li>   

    <h4>Arguments</h4>
    <p><span class = parameters>geometry</span>: a polygon geometry</p>

    <h4>Example usage</h4>
    <ul>
      <li><span class = function>comp_x_sym</span>( <span class = parameters>$geometry</span> )  &rarr; [0..1]</li>
    </ul>
    """
    if geometry.type() != Qgis.GeometryType.Polygon:
        parent.setEvalErrorString(
            "Only polygon geometry are supported for function `comp_x_sym`"
        )
        return

    A = geometry.area()
    if A == 0:
        return None

    centroid_geom = geometry.centroid()
    centroid_point = centroid_geom.asPoint()

    # Reflect across the horizontal axis (x-axis) passing through the centroid
    reflected = _reflect_geometry_horizontally(geometry, centroid_point.y())

    A_X = geometry.intersection(reflected).area()

    return A_X / A


def _reflect_geometry_horizontally(geometry: QgsGeometry, centroid_y: float) -> QgsGeometry:
    """Return a geometry reflected across the horizontal axis (y mirrored) about centroid_y.
    Works for single and multi polygon geometries using XY coordinates.
    """
    if geometry.isMultipart():
        multi = geometry.asMultiPolygon()
        reflected_multi = []
        for poly in multi:
            reflected_poly = []
            for ring in poly:
                reflected_ring = [QgsPointXY(pt.x(), 2 * centroid_y - pt.y()) for pt in ring]
                reflected_poly.append(reflected_ring)
            reflected_multi.append(reflected_poly)
        return QgsGeometry.fromMultiPolygonXY(reflected_multi)
    else:
        poly = geometry.asPolygon()
        reflected_poly = []
        for ring in poly:
            reflected_ring = [QgsPointXY(pt.x(), 2 * centroid_y - pt.y()) for pt in ring]
            reflected_poly.append(reflected_ring)
        return QgsGeometry.fromPolygonXY(reflected_poly)

