"""Build docs/data/weekend.json: everything for the next ~2 weekends near home, in one small file.

Read by the Event Finder's "This weekend" page and by the Trailbook's weekend page (any site can load it).
  scout   - Scout events (from events.json) within MAX_MILES of home, plus online ones
  public  - public programs that are not Scout events: ranger programs, star parties, kids' workshops, trail work
  alerts  - National Park closures and warnings
Each page works out "this weekend" / "next weekend" itself, so the file stays right between nightly runs.
"""
import json
import math
import os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, "docs", "data")
OUT = os.path.join(D, "weekend.json")
LA = ZoneInfo("America/Los_Angeles")
HOME = {"zip": "91401", "lat": 34.1714, "lng": -118.4440}
MAX_MILES = 200          # Scout events (covers Southern California); pages narrow this from the viewer's ZIP
MAX_PUBLIC_MILES = 300   # ranger programs at farther parks are still worth a weekend trip
DAYS = 17                # covers this weekend and next
# visitor-center points for parks whose programs come without a map point
PARK_POINT = {"Channel Islands National Park": (34.2483, -119.2668), "Santa Monica Mountains National Recreation Area": (34.0997, -118.7176),
              "Cabrillo National Monument": (32.6735, -117.2425), "Joshua Tree National Park": (34.1349, -116.3131),
              "Death Valley National Park": (36.4617, -116.8669), "Sequoia & Kings Canyon National Parks": (36.4864, -118.5658),
              "Pinnacles National Park": (36.4934, -121.1462), "Mojave National Preserve": (35.1406, -115.5103),
              "Manzanar National Historic Site": (36.7280, -118.1546)}


def load(name, default):
    try:
        with open(os.path.join(D, name)) as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def miles(lat, lng):
    if lat is None or lng is None:
        return None
    la1, lo1, la2, lo2 = map(math.radians, (HOME["lat"], HOME["lng"], lat, lng))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return round(3958.8 * 2 * math.asin(math.sqrt(h)))


def rnd(v):
    return None if v is None else round(float(v), 4)


def in_window(start, end, lo, hi):
    return start[:10] <= hi and (end or start)[:10] >= lo


def slim(e, kind):
    return {
        "kind": kind, "title": e["title"], "session": e.get("session", ""),
        "start": e["start"], "end": e.get("end", ""), "tz": e.get("tz", ""),
        "location": e.get("location", ""), "miles": e.get("_mi"), "approx": bool(e.get("approx")),
        "lat": rnd(e.get("lat")), "lng": rnd(e.get("lng")),
        "online": bool(e.get("online")), "programs": e.get("programs", []), "badges": e.get("badges", [])[:6],
        "topics": [t for t in e.get("topics", []) if t not in ("Online / Virtual",)][:4],
        "council": e.get("council", ""), "url": e.get("url", ""), "fees": e.get("fees", [])[:2],
        "trailbook": e.get("trailbook", ""),
    }


def main():
    today = datetime.now(LA).date()
    lo, hi = today.isoformat(), (today + timedelta(days=DAYS)).isoformat()
    scout = []
    for e in load("events.json", {"events": []})["events"]:
        if not in_window(e["start"], e.get("end"), lo, hi):
            continue
        if "Meetings & Admin" in e["topics"] or ("Fundraising / Dinners" in e["topics"] and not e["badges"]):
            continue
        if (e.get("end") or e["start"])[:10] > (today + timedelta(days=60)).isoformat() or \
                e["start"][:10] < (today - timedelta(days=3)).isoformat():
            continue  # long-running listings ("nominations open", "open all year") are not weekend plans
        e["_mi"] = miles(e.get("lat"), e.get("lng"))
        if e.get("online") or (e["_mi"] is not None and e["_mi"] <= MAX_MILES):
            scout.append(slim(e, "scout"))
    public = []
    for e in load("public_events.json", {"events": []})["events"]:
        if in_window(e["start"], e.get("end"), lo, hi):
            e["_mi"] = miles(e.get("lat"), e.get("lng"))
            public.append(slim(e, "public"))
    progs = load("ranger_programs.json", {"programs": []})["programs"]
    park_mi = {k: miles(*v) for k, v in PARK_POINT.items()}
    for p in progs:  # some programs have no map point; use the nearest known point in the same park
        m = miles(p.get("lat"), p.get("lng"))
        if m is not None:
            park_mi[p["park"]] = min(m, park_mi.get(p["park"]) or m)
    for p in progs:
        mi = miles(p.get("lat"), p.get("lng"))
        pt = (p.get("lat"), p.get("lng")) if mi is not None else PARK_POINT.get(p["park"], (None, None))
        mi = park_mi.get(p["park"]) if mi is None else mi
        if mi is not None and mi > MAX_PUBLIC_MILES:
            continue
        for d in p["nextDates"]:
            if lo <= d <= hi:
                public.append({
                    "kind": "ranger", "title": p["title"], "session": "", "start": d + "T00:00", "end": "",
                    "time": p.get("time", ""), "tz": "PT", "location": ", ".join(x for x in [p.get("where"), p["park"]] if x),
                    "miles": mi, "lat": rnd(pt[0]), "lng": rnd(pt[1]), "approx": False, "online": False,
                    "programs": ["Cub Scouts", "Scouts BSA"],
                    "badges": [], "topics": ["Ranger / Park Program"], "council": p["park"], "url": p["url"],
                    "fees": ["Free"] if p.get("free") else [], "trailbook": "", "parkCode": p.get("parkCode", ""),
                })
    alerts = load("park_alerts.json", {"alerts": [], "parks": {}})
    key = lambda x: (x["start"], x["title"])
    json.dump({
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"), "home": HOME, "from": lo, "to": hi,
        "scout": sorted(scout, key=key), "public": sorted(public, key=key),
        "alerts": alerts.get("alerts", []), "parks": alerts.get("parks", {}),
    }, open(OUT, "w"), separators=(",", ":"), ensure_ascii=False)
    # California ZIP points (about 60 KB) so the pages can measure from any viewer's ZIP
    z = load("zips.json", {})
    json.dump({k: v for k, v in z.items() if "90000" <= k <= "96199"}, open(os.path.join(D, "zips-ca.json"), "w"),
              separators=(",", ":"))
    print(f"  weekend.json: {len(scout)} Scout events, {len(public)} public programs, {len(alerts.get('alerts', []))} alerts")


if __name__ == "__main__":
    main()
