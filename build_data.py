#!/usr/bin/env python3
"""Build the map data embedded in index.html (<script id="map-data">).

Two levels of Hồ Chí Minh City, as merged on 1 July 2025 (Resolution 202/2025/QH15), on a map of
the whole of Vietnam:
  w  the 168 commune-level units in force since 1 July 2025 (113 wards, 54 communes, 1 special
     zone; Resolution 1685/NQ-UBTVQH15), grouped by the former district each lies in, among the
     34 provinces of today;
  d  the 38 former district-level units of 30 June 2025 (22 of the old city, 9 of Bình Dương,
     7 of Bà Rịa – Vũng Tàu), grouped by the former province, among the 63 provinces of before.

Inputs
  <provinces-db>   a checkout of github.com/thanglequoc/vietnamese-provinces-database (MIT). Used:
                     json/geojson/79_ho_chi_minh/wards/*.geojson   the 168 units: code, name, area
                     json/geojson/*/*.geojson                      the 34 provinces: code, area
                     json/full_json_generated_data_vn_units.json   the 34 provinces: name, kind
                     dataset-generation-scripts/resources/gis/sapnhapbando_geo_objects.sql
                                                                  what each unit was formed from
                   Shapes and areas were collected from sapnhap.bando.com.vn.
  <adm2.geojson>   geoBoundaries VNM ADM2 (OCHA ROAP and the Government of Viet Nam, 2020,
                   CC BY 3.0 IGO): the former district boundaries.
  <mapping.csv>    data/ho-chi-minh.csv from github.com/Dorabot-io/sap-nhap-2025 (CC BY 4.0): every
                   old commune, its old district and the new unit it went into, wholly or in part,
                   copied from Resolution 1685/NQ-UBTVQH15.
  <vietnam63.html> the index.html of the owner's Vietnam 63 app (github.com/JohnBui765/My-country-terrain-1):
                   the 63 provinces (the same 2020 district boundaries, merged), Hoàng Sa and Trường Sa,
                   which of the 34 each went into, area and 2021 population (Statistical Yearbook of
                   Vietnam 2021), the neighbouring countries (Natural Earth, public domain) and the
                   names of seas, countries and capitals.
Requires Python 3.10+, numpy, and shapely 2.1+ with GEOS 3.12+ (pip install numpy shapely).

Usage
  python3 build_data.py <provinces-db> <adm2.geojson> <mapping.csv> <vietnam63.html>

What it does
  1. Everything is projected with Lambert's azimuthal equal-area projection centred at 16° N,
     106° E, in units of 10 m: areas are true, and distances true to 0.25% on the mainland
     (0.6% at the far end of Trường Sa).
  2. The 168 shapes are noded into one network of borders and rebuilt from its faces, so that
     neighbours share every edge exactly (42 of them did not quite match in the source).
  3. Which former districts each unit came from is read from the resolution (the mapping). A unit
     from one district goes to it whole; a unit from two or more is cut along the 2020 district
     lines, between those districts only. The former districts are then the union of their pieces,
     so both levels share one set of borders.
  4. The city's units are simplified together (shapely.coverage_simplify), so shared borders stay
     shared. The provinces around are fitted to the city's outline: gaps go to the neighbour that
     borders them, or else to the sea. The 63 are grouped into the 34 by Resolution 202/2025/QH15.
  5. Colours: the provinces take eight jade tones and each former district a family of hues for
     its wards, chosen so that no two neighbours (the city's units, and the provinces across its
     edge) are closer than ΔE 0.045 in OKLab, in normal vision and simulated red–green colour
     blindness, in light and dark mode.
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
# Lambert azimuthal equal-area, centred on Vietnam: every area keeps its true size, and lengths are
# within 0.21 % of true on the mainland and up to 0.61 % at the far end of Trường Sa (1,400 km from
# the centre). One unit is 10 m; y grows
# southward. ORIGIN puts the top-left corner of the drawn window at (0, 0); set by set_window().
import numpy as np
LAT0, LON0 = 16.0, 106.0
RADIUS = 6371008.8 / 10                    # the Earth's mean radius, in units of 10 m
ORIGIN = [0.0, 0.0]
M_PER_UNIT = 10.0
def _laea(lon, lat):
    p, l, p1 = np.radians(lat), np.radians(np.asarray(lon, dtype=float) - LON0), math.radians(LAT0)
    k = np.sqrt(2 / (1 + math.sin(p1) * np.sin(p) + math.cos(p1) * np.cos(p) * np.cos(l)))
    return RADIUS * k * np.cos(p) * np.sin(l), -RADIUS * k * (math.cos(p1) * np.sin(p) - math.sin(p1) * np.cos(p) * np.cos(l))
def xy(lon, lat):
    x, y = _laea(lon, lat)
    return x - ORIGIN[0], y - ORIGIN[1]
def P(lon, lat):
    x, y = xy(lon, lat)
    return [round(float(x)), round(float(y))]
def proj(g): return shapely.transform(g, lambda a: np.column_stack(xy(a[:, 0], a[:, 1])))
def km2(g): return g.area * 1e-4          # equal-area: one unit² is 100 m² everywhere
def imerc(m): return (2 * math.atan(math.exp(m * math.pi / 180)) - math.pi / 2) * 180 / math.pi

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
    {'num': 'I', 'en': 'Former Hồ Chí Minh City', 'short': 'Former HCMC', 'label': 'HỒ CHÍ MINH CITY', 'code': '79'},
    {'num': 'II', 'en': 'Former Bình Dương Province', 'short': 'Bình Dương', 'label': 'BÌNH DƯƠNG', 'code': '74'},
    {'num': 'III', 'en': 'Former Bà Rịa – Vũng Tàu Province', 'short': 'Bà Rịa – Vũng Tàu', 'label': 'BÀ RỊA – VŨNG TÀU', 'code': '77'},
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
D_NOTES = {
    'tduc': 'A city within the city from 1 January 2021, formed from District 2, District 9 and the old Thủ Đức District (Resolution 1111/NQ-UBTVQH14).',
    'ldat': 'Formed on 1 January 2025 by merging Long Điền and Đất Đỏ districts (Resolution 1256/NQ-UBTVQH15).',
    'pmy': 'Tân Thành District until 2018, then the town of Phú Mỹ; the 2025 resolution calls it a city.',
    'cdao': 'The Côn Đảo islands, about 180 km south of Vũng Tàu. Since 1 July 2025 the whole district has been one special zone.',
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

def label_point(g):
    poly = max(polys_of(g), key=lambda q: q.area)
    pt = polylabel(poly, tolerance=1.0)
    return [round(pt.x), round(pt.y)], round(2 * poly.boundary.distance(pt), 1)

# ---------------------------------------------------------------- the country: Vietnam 63 and 34
def load_country(vn63_html):
    """The owner's Vietnam 63 map: 63 provinces (district boundaries of OCHA ROAP and the Government
    of Viet Nam, 2020, merged into provinces), Hoàng Sa and Trường Sa at their true positions, the
    neighbouring countries (Natural Earth), and its names of seas, countries and capitals. All of it
    is in that app's Mercator units; returned in longitude and latitude."""
    h = Path(vn63_html).read_text(encoding='utf-8')
    V = json.loads(re.search(r'<script id="vn-data" type="application/json">(.*?)</script>', h, re.S).group(1))
    MP = V['meta']['proj']
    to_ll = lambda r: [(x / MP['s'] + MP['lon0'], imerc(MP['mtop'] - y / MP['s'])) for x, y in r]
    def geom(d):                                   # even-odd rings, as the apps fill them
        g = Polygon()
        for r in parse_rings(d):
            if len(r) >= 3: g = g.symmetric_difference(Polygon(to_ll(r)).buffer(0))
        return g.buffer(0)
    provs = [{**{k: p[k] for k in ('c', 'n', 'to', 'area', 'pop', 'city')}, 'll': geom(p['d'])} for p in V['provinces']]
    land = [geom(d) for d in V['land']]
    borders = [LineString(to_ll(r)) for r in parse_rings(V['borders']) if len(r) >= 2]
    deco = {k: [{'t': it['t'], 'big': bool(it.get('big')), 'll': to_ll([it['at']])[0]} for it in V['deco'].get(k, [])]
            for k in ('countries', 'water', 'capitals', 'islands')}
    assert len(provs) == 63 and len({p['to'] for p in provs}) == 34
    return provs, land, borders, deco

