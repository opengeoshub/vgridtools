## Vgrid DGGS Expressions is integrated into QGIS field calculator
<li>
    <a href="#latlong2dggs">Lat Long to DGGS</a>
    <ul>
        <li><a href="#latlon2h3">latlon2h3</a></li>
        <li><a href="#latlon2s2">latlon2s2</a></li>
        <li><a href="#latlon2a5">latlon2a5</a></li>
        <li><a href="#latlon2rhealpix">latlon2rhealpix</a></li>
        <li><a href="#latlon2isea4t">latlon2isea4t</a></li>
        <li><a href="#latlon2isea3h">latlon2isea3h</a></li>
        <li><a href="#latlon2dggal">latlon2dggal</a></li>
        <li><a href="#latlon2qtm">latlon2qtm</a></li>
        <li><a href="#latlon2olc">latlon2olc</a></li>
        <li><a href="#latlon2geohash">latlon2geohash</a></li>
        <li><a href="#latlon2georef">latlon2georef</a></li>
        <li><a href="#latlon2mgrs">latlon2mgrs</a></li>
        <li><a href="#latlon2tilecode">latlon2tilecode</a></li>
        <li><a href="#latlon2quadkey">latlon2quadkey</a></li>
        <li><a href="#latlon2maidenhead">latlon2maidenhead</a></li>
        <li><a href="#latlon2gars">latlon2gars</a></li>
    </ul>
</li>
<li>
    <a href="#compactness">Calculate Polygon Compactness</a>
    <ul>
        <li><a href="#comp_pp">comp_pp</a></li>
        <li><a href="#comp_schwartz">comp_schwartz</a></li>
        <li><a href="#comp_reock">comp_reock</a></li>
        <li><a href="#comp_box_reock">comp_box_reock</a></li>
        <li><a href="#comp_cvh">comp_cvh</a></li>
        <li><a href="#comp_skew">comp_skew</a></li>
        <li><a href="#comp_x_sym">comp_x_sym</a></li>
        <li><a href="#comp_y_sym">comp_x_sym</a></li>
        <li><a href="#comp_lw">comp_lw</a></li>
    </ul>
</li>

<a id="latlong2dggs"></a>
### latlon2h3

Convert (lat, long) to H3 ID.
<h4>Syntax</h4>
<li>
<code>latlon2h3(lat, long, resolution)</span> </code>
</li> 
<h4>Arguments</h4>
<li>
<code>lat</code>: latitude coordinate field or value
</li>
<li>
<code>long</code>: longitude coordinate field or value
</li>
<li>
<code>resolution</code>: H3 resolution [0..15]
</li>
<h4>Example usage</h4>
<li>
<code>latlon2h3(10.775275567242561, 106.70679737574993, 13) → '8d65b56628e46bf'</code>  
</li>
<li>
<code>Point features: latlon2h3($y, $x, 13)</code>
</li>
<br/>
<div align="center">
  <img src="https://raw.githubusercontent.com/opengeoshub/vgridtools/main/images/readme/latlon2h3.png">
</div>

### latlon2s2

Convert (lat, long) to S2 Token.
<h4>Syntax</h4>
<li>
<code>latlon2s2(lat, long, resolution)</span> </code>
</li> 
<h4>Arguments</h4>
<li>
<code>lat</code>: latitude coordinate field or value
</li>
<li>
<code>long</code>: longitude coordinate field or value
</li>
<li>
<code>resolution</code>: S2 resolution [0..30]
</li>
<h4>Example usage</h4>
<li>
<code>latlon2s2(10.775275567242561, 106.70679737574993, 21) → '31752f45cc94'</code>
</li>
<li>
<code>Point features: latlon2s2($y, $x, 21)</code>
</li>
<br/>
<div align="center">
  <img src="https://raw.githubusercontent.com/opengeoshub/vgridtools/main/images/readme/latlon2s2.png">
</div>


### latlon2a5

Convert (lat, long) to A5 Hex.
<h4>Syntax</h4>
<li>
<code>latlon2a5(lat, long, resolution)</span> </code>
</li> 
<h4>Arguments</h4>
<li>
<code>lat</code>: latitude coordinate field or value
</li>
<li>
<code>long</code>: longitude coordinate field or value
</li>
<li>
<code>resolution</code>: A5 resolution [0..29]
</li>
<h4>Example usage</h4>
<li>
<code>latlon2a5(10.775275567242561, 106.70679737574993, 16) → '7a9408e938000000'</code> 
</li>
<li>
<code>Point features: latlon2a5($y, $x, 16)</code>
</li>
<br/>
<div align="center">
  <img src="https://raw.githubusercontent.com/opengeoshub/vgridtools/main/images/readme/latlon2a5.png">
