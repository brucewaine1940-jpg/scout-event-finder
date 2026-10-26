"""Merit badge / Scouting events listed on Eventbrite (museums, independent counselors, online classes...).

Reads a handful of public Eventbrite search pages (allowed by Eventbrite's robots.txt), keeps only
Scouting-related events, then reads each kept event's own page once for exact times and address.
All data comes from the schema.org JSON-LD Eventbrite publishes for search engines.
Edit SEARCHES below to add places or keywords.
"""
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(__file__))
from tagging import tag  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "data", "events.json")
CACHE = os.path.join(ROOT, "data", "eventbrite_cache.json")
SEEN = os.path.join(ROOT, "data", "first_seen.json")
ZIPS = os.path.join(ROOT, "docs", "data", "zips.json")
BASE = "https://www.eventbrite.com"
HDR = {"User-Agent": "ScoutEventFinder/1.0 (volunteer Scout leader project; nightly, rate-limited)"}
DELAY = 2.0

SEARCHES = [
    "/d/united-states/merit-badge/",
    "/d/united-states/merit-badge-class/",
    "/d/united-states/scouts-bsa/",
    "/d/united-states/cub-scouts/",
    "/d/united-states/eagle-scout/",
    "/d/online/merit-badge/",
    "/d/online/scouts/",
    "/d/ca--los-angeles/merit-badge/",
    "/d/ca--los-angeles/boy-scouts-merit-badge/",
    "/d/united-states--california/merit-badge/",
    "/d/ca--orange/merit-badge/",
    "/d/ca--san-diego/merit-badge/",
]
KEEP = re.compile(r"merit[\s-]*badge|scouts? ?bsa|scouting america|\bboy scouts?\b|cub scouts?|eagle scout|webelos|"
                  r"arrow of light|\bBSA\b|\bMBU\b", re.I)
GIRL_ONLY = re.compile(r"girl scouts?|brownies?|daisies|juniors? badge|cadettes?", re.I)

STATES = dict(zip(
    "AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA "
    "RI SC SD TN TX UT VT VA WA WV WI WY DC PR".split(),
    ["Alabama", "Alaska", "Arizona", "Arkansas", "California", "Colorado", "Connecticut", "Delaware", "Florida",
     "Georgia", "Hawaii", "Idaho", "Illinois", "Indiana", "Iowa", "Kansas", "Kentucky", "Louisiana", "Maine",
     "Maryland", "Massachusetts", "Michigan", "Minnesota", "Mississippi", "Missouri", "Montana", "Nebraska", "Nevada",
     "New Hampshire", "New Jersey", "New Mexico", "New York", "North Carolina", "North Dakota", "Ohio", "Oklahoma",
     "Oregon", "Pennsylvania", "Rhode Island", "South Carolina", "South Dakota", "Tennessee", "Texas", "Utah",
     "Vermont", "Virginia", "Washington", "West Virginia", "Wisconsin", "Wyoming", "District of Columbia",
     "Puerto Rico"]))

session = requests.Session()
session.headers.update(HDR)


def get(url):
    try:
        r = session.get(url, timeout=60)
        time.sleep(DELAY)
        return r.text if r.ok else ""
    except requests.RequestException as ex:
        print(f"  ! {url}: {ex}")
        return ""


def ld_events(html):
    out = []

    def walk(o):
        if isinstance(o, list):
            for x in o:
                walk(x)
        elif isinstance(o, dict):
            t = o.get("@type", "")
            if isinstance(t, str) and t.endswith("Event"):
                out.append(o)
            for v in o.values():
                if isinstance(v, (dict, list)):
                    walk(v)

    for s in BeautifulSoup(html, "html.parser").find_all("script", type="application/ld+json"):
        try:
            walk(json.loads(s.string or ""))
        except ValueError:
            pass
    return out


def scout_related(e):
    text = f"{e.get('name', '')} {e.get('description', '')}"
    if not KEEP.search(text):
        return False
    # Girl Scout badge classes are a different program; keep them only if they also mention merit badges
    return not (GIRL_ONLY.search(text) and not re.search(r"merit[\s-]*badge", text, re.I))


ZONE_BY_STATE = {**{k: "PT" for k in ["California", "Washington", "Oregon", "Nevada"]},
                 **{k: "MT" for k in ["Arizona", "Colorado", "Utah", "New Mexico", "Montana", "Wyoming", "Idaho"]},
                 **{k: "CT" for k in ["Texas", "Illinois", "Wisconsin", "Minnesota", "Iowa", "Missouri", "Arkansas",
                                      "Louisiana", "Mississippi", "Alabama", "Oklahoma", "Kansas", "Nebraska",
                                      "South Dakota", "North Dakota", "Tennessee"]},
                 "Alaska": "AKT", "Hawaii": "HT"}


