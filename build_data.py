#!/usr/bin/env python3
"""Build the map data embedded in index.html (<script id="map-data">).

Two levels of Hồ Chí Minh City, as merged on 1 July 2025 (Resolution 202/2025/QH15):
  w  the 168 commune-level units in force since 1 July 2025 (113 phường, 54 xã, 1 đặc khu;
     Resolution 1685/NQ-UBTVQH15), grouped by the former district each lies in;
  d  the 38 former district-level units of 30 June 2025 (22 of the old city, 9 of Bình Dương,
     7 of Bà Rịa – Vũng Tàu), grouped by the former province.

Inputs
  <provinces-db>   a checkout of github.com/thanglequoc/vietnamese-provinces-database (MIT). Used:
                     json/geojson/79_ho_chi_minh/wards/*.geojson   the 168 units: code, name, area
                     json/geojson/<nn>_*/<nn>_*.geojson            neighbouring provinces
                     dataset-generation-scripts/resources/gis/sapnhapbando_geo_objects.sql
                                                                  what each unit was formed from
                   Shapes and areas were collected from sapnhap.bando.com.vn.
  <adm2.geojson>   geoBoundaries VNM ADM2 (OCHA ROAP and the Government of Viet Nam, 2020,
                   CC BY 3.0 IGO): the former district boundaries.
  <world-atlas>    npm pack world-atlas@2.0.2 (Natural Earth 1:50m, public domain): Cambodia.
  <mapping.csv>    data/ho-chi-minh.csv from github.com/Dorabot-io/sap-nhap-2025 (CC BY 4.0): every
                   old commune, its old district and the new unit it went into, wholly or in part,
                   copied from Resolution 1685/NQ-UBTVQH15.
Requires Python 3.10+ and shapely 2.1+ with GEOS 3.12+ (pip install shapely).

Usage
  python3 build_data.py <provinces-db> <adm2.geojson> <world-atlas/package> <mapping.csv>

What it does
  1. The 168 shapes are noded into one network of borders and rebuilt from its faces, so that
     neighbours share every edge exactly (42 of them did not quite match in the source).
  2. Which former districts each unit came from is read from the resolution (the mapping). A unit
     from one district goes to it whole; a unit from two or more is cut along the 2020 district
     lines, between those districts only. The former districts are then the union of their pieces,
     so both levels share one set of borders.
  3. Everything is simplified together (shapely.coverage_simplify), so shared borders stay shared,
     and written in the app's own Mercator units of about 10 m.
"""
import json, math, re, sys, glob
from datetime import date
from pathlib import Path

import shapely
from shapely.geometry import LineString, MultiPolygon, Polygon, box, shape, Point
from shapely.ops import polylabel, polygonize, unary_union, transform
from shapely.strtree import STRtree

ROOT = Path(__file__).resolve().parent
INDEX = ROOT / 'index.html'

# ---------------------------------------------------------------- projection (same as the app)
# Mercator; one unit is 10 m along the equator (about 9.8 m at the city's latitude).
EXT_LON = (105.55, 108.35)
EXT_LAT = (7.95, 12.35)
def merc(lat): return 180 / math.pi * math.log(math.tan(math.pi / 4 + lat * math.pi / 360))
PROJ = {'lon0': EXT_LON[0], 'mtop': merc(EXT_LAT[1]), 's': 11132.0}
def px(lon): return (lon - PROJ['lon0']) * PROJ['s']
def py(lat): return (PROJ['mtop'] - merc(lat)) * PROJ['s']
def P(lon, lat): return [round(px(lon)), round(py(lat))]
def proj(g): return shapely.transform(g, lambda a: __import__("numpy").column_stack([(a[:, 0] - PROJ["lon0"]) * PROJ["s"], (PROJ["mtop"] - 180 / math.pi * __import__("numpy").log(__import__("numpy").tan(math.pi / 4 + a[:, 1] * math.pi / 360))) * PROJ["s"]]))
LAT0 = 10.8
M_PER_UNIT = 10.0 * math.cos(math.radians(LAT0))      # metres per unit near the city
def lat_of(y):
    m = PROJ['mtop'] - y / PROJ['s']
    return (2 * math.atan(math.exp(m * math.pi / 180)) - math.pi / 2) * 180 / math.pi
def km2(g):
    """Area in km². A unit is 10 m × cos(latitude) on the ground, so each piece is scaled at its own
    latitude (Côn Đảo, at 8.7°N, would otherwise come out about 1.3 % small)."""
    return sum(p.area * (0.01 * math.cos(math.radians(lat_of(p.centroid.y)))) ** 2 for p in polys_of(g))

# ---------------------------------------------------------------- compact path codec
# "M x yl dx dy dx dy ... z" with integer units; negative numbers carry their own separator.
def enc_num(n, first=False):
    return str(n) if (n < 0 or first) else ' ' + str(n)