</div>


### latlon2rhealpix

Convert (lat, long) to rHEALPix ID.
<h4>Syntax</h4>
<li>
<code>latlon2rhealpix(lat, long, resolution)</span> </code>
</li> 
<h4>Arguments</h4>
<li>
<code>lat</code>: latitude coordinate field or value
</li>
<li>
<code>long</code>: longitude coordinate field or value
</li>
<li>
<code>resolution</code>: rHEALPix resolution [0..15]
</li>
<h4>Example usage</h4>
<li>
<code>latlon2rhealpix(10.775275567242561, 106.70679737574993, 12) → 'R312603625535'</code>
</li>
<li>
<code>Point features: latlon2rhealpix($y, $x, 12)</code>
</li>
<br/>
<div align="center">
  <img src="https://raw.githubusercontent.com/opengeoshub/vgridtools/main/images/readme/latlon2rhealpix.png">
</div>

### latlon2isea4t

Convert (lat, long) to OpenEAGGR ISEA4T ID (Windows only).
<h4>Syntax</h4>
<li>
<code>latlon2isea4t(lat, long, resolution)</span> </code>
</li> 
<h4>Arguments</h4>
<li>
<code>lat</code>: latitude coordinate field or value
</li>
<li>
<code>long</code>: longitude coordinate field or value
</li>
<li>
<code>resolution</code>: ISEA4T resolution [0..39]
</li>
<h4>Example usage</h4>
<li>
<code>latlon2isea4t(10.775275567242561, 106.70679737574993, 20) → '1310231333101123322130'</code>
</li>
<li>
<code>Point features: latlon2isea4t($y, $x, 20)</code>
</li>
<br/>
<div align="center">
  <img src="https://raw.githubusercontent.com/opengeoshub/vgridtools/main/images/readme/latlon2isea4t.png">
</div>

### latlon2isea3h

Convert (lat, long) to OpenEAGGR ISEA3H ID (Windows only).
<h4>Syntax</h4>
<li>
<code>latlon2isea3h(lat, long, resolution)</span> </code>
</li> 
<h4>Arguments</h4>
<li>
<code>lat</code>: latitude coordinate field or value
</li>
<li>
<code>long</code>: longitude coordinate field or value
</li>
<li>
<code>resolution</code>: ISEA3H resolution [0..40]
</li>
<h4>Example usage</h4>
<li>
<code>latlon2isea3h(10.775275567242561, 106.70679737574993, 20) → '132022636,-1020'</code>
</li>
<li>
<code>Point features: latlon2isea3h($y, $x, 20)</code>
</li>
<br/>
<div align="center">
  <img src="https://raw.githubusercontent.com/opengeoshub/vgridtools/main/images/readme/latlon2isea3h.png">
</div>

### latlon2dggal

Convert (lat, long) to DGGAL ID.
<h4>Syntax</h4>
<li>
<code>latlon2dggal(dggs_type, lat, long, resolution)</span> </code>
</li> 
<h4>Arguments</h4>
<li>
<code>dggs_type</code>: DGGS type (<code>'gnosis','isea3h','isea9r','ivea3h','ivea9r','rtea3h','rtea9r','rhealpix'</code>)
</li>
<li>
<code>lat</code>: latitude coordinate field or value
</li>
<li>
<code>long</code>: longitude coordinate field or value
</li>
<li>
<code>resolution</code>: DGGS resolution
</li>
<h4>Example usage</h4>
<li>
<code>latlon2dggal('isea9r', 10.775275567242561, 106.70679737574993, 7) → 'H7-629F2'</code>
</li>
<li>
<code>Point features: latlon2dggal('isea9r', $y, $x, 7)</code>
</li>
<br/>
<div align="center">
  <img src="https://raw.githubusercontent.com/opengeoshub/vgridtools/main/images/readme/latlon2dggal.png">
</div>

### latlon2qtm

Convert (lat, long) to QTM.
<h4>Syntax</h4>
<li>
<code>latlon2qtm(lat, long, resolution)</span> </code>
</li> 
<h4>Arguments</h4>
<li>
<code>lat</code>: latitude coordinate field or value
</li>
<li>
<code>long</code>: longitude coordinate field or value
</li>
<li>
<code>resolution</code>: QTM resolution [1..24]
</li>
<h4>Example usage</h4>
<li>
<code>latlon2qtm(10.775275567242561, 106.70679737574993, 18) → '420123231312110130'</code>
</li>
<li>
<code>Point features: latlon2qtm($y, $x, 18)</code>
</li>
<br/>
<div align="center">
  <img src="https://raw.githubusercontent.com/opengeoshub/vgridtools/main/images/readme/latlon2qtm.png">