def set_window(provs):
    """The drawn window: Vietnam with Hoàng Sa and Trường Sa, and ~650 km around (the mist is solid
    farther out). Fixes ORIGIN so that the window starts at (0, 0)."""
    ORIGIN[0] = ORIGIN[1] = 0.0
    x0, y0, x1, y1 = proj(unary_union([p['ll'] for p in provs])).bounds
    m = 65000
    ORIGIN[0], ORIGIN[1] = x0 - m, y0 - m
    return box(0, 0, x1 - x0 + 2 * m, y1 - y0 + 2 * m)

def fit_country(provs, city, old_geoms):
    """Hồ Chí Minh City's own outline (30 m) replaces the coarse one (0.7 km) of the three provinces it
    was made from. Neighbours give up what overlaps it and take in the gaps up to it; a gap that
    touches no neighbour is sea."""
    old = set(old_geoms)
    coarse3 = unary_union([p['geom'] for p in provs if p['c'] in old]).buffer(0)
    near = [p for p in provs if p['c'] not in old and p['geom'].distance(city) < 3000]
    for p in near: p['geom'] = p['geom'].difference(city).buffer(0)
    others = unary_union([p['geom'] for p in provs if p['c'] not in old])
    gap = coarse3.difference(city).difference(others).buffer(0)
    given = sea = 0.0
    for q in polys_of(gap):
        best, bl = None, 0
        for p in near:
            l = q.buffer(1).intersection(p['geom'].boundary).length
            if l > bl: best, bl = p, l
        if best is not None and bl > 50:           # at least 500 m of border with that neighbour
            best['geom'] = unary_union([best['geom'], q]).buffer(0); given += km2(q)
        else: sea += km2(q)
    for p in provs:
        if p['c'] in old: p['geom'] = old_geoms[p['c']]
    print(f'country: HCMC fitted in; {given:.1f} km² of gap given to {len(near)} neighbouring provinces, {sea:.1f} km² left as sea')