def encode(rings):
    parts = []
    for ring in rings:
        pts = []
        for x, y in ring:
            p = (int(round(x)), int(round(y)))
            if not pts or p != pts[-1]: pts.append(p)
        if len(pts) > 2 and pts[0] == pts[-1]: pts.pop()
        if len(pts) < 3: continue
        s = f'M{pts[0][0]} {pts[0][1]}l'
        first = True
        for (ax, ay), (bx, by) in zip(pts, pts[1:]):
            s += enc_num(bx - ax, first) + enc_num(by - ay)
            first = False
        parts.append(s + 'z')
    return ''.join(parts)

def encode_lines(lines):
    parts = []
    for ln in lines:
        pts = []
        for x, y in ln:
            p = (int(round(x)), int(round(y)))
            if not pts or p != pts[-1]: pts.append(p)
        if len(pts) < 2: continue
        s = f'M{pts[0][0]} {pts[0][1]}l'
        first = True
        for (ax, ay), (bx, by) in zip(pts, pts[1:]):
            s += enc_num(bx - ax, first) + enc_num(by - ay)
            first = False
        parts.append(s + 'z')
    return ''.join(parts)

def parse_rings(d):
    out = []
    for m in re.finditer(r'M(-?\d+) (-?\d+)l([^z]*)z', d):
        x, y = int(m.group(1)), int(m.group(2))
        ring = [(x, y)]
        nums = list(map(int, re.findall(r'-?\d+', m.group(3))))
        for i in range(0, len(nums) - 1, 2):
            x += nums[i]; y += nums[i + 1]; ring.append((x, y))
        out.append(ring)
    return out

def polys_of(g):
    if g.is_empty: return []
    if isinstance(g, Polygon): return [g]
    return [q for q in getattr(g, 'geoms', []) if isinstance(q, Polygon) and not q.is_empty] + \
           [r for q in getattr(g, 'geoms', []) if not isinstance(q, Polygon) for r in polys_of(q)]

def rings_of(g):
    return [r for p in polys_of(g) for r in [list(p.exterior.coords)] + [list(h.coords) for h in p.interiors]]

def lines_of(g):
    if g.is_empty: return []
    if isinstance(g, LineString): return [list(g.coords)]
    out = []
    for q in getattr(g, 'geoms', []): out.extend(lines_of(q))
    return out

def bbox(points):
    xs = [p[0] for p in points]; ys = [p[1] for p in points]
    return [min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)]

def ring_area(r):
    return abs(sum(r[i - 1][0] * r[i][1] - r[i][0] * r[i - 1][1] for i in range(len(r)))) / 2

def clean(g):
    g = shapely.make_valid(g)
    return unary_union(polys_of(g)) if not isinstance(g, (Polygon, MultiPolygon)) else g

# ---------------------------------------------------------------- the former districts
# Province 0 = the old Hồ Chí Minh City, 1 = Bình Dương, 2 = Bà Rịa – Vũng Tàu.
PROVINCES = [
    {'num': 'I', 'vi': 'TP. Hồ Chí Minh (cũ)', 'en': 'Former Hồ Chí Minh City', 'short': 'Old HCMC', 'code': '79'},
    {'num': 'II', 'vi': 'Tỉnh Bình Dương', 'en': 'Former Bình Dương province', 'short': 'Bình Dương', 'code': '74'},
    {'num': 'III', 'vi': 'Tỉnh Bà Rịa – Vũng Tàu', 'en': 'Former Bà Rịa – Vũng Tàu province', 'short': 'Bà Rịa – Vũng Tàu', 'code': '77'},
]
# id, geoBoundaries names (2020; merged where the units were merged before 2025), name, type, province.
# Types as on 30 June 2025: quận (urban district), huyện (rural district), thành phố (city).
DISTRICTS = [
    # The old city, in the order of the national statistical code list.
    ('q1', ['Quan 1'], 'Quận 1', 'quận', 0), ('q12', ['Quan 12'], 'Quận 12', 'quận', 0),
    ('gvap', ['Go Vap'], 'Gò Vấp', 'quận', 0), ('bthanh', ['Binh Thanh'], 'Bình Thạnh', 'quận', 0),
    ('tbinh', ['Tan Binh'], 'Tân Bình', 'quận', 0), ('tphu', ['Tan Phu'], 'Tân Phú', 'quận', 0),
    ('pnhuan', ['Phu Nhuan'], 'Phú Nhuận', 'quận', 0),
    ('tduc', ['Thu Duc', 'Quan 9', 'Quan 2'], 'Thủ Đức', 'thành phố', 0),
    ('q3', ['Quan 3'], 'Quận 3', 'quận', 0), ('q10', ['Quan 10'], 'Quận 10', 'quận', 0),
    ('q11', ['Quan 11'], 'Quận 11', 'quận', 0), ('q4', ['Quan 4'], 'Quận 4', 'quận', 0),
    ('q5', ['Quan 5'], 'Quận 5', 'quận', 0), ('q6', ['Quan 6'], 'Quận 6', 'quận', 0),
    ('q8', ['Quan 8'], 'Quận 8', 'quận', 0), ('btan', ['Binh Tan'], 'Bình Tân', 'quận', 0),
    ('q7', ['Quan 7'], 'Quận 7', 'quận', 0),
    ('cchi', ['Cu Chi'], 'Củ Chi', 'huyện', 0), ('hmon', ['Hoc Mon'], 'Hóc Môn', 'huyện', 0),
    ('bchanh', ['Binh Chanh'], 'Bình Chánh', 'huyện', 0), ('nbe', ['Nha Be'], 'Nhà Bè', 'huyện', 0),
    ('cgio', ['Can Gio'], 'Cần Giờ', 'huyện', 0),
    # Bình Dương.
    ('tdm', ['Thu Dau Mot'], 'Thủ Dầu Một', 'thành phố', 1), ('bbang', ['Bau Bang'], 'Bàu Bàng', 'huyện', 1),
    ('dtieng', ['Dau Tieng'], 'Dầu Tiếng', 'huyện', 1), ('bcat', ['Ben Cat'], 'Bến Cát', 'thành phố', 1),
    ('pgiao', ['Phu Giao'], 'Phú Giáo', 'huyện', 1), ('tuyen', ['Tan Uyen'], 'Tân Uyên', 'thành phố', 1),
    ('dian', ['Di An'], 'Dĩ An', 'thành phố', 1), ('tan', ['Thuan An'], 'Thuận An', 'thành phố', 1),
    ('btuyen', ['Bac Tan Uyen'], 'Bắc Tân Uyên', 'huyện', 1),
    # Bà Rịa – Vũng Tàu.
    ('vtau', ['Vung Tau'], 'Vũng Tàu', 'thành phố', 2), ('bria', ['Ba Ria'], 'Bà Rịa', 'thành phố', 2),
    ('cduc', ['Chau Duc'], 'Châu Đức', 'huyện', 2), ('xmoc', ['Xuyen Moc'], 'Xuyên Mộc', 'huyện', 2),
    ('ldat', ['Long Dien', 'Dat Do'], 'Long Đất', 'huyện', 2), ('pmy', ['Tan Thanh'], 'Phú Mỹ', 'thành phố', 2),
    ('cdao', ['Con Dao'], 'Côn Đảo', 'huyện', 2),
]
TYPE_EN = {'quận': 'Urban district', 'huyện': 'Rural district', 'thành phố': 'City',
           'phường': 'Ward', 'xã': 'Commune', 'đặc khu': 'Special zone'}
