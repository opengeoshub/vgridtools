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

group_name = "DGGS Vgrid"

def maximum_inscribed_circle(geometry: QgsGeometry) -> QgsGeometry:
    geos_geo = QgsGeos(geometry.get())
    epsilon = 0.00000001
    line_string = geos_geo.maximumInscribedCircle(epsilon)[0]

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
    <h4>Example usage</h4>

    <ul>
      <li><span class = function>latlon2h3</span>(<span class = parameters>10.775275567242561, 106.70679737574993, 13</span>)&rarr; '8d65b56628e46bf'</li>
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
      <li><span class = function>latlon2s2</span>(<span class = parameters>lat, long, resolution [0-..30]</span>)</li>
    <h4>Example usage</h4>

    <ul>
      <li><span class = function>latlon2s2</span>(<span class = parameters>10.775275567242561, 106.70679737574993, 21</span>)&rarr; '31752f45cc94'</li>
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
      <li><span class = function>latlon2a5</span>(<span class = parameters>lat, long, resolution [0..29]</span>)</li>
    <h4>Example usage</h4>

    <ul>
      <li><span class = function>latlon2a5</span>(<span class = parameters>10.775275567242561, 106.70679737574993, 16</span>)&rarr; '7a9408e938000000'</li>
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
      <li><span class = function>latlon2rhealpix</span>(<span class = parameters>lat, long, resolution [0..15]</span>)</li>
    <h4>Example usage</h4>

    <ul>
      <li><span class = function>latlon2rhealpix</span>(<span class = parameters>10.775275567242561, 106.70679737574993, 12</span>)&rarr; 'R312603625535'</li>
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
      <li><span class = function>latlon2isea4t</span>(<span class = parameters>lat, long, resolution [0..39]</span>)</li>
    <h4>Example usage</h4>

    <ul>
      <li><span class = function>latlon2isea4t</span>(<span class = parameters>10.775275567242561, 106.70679737574993, 20</span>)&rarr; '1310231333101123322130'</li>
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
    <h4>Example usage</h4>

    <ul>
      <li><span class = function>latlon2dggal</span>(<span class = parameters>'isea9r', 10.775276, 106.706797, 7</span>)&rarr; 'H7-629F2'</li>
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
      <li><span class = function>latlon2qtm</span>(<span class = parameters>lat, long, resolution [1..24]</span>)</li>
    <h4>Example usage</h4>

    <ul>
      <li><span class = function>latlon2qtm</span>(<span class = parameters>10.775275567242561, 106.70679737574993, 18</span>)&rarr; '420123231312110130'</li>
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
      <li><span class = function>latlon2olc</span>(<span class = parameters>lat, long, resolution [2,4,6,8,10,11..15]</span>)</li>
    <h4>Example usage</h4>

    <ul>
      <li><span class = function>latlon2olc</span>(<span class = parameters>10.775275567242561, 106.70679737574993, 11</span>)&rarr; '7P28QPG4+4P7'</li>
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
      <li><span class = function>latlon2mgrs</span>(<span class = parameters>lat, long, resolution [0..5]</span>)</li>
    <h4>Example usage</h4>

    <ul>
      <li><span class = function>latlon2mgrs</span>(<span class = parameters>10.775275567242561, 106.70679737574993, 4</span>)&rarr; '48PXS86629165'</li>
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
      <li><span class = function>latlon2geohash</span>(<span class = parameters>lat, long, resolution [1..30]</span>)</li>
    <h4>Example usage</h4>

    <ul>
      <li><span class = function>latlon2geohash</span>(<span class = parameters>10.775275567242561, 106.70679737574993, 9</span>)&rarr; 'w3gvk1td8'</li>
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
      <li><span class = function>latlon2georef</span>(<span class = parameters>lat, long, resolution [0..10]</span>)</li>
    <h4>Example usage</h4>

    <ul>
      <li><span class = function>latlon2georef</span>(<span class = parameters>10.775275567242561, 106.70679737574993, 5</span>)&rarr; 'VGBL4240746516'</li>
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
      <li><span class = function>latlon2tilecode</span>(<span class = parameters>lat, long, resolution [0..29]</span>)</li>
    <h4>Example usage</h4>

    <ul>
      <li><span class = function>latlon2tilecode</span>(<span class = parameters>10.775275567242561, 106.70679737574993, 23</span>)&rarr; 'z23x6680752y3941728'</li>
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
      <li><span class = function>latlon2quadkey</span>(<span class = parameters>lat, long, resolution [0..29]</span>)</li>
    <h4>Example usage</h4>

    <ul>
      <li><span class = function>latlon2quadkey</span>(<span class = parameters>10.775275567242561, 106.70679737574993, 23</span>)&rarr; '13223011131020212310000'</li>
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
      <li><span class = function>latlon2maidenhead</span>(<span class = parameters>lat, long, resolution [1..4]</span>)</li>
    <h4>Example usage</h4>

    <ul>
      <li><span class = function>latlon2maidenhead</span>(<span class = parameters>10.775275567242561, 106.70679737574993, 4</span>)&rarr; 'OK30is46'</li>
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
      <li><span class = function>latlon2gars</span>(<span class = parameters>lat, long, resolution [1..4] (30, 15, 5, 1 minutes)</span>)</li>
    <h4>Example usage</h4>

    <ul>
      <li><span class = function>latlon2gars</span>(<span class = parameters>10.775275567242561, 106.70679737574993, 4</span>)&rarr; '574JK1918'</li>
    </ul>
    """
    return latlon2dggs.latlon2gars(latitude, longitude, resolution)


@qgsfunction(args="auto", group=group_name)
def compactness_skew(geometry: QgsGeometry, parent):
        """
        Calculate a skew compactness

        <p> A skew compactness compares the area of the maximum inscribed circle (A_mic) to the area of the minimum bounding circle (A_mbc). </p>

        <p>Can be written as:</p>
        <p>
        Skew = A_mic / A_mbc
        </p>

        <ul>
            <li> Where <b>A_mic</b> is the area of the maximum inscribed circle of the geometry </li>
            <li> Where <b>A_mbc</b> is the area of the minimum bounding circle of the geometry </li>
        </ul>

        Scores range from 0 to 1, where 0 is the least compact and 1 is the most compact.

        <h4>Syntax</h4>
        <p><b>compactness_skew</b>( <i>geometry</i> )</p>

        <h4>Arguments</h4>
        <p><i>geometry</i>: a polygon geometry</p>

        <h4>Example usage</h4>
        <ul>
        <li><b>compactness_skew</b>( $geometry )  &rarr; [0;1]</li>
        <li><b>compactness_skew</b>( geom_from_wkt('POLYGON((0 0, 4 0, 4 2, 0 2, 0 0))') ) &rarr; 0,2</li>
        </ul>
        """
        if geometry.type() != Qgis.GeometryType.Polygon:
            parent.setEvalErrorString(
                "Only polygon geometry are supported for function `compactness_skew`"
            )
            return

        # mic = maximum inscribed circle
        A_mic = maximum_inscribed_circle(geometry).area()
        # mbc = minimal bounding circle
        A_mbc = geometry.minimalEnclosingCircle()[0].area()

        return A_mic / A_mbc

@qgsfunction(args="auto", group=group_name)
def compactness_pp(geometry: QgsGeometry, parent):
    """
    Calculate a  <a href="https://en.wikipedia.org/wiki/Polsby%E2%80%93Popper_test">Polsby-Popper(PP) compactness</a> score

    <p>
    The Polsby-Popper (polsby & Popper, 1991) is the ratio of the area(A) of the geometry to the area of a circle whose circumference is equal to the perimeter(P) of the geometry .
    </p>

    <p>Can be written as:</p>
    <p>
    4 * pi * (A / P*P )
    </p>

    <ul>
      <li> Where <b>A</b> is the area of the geometry </li>
      <li> Where <b>P</b> is the perimeter of the geometry </li>
    </ul>

    a score of 0 indicating complete lack of compactness and a score of 1 indicating maximal compactness. Only a perfectly round geometry will reach a Polsby–Popper score of 1.

    <h4>Syntax</h4>
    <p><b>compactness_pp</b>( <i>geometry</i> )</p>

    <h4>Arguments</h4>
    <p><i>geometry</i>: a polygon geometry</p>

    <h4>Example usage</h4>
    <ul>
      <li><b>compactness_pp</b>( $geometry )  &rarr; [0;1]</li>
      <li><b>compactness_pp</b>( geom_from_wkt('POLYGON((0 0, 4 0, 4 2, 0 2, 0 0))') ) &rarr; 0,698131&hellip;</li>
    </ul>
    """
    if geometry.type() != Qgis.GeometryType.Polygon:
        parent.setEvalErrorString(
            "Only polygon geometry are supported for function `compactness_pp`"
        )
        return

    A = geometry.area()
    P = geometry.length()

    return (FOUR_PI * A) / (P * P)

@qgsfunction(args="auto", group=group_name)
def compactness_schwartz(geometry: QgsGeometry, parent):
    """
    Calculate a schwartzberg compactness

    <p>Can be written as:</p>
    <p>
    S = 1 / (P / (2pi * sqrt(A / pi)))
    </p>
    <ul>
      <li> Where <b>A</b> is the area of the geometry </li>
      <li> Where <b>P</b> is the perimeter of the geometry </li>
    </ul>


    Scores range from 0 to 1, where 0 is the least compact and 1 is the most compact.

    <h4>Syntax</h4>
    <p><b>compactness_schwartz</b>( <i>geometry</i> )</p>

    <h4>Arguments</h4>
    <p><i>geometry</i>: a polygon geometry</p>

    <h4>Example usage</h4>
    <ul>
      <li><b>compactness_schwartz</b>( $geometry )  &rarr; [0;1]</li>
      <li><b>compactness_schwartz</b>( geom_from_wkt('POLYGON((0 0, 4 0, 4 2, 0 2, 0 0))') ) &rarr; 0,8355&hellip;</li>
    </ul>
    """
    if geometry.type() != Qgis.GeometryType.Polygon:
        parent.setEvalErrorString(
            "Only polygon geometry are supported for function `compactness_schwartz`"
        )
        return

    A = geometry.area()
    P = geometry.length()

    return 1 / (P / (tau * sqrt(A / pi)))

@qgsfunction(args="auto", group=group_name)
def compactness_reock(geometry: QgsGeometry, parent):
    """
    Calculate a reock compactness

    <p> A reock compactness is the ratio between the area (A) of the geometry to the area of the minimum bounding circle (A_mbc)</p>

    <p>Can be written as:</p>
    <p>
    reock = A / A_mbc
    </p>
    <ul>
      <li> Where <b>A</b> is the area of the geometry </li>
      <li> Where <b>A_mbc</b> is the area of the minimum bounding circle of the geometry </li>
    </ul>

    Scores range from 0 to 1, where 0 is the least compact and 1 is the most compact.

    <h4>Syntax</h4>
    <p><b>compactness_reock</b>( <i>geometry</i> )</p>

    <h4>Arguments</h4>
    <p><i>geometry</i>: a polygon geometry</p>

    <h4>Example usage</h4>
    <ul>
      <li><b>compactness_reock</b>( $geometry )  &rarr; [0;1]</li>
      <li><b>compactness_reock</b>( geom_from_wkt('POLYGON((0 0, 4 0, 4 2, 0 2, 0 0))') ) &rarr; 0,51189&hellip;</li>
    </ul>
    """
    if geometry.type() != Qgis.GeometryType.Polygon:
        parent.setEvalErrorString(
            "Only polygon geometry are supported for function `compactness_reock`"
        )
        return

    A = geometry.area()
    A_mbc = geometry.minimalEnclosingCircle()[0].area()

    return A / A_mbc

@qgsfunction(args="auto", group=group_name)
def compactness_box_reock(geometry: QgsGeometry, parent):
    """
    Calculate a box reock compactness

    <p> A box reock compactness is the ratio between the area (A) of the geometry to the area of the minimum bounding box (A_bbox)</p>

    <p>Can be written as:</p>
    <p>
    box_reock = A / A_bbox
    </p>
    <ul>
      <li> Where <b>A</b> is the area of the geometry </li>
      <li> Where <b>A_bbox</b> is the area of the minimum bounding rectangle of the geometry </li>
    </ul>

    Scores range from 0 to 1, where 0 is the least compact and 1 is the most compact.

    <h4>Syntax</h4>
    <p><b>compactness_box_reock</b>( <i>geometry</i> )</p>

    <h4>Arguments</h4>
    <p><i>geometry</i>: a polygon geometry</p>

    <h4>Example usage</h4>
    <ul>
      <li><b>compactness_box_reock</b>( $geometry )  &rarr; [0;1]</li>
      <li><b>compactness_box_reock</b>( geom_from_wkt('POLYGON((0 0, 4 0, 4 2, 0 2, 0 0))') ) &rarr; 1</li>
      <li><b>compactness_box_reock</b>( geom_from_wkt('POLYGON((0 0, 4 0, 4 2, 0 0))') ) &rarr; 0.5</li>
    </ul>
    """
    if geometry.type() != Qgis.GeometryType.Polygon:
        parent.setEvalErrorString(
            "Only polygon geometry are supported for function `compactness_box_reock`"
        )
        return

    A = geometry.area()
    A_bbox = geometry.boundingBox().area()

    return A / A_bbox


@qgsfunction(args="auto", group=group_name)
def compactness_lw(geometry: QgsGeometry, parent):
    """
    Calculate a Length-Width Compactness

    <p> Length-Width compactness compares the width and the length of a geometry using its bouding box</p> 
    <p>Can be written as:</p>
    <p>
    lw =  W_bbox / L_bbox
    </p>
    <ul>
      <li> Where <b>W_bbox</b> is the shorter side of the bounding box of the geometry </li>
      <li> Where <b>L_bbox</b> the longer side of the bounding box of the geometry </li>
    </ul>

    Scores range from 0 to 1, where 0 is the least compact and 1 is the most compact.

    <h4>Syntax</h4>
    <p><b>compactness_lw</b>( <i>geometry</i> )</p>

    <h4>Arguments</h4>
    <p><i>geometry</i>: a polygon geometry</p>

    <h4>Example usage</h4>
    <ul>
      <li><b>compactness_lw</b>( $geometry )  &rarr; [0;1]</li>
      <li><b>compactness_lw</b>( geom_from_wkt('POLYGON((0 0, 4 0, 4 2, 0 2, 0 0))') ) &rarr; 0.5</li>
    </ul>
    """
    if geometry.type() != Qgis.GeometryType.Polygon:
        parent.setEvalErrorString(
            "Only polygon geometry are supported for function `compactness_lw`"
        )
        return

    bbox = geometry.boundingBox()

    # We define width as the shortest side
    width = min(bbox.height(), bbox.width())
    length = max(bbox.height(), bbox.width())

    return width / length


@qgsfunction(args="auto", group=group_name)
def compactness_cvh(geometry: QgsGeometry, parent):
    """
    Calculate a convex hull compactness

    <p> A convex hull compactness is the ratio between the area (A) of the geometry to the area of its convex hull (A_cvh)</p>

    <p>Can be written as:</p>
    <p>
    cvh = A / A_cvh
    </p>
    <ul>
      <li> Where <b>A</b> is the area of the geometry </li>
      <li> Where <b>A_cvh</b> is the area of the convex hull of the geometry </li>
    </ul>

    Scores range from 0 to 1, where 0 is the least compact and 1 is the most compact.

    <h4>Syntax</h4>
    <p><b>compactness_cvh</b>( <i>geometry</i> )</p>

    <h4>Arguments</h4>
    <p><i>geometry</i>: a polygon geometry</p>

    <h4>Example usage</h4>
    <ul>
      <li><b>compactness_cvh</b>( $geometry )  &rarr; [0;1]</li>
    </ul>
    """
    if geometry.type() != Qgis.GeometryType.Polygon:
        parent.setEvalErrorString(
            "Only polygon geometry are supported for function `compactness_cvh`"
        )
        return

    A = geometry.area()
    A_cvh = geometry.convexHull().area()

    if A_cvh == 0:
        return None

    return A / A_cvh


@qgsfunction(args="auto", group=group_name)
def compactness_x_sym(geometry: QgsGeometry, parent):
    """
    Calculate an X-Symmetry compactness score

    <p> X-Symmetry is the ratio between the overlapping area <b>A_O</b> of the geometry and its reflection across the horizontal axis and the original area <b>A_D</b>.</p>

    <p>Can be written as:</p>
    <p>
    x_sym = A_O / A_D
    </p>
    <ul>
      <li> Where <b>A_O</b> is the intersection area of the geometry with its reflection across the horizontal axis passing through its centroid </li>
      <li> Where <b>A_D</b> is the area of the original geometry </li>
    </ul>

    Scores range from 0 to 1, where 0 is the least compact and 1 is the most compact.

    <h4>Syntax</h4>
    <p><b>compactness_x_sym</b>( <i>geometry</i> )</p>

    <h4>Arguments</h4>
    <p><i>geometry</i>: a polygon geometry</p>

    <h4>Example usage</h4>
    <ul>
      <li><b>compactness_x_sym</b>( $geometry )  &rarr; [0;1]</li>
    </ul>
    """
    if geometry.type() != Qgis.GeometryType.Polygon:
        parent.setEvalErrorString(
            "Only polygon geometry are supported for function `compactness_x_sym`"
        )
        return

    A_D = geometry.area()
    if A_D == 0:
        return None

    centroid_geom = geometry.centroid()
    centroid_point = centroid_geom.asPoint()

    # Reflect across the horizontal axis (x-axis) passing through the centroid
    reflected = _reflect_geometry_horizontally(geometry, centroid_point.y())

    A_O = geometry.intersection(reflected).area()

    return A_O / A_D

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

