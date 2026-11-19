# HCMC Map

A practice app for Hồ Chí Minh City as it has been since the merger of 1 July 2025, at two levels:
the **168 wards and communes** of today's city, and the **38 districts** they replaced. The city sits
on an **equal-area map of the city and the provinces around it**, so you can see how big each unit
is next to the units above and below it. It is built for the iPhone: install it on the Home Screen and it works
offline, like a native app. It also runs on a laptop. It is a sister app of Map Learning and works
the same way.
Address: **https://johnbui765.github.io/HCMC-MAP/**

- **Two levels, one switch.** *Wards 168*: the 113 wards, 54 communes and the special zone of Côn
  Đảo, in force since 1 July 2025, shown with the **four provinces** around the city today. *Districts 38*: the
  district-level units of 30 June 2025, 22 from the old city, 9 from Bình Dương and 7 from Bà Rịa –
  Vũng Tàu, shown with the **nine provinces** of before that those four were formed from. The switch is at the top of Learn, Table,
  Practice and Progress; each level keeps its own progress. Practice covers the city only.
- **True sizes.** The map uses Lambert's azimuthal equal-area projection, centred on Vietnam: every
  ward, district, the city and every province keeps its true area, and across the region distances are true
  to 0.3%.
- **Zoom with two fingers.** On a phone or tablet, pinch to zoom; a tap only ever picks, at once
  (no double-tap or two-finger-tap zoom). If a tap could mean several tiny wards, the app asks you to
  pinch in rather than guess. On a laptop, use the mouse wheel (it glides) or the + and − buttons.
- **Smooth flights.** Every jump (a chip, a card, the ⤢ button) is one continuous flight that zooms
  out, across and back in, so you never lose your place. The seams between wards fade as you zoom
  away, then the former district lines; from far out the city is one name.
- **Sizes and bearings.**
  - Each card has a **Size** row: squares drawn to scale, each inside the next bigger unit (for
    example, *District 1: 1/870 of the city's area*).
  - A unit too small to see at the present zoom is ringed.
  - A tiny **compass** at the top right points to true north (on this projection north leans away
    from straight up, by less than 1° across the region, and the needle follows it).
- **Clean view.** The eye button at the bottom right (or H on a keyboard) hides the controls: the top
  card, the chips, the zoom and ⤢ buttons and the tab bar. The map, its taps and its cards keep working, and
  a practice question stays on screen. Tap the eye again to bring the controls back.
- **Mist like Map Learning's.** Drawn by the graphics chip over the whole screen: clear over the city, the
  provinces around it and the sea within 60 km of them, covering everything from about 240 km out,
  at every zoom and with no edges.
- **Grouped the way you already know the city.** Wards are grouped and numbered by their former
  district (District 1 first, Côn Đảo last). Each former district has a hue at least 40° around the
  colour wheel from its neighbours', and its wards are shades of it, separated by soft white seams;
  the borders between groups are slate lines. Tap a chip to fly to a group: the rest of the city turns grey and only that group is named.
  At the Districts level, picking a district greys out the rest the same way. 12 wards straddle two
  former districts; each is grouped with the one holding most of it, and the true old border is
  drawn dotted where it differs (85 km in all). Districts are grouped by former province.
- **Only the region.** The provinces around the city are in jade: Lâm Đồng, Đồng Nai, Tây Ninh and
  Đồng Tháp with the wards; the nine they were formed from with the districts (Lâm Đồng, Đắk Nông,
  Bình Thuận; Đồng Nai, Bình Phước; Tây Ninh, Long An; Đồng Tháp, Tiền Giang). The rest of Vietnam
  is plain land, like the neighbouring countries, unnamed and not tappable. Zooming out stops once
  the whole region shows, and the map can't be dragged more than 150 km past it.
- **The provinces' cards.** In Learn, tap one for its card: area, what it was formed from or
  became, population (63 provinces, 2021), its size next to the city, and its neighbours (those on
  the map as buttons, the others named).
- **The two levels are linked.** A ward's card shows its former district and what it was formed
  from, in the resolution's own list; a district's card shows which of today's wards its land went
  into. Tap a name to jump to the other level.
- **Labels never overlap.** Names that don't fit wait until you zoom in; small wards show their
  number from the Table. The inner city is dense (22 wards are under 2 km²), so zoom in there.
- **Practice** as in Map Learning: Daily review, Find it, Name it, Neighbours, Rebuild and Sprint,
  over the whole city or any mix of former districts (or former provinces). Typed answers ignore
  tone marks and the type words in Vietnamese or English (phường, xã, quận, huyện; ward, commune,
  district, city); only Thanh An (Dầu Tiếng) and Thạnh An (Cần Giờ) need their marks to be told apart.
- **Côn Đảo** is at its true position, about 180 km out at sea; the home view frames the mainland.

Place names are in Vietnamese with English type words (Bàn Cờ Ward, District 1, Bình Thạnh
District, Thủ Đức City, Đồng Nai Province); everything else is in English.

## Put it online (GitHub Pages)

1. Create a new public repository named `HCMC-MAP` (or open the one you already have).
2. Upload every file in this folder, replacing the old ones. All files sit at the top level.
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

After the first visit it works without internet. A phone that has an older version installed picks
up this one the next time the app is opened online (the cache is now `hcmc-map-v5`); progress is
kept.

## Your progress

Progress is stored on each device separately, for each level. To move it, open Progress, then
Details, then "Back up progress" (one file holds both levels), and use "Restore" on the other
device. "Reset this level" erases only the level on show.

## After editing any file

Change `VERSION` at the top of `sw.js` (for example to `PREFIX + 'v6'`). Otherwise installed
copies keep showing the cached version.

## Rebuilding the map data

The map data is embedded in `index.html`. `build_data.py` rebuilds it (Python 3.10+, numpy, and
shapely 2.1+ with GEOS 3.12+):

```sh
pip install numpy shapely
git clone --depth 1 https://github.com/thanglequoc/vietnamese-provinces-database
git clone --depth 1 https://github.com/Dorabot-io/sap-nhap-2025
git clone --depth 1 https://github.com/JohnBui765/My-country-terrain-1
curl -LO https://media.githubusercontent.com/media/wmgeolab/geoBoundaries/main/releaseData/gbOpen/VNM/ADM2/geoBoundaries-VNM-ADM2.geojson
python3 build_data.py vietnamese-provinces-database geoBoundaries-VNM-ADM2.geojson sap-nhap-2025/data/ho-chi-minh.csv My-country-terrain-1/index.html
```

What it does, in short:

1. Everything is projected with Lambert's azimuthal equal-area projection centred at 16° N,
   106° E, in units of 10 m.
2. The 168 ward shapes are noded into one network of borders and rebuilt from its faces, so that
   neighbours share every edge exactly (42 did not quite match in the source).
3. Which former districts each ward came from is read from the resolution (the Dorabot table). A
   ward from one district goes to it whole; a ward from two or more is cut along the 2020 district
   line, between those districts only. The former districts are then the union of their pieces,
   so both levels share one set of borders. 17 wards came from two or more districts; 12 are cut
   on the map, and in the other 5 the 2020 lines leave no visible piece (their cards still say so).
   Slivers outside the city's outline are left out, and specks under ~500 m² join the unit they
   touch. The city's units are simplified together to about 10 m, so close up the borders follow
   their real curves.
4. The 63 provinces come from the Vietnam 63 app and are fitted to the city's outline: the
   neighbours give up what overlaps it and take in the gaps up to it (a gap that touches no
   neighbour is sea). They are grouped into the 34 by Resolution 202/2025/QH15.
5. Colours: each former district gets a hue at least 40° from its neighbours' and its wards shades
   of it. Neighbours in different former districts, wards and the provinces across the city's edge,
   and neighbouring provinces are at least ΔE 0.045 apart (OKLab); wards inside one former district
   at least 0.025, by design; the grey around a picked district at least 0.045 from every colour.
   All of it holds in normal vision and simulated red–green colour blindness, in light and dark mode.
   In the app, five of the provinces around the city take another of the eight tones (Lâm Đồng and
   Đồng Tháp with the wards; Bình Thuận, Tiền Giang and Đồng Tháp with the districts), so that they
   also stand 0.045 apart from the plain land beyond the region.

The script prints what it did: the cut wards and their shares, where the 2020 lines disagree with
the resolution (Phường Bình Dương and Xã Bà Điểm; the resolution wins), districts whose area
differs from the 2020 shapes by more than 3 %, how the city was fitted in, and the colour checks.

`make_icon.py <Map Learning's icon.svg>` draws `icon.svg` from the city's outline, with Map
Learning's paper and ink. Render it at 1024 px as `icon-1024.png` (Chromium was used) and make the
smaller sizes from it; `maskable-512.png` has the outline at 77 % so it stays inside the safe zone.
`make_splash.py icon-1024.png` remakes the iPhone launch screens.

## Sources and licences

- **Wards: boundaries, names, codes and areas:** the merger map at sapnhap.bando.com.vn, as
  collected in the Vietnamese Provinces Database by Thang Le Quoc (dataset 5.2.0, MIT licence,
  see `LICENSE-vietnamese-provinces-database.txt`),
  github.com/thanglequoc/vietnamese-provinces-database. The site itself states no licence.
  Areas are the site's own figures (together 6,780.43 km²; Resolution 202/2025/QH15 gives the
  city 6,772.59 km²).