FULL_PREFIX = {'quận': 'Quận ', 'huyện': 'Huyện ', 'thành phố': 'Thành phố '}
D_NOTES = {
    'tduc': 'A city within the city from 1 January 2021, formed from Quận 2, Quận 9 and the old Thủ Đức district (Resolution 1111/NQ-UBTVQH14).',
    'ldat': 'Formed on 1 January 2025 by merging Long Điền and Đất Đỏ districts (Resolution 1256/NQ-UBTVQH15).',
    'pmy': 'Tân Thành district until 2018, then the town (thị xã) of Phú Mỹ; the 2025 resolution calls it a city (thành phố).',
    'cdao': 'The Côn Đảo islands, about 180 km south of Vũng Tàu. Since 1 July 2025 the whole district is one special zone (đặc khu).',
    'cgio': 'The old city’s only district on the sea, and home of the Cần Giờ mangrove forest.',
}

# ---------------------------------------------------------------- inputs
def load_feature(path):
    d = json.loads(Path(path).read_text(encoding='utf-8'))
    f = d['features'][0] if 'features' in d else d
    return shape(f['geometry']), f.get('properties', {})

def load_units(db):
    units = []
    for p in sorted(glob.glob(str(Path(db) / 'json/geojson/79_ho_chi_minh/wards/*.geojson'))):
        g, pr = load_feature(p)
        units.append({'code': pr['code'], 'name': pr['name'], 'full': pr['fullName'], 'areaOfficial': pr['areaKm2'],
                      'geom': clean(proj(clean(g)))})
    assert len(units) == 168, len(units)
    sql = (Path(db) / 'dataset-generation-scripts/resources/gis/sapnhapbando_geo_objects.sql').read_text(encoding='utf-8')
    before = {m.group(1): (m.group(2), m.group(3)) for m in
              re.finditer(r"\('(\d{5})', '([^']+)', '79', '[^']+', '([^']*)', NULL, NULL\)", sql)}
    # The JSON places some tone marks the new way (Hoà); the merger text, like official documents,
    # the traditional way (Hòa). Names are taken from the merger text, after checking they agree.
    import unicodedata
    bare = lambda s: ''.join(ch for ch in unicodedata.normalize('NFD', s.lower()) if unicodedata.category(ch) != 'Mn')
    for u in units:
        nm, txt = before[u['code']]
        assert bare(nm) == bare(u['full']), (nm, u['full'])
        u['full'] = unicodedata.normalize('NFC', nm)
        u['from'] = txt
        kind = next(k for k in ('phường', 'xã', 'đặc khu') if u['full'].lower().startswith(k + ' '))
        u['type'] = kind
        u['name'] = u['full'][len(kind) + 1:]
    kinds = [u['type'] for u in units]
    assert (kinds.count('phường'), kinds.count('xã'), kinds.count('đặc khu')) == (113, 54, 1), kinds
    return units