# English, with Vietnamese names: the type follows the name ("Đồng Nai Province", "Bàn Cờ Ward"), as in
# the English the Vietnamese government uses; numbered units put it first ("District 1", "Ward 5").
def english_old_unit(full):
    m = re.match(r'^(Phường|Xã|Thị trấn|Huyện|Quận|Thành phố|Thị xã) (.+)$', full)
    if not m: return full
    kind, name = m.groups()
    word = {'Phường': 'Ward', 'Xã': 'Commune', 'Thị trấn': 'Township', 'Huyện': 'District', 'Quận': 'District',
            'Thành phố': 'City', 'Thị xã': 'Town'}[kind]
    return f'{word} {name}' if name.isdigit() else f'{name} {word}'

PROVINCE_NOTES = {
    '46': 'Thừa Thiên Huế Province until 31 December 2024; a centrally run city from 1 January 2025 (Resolution 175/2024/QH15).',
    '01': 'The capital. Took in Hà Tây Province, Mê Linh District and four communes of Lương Sơn in 2008 (Resolution 15/2008/QH12).',
}
P34_NOTES = {
    # Dates as the database's release table gives them ("effect from").
    '22': 'A centrally run city since 1 September 2026 (Resolution 36/2026/QH16), as listed in the Vietnamese Provinces Database 5.2.0.',
    '24': 'A centrally run city since 20 September 2026 (Resolution 39/2026/QH16), as listed in the Vietnamese Provinces Database 5.2.0.',
    '75': 'A centrally run city since 30 April 2026 (Resolution 30/2026/QH16), as listed in the Vietnamese Provinces Database 5.2.0.',
}

def group34(provs, db):
    """The 34 provinces and cities of 1 July 2025 (Resolution 202/2025/QH15) are whole old provinces
    joined; their areas and present status come from the Vietnamese Provinces Database 5.2.0."""
    import unicodedata
    bare = lambda s: ''.join(ch for ch in unicodedata.normalize('NFD', s.lower()) if unicodedata.category(ch) != 'Mn').replace('đ', 'd')
    full = json.load(open(Path(db) / 'json/full_json_generated_data_vn_units.json', encoding='utf-8'))
    by_name = {bare(x['Name']): x for x in full}
    area = {}
    for f in glob.glob(str(Path(db) / 'json/geojson/*/*.geojson')):
        if '/wards/' in f: continue
        g, pr = load_feature(f); area[pr['code']] = pr['areaKm2']
    groups = {}
    for p in provs:
        name = re.sub(r' (province|city|City)$', '', p['to'])
        x = by_name[bare(name)]
        p['g'] = x['Code']
        groups.setdefault(x['Code'], {'c': x['Code'], 'n': name, 'kind': 'city' if x['AdministrativeUnitShortName'] == 'Thành phố' else 'province',
                                      'area': area[x['Code']], 'members': []})['members'].append(p['c'])
    assert len(groups) == 34 and abs(sum(g['area'] for g in groups.values()) - 331325.62) < 1, sum(g['area'] for g in groups.values())
    return groups

