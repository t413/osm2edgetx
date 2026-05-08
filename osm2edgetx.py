#!/usr/bin/env python3
"""
Usage:
osm2edgetx.py — Fetch and/or reprocess OSM map tiles for the yaapu EdgeTX map widget.
  python osm2edgetx.py --help
"""

import argparse, math, sys, time, pathlib
import getpass, socket, urllib.request

try:
    from PIL import Image
except ImportError:
    sys.exit("Pillow is required: pip install Pillow")

OSM_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
DEFAULT_MAX_ZOOM = 17   # OSM goes to 19; 17 is a good drone/RC detail level
FETCH_DELAY = 0.1       # seconds between requests — be polite to OSM


# ---------------------------------------------------------------------------
# Geo helpers
# ---------------------------------------------------------------------------

def tile_to_lonlat(x, y, z):
    """NW corner of tile (x, y, z) -> (lon_deg, lat_deg)"""
    n = 2 ** z
    lon = x / n * 360.0 - 180.0
    lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n))))
    return lon, lat


def lonlat_to_tile(lon, lat, z):
    """(lon_deg, lat_deg, zoom) -> (tile_x, tile_y)"""
    n = 2 ** z
    x = int((lon + 180.0) / 360.0 * n)
    lat_r = math.radians(lat)
    y = int((1.0 - math.log(math.tan(lat_r) + 1.0 / math.cos(lat_r)) / math.pi) / 2.0 * n)
    return x, y


def tiles_for_radius(lat, lon, radius_km, z):
    """Return (x_min, x_max, y_min, y_max) tile range covering a circle of radius_km around (lat, lon) at zoom z"""
    delta_lat = radius_km / 111.0
    delta_lon = radius_km / (111.0 * math.cos(math.radians(lat)))

    x0, y0 = lonlat_to_tile(lon - delta_lon, lat + delta_lat, z)  # NW
    x1, y1 = lonlat_to_tile(lon + delta_lon, lat - delta_lat, z)  # SE
    n = 2 ** z
    return (
        max(0, min(x0, x1)),
        min(n - 1, max(x0, x1)),
        max(0, min(y0, y1)),
        min(n - 1, max(y0, y1)),
    )


def zoom_start_for_radius(radius_km, max_zoom):
    """Find the lowest useful zoom: first level where the area fits in ~4 tiles, then back off one step so the overview is visible."""
    for z in range(1, max_zoom + 1):
        tile_km = 40075.0 / (2 ** z)
        if tile_km < radius_km * 4:
            return max(1, z - 1)
    return 1


# ---------------------------------------------------------------------------
# Fetch
# ---------------------------------------------------------------------------

def make_user_agent():
    try:
        user = getpass.getuser()
    except Exception:
        user = "unknown"
    try:
        ip = socket.gethostbyname(socket.gethostname())
    except Exception:
        ip = "unknown"
    return f"osm-converter/1.0 (timo@t413.com) for {user}/{ip}"


def _fmt_bytes(n):
    if n < 1024:
        return f"{n} B"
    if n < 1024 ** 2:
        return f"{n / 1024:.1f} KB"
    return f"{n / 1024 ** 2:.2f} MB"


def fetch_tiles(lat, lon, radius_km, max_zoom, osm_root: pathlib.Path, dry_run: bool):
    ua = make_user_agent()
    headers = {"User-Agent": ua}
    z_start = zoom_start_for_radius(radius_km, max_zoom)

    print(f"  User-Agent : {ua}")
    print(f"  Center     : {lat}, {lon}")
    print(f"  Radius     : {radius_km} km")
    print(f"  Zoom range : {z_start}–{max_zoom}")
    print()

    total_bytes = 0
    fetched = skipped = errors = 0

    for z in range(z_start, max_zoom + 1):
        x_min, x_max, y_min, y_max = tiles_for_radius(lat, lon, radius_km, z)
        count = (x_max - x_min + 1) * (y_max - y_min + 1)
        print(f"  z={z:2d}  x=[{x_min}..{x_max}]  y=[{y_min}..{y_max}]  ({count} tiles)")

        for x in range(x_min, x_max + 1):
            for y in range(y_min, y_max + 1):
                dest = osm_root / str(z) / str(x) / f"{y}.png"
                if dest.exists():
                    skipped += 1
                    continue

                url = OSM_URL.format(z=z, x=x, y=y)
                if dry_run:
                    print(f"    [dry-run] GET {url}")
                    fetched += 1
                    continue

                dest.parent.mkdir(parents=True, exist_ok=True)
                try:
                    req = urllib.request.Request(url, headers=headers)
                    with urllib.request.urlopen(req, timeout=15) as resp:
                        data = resp.read()
                    dest.write_bytes(data)
                    total_bytes += len(data)
                    fetched += 1
                    print(f"    + z={z} x={x} y={y}  {len(data)//1024}KB  [total {_fmt_bytes(total_bytes)}]")
                    time.sleep(FETCH_DELAY)
                except Exception as exc:
                    print(f"    ERROR z={z} x={x} y={y}: {exc}", file=sys.stderr)
                    errors += 1

    print()
    print(f"  Fetch done.  fetched={fetched}  skipped={skipped}  errors={errors}  downloaded={_fmt_bytes(total_bytes)}")
    return fetched, skipped, errors, total_bytes


# ---------------------------------------------------------------------------
# Convert / resize
# ---------------------------------------------------------------------------