def district_id(huyen):
    name = re.sub(r'^(Huyện|Quận|Thành phố|Thị xã) ', '', huyen)
    if huyen.startswith('Quận ') and name[0].isdigit(): name = 'Quận ' + name
    if name == 'Long Điền': name = 'Long Đất'      # merged into Long Đất on 1 January 2025
    ids = [d[0] for d in DISTRICTS if d[2] == name]
    assert len(ids) == 1, huyen
    return ids[0]

def load_mapping(path, units):
    import csv
    rows = list(csv.DictReader(open(path, encoding='utf-8-sig')))
    by_full = {u['full']: u for u in units}
    import unicodedata
    bare = lambda s: ''.join(ch for ch in unicodedata.normalize('NFD', s.lower()) if unicodedata.category(ch) != 'Mn')
    by_bare = {bare(u['full']): u for u in units}
    for u in units: u['dset'], u['src'] = [], []
    # The resolution lists the units of 30 June 2025. A row for an older unit, merged into one of them
    # in an earlier round, shows through that unit (qua_don_vi), and its 'phan' describes the older
    # unit, not the 2025 one: old Phường 13 (Gò Vấp) was split in January 2025 between Phường 14 and
    # Phường 15, which then went wholly into An Hội Tây and An Hội Đông. So a 2025 unit counts as
    # partly taken only when it went into more than one new unit, or its own row says so.
    targets, own_part = {}, {}
    for r in rows:
        key = (r['qua_don_vi'] or r['xa_cu'], district_id(r['huyen_cu']))
        targets.setdefault(key, set()).add(bare(r['xa_moi']))
        if not r['qua_don_vi']: own_part[key] = own_part.get(key, False) or r['phan'] != 'toan_bo'
    for r in rows:
        u = by_full.get(r['xa_moi']) or by_bare[bare(r['xa_moi'])]
        did = district_id(r['huyen_cu'])
        if did not in u['dset']: u['dset'].append(did)
        old = r['qua_don_vi'] or r['xa_cu']
        if not any(x[0] == old and x[1] == did for x in u['src']):
            u['src'].append([old, did, len(targets[(old, did)]) > 1 or own_part.get((old, did), False)])
    for u in units: assert u['dset'], u['full']
    print(f"mapping: {len(rows)} rows; units from 2+ former districts: {sum(len(u['dset']) > 1 for u in units)}")

def load_districts(adm2_path, city):
    G = json.loads(Path(adm2_path).read_text(encoding='utf-8'))
    found = {}
    for f in G['features']:
        nm = f['properties']['shapeName']
        g = shape(f['geometry'])
        if g.representative_point().distance(g) > 0: continue
        gp = clean(proj(clean(g)))
        inside = gp.intersection(city).area / gp.area
        if inside < 0.5: continue
        assert nm not in found, nm
        found[nm] = gp
    out = []
    used = set()
    for did, keys, name, typ, prov in DISTRICTS:
        g = unary_union([found[k] for k in keys]).buffer(0)
        used.update(keys)
        out.append({'id': did, 'n': name, 'type': typ, 'prov': prov, 'gb': g})
    left = set(found) - used
    assert not left, left
    return out

# ---------------------------------------------------------------- 1. one network of borders
def rebuild_faces(units, extra_lines):
    """Node every unit's boundary (and the extra cut lines) and polygonize. Each face goes to the
    unit that holds it; slivers where the source shapes did not quite meet go to a neighbour."""
    lines = unary_union([u['geom'].boundary for u in units] + extra_lines)
    faces = list(polygonize(lines))
    geoms = [u['geom'] for u in units]
    tree = STRtree(geoms)
    owner = []
    for f in faces:
        rp = f.representative_point()
        cands = [i for i in tree.query(f) if geoms[i].intersects(f)]
        best, ba = None, 0
        for i in cands:
            a = geoms[i].intersection(f).area
            if a > ba: best, ba = i, a
        owner.append(best if best is not None and ba > 0.5 * f.area else None)
    # Orphans: gaps between source shapes. Small ones join the neighbour with the longest shared edge.
    # A face outside the city's outline (where a cut line runs just past the edge) is never taken in.
    shell = unary_union([Polygon(p.exterior) for p in polys_of(unary_union(geoms))])
    outside = {k for k, f in enumerate(faces) if owner[k] is None and not shell.contains(f.representative_point())}
    orphans = sum(1 for o in owner if o is None) - len(outside)
    ftree = STRtree(faces)
    changed = True
    while changed:
        changed = False
        for k, f in enumerate(faces):
            if owner[k] is not None or k in outside: continue
            if km2(f) > 0.5: continue
            best, bl = None, 0
            for j in ftree.query(f.buffer(0.5)):
                if j == k or owner[j] is None: continue
                l = f.boundary.intersection(faces[j].boundary).length
                if l > bl: best, bl = owner[j], l
            if best is not None: owner[k] = best; changed = True
    gaps = [km2(f) for k, f in enumerate(faces) if owner[k] is None and k not in outside]
    print(f'faces: {len(faces):,}; gaps between source shapes: {orphans}, of which left as holes: {len(gaps)} '
          f'({sum(gaps):.3f} km²); outside the outline, left out: {len(outside)} ({sum(km2(faces[k]) for k in outside):.4f} km²)')
    return faces, owner

