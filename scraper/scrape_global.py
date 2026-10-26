"""Nightly collector for global.scoutingevent.com (Black Pug / 247Scouting).

How it works (all public pages, no login):
  1. Map view  (?calendarType=4)  -> every session with lat/lng, start/end, council, link.
                                     Paged 2,000 sessions per page.
  2. Map view per site category   -> which categories each session belongs to.
  3. List view (?calendarType=1)  -> location text, short description, image (50 per page).
  4. Event pages (/123-slug)      -> full description, fetched only for events not yet cached.
Then tags everything (see tagging.py) and writes docs/data/events.json for the website.
"""
import html as htmllib
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(__file__))
from tagging import SITE_CATEGORIES, tag  # noqa: E402

BASE = "https://global.scoutingevent.com"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "data", "events.json")
CACHE = os.path.join(ROOT, "data", "details_cache.json")
SEEN = os.path.join(ROOT, "data", "first_seen.json")

DELAY = float(os.environ.get("SCRAPE_DELAY", "1.0"))          # seconds between requests (be polite)
MAX_DETAILS = int(os.environ.get("MAX_DETAIL_FETCHES", "1200"))  # new event pages per run
COMMON = {"filter-country": "232", "filter-state": "0", "filter-distance": "", "filter-zipcode": "",
          "searchterm": "", "printCalendar": "0", "printCalendarMonths": "1"}

session = requests.Session()
session.headers["User-Agent"] = ("ScoutEventFinder/1.0 (volunteer Scout leader project; "
                                 "nightly, rate-limited; github.com)")

TZ = {"ET": "America/New_York", "EST": "America/New_York", "EDT": "America/New_York",
      "CT": "America/Chicago", "CST": "America/Chicago", "CDT": "America/Chicago",
      "MT": "America/Denver", "MDT": "America/Denver", "MST": "America/Phoenix",
      "PT": "America/Los_Angeles", "PST": "America/Los_Angeles", "PDT": "America/Los_Angeles",
      "AKT": "America/Anchorage", "HT": "Pacific/Honolulu", "HST": "Pacific/Honolulu",
      "AST": "America/Puerto_Rico", "ChST": "Pacific/Guam", "CET": "Europe/Berlin",
      "JST": "Asia/Tokyo", "KST": "Asia/Seoul", "GMT": "UTC", "UTC": "UTC"}

_S = r"'((?:[^'\\]|\\.)*)'"
MARKER = re.compile(r"createMarker\(" + r"\s*,\s*".join([_S] * 10) + r"\)")


def get(path, params=None, tries=3):
    for i in range(tries):
        try:
            r = session.get(BASE + path, params=params, timeout=60)
            r.raise_for_status()
            time.sleep(DELAY)
            return r.text
        except requests.RequestException as e:
            print(f"  ! {path} {params or ''}: {e} (try {i + 1})", flush=True)
            time.sleep(5 * (i + 1))
    return ""


def unescape(s):
    return htmllib.unescape(re.sub(r"\\(.)", r"\1", s))


def parse_time(s):
    """'Oct 15, 2026 06:00 PM CT' -> (local ISO, UTC ISO, tz label)."""
    m = re.match(r"(\w{3} \d{1,2}, \d{4} \d{1,2}:\d{2} [AP]M)\s*(\S+)?", s.strip())
    if not m:
        return None, None, ""
    dt = datetime.strptime(m.group(1), "%b %d, %Y %I:%M %p")
    label = m.group(2) or ""
    local = dt.replace(tzinfo=ZoneInfo(TZ.get(label, "America/New_York")))
    return dt.strftime("%Y-%m-%dT%H:%M"), local.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"), label


def map_sessions(extra=None):
    """All sessions from the map view, following its 2,000-per-page paging."""
    out, page = [], 1
    while True:
        params = {**COMMON, "calendarType": "4", "page": str(page), **(extra or {})}
        html = get("/", params)
        rows = MARKER.findall(html)
        out.extend(rows)
        if len(rows) < 2000 or page > 20:
            return out
        page += 1


