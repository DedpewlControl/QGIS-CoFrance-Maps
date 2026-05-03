#!/usr/bin/env python3
"""
Convert AMSR .sct / .ese files to styled GeoJSON.

- .sct linework is exported as ONE single MultiLineString feature.
  Each blank-line-separated block in the .sct file becomes one line inside the
  MultiLineString coordinates array.

- .ese text labels are exported as individual MultiPoint text features.

Expected .sct line format:
    N044.04.47.414 E002.33.44.754 N044.03.30.000 E002.36.20.000 COLOR_MRVA1

Expected .ese line format:
    N043.49.48.238:E001.17.18.228:2000

Coordinates are exported as GeoJSON lon/lat in EPSG:4326.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

Coord = Tuple[float, float]

DMS_RE = re.compile(r"^([NSEW])(\d{2,3})\.(\d{2})\.(\d{2}(?:\.\d+)?)$")
SCT_RE = re.compile(
    r"^\s*"
    r"([NS]\d{2,3}\.\d{2}\.\d{2}(?:\.\d+)?)\s+"
    r"([EW]\d{2,3}\.\d{2}\.\d{2}(?:\.\d+)?)\s+"
    r"([NS]\d{2,3}\.\d{2}\.\d{2}(?:\.\d+)?)\s+"
    r"([EW]\d{2,3}\.\d{2}\.\d{2}(?:\.\d+)?)"
    r"(?:\s+(\S+))?\s*$"
)
ESE_RE = re.compile(
    r"^\s*"
    r"([NS]\d{2,3}\.\d{2}\.\d{2}(?:\.\d+)?)\s*:"
    r"\s*([EW]\d{2,3}\.\d{2}\.\d{2}(?:\.\d+)?)\s*:"
    r"\s*(.+?)\s*$"
)


def dms_to_decimal(value: str) -> float:
    """Convert SCT/ESE DMS strings like N043.49.48.238 to decimal degrees."""
    match = DMS_RE.match(value.strip())
    if not match:
        raise ValueError(f"Invalid coordinate: {value!r}")

    hemi, degrees, minutes, seconds = match.groups()
    decimal = int(degrees) + int(minutes) / 60.0 + float(seconds) / 3600.0
    if hemi in {"S", "W"}:
        decimal *= -1
    return decimal


def parse_sct_multilines(path: Path) -> List[List[Coord]]:
    """
    Parse .sct linework into MultiLineString coordinates.

    Returns:
        [
            [(lon, lat), (lon, lat), ...],  # first blank-line-separated block
            [(lon, lat), (lon, lat), ...],  # second block
            ...
        ]

    The parser preserves segment vertices exactly as pairs, including duplicated
    adjacent points, because the source linework is segment-based.
    """
    multiline: List[List[Coord]] = []
    current_line: List[Coord] = []

    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8-sig", errors="replace").splitlines(), 1
    ):
        line = raw_line.strip()

        if not line:
            if len(current_line) >= 2:
                multiline.append(current_line)
            current_line = []
            continue

        if line.startswith(";") or line.startswith("#"):
            continue

        match = SCT_RE.match(line)
        if not match:
            raise ValueError(f"Could not parse SCT line {line_number}: {raw_line!r}")

        lat1, lon1, lat2, lon2, _color_name = match.groups()
        current_line.append((dms_to_decimal(lon1), dms_to_decimal(lat1)))
        current_line.append((dms_to_decimal(lon2), dms_to_decimal(lat2)))

    if len(current_line) >= 2:
        multiline.append(current_line)

    return multiline


def parse_ese_labels(path: Path) -> List[Tuple[Coord, str]]:
    """Parse .ese text labels into ((lon, lat), text) tuples."""
    labels: List[Tuple[Coord, str]] = []

    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8-sig", errors="replace").splitlines(), 1
    ):
        line = raw_line.strip()

        if not line or line.startswith(";") or line.startswith("#"):
            continue

        match = ESE_RE.match(line)
        if not match:
            raise ValueError(f"Could not parse ESE line {line_number}: {raw_line!r}")

        lat, lon, text = match.groups()
        labels.append(((dms_to_decimal(lon), dms_to_decimal(lat)), text))

    return labels


def rgb(value: str) -> List[int]:
    """Convert '#RRGGBB' or 'R,G,B' to [R, G, B]."""
    value = value.strip()
    if "," in value:
        parts = [int(part.strip()) for part in value.split(",")]
        if len(parts) != 3 or any(part < 0 or part > 255 for part in parts):
            raise ValueError(f"Invalid RGB color: {value!r}")
        return parts

    value = value.lstrip("#")
    if not re.fullmatch(r"[0-9a-fA-F]{6}", value):
        raise ValueError(f"Invalid hex color: {value!r}")
    return [int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)]


def build_geojson(
    sct_path: Optional[Path],
    ese_path: Optional[Path],
    name: str,
    line_color: Sequence[int],
    line_width: float,
    line_opacity: float,
    text_color: Sequence[int],
    font_family: str,
    font_size: int,
    font_weight: int,
    include_z: bool,
) -> dict:
    features = []

    if sct_path:
        multiline = parse_sct_multilines(sct_path)
        if multiline:
            if include_z:
                coordinates = [
                    [[lon, lat, 0] for lon, lat in line]
                    for line in multiline
                ]
            else:
                coordinates = [
                    [[lon, lat] for lon, lat in line]
                    for line in multiline
                ]

            features.append(
                {
                    "type": "Feature",
                    "properties": {
                        "name": name,
                        "lineStyle": {
                            "color": list(line_color),
                            "width": line_width,
                            "opacity": line_opacity,
                            "dashArray": None,
                        },
                    },
                    "geometry": {
                        "type": "MultiLineString",
                        "coordinates": coordinates,
                    },
                }
            )

    if ese_path:
        for (lon, lat), text in parse_ese_labels(ese_path):
            coordinate = [lon, lat, 0] if include_z else [lon, lat]
            features.append(
                {
                    "type": "Feature",
                    "properties": {
                        "uuid": f"{name} Altitudes",
                        "textStyle": {
                            "color": list(text_color),
                            "fontFamily": font_family,
                            "fontSize": font_size,
                            "fontWeight": font_weight,
                            "text": text,
                        },
                    },
                    "geometry": {
                        "type": "MultiPoint",
                        "coordinates": [coordinate],
                    },
                }
            )

    return {"type": "FeatureCollection", "features": features}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert AMSR .sct/.ese files to styled GeoJSON. SCT lines become one MultiLineString feature."
    )
    parser.add_argument("--sct", type=Path, help="Input .sct linework file")
    parser.add_argument("--ese", type=Path, help="Input .ese text label file")
    parser.add_argument("-o", "--output", type=Path, required=True, help="Output .geojson file")
    parser.add_argument("--name", default="AMSR", help="Feature name, e.g. 'Nice AMSR' or 'LFBO AMSR'")
    parser.add_argument("--line-color", default="#2d74b3", help="Line color as #RRGGBB or R,G,B")
    parser.add_argument("--line-width", type=float, default=0.26)
    parser.add_argument("--line-opacity", type=float, default=1.0)
    parser.add_argument("--text-color", default="#2d74b3", help="Text color as #RRGGBB or R,G,B")
    parser.add_argument("--font-family", default="Arial")
    parser.add_argument("--font-size", type=int, default=16)
    parser.add_argument("--font-weight", type=int, default=600)
    parser.add_argument("--z", action="store_true", help="Include a zero Z value in every coordinate")
    parser.add_argument("--indent", type=int, default=4, help="JSON indentation. Use 0 for minified output.")
    args = parser.parse_args()

    if not args.sct and not args.ese:
        parser.error("Provide at least one of --sct or --ese")
    if args.sct and not args.sct.exists():
        parser.error(f"SCT file not found: {args.sct}")
    if args.ese and not args.ese.exists():
        parser.error(f"ESE file not found: {args.ese}")
    return args


def main() -> None:
    args = parse_args()
    data = build_geojson(
        sct_path=args.sct,
        ese_path=args.ese,
        name=args.name,
        line_color=rgb(args.line_color),
        line_width=args.line_width,
        line_opacity=args.line_opacity,
        text_color=rgb(args.text_color),
        font_family=args.font_family,
        font_size=args.font_size,
        font_weight=args.font_weight,
        include_z=args.z,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as f:
        if args.indent and args.indent > 0:
            json.dump(data, f, ensure_ascii=False, indent=args.indent)
            f.write("\n")
        else:
            json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
            f.write("\n")


if __name__ == "__main__":
    main()
