#!/usr/bin/env python3
import argparse
import json
from collections import defaultdict
from copy import deepcopy


MULTI_TYPES = {
    "Point": "MultiPoint",
    "LineString": "MultiLineString",
    "Polygon": "MultiPolygon",
}


def flatten_geometry(geometry):
    gtype = geometry["type"]
    coords = geometry["coordinates"]

    if gtype in MULTI_TYPES:
        return MULTI_TYPES[gtype], [coords]

    if gtype.startswith("Multi"):
        return gtype, coords

    raise ValueError(f"Unsupported geometry type: {gtype}")


def merge_features(features, name_field="name", remove_fid=True):
    groups = defaultdict(list)

    for feature in features:
        props = feature.get("properties", {})
        if remove_fid:
            props.pop("fid", None)

        name = props.get(name_field)
        if not name:
            groups[id(feature)].append(feature)
        else:
            groups[name].append(feature)

    merged = []

    for _, items in groups.items():
        if len(items) == 1:
            merged.append(items[0])
            continue

        base = deepcopy(items[0])
        base_props = base.get("properties", {})

        geometry_type = None
        all_coords = []

        for feature in items:
            geom = feature.get("geometry")
            if not geom:
                continue

            multi_type, coords = flatten_geometry(geom)

            if geometry_type is None:
                geometry_type = multi_type
            elif geometry_type != multi_type:
                raise ValueError(
                    f"Cannot merge mixed geometry types for name "
                    f"'{base_props.get(name_field)}': {geometry_type} vs {multi_type}"
                )

            all_coords.extend(coords)

        base["geometry"] = {
            "type": geometry_type,
            "coordinates": all_coords,
        }

        if remove_fid:
            base_props.pop("fid", None)

        base["properties"] = base_props
        merged.append(base)

    return merged


def main():
    parser = argparse.ArgumentParser(
        description="Merge GeoJSON features with the same name into Multi geometries."
    )
    parser.add_argument("input", help="Input GeoJSON file")
    parser.add_argument("output", help="Output GeoJSON file")
    parser.add_argument("--name-field", default="name", help="Property field used for grouping")
    parser.add_argument("--keep-fid", action="store_true", help="Keep fid fields instead of removing them")

    args = parser.parse_args()

    with open(args.input, "r", encoding="utf-8") as f:
        data = json.load(f)

    if data.get("type") != "FeatureCollection":
        raise ValueError("Input must be a GeoJSON FeatureCollection")

    data["features"] = merge_features(
        data.get("features", []),
        name_field=args.name_field,
        remove_fid=not args.keep_fid,
    )

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"Done. Wrote {len(data['features'])} merged features to {args.output}")


if __name__ == "__main__":
    main()