</div>

### latlon2olc

Convert (lat, long) to Open Location Code (OLC)/ Google Plus Code.
<h4>Syntax</h4>
<li>
<code>latlon2olc(lat, long, resolution)</span> </code>
</li> 
<h4>Arguments</h4>
<li>
<code>lat</code>: latitude coordinate field or value
</li>
<li>
<code>long</code>: longitude coordinate field or value
</li>
<li>
<code>resolution</code>: OLC resolution [2,4,6,8,10,11..15]
</li>
<h4>Example usage</h4>
<li>
<code> latlon2olc(10.775275567242561, 106.70679737574993, 11)  → '7P28QPG4+4P7'</code>
</li>
<li>
<code>Point features: latlon2olc($y, $x, 11)</code>
</li>
<br/>
<div align="center">
  <img src="https://raw.githubusercontent.com/opengeoshub/vgridtools/main/images/readme/latlon2olc.png">
</div>

### latlon2geohash

Convert (lat, long) to Geohash ID.
<h4>Syntax</h4>
<li>
<code>latlon2geohash(lat, long, resolution)</span> </code>
</li> 
<h4>Arguments</h4>
<li>
<code>lat</code>: latitude coordinate field or value
</li>
<li>
<code>long</code>: longitude coordinate field or value
</li>
<li>
<code>resolution</code>: Geohash resolution [1..30]
</li>
<h4>Example usage</h4>
<li>
<code>latlon2geohash(10.775275567242561, 106.70679737574993, 9) → 'w3gvk1td8'</code>
</li>
<li>
<code>Point features: latlon2geohash($y, $x, 9)</code>
</li>
<br/>
<div align="center">
  <img src="https://raw.githubusercontent.com/opengeoshub/vgridtools/main/images/readme/latlon2geohash.png">
</div>

### latlon2georef

Convert (lat, long) to GEOREF ID.
<h4>Syntax</h4>
<li>
<code>latlon2georef(lat, long, resolution)</span> </code>
</li> 
<h4>Arguments</h4>
<li>
<code>lat</code>: latitude coordinate field or value
</li>
<li>
<code>long</code>: longitude coordinate field or value
</li>
<li>
<code>resolution</code>: GEOREF resolution [0..10]
</li>
<h4>Example usage</h4>
<li>
<code>latlon2georef(10.775275567242561, 106.70679737574993, 5) → 'VGBL4240746516'</code>
</li>
<li>
<code>Point features: latlon2georef($y, $x, 5)</code>
</li>
<br/>
<div align="center">
  <img src="https://raw.githubusercontent.com/opengeoshub/vgridtools/main/images/readme/latlon2georef.png">
</div>

### latlon2mgrs

Convert (lat, long) to MGRS ID.
<h4>Syntax</h4>
<li>
<code>latlon2mgrs(lat, long, resolution)</span> </code>
</li> 
<h4>Arguments</h4>
<li>
<code>lat</code>: latitude coordinate field or value
</li>
<li>
<code>long</code>: longitude coordinate field or value
</li>
<li>
<code>resolution</code>: MGRS resolution [0..5]
</li>
<h4>Example usage</h4>
<li>
<code> latlon2mgrs(10.775275567242561, 106.70679737574993, 4) → '48PXS86629165'</code>
</li>
<li>
<code>Point features: latlon2mgrs($y, $x, 4)</code>
</li>
<br/>
<div align="center">
  <img src="https://raw.githubusercontent.com/opengeoshub/vgridtools/main/images/readme/latlon2mgrs.png">
</div>

### latlon2tilecode

Convert (lat, long) to Tilecode ID.
<h4>Syntax</h4>
<li>
<code>latlon2tilecode(lat, long, resolution)</span> </code>
</li> 
<h4>Arguments</h4>
<li>
<code>lat</code>: latitude coordinate field or value
</li>
<li>
<code>long</code>: longitude coordinate field or value
</li>
<li>
<code>resolution</code>: Tilecode resolution [0..29]
</li>
<h4>Example usage</h4>
<li>
<code>latlon2tilecode(10.775275567242561, 106.70679737574993, 23) → 'z23x6680752y3941728'</code>
</li>
<li>
<code>Point features: latlon2tilecode($y, $x, 23)</code>
</li>
<br/>
<div align="center">
  <img src="https://raw.githubusercontent.com/opengeoshub/vgridtools/main/images/readme/latlon2tilecode.png">
</div>

### latlon2quadkey

