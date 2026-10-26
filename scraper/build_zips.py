"""One-time: build docs/data/zips.json (US ZIP -> [lat, lng]) from free GeoNames data.

Used by the website's "distance from ZIP" filter. Runs in GitHub Actions only if the file is missing.
Data: GeoNames postal codes, CC BY 4.0 (https://www.geonames.org/).
"""
import io
import json
import os
import zipfile

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "data", "zips.json")

if os.path.exists(OUT):
    print("zips.json already exists - skipping")
    raise SystemExit

r = requests.get("https://download.geonames.org/export/zip/US.zip", timeout=120)
r.raise_for_status()
z = zipfile.ZipFile(io.BytesIO(r.content))
zips = {}
for line in z.read("US.txt").decode("utf-8").splitlines():
    p = line.split("\t")
    if len(p) > 10 and p[9] and p[10]:
        zips[p[1]] = [round(float(p[9]), 3), round(float(p[10]), 3)]
os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w") as f:
    json.dump(zips, f, separators=(",", ":"))
print(f"wrote {len(zips)} ZIP codes")
