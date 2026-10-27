"""Group campsites on federal land near home, from Recreation.gov's official RIDB API.

Needs a free RIDB key (ridb.recreation.gov -> API Keys) saved as the GitHub secret RIDB_API_KEY.
Writes docs/data/group_campsites.json: one row per campground that has group sites, with
capacity, fee text, distance and the Recreation.gov booking link. Skips quietly without a key.
"""
import json
import math
import os
import re
import sys
import time

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "data", "group_campsites.json")
API = "https://ridb.recreation.gov/api/v1"
HOME = (34.1714, -118.4440)  # 91401 Van Nuys / Valley Glen
RADIUS_MI = int(os.environ.get("RIDB_RADIUS", "200"))  # ~3-4 hrs drive
GROUP = re.compile(r"\bgroup\b", re.I)


def miles(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (*a, *b))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return round(3958.8 * 2 * math.asin(math.sqrt(h)))


def get(s, path, **params):
    for attempt in range(4):
        r = s.get(f"{API}/{path}", params=params, timeout=60)
        if r.status_code == 429:
            time.sleep(5 * (attempt + 1))
            continue
        r.raise_for_status()
        return r.json()
    r.raise_for_status()


def paged(s, path, **params):
    off = 0
    while True:
        j = get(s, path, limit=50, offset=off, **params)
        rows = j.get("RECDATA", [])
        yield from rows
        off += len(rows)
        if not rows or off >= int(j.get("METADATA", {}).get("RESULTS", {}).get("TOTAL_COUNT", 0)):
            break
        time.sleep(1.3)


def attr(site, name):
    for a in site.get("ATTRIBUTES") or []:
        if a.get("AttributeName", "").lower() == name.lower():
            return a.get("AttributeValue")
    return None


def to_int(v):
    m = re.search(r"\d+", str(v or ""))
    return int(m.group()) if m else None


def fit(cap):
    if cap is None:
        return "Check capacity"
    if cap >= 60:
        return "Pack or troop"
    if cap >= 25:
        return "Troop / large den group"
    return "Small troop or patrol"


def clean(t):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", t or "")).strip()


def main():
    key = os.environ.get("RIDB_API_KEY")
    if not key:
        print("RIDB_API_KEY not set - group campsite finder skipped.")
        return
    s = requests.Session()
    s.headers.update({"apikey": key, "Accept": "application/json",
                      "User-Agent": "ScoutEventFinder/1.0 (volunteer Scout leader project)"})
    out = []
    # the API's radius/activity filters proved unreliable, so pull the state and filter here
    allf = list(paged(s, "facilities", state=os.environ.get("RIDB_STATES", "CA"), full="true"))
    facilities = [f for f in allf if f.get("FacilityLatitude") and f.get("FacilityLongitude")
                  and re.search(r"camp", f.get("FacilityTypeDescription", ""), re.I)
                  and miles(HOME, (f["FacilityLatitude"], f["FacilityLongitude"])) <= RADIUS_MI]
    print(f"  {len(allf)} facilities in state, {len(facilities)} campgrounds within {RADIUS_MI} mi")
    for f in facilities:
        lat, lng = f["FacilityLatitude"], f["FacilityLongitude"]
        try:
            sites = list(paged(s, f"facilities/{f['FacilityID']}/campsites"))
        except requests.RequestException as ex:
            print(f"  ! {f.get('FacilityName')}: {str(ex)[:100]}")
            time.sleep(1.3)
            continue
        groups = [x for x in sites if GROUP.search(f"{x.get('CampsiteType', '')} {x.get('CampsiteName', '')}")]
        if not groups:
            time.sleep(1.3)
            continue
        caps = [to_int(attr(x, "Max Num of People")) for x in groups]
        known = [c for c in caps if c]
        org = next((o.get("OrgName") for o in f.get("ORGANIZATION") or [] if o.get("OrgName")), "")
        area = next((a.get("RecAreaName") for a in f.get("RECAREA") or [] if a.get("RecAreaName")), "")
        time.sleep(1.3)  # RIDB allows ~50 requests a minute
        out.append({
            "id": f["FacilityID"],
            "name": f.get("FacilityName", "").title(),
            "area": area, "agency": org,
            "lat": lat, "lng": lng, "miles": miles(HOME, (lat, lng)),
            "groupSites": len(groups),
            "maxPeople": max(known) if known else None,
            "minPeople": min(known) if known else None,
            "fit": fit(max(known) if known else None),
            "reservable": bool(f.get("Reservable")),
            "fees": clean(f.get("FacilityUseFeeDescription"))[:300],
            "phone": f.get("FacilityPhone", ""),
            "url": f"https://www.recreation.gov/camping/campgrounds/{f['FacilityID']}",
            "about": clean(f.get("FacilityDescription"))[:400],
        })
    out = list({r["id"]: r for r in out}.values())  # the state list can repeat a facility
    out.sort(key=lambda r: r["miles"])
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump({"updated": time.strftime("%Y-%m-%d"), "home": "91401", "radiusMiles": RADIUS_MI,
               "campgrounds": out}, open(OUT, "w"), indent=1, ensure_ascii=False)
    print(f"  {len(out)} campgrounds with group sites written")


if __name__ == "__main__":
    try:
        main()
    except Exception as ex:  # noqa: BLE001 - never break the nightly run
        print(f"ridb failed: {ex}")
        sys.exit(0)
