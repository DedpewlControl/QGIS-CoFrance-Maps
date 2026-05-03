import json

INPUT = "3_CCA_Nice_AMSR.geojson"
OUTPUT = "3_CCA_Nice_AMSR_merged.geojson"
TARGET_NAME = "Nice AMSR"

with open(INPUT, "r", encoding="utf-8") as f:
    data = json.load(f)

merged_lines = []
merged_properties = None
other_features = []

for feature in data["features"]:
    props = feature.get("properties", {})
    geom = feature.get("geometry", {})

    if props.get("name") == TARGET_NAME and geom.get("type") == "LineString":
        if merged_properties is None:
            merged_properties = dict(props)
            merged_properties.pop("fid", None)

        merged_lines.append(geom["coordinates"])
    else:
        props.pop("fid", None)
        other_features.append(feature)

merged_feature = {
    "type": "Feature",
    "properties": merged_properties,
    "geometry": {
        "type": "MultiLineString",
        "coordinates": merged_lines
    }
}

data["features"] = other_features + [merged_feature]

with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2)

print(f"Saved merged GeoJSON to {OUTPUT}")