- **Composition of each ward** (which old wards and communes, wholly or in part, from which
  district): Resolution 1685/NQ-UBTVQH15 of 16 June 2025, as tabulated by Dorabot
  (dorabot.io/dia-chi/sap-nhap), CC BY 4.0. Names keep the resolution's spelling (Hòa, not Hoà).
- **Former districts:** district boundaries from OCHA ROAP and the Government of Viet Nam (2020),
  licensed CC BY 3.0 IGO, via geoBoundaries (www.geoboundaries.org, William & Mary geoLab), fitted
  to the wards as above. District 2, District 9 and Thủ Đức District are joined as Thủ Đức City
  (1 January 2021, Resolution 1111/NQ-UBTVQH14); Long Điền and Đất Đỏ as Long Đất (1 January 2025,
  Resolution 1256/NQ-UBTVQH15). Their areas are measured on this map.
- **Provinces:** the 63 from the Vietnam 63 app (the same 2020 district boundaries, merged, with
  Hoàng Sa and Trường Sa at their true positions). The data holds them all; the app shows only the
  provinces around the city and draws the rest as plain land. Their areas and 2021 populations are from the
  Statistical Yearbook of Vietnam 2021. The 34 are grouped as in Resolution 202/2025/QH15, with the
  areas, names and status listed in the Vietnamese Provinces Database 5.2.0. As it records, Đồng
  Nai (30 April 2026), Quảng Ninh (1 September 2026) and Bắc Ninh (20 September 2026) have since
  become centrally run cities (Resolutions 30, 36 and 39/2026/QH16); the map follows it.
- **Numbering:** former districts in the order of the national statistical code list; wards by
  former district, then by their official code.
- **Around Vietnam:** the neighbouring countries from Natural Earth (public domain), via the Vietnam
  63 app. Biển Đông is labelled East Sea, the name Vietnam uses in English.
- **Typeface:** Be Vietnam Pro, SIL Open Font License 1.1 (see `OFL.txt`).
