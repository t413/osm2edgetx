# osm2edgetx: Map tiles for your flight controller 🗺

[![GitHub](https://img.shields.io/badge/GitHub-t413/osm2edgetx-black?style=flat-square&logo=github)](https://github.com/t413/osm2edgetx)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)
[![Python 3.8+](https://img.shields.io/badge/Python-3.8+-blue?style=flat-square)](https://www.python.org/)

Fetch OpenStreetMap tiles and prepare them for the [yaapu EdgeTX map widget](https://github.com/yaapu/HorusMappingWidget). Automated grid downloads, smart zoom pyramids, and automatic resizing—all in one tool.

[<img src="https://t413.com/p/projects/osm2edgetx/osm2edgetx.jpeg" width="400" alt="osm2edgetx in action">](https://t413.com/p/projects/osm2edgetx/osm2edgetx.jpeg)

*OSM maps on the HelloRadio V12*

---

## Features

- **Designed for the [yaapu EdgeTX map widget](https://github.com/yaapu/HorusMappingWidget)**
- **Smart tile fetching** from [OpenStreetMap](https://openstreetmap.org/) — specify a center point, radius, and zoom range
- **Automatic pyramid building** — starts zoomed out, steps into your requested max zoom (saves bandwidth on overview levels)
- **Incremental downloads** — re-runs skip existing tiles, safe to resume partial downloads
- **Automatic resizing** — converts 256×256 OSM tiles down to 100px (or custom) to satisfy the yaapu script requirement
- **Coverage reporting** — see exactly what area you've got cached at each zoom level
- **Single dependency** — just Pillow for image resizing (or use system ImageMagick)
- **One-shot workflow** — fetch and convert in a single command

## Installation

```bash
git clone https://github.com/t413/osm2edgetx.git
cd osm2edgetx
pip install Pillow
```

## Usage

### Fetch tiles around a location

Download a 2km radius around a coordinate, zoomed from level 12 to 13, save OSM tiles to `./tiles`, qgis output to `--qgis ./qgis_default`:

```bash
python osm2edgetx.py \
  --osm ./tiles \
  --fetch "37.87, -122.32" \
  --radius 2 \
  --zoom 13 \
  --qgis ./qgis_default
```

Output:
```
============================================================
FETCH
============================================================
  Center     : 37.87, -122.32
  Radius     : 2.0 km
  Zoom range : 12–13

  z=12  x=[656..656]  y=[1581..1582]  (2 tiles)
    + z=12 x=656 y=1581  32KB  [total 32.2 KB]
    + z=12 x=656 y=1582  28KB  [total 60.8 KB]
  z=13  x=[1312..1313]  y=[3163..3164]  (4 tiles)
    + z=13 x=1312 y=3163  14KB  [total 75.1 KB]
    + z=13 x=1312 y=3164  8KB  [total 83.7 KB]
    + z=13 x=1313 y=3163  33KB  [total 117.0 KB]
    + z=13 x=1313 y=3164  33KB  [total 150.9 KB]

  Fetch done.  fetched=6  skipped=0  errors=0  downloaded=150.9 KB

============================================================
CONVERT / RESIZE
============================================================
  OSM source : /Users/timo/Downloads/test
  QGIS dest  : /Users/timo/Downloads/qgis_test
  Resize to  : 100px

  converted z=12 x=656 y=1581
  converted z=12 x=656 y=1582
  converted z=13 x=1312 y=3163
  converted z=13 x=1312 y=3164
  converted z=13 x=1313 y=3163
  converted z=13 x=1313 y=3164

  Convert done.  converted=6  skipped=0  errors=0

OSM TILE COVERAGE
  zoom 12:      2 tiles,  191.5 sq-km
  zoom 13:      4 tiles,  95.7 sq-km

All done.
```

### Go Fly!