def tz_label(region, st):
    if region in ZONE_BY_STATE:
        return ZONE_BY_STATE[region]
    if region:
        return "ET"
    off = st.utcoffset()
    if off is None:
        return ""
    h = int(off.total_seconds() // 3600)
    return f"UTC{h:+d}"


def parse_dt(s):
    if not s:
        return None
    if len(s) == 10:
        return datetime.fromisoformat(s + "T00:00:00+00:00")
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def load(p, d):
    try:
        with open(p) as f:
            return json.load(f)
    except (OSError, ValueError):
        return d


def main():
    data = load(OUT, None)
    if not data:
        sys.exit("events.json missing - run scrape_global.py first")
    cache, seen, zips = load(CACHE, {}), load(SEEN, {}), load(ZIPS, {})
    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")

    found = {}
    for path in SEARCHES:
        for e in ld_events(get(BASE + path)):
            url = (e.get("url") or "").split("?")[0]
            if url and scout_related(e):
                found[url] = e
    print(f"  Eventbrite: {len(found)} Scouting-related events in search results")

    # Event pages: exact times, full address, organizer. Re-read each page at most every 3 days.
    for url in found:
        c = cache.get(url)
        if c and c.get("fetched", "") > (now - timedelta(days=3)).strftime("%Y-%m-%d"):
            continue
        evs = [x for x in ld_events(get(url)) if x.get("startDate")]
        if evs:
            cache[url] = {"fetched": today, "event": evs[0]}

    events = [e for e in data["events"] if not e["id"].startswith("eb-")]
    n = 0
    for url, summary in found.items():
        e = (cache.get(url) or {}).get("event") or summary
        st, en = parse_dt(e.get("startDate")), parse_dt(e.get("endDate") or e.get("startDate"))
        if not st or (en or st) < now:
            continue
        loc = e.get("location") or {}
        if isinstance(loc, list):
            loc = loc[0] if loc else {}
        addr = loc.get("address") or {}
        if isinstance(addr, str):
            addr = {"streetAddress": addr}
        street = addr.get("streetAddress", "")
        z = re.search(r"\b(\d{5})\b", f"{street} {addr.get('postalCode', '')}")
        latlng = zips.get(z.group(1)) if z else None
        if not latlng and isinstance(loc.get("geo"), dict):
            try:
                latlng = [float(loc["geo"]["latitude"]), float(loc["geo"]["longitude"])]
            except (KeyError, TypeError, ValueError):
                latlng = None
        online = "Online" in str(e.get("eventAttendanceMode", "")) or loc.get("@type") == "VirtualLocation"
        region = STATES.get(addr.get("addressRegion", "").upper(), addr.get("addressRegion", ""))
        place = "Online" if online else ", ".join(
            x for x in [loc.get("name", ""), addr.get("addressLocality", ""), region] if x) or street
        title = re.sub(r"\s+", " ", e.get("name", "")).strip()
        desc = re.sub(r"\s+", " ", BeautifulSoup(e.get("description") or "", "html.parser").get_text(" ")).strip()
        org = (e.get("organizer") or {}).get("name", "") if isinstance(e.get("organizer"), dict) else ""
        price = []
        offers = e.get("offers") or []
        for o in offers if isinstance(offers, list) else [offers]:
            if isinstance(o, dict) and o.get("lowPrice"):
                price.append(f"${float(o['lowPrice']):.0f}" if float(o["lowPrice"]) else "Free")
        sid = "eb-" + hashlib.md5(url.encode()).hexdigest()[:12]
        seen.setdefault(sid, today)
        t = tag(title, desc, set(), "Online" if online else place)
        if online and not t["online"]:
            t["online"] = True
            t["topics"].append("Online / Virtual")
        events.append({
            "id": sid, "eid": sid, "org": "", "council": org or "Eventbrite listing", "title": title, "session": "",
            "start": st.strftime("%Y-%m-%dT%H:%M"), "end": en.strftime("%Y-%m-%dT%H:%M"),
            "tz": tz_label(region, st),
            "startUtc": st.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
            "endUtc": en.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
            "lat": latlng[0] if latlng else None, "lng": latlng[1] if latlng else None,
            "location": place,
            "desc": desc[:600], "fees": price[:1], "url": url, "firstSeen": seen[sid], "source": "Eventbrite",
            **t,
        })
        n += 1
    cache = {u: v for u, v in cache.items() if u in found}
    events.sort(key=lambda e: (e["startUtc"] or "", e["title"]))
    data.update(events=events, count=len(events))
    json.dump(data, open(OUT, "w"), separators=(",", ":"), ensure_ascii=False)
    json.dump(cache, open(CACHE, "w"), ensure_ascii=False)
    json.dump(seen, open(SEEN, "w"))
    print(f"  Eventbrite: {n} upcoming events added")


if __name__ == "__main__":
    main()