# ---------------------------------------------------------------- 2. former districts
TOLERANCE = 3.0      # coverage simplification, in units (~30 m)
def assign_districts(units, dists):
    gb = [d['gb'] for d in dists]
    idx = {d['id']: i for i, d in enumerate(dists)}
    for u in units:
        u['allowed'] = [idx[x] for x in u['dset']]
        g = u['geom']
        shares = [(gb[i].intersection(g).area, i) for i in range(len(gb))]
        tot = sum(a for a, _ in shares) or 1
        u['geo'] = sorted(((a / tot, i) for a, i in shares if a / tot >= 0.01), reverse=True)
        u['split'] = len(u['allowed']) > 1
        outside = sum(sh for sh, i in u['geo'] if i not in u['allowed'])
        if outside > 0.08:
            print(f"   2020 lines put {outside:.0%} of {u['full']} outside the districts it came from "
                  f"({', '.join(dists[i]['n'] for i in u['allowed'])}); the resolution wins")
    cuts = []
    for u in units:
        if not u['split']: continue
        # The old line runs a little past the unit's edge, so that noding joins it to that edge.
        reach = u['geom'].buffer(6)
        for i in u['allowed']: cuts.append(gb[i].boundary.intersection(reach))
    return cuts

def district_of_faces(units, dists, faces, owner):
    gb = [d['gb'] for d in dists]
    fd = []
    for k, f in enumerate(faces):
        u = units[owner[k]] if owner[k] is not None else None
        if u is None: fd.append(None); continue
        if not u['split']: fd.append(u['allowed'][0]); continue
        # Among the districts the unit came from, the one holding most of this face; a face beyond
        # all of them (where the sources disagree) goes to the nearest.
        best = max(u['allowed'], key=lambda i: gb[i].intersection(f).area)
        if gb[best].intersection(f).area < 0.3 * f.area:
            c = f.representative_point()
            best = min(u['allowed'], key=lambda i: gb[i].distance(c))
        fd.append(best)
    # Inside a cut unit, thin or tiny pieces (where the old line runs along the unit's edge) take
    # the district of the piece of the same unit they share most border with.
    ftree = STRtree(faces)
    for _ in range(6):
        groups = {}
        for k in range(len(faces)):
            if owner[k] is not None and units[owner[k]]['split']: groups.setdefault((owner[k], fd[k]), []).append(k)
        moved = 0
        for (ui, di), ks in groups.items():
            # The district's whole share of the unit goes if it is a sliver (under 0.15 km², under
            # ~140 m across everywhere, or under 3 % of the unit). Otherwise only its stray fragments
            # go: tiny or thin pieces apart from the main one; real pieces stay.
            whole = unary_union([faces[k] for k in ks])
            sliver = lambda q: km2(q) < 0.15 or q.buffer(-7).is_empty
            if sliver(whole) or whole.area < 0.03 * units[ui]['geom'].area: pieces = [whole]
            else: pieces = [q for q in polys_of(whole) if sliver(q)]
            for piece in pieces:
                pk = [k for k in ks if piece.contains(faces[k].representative_point())]
                best, bl = None, 0
                for k in pk:
                    for j in ftree.query(faces[k].buffer(0.5)):
                        if owner[j] != ui or fd[j] == di: continue
                        l = faces[k].boundary.intersection(faces[j].boundary).length
                        if l > bl: best, bl = fd[j], l
                if best is not None:
                    for k in pk: fd[k] = best
                    moved += 1
        if not moved: break
    return fd

# ---------------------------------------------------------------- neighbours and colours
def segments(rings):
    keys = set()
    for r in rings:
        for i in range(len(r)):
            a, b = r[i], r[(i + 1) % len(r)]
            if a != b: keys.add((a, b) if a < b else (b, a))
    return keys

def neighbours(items):
    segs = {it['c']: segments(parse_rings(it['d'])) for it in items}
    nb = {it['c']: set() for it in items}
    codes = [it['c'] for it in items]
    # Neighbours share a border at least ~30 m long; touching at a corner does not count.
    for i, a in enumerate(codes):
        for b in codes[i + 1:]:
            shared = segs[a] & segs[b]
            if sum(math.dist(p, q) for p, q in shared) >= 3: nb[a].add(b); nb[b].add(a)
    return nb

def five_colours(codes, nb):
    order = sorted(codes, key=lambda c: -len(nb[c]))
    col = {}
    sys.setrecursionlimit(10000)
    def go(i):
        if i == len(order): return True
        c = order[i]
        for k in range(5):
            if all(col.get(n) != k for n in nb[c]):
                col[c] = k
                if go(i + 1): return True
                del col[c]
        return False
    assert go(0)
    return col

def label_point(g):
    poly = max(polys_of(g), key=lambda q: q.area)
    pt = polylabel(poly, tolerance=1.0)
    return [round(pt.x), round(pt.y)], round(2 * poly.boundary.distance(pt), 1)