def list_view():
    """Location / snippet / image per event path from the list view."""
    info, page = {}, 1
    while page < 200:
        html = get("/", {**COMMON, "calendarType": "1", "page": str(page)})
        soup = BeautifulSoup(html, "html.parser")
        items = soup.select("div.cal-event .cal-content")
        if not items:
            break
        for c in items:
            a = c.select_one(".cal-title a")
            if not a:
                continue
            path = re.sub(r"^https?://[^/]+", "", a.get("href", ""))
            loc = c.select_one(".cal-loc-content a, .cal-loc-content")
            desc = c.select_one(".cal-desc")
            img = c.find_parent(class_="cal-event").select_one(".cal-img img")
            info.setdefault(path, {
                "event": a.get_text(" ", strip=True),
                "location": loc.get_text(" ", strip=True) if loc else "",
                "snippet": desc.get_text(" ", strip=True).replace("Read More", "").strip() if desc else "",
                "image": requests.compat.urljoin(BASE + "/", img.get("src") or "") if img and img.get("src") else "",
            })
        print(f"  list page {page}: {len(items)} items", flush=True)
        page += 1
    return info


def detail(path):
    html = get(path)
    if not html:
        return None
    soup = BeautifulSoup(html, "html.parser")
    box = soup.select_one("#eventdescription")
    text = box.get_text("\n", strip=True) if box else ""
    text = re.sub(r"^.*?\|\s*Share\s*\|\s*Tweet\s*", "", text, flags=re.S)
    text = re.sub(r"^(?:Event Details|Register(?: for [^\n]*)?|Share|Tweet|\|)\n", "", text, flags=re.M)
    text = re.sub(r"\n{2,}", "\n", text)
    fees = sorted({f for f in re.findall(r"\$\s?\d[\d,]*(?:\.\d\d)?", text)},
                  key=lambda x: float(re.sub(r"[^\d.]", "", x) or 0))
    return {"desc": text[:4000], "fees": fees[:6]}


def load(p, default):
    try:
        with open(p) as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def main():
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    print("1/4 map view (all sessions)...", flush=True)
    rows = map_sessions()
    print(f"   {len(rows)} sessions", flush=True)
    if len(rows) < 100:
        sys.exit("Too few sessions found - the site layout may have changed. Not overwriting data.")

    print("2/4 categories...", flush=True)
    cats = {}
    for cid in SITE_CATEGORIES:
        for r in map_sessions({"filter-region-preset[]": str(cid)}):
            cats.setdefault(r[4], set()).add(cid)

    print("3/4 list view...", flush=True)
    info = list_view()

    print("4/4 event pages (new only)...", flush=True)
    cache = load(CACHE, {})
    paths = sorted({unescape(r[7]) for r in rows})
    fetched = 0
    for p in paths:
        if p in cache or fetched >= MAX_DETAILS:
            continue
        d = detail(p)
        if d is not None:
            cache[p] = d
            fetched += 1
    cache = {p: v for p, v in cache.items() if p in set(paths)}  # drop expired events
    print(f"   fetched {fetched} new event pages; cache {len(cache)}", flush=True)

    seen = load(SEEN, {})
    events = []
    for r in rows:
        org, lat, lng, event_id, session_id, council, title, path, start, end = map(unescape, r)
        li = info.get(path, {})
        ev_name = li.get("event") or title.split(":")[0].strip()
        sess = title[len(ev_name):].lstrip(" :").strip() if title.startswith(ev_name) else ""
        s_local, s_utc, tzl = parse_time(start)
        e_local, e_utc, _ = parse_time(end)
        d = cache.get(path, {})
        desc = d.get("desc") or li.get("snippet", "")
        site_cats = cats.get(session_id, set())
        tags = tag(f"{ev_name} {sess}", desc, site_cats)
        seen.setdefault(session_id, today)
        events.append({
            "id": session_id, "eid": event_id, "org": org,
            "council": council, "title": ev_name, "session": sess,
            "start": s_local, "end": e_local, "tz": tzl, "startUtc": s_utc, "endUtc": e_utc,
            "lat": round(float(lat), 4) if lat else None, "lng": round(float(lng), 4) if lng else None,
            "location": li.get("location", ""),
            "desc": desc[:600], "fees": d.get("fees", []),
            "url": BASE + path, "firstSeen": seen[session_id],
            **tags,
        })
    seen = {k: v for k, v in seen.items() if k in {e["id"] for e in events}}
    events.sort(key=lambda e: (e["startUtc"] or "", e["title"]))

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump({"updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
                   "source": BASE, "count": len(events), "events": events},
                  f, separators=(",", ":"), ensure_ascii=False)
    with open(CACHE, "w") as f:
        json.dump(cache, f, ensure_ascii=False)
    with open(SEEN, "w") as f:
        json.dump(seen, f)
    print(f"Done: {len(events)} sessions written to {OUT}", flush=True)


if __name__ == "__main__":
    main()
