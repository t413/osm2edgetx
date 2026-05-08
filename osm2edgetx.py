#!/usr/bin/env python3
"""
osm2edgetx.py — Reprocess OSM map tiles for use with the yaapu EdgeTX map widget.
Usage:
  python osm2edgetx.py --help
"""

import argparse, math, sys, time, pathlib

try:
    from PIL import Image
except ImportError:
    sys.exit("Pillow is required: pip install Pillow")


def tile_to_lonlat(x, y, z):
    """Return (lon_deg, lat_deg) for the NW corner of OSM tile (x, y, z)."""
    n = 2 ** z
    lon = x / n * 360.0 - 180.0
    lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n))))
    return lon, lat


def process_tiles(osm_root: pathlib.Path, qgis_root: pathlib.Path, max_dim: int, dry_run: bool):
    skipped = converted = errors = 0
    start_time = time.time()

    # Walk z/x/y.png tree
    for z_dir in sorted(osm_root.iterdir()):
        if not z_dir.is_dir():
            continue
        try:
            z = int(z_dir.name)
        except ValueError:
            continue

        for x_dir in sorted(z_dir.iterdir()):
            if not x_dir.is_dir():
                continue
            try:
                x = int(x_dir.name)
            except ValueError:
                continue

            for src in sorted(x_dir.glob("*.png")):
                try:
                    y = int(src.stem)
                except ValueError:
                    continue

                # QGIS layout mirrors OSM: z/x/y.png
                dest = qgis_root / str(z) / str(x) / f"{y}.png"

                if dest.exists():
                    skipped += 1
                    continue

                if dry_run:
                    lon, lat = tile_to_lonlat(x, y, z)
                    print(f"[dry-run] Processing {src} -> {dest} ({lat:.4f}, {lon:.4f})")
                    converted += 1
                    continue

                dest.parent.mkdir(parents=True, exist_ok=True)
                print(f"Processing {src} -> {dest}")
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
                    converted += 1
                except Exception as exc:
                    print(f"ERROR {src}: {exc}", file=sys.stderr)
                    errors += 1

    duration = time.time() - start_time
    rate = converted / duration if duration > 0 else 0

    return converted, skipped, errors, duration, rate


def main():
    parser = argparse.ArgumentParser(
        description="Convert OSM tiles to EdgeTX/yaapu QGIS-compatible tiles."
    )
    parser.add_argument("--osm", required=True, metavar="PATH",
                        help="Root directory of OSM tiles (z/x/y.png)")
    parser.add_argument("--qgis", required=True, metavar="PATH",
                        help="Output directory for QGIS tiles (z/x/y.png)")
    parser.add_argument("--resize", type=int, default=100, metavar="PX",
                        help="Max dimension for output tiles in pixels (default: 100)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print what would be done without writing files")
    args = parser.parse_args()

    osm_root = pathlib.Path(args.osm)
    qgis_root = pathlib.Path(args.qgis)

    if not osm_root.is_dir():
        sys.exit(f"OSM path not found: {osm_root}")

    if not args.dry_run:
        qgis_root.mkdir(parents=True, exist_ok=True)

    print(f"OSM source : {osm_root}")
    print(f"QGIS dest  : {qgis_root}")
    print(f"Resize to  : {args.resize}px max dimension")
    if args.dry_run:
        print("(dry run — no files written)")
    print()

    converted, skipped, errors, duration, rate = process_tiles(osm_root, qgis_root, args.resize, args.dry_run)

    print(f"\nFinished in {duration:.2f} seconds.")
    print(f"Processed: {converted} files ({rate:.2f} files/sec)")
    print(f"Skipped:   {skipped} files (already exist)")
    print(f"Errors:    {errors}")


if __name__ == "__main__":
    main()