# ---------------------------------------------------------------- context: neighbours and Cambodia
NEIGHBOUR_PROVINCES = [
    ('80', 'Tây Ninh'), ('75', 'Đồng Nai'), ('82', 'Đồng Tháp'), ('68', 'Lâm Đồng'), ('86', 'Vĩnh Long'),
    ('92', 'Cần Thơ'),
]
def load_context(db, world_atlas, city, ext):
    provs = []
    for code, name in NEIGHBOUR_PROVINCES:
        paths = glob.glob(str(Path(db) / f'json/geojson/{code}_*/{code}_*.geojson'))
        if not paths: print('  (no file for', name, ')'); continue
        g, _ = load_feature(paths[0])
        gp = clean(proj(clean(g))).intersection(ext)
        if gp.is_empty: continue
        provs.append({'code': code, 'n': name, 'geom': gp})
    # Natural Earth's Cambodia, trimmed where it overlaps the Vietnamese provinces.
    T = json.loads((Path(world_atlas) / 'countries-50m.json').read_text())
    sc, tr = T['transform']['scale'], T['transform']['translate']
    arcs = []
    for a in T['arcs']:
        x = y = 0; pts = []
        for dx, dy in a:
            x += dx; y += dy; pts.append((px(x * sc[0] + tr[0]), py(y * sc[1] + tr[1])))
        arcs.append(pts)
    def ring(ix):
        out = []
        for i in ix:
            seg = arcs[i] if i >= 0 else arcs[~i][::-1]
            out.extend(seg if not out else seg[1:])
        return out
    kh = next(g for g in T['objects']['countries']['geometries'] if g.get('id') == '116')
    polys = kh['arcs'] if kh['type'] == 'MultiPolygon' else [kh['arcs']]
    kh_geom = unary_union([Polygon(ring(p[0]), [ring(h) for h in p[1:]]).buffer(0) for p in polys]).intersection(ext)
    vn = unary_union([city] + [p['geom'] for p in provs]).buffer(0)
    kh_geom = kh_geom.difference(vn).buffer(0)
    # Overlaps between neighbours and the city: the city's own shapes win.
    for p in provs: p['geom'] = p['geom'].difference(city).buffer(0)
    # Slivers between shapes from different sources: fill where both sides are close.
    near = 40      # units ≈ 400 m
    others = unary_union([p['geom'] for p in provs] + [kh_geom])
    filler = city.buffer(near).intersection(others.buffer(near)).difference(city).difference(others)
    filler = unary_union([q for q in polys_of(filler) if q.area < 2e5])
    land = unary_union([others, filler]).buffer(0)
    land = land.simplify(3, preserve_topology=True)
    print(f'context: {len(provs)} provinces + Cambodia; sliver filler {km2(filler):.2f} km²')
    # Province borders among the neighbours (and with the city, drawn by the city's own outline).
    pb = unary_union([p['geom'].boundary for p in provs])
    pb = pb.difference(land.boundary.buffer(8)).difference(city.buffer(8))
    intl = kh_geom.boundary.difference(land.boundary.buffer(8)).difference(city.buffer(8))
    pb = pb.difference(intl.buffer(8))
    return provs, kh_geom, land, pb.simplify(3), intl.simplify(3)