Convert (lat, long) to Quadkey ID.
<h4>Syntax</h4>
<li>
<code>latlon2quadkey(lat, long, resolution)</span> </code>
</li> 
<h4>Arguments</h4>
<li>
<code>lat</code>: latitude coordinate field or value
</li>
<li>
<code>long</code>: longitude coordinate field or value
</li>
<li>
<code>resolution</code>: Quadkey resolution [0..29]
</li>
<h4>Example usage</h4>
<li>
<code>latlon2quadkey(10.775275567242561, 106.70679737574993, 23) → '13223011131020212310000'</code>
</li>
<li>
<code>Point features: latlon2quadkey($y, $x, 23)</code>
</li>
<br/>
<div align="center">
  <img src="https://raw.githubusercontent.com/opengeoshub/vgridtools/main/images/readme/latlon2quadkey.png">
</div>

### latlon2maidenhead

Convert (lat, long) to Maidenhead ID.
<h4>Syntax</h4>
<li>
<code>latlon2maidenhead(lat, long, resolution)</span> </code>
</li> 
<h4>Arguments</h4>
<li>
<code>lat</code>: latitude coordinate field or value
</li>
<li>
<code>long</code>: longitude coordinate field or value
</li>
<li>
<code>resolution</code>: Maidenhead resolution [1..4]
</li>
<h4>Example usage</h4>
<li>
<code>latlon2maidenhead(10.775275567242561, 106.70679737574993, 4) → 'OK30is46' </code>
</li>
<li>
<code>Point features: latlon2maidenhead($y, $x, 4)</code>
</li>
<br/>
<div align="center">
  <img src="https://raw.githubusercontent.com/opengeoshub/vgridtools/main/images/readme/latlon2maidenhead.png">
</div>

### latlon2gars

Convert (lat, long) to GARS Code.
<h4>Syntax</h4>
<li>
<code>latlon2gars(lat, long, resolution)</span> </code>
</li> 
<h4>Arguments</h4>
<li>
<code>lat</code>: latitude coordinate field or value
</li>
<li>
<code>long</code>: longitude coordinate field or value
</li>
<li>
<code>resolution</code>: GARS resolution [1..4] (30, 15, 5, 1 minutes)
</li>
<h4>Example usage</h4>
<li>
<code>latlon2gars(10.775275567242561, 106.70679737574993, 4) → '574JK1918'</code>
</li>
<li>
<code>Point features: latlon2gars($y, $x, 4)</code>
</li>
<br/>
<div align="center">
  <img src="https://raw.githubusercontent.com/opengeoshub/vgridtools/main/images/readme/latlon2gars.png">
</div>

<a id="compactness"></a>

### comp_pp

#### Calculate Polsby–Popper (PP) Compactness.
Polsby-Popper Compactness is the ratio of the area **A** of the geometry to the area of a circle whose circumference is equal to the perimeter **P** of the geometry.

$$
\text{comp\_pp} = \frac{4 \pi A}{P^2}
$$

Scores range from 0 to 1, where 0 is the least compact and 1 is the most compact. 

<h4>Syntax</h4>
<li>
<code>comp_pp(geometry)</code>
</li>
<h4>Arguments</h4>
<li>
<code>geometry</code>: a polygon geometry
</li>
<h4>Example usage</h4>
<li>
<code>comp_pp($geometry)  → [0..1]</code>
</li>

### comp_schwartz

#### Calculate Schwartzberg Compactness.
Schwartzberg Compactness is the ratio of the perimeter **P** of the geometry to the circumference of a circle whose area is equal to the area of the geometry

$$
\text{comp\_schwartz} = \frac{1}{\tfrac{P}{2\pi \sqrt{\tfrac{A}{\pi}}}}
$$

Scores range from 0 to 1, where 0 is the least compact and 1 is the most compact. 

<h4>Syntax</h4>
<li>
<code>comp_schwartz(geometry)</code>
</li>
<h4>Arguments</h4>
<li>
<code>geometry</code>: a polygon geometry
</li>
<h4>Example usage</h4>
<li>
<code>comp_schwartz($geometry)  → [0..1]</code>
</li>

### comp_reock

#### Calculate Reock Compactness.
Reock is the ratio of the area **A** of the geometry to the area of its minimum bounding circle **$A_{\text{mbc}}$**.

$$
comp\_reock = \frac{A}{A_{mbc}}
$$

Scores range from 0 to 1, where 0 is the least compact and 1 is the most compact. 

<h4>Syntax</h4>
<li>
<code>comp_reock(geometry)</code>
</li>
<h4>Arguments</h4>
<li>
<code>geometry</code>: a polygon geometry
</li>
<h4>Example usage</h4>
<li>
<code>comp_reock($geometry)  → [0..1]</code>
</li>

