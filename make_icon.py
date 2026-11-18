#!/usr/bin/env python3
"""Write icon.svg: the city's mainland outline in ink on paper, in the style of Map Learning's icon.

Usage: python3 make_icon.py <map-learning-icon.svg>
Reads the outline from the map data in index.html and the paper, ink and shadow definitions from
Map Learning's icon.svg, so the two apps look like a pair. Render icon.svg at 1024 px to
icon-1024.png (any SVG renderer; Chromium was used), then make the other sizes from it.
"""
import json, re, sys
from pathlib import Path
from shapely.geometry import Polygon

ROOT = Path(__file__).resolve().parent

def main(ref_svg):
    html = (ROOT / 'index.html').read_text(encoding='utf-8')
    D = json.loads(re.search(r'<script id="map-data" type="application/json">(.*?)</script>', html, re.S).group(1))
    rings = []
    for m in re.finditer(r'M(-?\d+) (-?\d+)l([^z]*)z', D['outline']):
        x, y = int(m.group(1)), int(m.group(2)); r = [(x, y)]
        n = list(map(int, re.findall(r'-?\d+', m.group(3))))
        for i in range(0, len(n) - 1, 2): x += n[i]; y += n[i + 1]; r.append((x, y))
        rings.append(r)
    main_ring = Polygon(max(rings, key=lambda r: Polygon(r).area))
    x0, y0, x1, y1 = main_ring.bounds
    size = 700                                   # the mainland fits a 700 px square, centred
    k = size / max(x1 - x0, y1 - y0)
    ox, oy = (1024 - (x1 - x0) * k) / 2, (1024 - (y1 - y0) * k) / 2 + 6
    g = main_ring.simplify(1.6 / k)
    pts = [(ox + (x - x0) * k, oy + (y - y0) * k) for x, y in g.exterior.coords]
    d = 'M' + ' L'.join(f'{x:.1f} {y:.1f}' for x, y in pts) + 'Z'
    ref = Path(ref_svg).read_text(encoding='utf-8')
    head = ref[:ref.index('</defs>') + len('</defs>')]
    svg = f'''{head}
  <rect width="1024" height="1024" fill="url(#paper)"/>
  <rect width="1024" height="1024" fill="url(#glow)"/>
  <g>
    <path d="{d}" fill="#000" filter="url(#shadow)"/>
    <path d="{d}" fill="url(#ink)" filter="url(#bevel)"/>
  </g>
</svg>
'''
    (ROOT / 'icon.svg').write_text(svg, encoding='utf-8')
    print(f'icon.svg: {len(pts)} points')

if __name__ == '__main__':
    if len(sys.argv) != 2: sys.exit(__doc__)
    main(sys.argv[1])
