# HCMC Map

A practice app for Hồ Chí Minh City as it has been since the merger of 1 July 2025, at two levels:
the **168 wards and communes** of today's city, and the **38 districts** they replaced. It is built
for the iPhone: install it on the Home Screen and it works offline, like a native app. It also runs
on a laptop. It is a sister app of Map Learning and works the same way.
Address: **https://johnbui765.github.io/HCMC-MAP/**

- **Two levels, one switch.** *Wards 168*: the 113 wards (phường), 54 communes (xã) and the special
  zone (đặc khu) of Côn Đảo, in force since 1 July 2025. *Districts 38*: the district-level units of
  30 June 2025, 22 from the old city, 9 from Bình Dương and 7 from Bà Rịa – Vũng Tàu. The switch is
  at the top of Learn, Table, Practice and Progress; each level keeps its own progress.
- **Grouped the way you already know the city.** Wards are grouped and numbered by the former
  district each lies in (Quận 1 first, Côn Đảo last), with the old district lines drawn over them;
  districts are grouped by the former province. Tap a group chip to fly to it.
- **The two levels are linked.** A ward's card shows its former district and what it was formed
  from, in the resolution's own list ("Phường 1, Phường 2 … (Quận 3)"); a district's card shows
  which of today's wards its land went into. Tap a name to jump to the other level.
- **Labels never overlap.** Names that don't fit wait until you zoom in; small wards show their
  number from the Table. The inner city is dense (22 wards are under 2 km²), so zoom in there.
- **Made for fingers:** pinch, double-tap to zoom in, two-finger tap to zoom out, flick to glide. If
  a tap could mean more than one small ward, the map zooms in instead of guessing.
- **Practice** as in Map Learning: Daily review, Find it, Name it, Neighbours, Rebuild and Sprint,
  over the whole city or any mix of former districts (or former provinces). Typed answers ignore
  tone marks and the words phường, xã, quận, huyện; only Thanh An (Dầu Tiếng) and Thạnh An (Cần Giờ)
  need their marks to be told apart.
- **Côn Đảo** is at its true position, about 180 km out at sea; the home view frames the mainland.
  The chip **Côn Đảo** (Districts) or the group **38 Côn Đảo** (Wards) flies there.

The app is in English; place names are in Vietnamese.

## Put it online (GitHub Pages)

1. Create a new public repository named `HCMC-MAP`.
2. Upload every file in this folder. All files sit at the top level, so there are no folders to keep.
3. In the repository, open Settings, then Pages. Under "Build and deployment", choose
   "Deploy from a branch", branch `main`, folder `/ (root)`, and save.
4. After a minute the app is at `https://johnbui765.github.io/HCMC-MAP/`.

All your apps share the address `johnbui765.github.io`, so this one keeps to itself: its identity
on your devices is `/HCMC-MAP/` (the manifest `id`), its offline cache names start with
`hcmc-map-` (and its service worker deletes only caches with that prefix), and its saved progress
is under `hcmc-map.v1`. It never touches Map Learning's cache or progress. If the repository is ever
renamed, devices treat it as a different app. Always open the address with the capital letters
exactly as above.

## Install it

- **iPhone:** open the link in Safari, tap Share, then "Add to Home Screen".
- **Laptop:** open the link in Chrome or Edge and click the install icon in the address bar.

After the first visit it works without internet.

## Your progress

Progress is stored on each device separately, for each level. To move it, open Progress, then
Details, then "Back up progress" (one file holds both levels), and use "Restore" on the other
device. "Reset this level" erases only the level on show.

## After editing any file

Change `VERSION` at the top of `sw.js` (for example to `PREFIX + 'v2'`). Otherwise installed
copies keep showing the cached version.

## Rebuilding the map data

The map data is embedded in `index.html`. `build_data.py` rebuilds it (Python 3.10+, shapely 2.1+
with GEOS 3.12+):

```sh
pip install shapely
git clone --depth 1 https://github.com/thanglequoc/vietnamese-provinces-database
git clone --depth 1 https://github.com/Dorabot-io/sap-nhap-2025
curl -LO https://media.githubusercontent.com/media/wmgeolab/geoBoundaries/main/releaseData/gbOpen/VNM/ADM2/geoBoundaries-VNM-ADM2.geojson
npm pack world-atlas@2.0.2 && tar xzf world-atlas-2.0.2.tgz
python3 build_data.py vietnamese-provinces-database geoBoundaries-VNM-ADM2.geojson package sap-nhap-2025/data/ho-chi-minh.csv
```

What it does, in short:

1. The 168 ward shapes are noded into one network of borders and rebuilt from its faces, so that
   neighbours share every edge exactly (42 did not quite match in the source).
2. Which former districts each ward came from is read from the resolution (the Dorabot table). A
   ward from one district goes to it whole; a ward from two or more is cut along the 2020 district
   line, between those districts only. The former districts are then the union of their pieces,
   so both levels share one set of borders. 17 wards came from two or more districts; 12 are cut
   on the map, and in the other 5 the 2020 lines leave no visible piece (their cards still say so).
3. Everything is simplified together to about 30 m (shapely's coverage simplification, which keeps
   shared borders shared) and written in the app's own Mercator units of about 10 m.

The script prints what it did: the cut wards and their shares, where the 2020 lines disagree with
the resolution (Phường Bình Dương and Xã Bà Điểm; the resolution wins), and districts whose area
differs from the 2020 shapes by more than 3 %.

`make_icon.py <Map Learning's icon.svg>` draws `icon.svg` from the city's outline, with Map
Learning's paper and ink. Render it at 1024 px as `icon-1024.png` (Chromium was used) and make the
smaller sizes from it; `maskable-512.png` has the outline at 77 % so it stays inside the safe zone.
`make_splash.py icon-1024.png` remakes the iPhone launch screens.

## Sources and licences

- **Wards: boundaries, names, codes and areas:** the merger map at sapnhap.bando.com.vn, as
  collected in the Vietnamese Provinces Database by Thang Le Quoc (dataset 5.2.0, MIT licence),
  github.com/thanglequoc/vietnamese-provinces-database. The site itself states no licence.
  Areas are the site's own figures (together 6,780.43 km²; Resolution 202/2025/QH15 gives the
  city 6,772.59 km²).
- **Composition of each ward** (which old wards and communes, wholly or in part, from which
  district): Resolution 1685/NQ-UBTVQH15 of 16 June 2025, as tabulated by Dorabot
  (dorabot.io/dia-chi/sap-nhap), CC BY 4.0. Names keep the resolution's spelling (Hòa, not Hoà).
- **Former districts:** district boundaries from OCHA ROAP and the Government of Viet Nam (2020),
  licensed CC BY 3.0 IGO, via geoBoundaries (www.geoboundaries.org, William & Mary geoLab), fitted
  to the wards as above. Quận 2, Quận 9 and Thủ Đức are joined as the city of Thủ Đức (1 January
  2021, Resolution 1111/NQ-UBTVQH14); Long Điền and Đất Đỏ as Long Đất (1 January 2025, Resolution
  1256/NQ-UBTVQH15). Their areas are measured on this map.
- **Numbering:** former districts in the order of the national statistical code list; wards by
  former district, then by their official code.
- **Around the city:** neighbouring provinces from the same database; Cambodia from Natural Earth
  1:50m (public domain), via world-atlas. Biển Đông is labelled East Sea, the name Vietnam uses in
  English.
- **Typeface:** Be Vietnam Pro, SIL Open Font License 1.1 (see `OFL.txt`).