# ---------------------------------------------------------------- colours, checked as in the jade range
# ΔE is the distance in OKLab; 0.045 is the floor for any two units that touch, in normal vision and
# in protan and deutan colour-blind vision (Machado et al. 2009, severity 1).
JADE = {'light': ['#c8ead0', '#afe1df', '#b4d9bc', '#9bd0cd', '#a2c7aa', '#89bebc', '#91b699', '#7aadaa'],
        'dark': ['#53725b', '#3d6a68', '#416149', '#295957', '#315039', '#1a4846', '#22402a', '#093837']}
DE_MIN = 0.045
CVD = {'protan': [[0.152286, 1.052583, -0.204868], [0.114503, 0.786281, 0.099216], [-0.003882, -0.048116, 1.051998]],
       'deutan': [[0.367322, 0.860646, -0.227968], [0.280085, 0.672501, 0.047413], [-0.011820, 0.042940, 0.968881]]}
def _lin(c): c /= 255; return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
def _srgb(c): c = min(1, max(0, c)); return round(255 * (12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055))
def _oklab(r, g, b):
    l = (0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b) ** (1 / 3)
    m = (0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b) ** (1 / 3)
    s = (0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b) ** (1 / 3)
    return (0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s, 1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s,
            0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s)
def lab_of(hexc, vision='normal'):
    r, g, b = (_lin(int(hexc[i:i + 2], 16)) for i in (1, 3, 5))
    if vision != 'normal':
        M = CVD[vision]; r, g, b = (max(0.0, M[i][0] * r + M[i][1] * g + M[i][2] * b) for i in range(3))
    return _oklab(r, g, b)
def dE(a, b, vision='normal'): return math.dist(lab_of(a, vision), lab_of(b, vision))
def dE_all(a, b): return min(dE(a, b, v) for v in ('normal', 'protan', 'deutan'))
def oklch(L, C, h):
    a, b = C * math.cos(math.radians(h)), C * math.sin(math.radians(h))
    l, m, s = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3, (L - 0.1055613458 * a - 0.0638541728 * b) ** 3, (L - 0.0894841775 * a - 1.2914855480 * b) ** 3
    rgb = (4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s, -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
           -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s)
    return '#' + ''.join(f'{_srgb(c):02x}' for c in rgb)

def jade_tones(codes, nb):
    """One of the eight jade tones per province, so that neighbours look as different as the tones
    allow (normal and colour-blind, both themes), spreading the tones' use."""
    pair = [[min(dE_all(JADE[th][a], JADE[th][b]) for th in JADE) if a != b else 0 for b in range(8)] for a in range(8)]
    use = [0] * 8; tone = {}
    for c in sorted(codes, key=lambda c: -len(nb[c])):
        near = [tone[n] for n in nb[c] if n in tone]
        t = max(range(8), key=lambda k: (min([pair[k][n] for n in near] or [1]), -use[k]))
        tone[c] = t; use[t] += 1
    low = min([pair[tone[a]][tone[b]] for a in tone for b in nb[a] if b in tone] or [1])
    return tone, low

THEMES = {'light': {'L': [0.86, 0.79, 0.92, 0.74, 0.95], 'C': 0.075}, 'dark': {'L': [0.50, 0.59, 0.42, 0.66, 0.37], 'C': 0.09}}
HUES = list(range(0, 360, 20))                     # eighteen hues to choose from
def option_colour(h, s, th): return oklch(THEMES[th]['L'][s], THEMES[th]['C'] * (0.85 if s >= 3 else 1), h + (7 if s % 2 else -7))
_LAB = {}
def _labs(hexc):
    if hexc not in _LAB: _LAB[hexc] = [lab_of(hexc, v) for v in ('normal', 'protan', 'deutan')]
    return _LAB[hexc]
def _de(a, b): return min(math.dist(x, y) for x, y in zip(_labs(a), _labs(b)))
OPTS = [(h, s) for h in HUES for s in range(5)]
def _tables(tones_light, tones_dark):
    """ΔE between every pair of options, and between every option and every jade tone: the smaller of
    the two themes and of the three kinds of vision."""
    T = {(a, b): min(_de(option_colour(*a, th), option_colour(*b, th)) for th in THEMES) for a in OPTS for b in OPTS}
    E = {(a, t): min(_de(option_colour(*a, 'light'), JADE['light'][t]), _de(option_colour(*a, 'dark'), JADE['dark'][t])) for a in OPTS for t in range(8)}
    return T, E