def process_tiles(osm_root: pathlib.Path, qgis_root: pathlib.Path, max_dim: int, dry_run: bool):
    converted = skipped = errors = 0

    def int_key(p):
        return int(p.name) if p.name.isdigit() else -1

    for z_dir in sorted(osm_root.iterdir(), key=int_key):
        if not z_dir.is_dir() or not z_dir.name.isdigit():
            continue
        z = int(z_dir.name)

        for x_dir in sorted(z_dir.iterdir(), key=int_key):
            if not x_dir.is_dir() or not x_dir.name.isdigit():
                continue
            x = int(x_dir.name)

            for src in sorted(x_dir.glob("*.png"), key=lambda p: int(p.stem) if p.stem.isdigit() else -1):
                if not src.stem.isdigit():
                    continue
                y = int(src.stem)
                dest = qgis_root / str(z) / str(x) / f"{y}.png"

                if dest.exists():
                    skipped += 1
                    continue

                if dry_run:
                    print(f"  [dry-run] z={z} x={x} y={y}  {src} -> {dest}")
                    converted += 1
                    continue

                dest.parent.mkdir(parents=True, exist_ok=True)
                try:
                    with Image.open(src) as img:
                        w, h = img.size
                        if max(w, h) != max_dim:
                            scale = max_dim / max(w, h)
                            img = img.resize(
                                (max(1, round(w * scale)), max(1, round(h * scale))),
                                Image.LANCZOS,
                            )
                        img.save(dest, "PNG", optimize=True)
                    print(f"  converted z={z} x={x} y={y}")
                    converted += 1
                except Exception as exc:
                    print(f"  ERROR z={z} x={x} y={y}: {exc}", file=sys.stderr)
                    errors += 1

    return converted, skipped, errors


# ---------------------------------------------------------------------------
# Coverage report
# ---------------------------------------------------------------------------

def report_coverage(osm_root: pathlib.Path):
    if not osm_root.is_dir():
        return
    print()
    print("OSM TILE COVERAGE")
    for z_dir in sorted(osm_root.iterdir(), key=lambda p: int(p.name) if p.name.isdigit() else -1):
        if not z_dir.is_dir() or not z_dir.name.isdigit():
            continue
        z = int(z_dir.name)

        count = sum(1 for x_dir in z_dir.iterdir() if x_dir.is_dir()
                    for src in x_dir.glob("*.png") if src.stem.isdigit())
        if not count:
            continue

        tile_km = 40075.0 / (2 ** z)          # tile height in km (latitude)
        area_km2 = count * tile_km * tile_km   # each tile is tile_km × tile_km at equator
        print(f"  zoom {z:2d}:  {count:5d} tiles,  {area_km2:.1f} sq-km")

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Fetch OSM tiles and/or convert them for the yaapu EdgeTX map widget.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--osm", required=True, metavar="PATH",
                        help="Root directory for raw OSM tiles (z/x/y.png)")
    parser.add_argument("--qgis", metavar="PATH",
                        help="Output directory for resized QGIS tiles (optional)")
    parser.add_argument("--resize", type=int, default=100, metavar="PX",
                        help="Max tile dimension in pixels for QGIS output (default: 100)")

    fetch_group = parser.add_argument_group("fetch options")
    fetch_group.add_argument("--fetch", metavar="LAT,LON",
                             help="Fetch tiles centred on this coordinate, e.g. '47.6,-122.3'")
    fetch_group.add_argument("--radius", type=float, default=1.0, metavar="KM",
                             help="Fetch radius in km (default: 1)")
    fetch_group.add_argument("--zoom", type=int, default=DEFAULT_MAX_ZOOM, metavar="Z",
                             help=f"Maximum zoom level to fetch (default: {DEFAULT_MAX_ZOOM})")

    parser.add_argument("--dry-run", action="store_true",
                        help="Print what would be done without writing any files")
    parser.add_argument("--noreport", action="store_true", help="Don't print coverage report")
    args = parser.parse_args()

    if not args.fetch and not args.qgis:
        parser.error("Nothing to do: specify --fetch and/or --qgis.")

    osm_root = pathlib.Path(args.osm)
    if not args.dry_run:
        osm_root.mkdir(parents=True, exist_ok=True)

    # ── FETCH ────────────────────────────────────────────────────────────────
    if args.fetch:
        try:
            lat_s, lon_s = args.fetch.split(",")
            lat, lon = float(lat_s.strip()), float(lon_s.strip())
        except ValueError:
            parser.error("--fetch must be 'LAT,LON', e.g. '47.6,-122.3'")

        print("=" * 60)
        print("FETCH")
        print("=" * 60)
        fetch_tiles(lat, lon, args.radius, args.zoom, osm_root, args.dry_run)

    # ── CONVERT ──────────────────────────────────────────────────────────────
    if args.qgis:
        qgis_root = pathlib.Path(args.qgis)
        if not args.dry_run:
            qgis_root.mkdir(parents=True, exist_ok=True)

        print()
        print("=" * 60)
        print("CONVERT / RESIZE")
        print("=" * 60)
        print(f"  OSM source : {osm_root}")
        print(f"  QGIS dest  : {qgis_root}")
        print(f"  Resize to  : {args.resize}px")
        if args.dry_run:
            print("  (dry run — no files written)")
        print()

        converted, skipped, errors = process_tiles(osm_root, qgis_root, args.resize, args.dry_run)
        print()
        print(f"  Convert done.  converted={converted}  skipped={skipped}  errors={errors}")

    if not args.noreport:
        report_coverage(osm_root)
    print()
    print("All done.")


if __name__ == "__main__":
    main()
