"""One-time: build docs/data/zips.json (US ZIP -> [lat, lng]) and data/cities.json ("city|state" -> [lat, lng])
from free GeoNames data. Runs in GitHub Actions only if a file is missing.
Used for "distance from ZIP" and for events that only give a city (e.g. "Bakersfield, California").
Data: GeoNames postal codes, CC BY 4.0 (https://www.geonames.org/).
"""
import io
import json
import os
import zipfile

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "data", "zips.json")
CITIES = os.path.join(ROOT, "data", "cities.json")

if os.path.exists(OUT) and os.path.exists(CITIES):
    print("zips.json and cities.json already exist - skipping")
    raise SystemExit

r = requests.get("https://download.geonames.org/export/zip/US.zip", timeout=120)
r.raise_for_status()
z = zipfile.ZipFile(io.BytesIO(r.content))
zips, sums = {}, {}
for line in z.read("US.txt").decode("utf-8").splitlines():
    p = line.split("\t")
    if len(p) > 10 and p[9] and p[10]:
        lat, lng = float(p[9]), float(p[10])
        zips[p[1]] = [round(lat, 3), round(lng, 3)]
        for key in (f"{p[2].lower()}|{p[3].lower()}", f"{p[2].lower()}|{p[4].lower()}"):  # state name and code
            s = sums.setdefault(key, [0.0, 0.0, 0])
            s[0] += lat
            s[1] += lng
            s[2] += 1
os.makedirs(os.path.dirname(OUT), exist_ok=True)
if not os.path.exists(OUT):
    with open(OUT, "w") as f:
        json.dump(zips, f, separators=(",", ":"))
with open(CITIES, "w") as f:
    json.dump({k: [round(a / n, 3), round(b / n, 3)] for k, (a, b, n) in sums.items()}, f, separators=(",", ":"))
print(f"wrote {len(zips)} ZIP codes and {len(sums)} city keys")