def city_colours(items, group_of, edges, families):
    """items: the city's units (dicts with c, nb). With families, the units of one former district share
    its hue and differ in shade; without, each unit has its own hue and shade. edges: code → jade tones
    of the provinces it touches. Maximises the smallest ΔE over all touching pairs (then the number of
    pairs under 0.045), by repeatedly improving the worst pair."""
    import random
    rnd = random.Random(7)
    T, E = _tables(None, None)
    by = {u['c']: u for u in items}
    pairs = sorted({tuple(sorted((u['c'], c))) for u in items for c in u['nb']})
    hue = {}; shade = {}
    G = sorted({group_of(u) for u in items})
    gnb = {g: set() for g in G}
    for a, b in pairs:
        if group_of(by[a]) != group_of(by[b]): gnb[group_of(by[a])].add(group_of(by[b])); gnb[group_of(by[b])].add(group_of(by[a]))
    for g in sorted(G, key=lambda g: -len(gnb[g])):          # first guess: neighbouring families far apart
        near = [hue[n] for n in gnb[g] if n in hue]
        hue[g] = max(HUES, key=lambda h: (min([T[((h, 0), (n, 0))] for n in near] or [1]), -sum(1 for v in hue.values() if v == h)))
    for u in sorted(items, key=lambda u: -len(u['nb'])):
        same = {shade[c] for c in u['nb'] if c in shade and group_of(by[c]) == group_of(u)}
        shade[u['c']] = next(s for s in range(5) if s not in same)
    opt = lambda c: (hue[group_of(by[c])], shade[c])
    def score():
        vals = [T[(opt(a), opt(b))] for a, b in pairs] + [E[(opt(c), t)] for c in edges for t in edges[c]]
        return (min(vals), -sum(v < DE_MIN for v in vals), -sum(max(0, DE_MIN - v) for v in vals))
    def worst():
        w = [(T[(opt(a), opt(b))], a, b) for a, b in pairs] + [(E[(opt(c), t)], c, None) for c in edges for t in edges[c]]
        return sorted(w)[:6]
    def climb(best):
        for it in range(400):
            moved = False
            for _, a, b in worst():
                cands = []
                for c in (a, b):
                    if c is None: continue
                    g = group_of(by[c])
                    same = {shade[n] for n in by[c]['nb'] if group_of(by[n]) == g}
                    cands += [('s', c, s) for s in range(5) if s != shade[c] and s not in same]
                    cands += [('h', g, h) for h in HUES if h != hue[g]]
                rnd.shuffle(cands)
                for kind, key, val in cands:
                    old = (shade if kind == 's' else hue)[key]
                    (shade if kind == 's' else hue)[key] = val
                    sc = score()
                    if sc > best: best = sc; moved = True; break
                    (shade if kind == 's' else hue)[key] = old
                if moved: break
            if not moved: return best
        return best
    best = climb(score())
    # When stuck, shake: give a few families near the worst pair a random hue, climb again, and keep
    # the result only if it is better.
    for kick in range(60):
        if best[0] >= DE_MIN + 0.006: break
        saved = (dict(hue), dict(shade))
        _, a, b = worst()[0]
        for g in rnd.sample(sorted({group_of(by[a])} | gnb[group_of(by[a])]), k=min(2, 1 + len(gnb[group_of(by[a])]))):
            hue[g] = rnd.choice(HUES)
        trial = climb(score())
        if trial > best: best = trial
        else: hue, shade = saved
    for u in items:
        u['cl'], u['cd'] = option_colour(*opt(u['c']), 'light'), option_colour(*opt(u['c']), 'dark')
    return best, len(set(hue.values()))

