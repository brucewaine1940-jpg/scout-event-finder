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
MAX_MILES = 120          # Scout events; the pages let people narrow this
MAX_PUBLIC_MILES = 300   # ranger programs at farther parks are still worth a weekend trip
DAYS = 17                # covers this weekend and next


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


def in_window(start, end, lo, hi):
    return start[:10] <= hi and (end or start)[:10] >= lo


def slim(e, kind):
    return {
        "kind": kind, "title": e["title"], "session": e.get("session", ""),
        "start": e["start"], "end": e.get("end", ""), "tz": e.get("tz", ""),
        "location": e.get("location", ""), "miles": e.get("_mi"), "approx": bool(e.get("approx")),
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
    for p in load("ranger_programs.json", {"programs": []})["programs"]:
        mi = miles(p.get("lat"), p.get("lng"))
        if mi is not None and mi > MAX_PUBLIC_MILES:
            continue
        for d in p["nextDates"]:
            if lo <= d <= hi:
                public.append({
                    "kind": "ranger", "title": p["title"], "session": "", "start": d + "T00:00", "end": "",
                    "time": p.get("time", ""), "tz": "PT", "location": ", ".join(x for x in [p.get("where"), p["park"]] if x),
                    "miles": mi, "approx": False, "online": False, "programs": ["Cub Scouts", "Scouts BSA"],
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
    print(f"  weekend.json: {len(scout)} Scout events, {len(public)} public programs, {len(alerts.get('alerts', []))} alerts")


if __name__ == "__main__":
    main()