### comp_box_reock

#### Calculate Box Reock Compactness.
Box Reock is the ratio of the area **A** of the geometry to the area of its minimum bounding rectangle **$A_{\text{mbr}}$**.

$$
\text{comp\_box\_reock} = \frac{A}{A_{\text{mbr}}}
$$

Scores range from 0 to 1, where 0 is the least compact and 1 is the most compact. 

<h4>Syntax</h4>
<li>
<code>comp_box_reock(geometry)</code>
</li>
<h4>Arguments</h4>
<li>
<code>geometry</code>: a polygon geometry
</li>
<h4>Example usage</h4>
<li>
<code>comp_box_reock($geometry)  → [0..1]</code>
</li>

### comp_cvh

Calculate Convex Hull Compactness.
Convex Hull Compactness is the ratio of the area **A** of the geometry to the area of its convex hull **$A_{\text{cvh}}$**

$$
\text{comp\_cvh} = \frac{A}{A_{\text{cvh}}}
$$

Scores range from 0 to 1, where 0 is the least compact and 1 is the most compact. 

<h4>Syntax</h4>
<li>
<code>comp_cvh(geometry)</code>
</li>
<h4>Arguments</h4>
<li>
<code>geometry</code>: a polygon geometry
</li>
<h4>Example usage</h4>
<li>
<code>comp_cvh($geometry)  → [0..1]</code>
</li>

### comp_skew

#### Calculate Skew Compactness.
Skew Compactness is the ratio of the area **$A_{\text{mic}}$** of the maximum inscribed circle to the area of the minimum bounding circle **$A_{\text{mbc}}$**.

$$
\text{comp\_skew} = \frac{A_{\text{mic}}}{A_{\text{mbc}}}
$$

Scores range from 0 to 1, where 0 is the least compact and 1 is the most compact. 

<h4>Syntax</h4>
<li>
<code>comp_skew(geometry)</code>
</li>
<h4>Arguments</h4>
<li>
<code>geometry</code>: a polygon geometry
</li>
<h4>Example usage</h4>
<li>
<code>comp_skew($geometry)  → [0..1]</code>
</li>

### comp_x_sym

#### Calculate X‑Symmetry Compactness.
X-Symmetry compactness is calculated by dividing the intersection area **$A\bigl(I(G,G^X)\bigr)$** of the geometry with its reflection across the horizontal axis (x-axis) by the area of the original geometry **A**. 

$$
\text{comp\_x\_sym} = \frac{A\bigl(I(G,G^X)\bigr)}{A}
$$

Scores range from 0 to 1, where 0 is the least compact and 1 is the most compact. 

<h4>Syntax</h4>
<li>
<code>comp_x_sym(geometry)</code>
</li>
<h4>Arguments</h4>
<li>
<code>geometry</code>: a polygon geometry
</li>
<h4>Example usage</h4>
<li>
<code>comp_x_sym($geometry)  → [0..1]</code>
</li>


### comp_y_sym

#### Calculate Y‑Symmetry Compactness.
Y-Symmetry compactness is calculated by dividing the intersection area **$A\bigl(I(G,G^Y)\bigr)$** of the geometry with its reflection across the vertical axis (y-axis) by the area of the original geometry **A**. 

$$
\text{comp\_y\_sym} = \frac{A\bigl(I(G,G^Y)\bigr)}{A}
$$

Scores range from 0 to 1, where 0 is the least compact and 1 is the most compact. 

<h4>Syntax</h4>
<li>
<code>comp_y_sym(geometry)</code>
</li>
<h4>Arguments</h4>
<li>
<code>geometry</code>: a polygon geometry
</li>
<h4>Example usage</h4>
<li>
<code>comp_y_sym($geometry)  → [0..1]</code>
</li>

### comp_lw

#### Calculate Length–Width Compactness.
Length–Width Compactness is the ratio of the width **$W_{\text{mbr}}$** to the length **$L_{\text{mbr}}$** of the geometry’s minimum bounding rectangle.

$$
\text{comp\_lw}= \frac{W_{\text{mbr}}}{L_{\text{mbr}}}
$$

Scores range from 0 to 1, where 0 is the least compact and 1 is the most compact. 

<h4>Syntax</h4>
<li>
<code>comp_lw(geometry)</code>
</li>
<h4>Arguments</h4>
<li>
<code>geometry</code>: a polygon geometry
</li>
<h4>Example usage</h4>
<li>
<code>comp_lw($geometry)  → [0..1]</code>
</li>