# ---------------------------------------------------------------- main
def main(db, adm2, mapping, vn63):
    # The country first: it fixes the drawn window, and with it the origin of every coordinate.
    provs, land_ll, borders_ll, deco_ll = load_country(vn63)
    ext = set_window(provs)
    for p in provs: p['geom'] = clean(proj(p['ll']))
    print(f'window: {ext.bounds[2] / 100:.0f} km × {ext.bounds[3] / 100:.0f} km')

    units = load_units(db)
    load_mapping(mapping, units)
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
        parts = [(km2(g), di) for (uj, di), g in zip(keys, simp) if uj == ui]
        tot = sum(a for a, _ in parts)
        u['parts'] = sorted(((a / tot, di) for a, di in parts), reverse=True)
        u['dist'] = u['parts'][0][1]
    for di, d in enumerate(dists):
        d['final'] = unary_union(by_dist.get(di, [])).buffer(0)
        d['area'] = km2(d['final'])
        d['dev'] = d['area'] / km2(d['gb'].intersection(city0)) - 1
    city = unary_union([u['final'] for u in units]).buffer(0)

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

    cd = next(u for u in units if u['type'] == 'đặc khu')
    mainland = city.difference(cd['final'].buffer(100))
    to_box = lambda b: [round(b[0]), round(b[1]), round(b[2] - b[0]), round(b[3] - b[1])]

    # 3. Encode both levels, with English names: Vietnamese name, English type.
    def facts(g):
        d = encode(rings_of(g))
        rings = parse_rings(d)
        main = max(rings, key=ring_area)
        lab, sz = label_point(g)
        return {'d': d, 'box': bbox(main), 'lab': lab, 'sz': sz}
    WORD = {'phường': 'Ward', 'xã': 'Commune', 'đặc khu': 'Special Zone'}
    W = []
    for ui in uorder:
        u = units[ui]
        W.append({'c': u['code'], 'n': u['name'], 'full': f"{u['name']} {WORD[u['type']]}", 'vi': u['full'], 'type': u['type'], 'stt': u['stt'],
                  'r': dists[u['dist']]['stt'] - 1, 'area': u['areaOfficial'], 'areaMap': round(km2(u['final']), 2),
                  'parts': [[dists[di]['id'], max(1, round(s * 100))] for s, di in u['parts']] + [[dists[i]['id'], 0] for i in u['minor']],
                  'src': [[english_old_unit(old), did, part] for old, did, part in u['src']], **facts(u['final'])})
    def d_names(d):
        if d['n'].startswith('Quận '): return d['n'].replace('Quận', 'District'), d['n'].replace('Quận', 'District'), d['n']
        en = {'quận': 'District', 'huyện': 'District', 'thành phố': 'City'}[d['type']]
        vi = {'quận': 'Quận', 'huyện': 'Huyện', 'thành phố': 'Thành phố'}[d['type']]
        return d['n'], f"{d['n']} {en}", f"{vi} {d['n']}"
    Dl = []
    for di in dorder:
        d = dists[di]
        share = lambda u: next((s for s, dj in u['parts'] if dj == di), 0)
        wards = sorted((u['stt'], u['code'], share(u)) for u in units if di in u['allowed'])
        n, full, vi = d_names(d)
        Dl.append({'c': d['id'], 'n': n, 'full': full, 'vi': vi, 'type': d['type'], 'stt': d['stt'], 'r': d['prov'], 'area': round(d['area'], 1),
                   'wards': [[c, max(1, round(s * 100)) if s else 0] for _, c, s in wards], 'note': D_NOTES.get(d['id'], ''),
                   **facts(d['final'])})
    for it in W + Dl:
        if it['c'] in (cd['code'], 'cdao'): it['far'] = True
    for level in (W, Dl):
        nb = neighbours(level)
        by = {it['c']: it for it in level}
        for it in level: it['nb'] = sorted(nb[it['c']], key=lambda c: by[c]['stt'])
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
        wgroups.append({'id': d['id'], 'num': str(d['stt']), 'n': Dl[di]['n'], 'type': d['type'], 'prov': d['prov'],
                        'bbox': group_box(far), 'lab': lab, 'sz': sz})
    dgroups, old_geoms = [], {}
    for pi, pr in enumerate(PROVINCES):
        items = [it for it in Dl if it['r'] == pi]
        geom = unary_union([dists[di]['final'] for di in range(len(dists)) if dists[di]['prov'] == pi]).buffer(0)
        old_geoms[pr['code']] = geom
        far = [it for it in items if not it.get('far')] or items
        lab, sz = label_point(geom.difference(cd['final'].buffer(100)) if pi == 2 else geom)
        dgroups.append({**pr, 'bbox': group_box(far), 'area': round(km2(geom), 1), 'lab': lab, 'sz': sz})

    # 4. The country: 63 provinces (until 30 June 2025) and the 34 they became (from 1 July 2025).
    fit_country(provs, city, old_geoms)
    g34 = group34(provs, db)
    NAME63 = {'79': 'Hồ Chí Minh', '77': 'Bà Rịa – Vũng Tàu', '46': 'Huế'}
    CAPITAL, CITY63 = '01', {'31', '48', '92', '79', '46'}
    P63 = []
    for p in provs:
        n = NAME63.get(p['c'], p['n'])
        kind = 'capital' if p['c'] == CAPITAL else 'city' if p['c'] in CITY63 else 'province'
        full = n if kind == 'capital' else f"{n} {'City' if kind == 'city' else 'Province'}"
        # The three provinces that became the city are drawn by its own units; their outline here is
        # only for taps and names, so it is kept coarse (200 m).
        g = p['geom'].simplify(20, preserve_topology=True) if p['c'] in old_geoms else p['geom']
        P63.append({'c': p['c'], 'n': n, 'full': full, 'kind': kind, 'area': p['area'], 'pop': p['pop'], 'g': p['g'],
                    'hcmc': p['c'] in old_geoms, 'note': PROVINCE_NOTES.get(p['c'], ''), **facts(g)})
    # Neighbours from the full shapes: the three that became the city are kept coarse above, and
    # coarse edges no longer coincide with their neighbours' edges.
    nb63 = neighbours([{'c': p['c'], 'd': encode(rings_of(q['geom']))} if p['hcmc'] else p for p, q in zip(P63, provs)])
    for p in P63: p['nb'] = sorted(nb63[p['c']])
    P34 = []
    for code, g in sorted(g34.items()):
        geom = unary_union([p['geom'] for p in provs if p['g'] == code]).buffer(0)
        kind = 'capital' if code == '01' else g['kind']
        full = g['n'] if kind == 'capital' else f"{g['n']} {'City' if kind == 'city' else 'Province'}"
        lab, sz = label_point(geom)
        main = max(polys_of(geom), key=lambda q: q.area)
        P34.append({'c': code, 'n': g['n'], 'full': full, 'kind': kind, 'area': g['area'], 'members': sorted(g['members']),
                    'hcmc': code == '79', 'note': P34_NOTES.get(code, ''), 'lab': lab, 'sz': sz, 'box': to_box(main.bounds)})
    by63 = {p['c']: p for p in P63}
    for q in P34:
        q['nb'] = sorted({by63[n]['g'] for m in q['members'] for n in by63[m]['nb']} - {q['c']})
    t63, l63 = jade_tones([p['c'] for p in P63 if not p['hcmc']], {p['c']: [n for n in p['nb'] if not by63[n]['hcmc']] for p in P63})
    for p in P63: p['tone'] = t63.get(p['c'], -1)
    b34 = {q['c']: q for q in P34}
    t34, l34 = jade_tones([q['c'] for q in P34 if not q['hcmc']], {q['c']: [n for n in q['nb'] if not b34[n]['hcmc']] for q in P34})
    for q in P34: q['tone'] = t34.get(q['c'], -1)
    print(f'colours, provinces: closest neighbouring provinces ΔE {l63:.3f} (63) and {l34:.3f} (34), normal and colour-blind')

    # Colours of the city's units, now that the provinces across its edge have theirs: one hue family
    # per former district for the wards, a colour per former district for the districts.
    def touching(level, tone_of):
        segs = {u['c']: segments(parse_rings(u['d'])) for u in level}
        out = {}
        for p in P63:
            if p['hcmc']: continue
            sp = segments(parse_rings(p['d']))
            for u in level:
                if segs[u['c']] & sp: out.setdefault(u['c'], set()).add(tone_of(p))
        return out
    sw, fw = city_colours(W, lambda u: u['r'], touching(W, lambda p: b34[p['g']]['tone']), True)
    sd, fd2 = city_colours(Dl, lambda d: d['c'], touching(Dl, lambda p: p['tone']), False)
    print(f'colours, wards: {fw} hue families; closest touching pair ΔE {sw[0]:.3f}, {-sw[1]} pairs under {DE_MIN} (normal and colour-blind, both themes, provinces across the edge included)')
    print(f'colours, districts: closest touching pair ΔE {sd[0]:.3f}, {-sd[1]} pairs under {DE_MIN}')
    hl = min(_de(u[k], '#ffd43b') for u in W + Dl for k in ('cl', 'cd'))
    print(f'colours: the yellow of a selected unit is at least ΔE {hl:.3f} from every fill')
    # Around Vietnam: neighbouring countries and their borders, inside the window.
    land = clean(proj(unary_union(land_ll))).intersection(ext)
    land_polys = [encode(rings_of(q)) for q in polys_of(land) if q.area > 2e4]
    bl = [proj(b).intersection(ext) for b in borders_ll]
    borders = [l for g in bl for l in lines_of(g)]
    # Names: seas, countries and capitals from Vietnam 63, kept if inside the window; the two
    # archipelagos; and the bay off Vũng Tàu, once zoomed in.
    inside = lambda pt: 0 < pt[0] < ext.bounds[2] and 0 < pt[1] < ext.bounds[3]
    pick = lambda items: [{'t': it['t'], 'at': P(*it['ll']), 'big': it['big']} for it in items if inside(P(*it['ll']))]
    def arch(code, lon_min, lat_max):
        g = next(p['geom'] for p in provs if p['c'] == code)
        isl = unary_union([q for q in polys_of(g) if q.representative_point().x > xy(lon_min, 12)[0] and q.representative_point().y > xy(108, lat_max)[1]])
        return to_box(isl.bounds)
    deco = {
        'countries': pick(deco_ll['countries']), 'water': pick(deco_ll['water']) + [{'t': 'Gành Rái Bay', 'at': P(107.02, 10.43), 'big': False, 'minK': 0.09}],
        'capitals': pick(deco_ll['capitals']), 'islands': pick(deco_ll['islands']),
        'archipelagos': [{'t': 'Hoàng Sa Archipelago', 'of': 'Đà Nẵng', 'box': arch('48', 110.5, 18)},
                         {'t': 'Trường Sa Archipelago', 'of': 'Khánh Hòa', 'box': arch('56', 110.5, 13)}],
        'grid': {'lon': list(range(96, 126)), 'lat': list(range(0, 31)), 'tropic': 23.4367},
    }
    for w in deco['water']:
        assert not city.contains(Point(w['at'])), w['t']
    vn_main = unary_union([p['geom'] for p in provs if p['c'] not in ('48', '56')] + [p['geom'].intersection(box(0, 0, xy(110, 12)[0], ext.bounds[3])) for p in provs if p['c'] in ('48', '56')])
    region = city.difference(cd['final'].buffer(100)).buffer(9000)
    out = {
        'meta': {
            'proj': {'lat0': LAT0, 'lon0': LON0, 'R': RADIUS, 'ox': ORIGIN[0], 'oy': ORIGIN[1]}, 'm_per_unit': M_PER_UNIT,
            'extent': to_box(ext.bounds), 'mainland_bbox': to_box(mainland.bounds), 'territory_bbox': to_box(city.bounds),
            'cd_box': W[[it['c'] for it in W].index(cd['code'])]['box'], 'region_bbox': to_box(region.bounds),
            'country_bbox': to_box(vn_main.bounds), 'vn_bbox': to_box(unary_union([p['geom'] for p in provs]).bounds),
            'built': date.today().isoformat(), 'area_official': round(sum(u['areaOfficial'] for u in units), 2),
            'area_city': 6772.59, 'area_vietnam': round(sum(g['area'] for g in g34.values()), 2), 'area_map': round(km2(city), 1),
            'jade': JADE,
        },
        'outline': encode(rings_of(city)),
        'w': {'units': W, 'groups': wgroups},
        'd': {'units': Dl, 'groups': dgroups},
        'p63': P63, 'p34': P34,
        'land': land_polys, 'borders': encode_lines(borders),
        'deco': deco,
    }
    blob = json.dumps(out, ensure_ascii=False, separators=(',', ':'))
    html = INDEX.read_text(encoding='utf-8')
    new, n = re.subn(r'(<script id="map-data" type="application/json">).*?(</script>)',
                     lambda m: m.group(1) + blob + m.group(2), html, count=1, flags=re.S)
    assert n == 1
    INDEX.write_text(new, encoding='utf-8')
    print(f'wrote {len(blob):,} bytes: wards {sum(len(u["d"]) for u in W):,}, districts {sum(len(d["d"]) for d in Dl):,}, '
          f'provinces {sum(len(p["d"]) for p in P63):,}, land {sum(map(len, land_polys)):,}, borders {len(out["borders"]):,}')
    print(f'area: wards listed {out["meta"]["area_official"]} km², city on the map {out["meta"]["area_map"]} km², Vietnam {out["meta"]["area_vietnam"]} km²')

if __name__ == '__main__':
    if len(sys.argv) != 5: sys.exit(__doc__)
    main(*sys.argv[1:])