# ---------------------------------------------------------------- main
def main(db, adm2, world_atlas, mapping):
    units = load_units(db)
    load_mapping(mapping, units)
    ext = box(px(EXT_LON[0]), py(EXT_LAT[1]), px(EXT_LON[1]), py(EXT_LAT[0]))
    city0 = unary_union([u['geom'] for u in units]).buffer(0)
    dists = load_districts(adm2, city0)
    print(f'former districts: {len(dists)}')

    # 1–2. Faces of one network, with the old district lines added inside the units they cut.
    cuts = assign_districts(units, dists)
    split = [u for u in units if u['split']]
    print(f'units cut by a former district line: {len(split)}')
    faces, owner = rebuild_faces(units, cuts)
    fd = district_of_faces(units, dists, faces, owner)

    # Atoms: one piece per (unit, district). They tile the city exactly, so they simplify as one coverage.
    atoms = {}
    for k, f in enumerate(faces):
        if owner[k] is None: continue
        atoms.setdefault((owner[k], fd[k]), []).append(f)
    keys = list(atoms)
    geoms = [unary_union(atoms[k]).buffer(0) for k in keys]
    assert shapely.coverage_is_valid(geoms), 'atoms do not form a coverage'
    print(f'atoms: {len(geoms)}; vertices before {int(shapely.get_num_coordinates(geoms).sum()):,}')
    simp = list(shapely.coverage_simplify(geoms, tolerance=TOLERANCE))
    print(f'vertices after {int(shapely.get_num_coordinates(simp).sum()):,}')
    # Specks: a piece under ~500 m² that touches another atom (a sliver from a hairline gap in the
    # source, cut off by the simplification) joins the atom it shares most border with. Islets in
    # the sea touch nothing and stay.
    speck = 500 / M_PER_UNIT ** 2
    pieces = [(a, q) for a, g in enumerate(simp) for q in polys_of(g)]
    ptree = STRtree([q for _, q in pieces])
    goes = {}
    for n, (a, q) in enumerate(pieces):
        if q.area >= speck: continue
        best, bl = None, 0
        for m in ptree.query(q.buffer(0.5)):
            b, r = pieces[m]
            if m == n or b == a: continue
            l = q.boundary.intersection(r.boundary).length
            if l > bl: best, bl = b, l
        if best is not None: goes[n] = best
    if goes:
        simp = [unary_union([q for n, (a, q) in enumerate(pieces) if goes.get(n, a) == t]).buffer(0) for t in range(len(simp))]
    print(f'specks moved to the neighbour they touch: {len(goes)}')

    # Units and districts from their atoms.
    by_unit, by_dist = {}, {}
    for (ui, di), g in zip(keys, simp):
        by_unit.setdefault(ui, []).append(g); by_dist.setdefault(di, []).append(g)
    for ui, u in enumerate(units):
        u['final'] = unary_union(by_unit[ui]).buffer(0)
        # Share of the unit in each former district, from the pieces actually drawn.
        parts = [(km2(g), di) for (uj, di), g in zip(keys, simp) if uj == ui]
        tot = sum(a for a, _ in parts)
        u['parts'] = sorted(((a / tot, di) for a, di in parts), reverse=True)
        u['dist'] = u['parts'][0][1]
    for di, d in enumerate(dists):
        d['final'] = unary_union(by_dist.get(di, [])).buffer(0)
        d['area'] = km2(d['final'])
        gba = km2(d['gb'].intersection(city0))
        d['dev'] = d['area'] / gba - 1
    city = unary_union([u['final'] for u in units]).buffer(0)

    # Report the cut units. A district the unit took only a sliver from may get no piece at all
    # (the 2020 lines do not show it); the unit's card still names it.
    name_of = {i: d['n'] for i, d in enumerate(dists)}
    for u in units:
        drawn = [di for _, di in u['parts']]
        u['minor'] = [i for i in u['allowed'] if i not in drawn]
        if u['split']:
            print('  cut:', u['full'], ' / '.join(f"{name_of[di]} {s:.0%}" for s, di in u['parts']),
                  ('| no piece drawn for ' + ', '.join(name_of[i] for i in u['minor'])) if u['minor'] else '')
    for d in dists:
        if abs(d['dev']) > 0.03: print(f"  district area vs geoBoundaries: {d['n']} {d['dev']:+.1%}")

    # Order: the former districts as listed above (the national code list), units by their code.
    dorder = list(range(len(dists)))
    for n, di in enumerate(dorder, 1): dists[di]['stt'] = n
    uorder = sorted(range(len(units)), key=lambda i: (dists[units[i]['dist']]['stt'], units[i]['code']))
    for n, ui in enumerate(uorder, 1): units[ui]['stt'] = n

    # Côn Đảo lies far out at sea; the home view frames the mainland.
    cd = next(u for u in units if u['type'] == 'đặc khu')
    mainland = city.difference(cd['final'].buffer(100))
    to_box = lambda b: [round(b[0]), round(b[1]), round(b[2] - b[0]), round(b[3] - b[1])]

    # 3. Encode both levels.
    def facts(g):
        d = encode(rings_of(g))
        rings = parse_rings(d)
        main = max(rings, key=ring_area)
        lab, sz = label_point(g)
        return {'d': d, 'box': bbox(main), 'lab': lab, 'sz': sz}
    W = []
    for ui in uorder:
        u = units[ui]
        W.append({'c': u['code'], 'n': u['name'], 'full': u['full'], 'type': u['type'], 'stt': u['stt'],
                  'r': dists[u['dist']]['stt'] - 1, 'area': u['areaOfficial'], 'areaMap': round(km2(u['final']), 2),
                  'parts': [[dists[di]['id'], max(1, round(s * 100))] for s, di in u['parts']] + [[dists[i]['id'], 0] for i in u['minor']],
                  'src': u['src'], **facts(u['final'])})
    Dl = []
    for di in dorder:
        d = dists[di]
        share = lambda u: next((s for s, dj in u['parts'] if dj == di), 0)
        wards = sorted((u['stt'], u['code'], share(u)) for u in units if di in u['allowed'])
        Dl.append({'c': d['id'], 'n': d['n'], 'full': FULL_PREFIX[d['type']] + d['n'] if not d['n'].startswith('Quận') else d['n'],
                   'type': d['type'], 'stt': d['stt'], 'r': d['prov'], 'area': round(d['area'], 1),
                   'wards': [[c, max(1, round(s * 100)) if s else 0] for _, c, s in wards], 'note': D_NOTES.get(d['id'], ''),
                   **facts(d['final'])})
    # Côn Đảo is ~180 km out at sea: group views and the home view leave it out.
    for it in W + Dl:
        if it['c'] in (cd['code'], 'cdao'): it['far'] = True
    for level in (W, Dl):
        nb = neighbours(level)
        col = five_colours([it['c'] for it in level], nb)
        by = {it['c']: it for it in level}
        for it in level:
            it['nb'] = sorted(nb[it['c']], key=lambda c: by[c]['stt'])
            it['col'] = col[it['c']]
    # Typed answers must not be ambiguous within a level.
    def norm(s):
        import unicodedata
        s = s.lower().replace('đ', 'd')
        s = ''.join(ch for ch in unicodedata.normalize('NFD', s) if unicodedata.category(ch) != 'Mn')
        return re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9 ]+', ' ', s)).strip()
    for level in (W, Dl):
        ns = [norm(it['n']) for it in level]
        dup = sorted({n for n in ns if ns.count(n) > 1})
        if dup: print('  same name without tone marks (typed bare, the app accepts the one asked about):', dup)

    def group_box(items):
        bs = [it['box'] for it in items]
        x0 = min(b[0] for b in bs); y0 = min(b[1] for b in bs)
        x1 = max(b[0] + b[2] for b in bs); y1 = max(b[1] + b[3] for b in bs)
        return [x0, y0, x1 - x0, y1 - y0]
    wgroups = []
    for di in dorder:
        d = dists[di]
        items = [it for it in W if it['r'] == d['stt'] - 1]
        far = [it for it in items if not it.get('far')] or items
        lab, sz = label_point(unary_union([units[ui]['final'] for ui in range(len(units)) if units[ui]['dist'] == di]))
        wgroups.append({'id': d['id'], 'num': str(d['stt']), 'n': d['n'], 'type': d['type'], 'prov': d['prov'],
                        'bbox': group_box(far), 'lab': lab, 'sz': sz})
    dgroups = []
    for pi, pr in enumerate(PROVINCES):
        items = [it for it in Dl if it['r'] == pi]
        geom = unary_union([dists[di]['final'] for di in range(len(dists)) if dists[di]['prov'] == pi]).buffer(0)
        far = [it for it in items if not it.get('far')] or items
        lab, sz = label_point(geom.difference(cd['final'].buffer(100)) if pi == 2 else geom)
        dgroups.append({**pr, 'bbox': group_box(far), 'area': round(km2(geom), 1), 'lab': lab, 'sz': sz})

    # 4. Context.
    provs, kh, land, pb, intl = load_context(db, world_atlas, city, ext)
    land_polys = [encode(rings_of(q)) for q in polys_of(land) if q.area > 50]
    water = lambda lon, lat: not land.contains(Point(px(lon), py(lat))) and not city.contains(Point(px(lon), py(lat)))
    # Names of the neighbours, placed within ~26 km of the city: farther out the mist is solid and a
    # label would never show (Cần Thơ and Cambodia lie beyond it).
    labels = []
    reach = city.buffer(2600)
    for name, g in [(p['n'].upper(), p['geom']) for p in provs] + [('CAMBODIA', kh)]:
        near = g.intersection(reach)
        if near.area > 4e5: labels.append({'t': name, 'at': label_point(near)[0]})
        else: print(f'  no label for {name}: nothing of it within 26 km of the city')
    # (name, lon, lat, big, zoom from which it shows: the bay is narrow)
    seas = [('East Sea', 107.0, 10.12, True, 0), ('Gành Rái Bay', 107.02, 10.43, False, 0.09)]
    for t, lon, lat, big, mk in seas:
        assert water(lon, lat), t
    deco = {
        'labels': labels,
        'water': [{'t': t, 'at': P(lon, lat), 'big': big, 'minK': mk} for t, lon, lat, big, mk in seas],
        # Every quarter degree; the app thins it to every degree when zoomed far out.
        'grid': {'lon': [x / 4 for x in range(math.ceil(EXT_LON[0] * 4), math.floor(EXT_LON[1] * 4) + 1)],
                 'lat': [x / 4 for x in range(math.ceil(EXT_LAT[0] * 4), math.floor(EXT_LAT[1] * 4) + 1)]},
    }

    out = {
        'meta': {
            'proj': PROJ, 'extent': to_box(ext.bounds), 'mainland_bbox': to_box(mainland.bounds),
            'territory_bbox': to_box(city.bounds), 'cd_box': W[[it['c'] for it in W].index(cd['code'])]['box'],
            'm_per_unit': round(M_PER_UNIT, 3), 'built': date.today().isoformat(),
            'area_official': round(sum(u['areaOfficial'] for u in units), 2), 'area_map': round(km2(city), 1),
        },
        'outline': encode(rings_of(city)),
        'w': {'units': W, 'groups': wgroups},
        'd': {'units': Dl, 'groups': dgroups},
        'land': land_polys, 'pborders': encode_lines(lines_of(pb)), 'iborders': encode_lines(lines_of(intl)),
        'deco': deco,
    }
    blob = json.dumps(out, ensure_ascii=False, separators=(',', ':'))
    html = INDEX.read_text(encoding='utf-8')
    new, n = re.subn(r'(<script id="map-data" type="application/json">).*?(</script>)',
                     lambda m: m.group(1) + blob + m.group(2), html, count=1, flags=re.S)
    assert n == 1
    INDEX.write_text(new, encoding='utf-8')
    print(f'wrote {len(blob):,} bytes: units {sum(len(u["d"]) for u in W):,}, districts {sum(len(d["d"]) for d in Dl):,}, '
          f'land {sum(map(len, land_polys)):,}')
    print(f'area: official {out["meta"]["area_official"]} km², on the map {out["meta"]["area_map"]} km²')

if __name__ == '__main__':
    if len(sys.argv) != 5: sys.exit(__doc__)
    main(*sys.argv[1:])
