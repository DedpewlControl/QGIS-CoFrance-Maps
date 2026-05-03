# QGIS-CoFrance-Maps

📁 How to use
Create folders:
input_geojson/
merged_geojson/
Drop your .geojson files into input_geojson/
Run:
python merge_geojson.py
Get merged files in:
merged_geojson/


⚠️ Notes (important in GIS context)
It only merges features with the same name AND same geometry type
If a name appears with different geometry types → it skips those conflicts (prints warning)
Works perfectly for:
MultiLineString
MultiPoint
MultiPolygon