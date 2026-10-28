"""Events a council lists on its OWN scoutingevent.com calendar but not on the global one.

Some councils publish events only to their council calendar (scoutingevent.com/<code>/Calendar), so the
global map that scrape_global.py reads never sees them (e.g. Greater California Council's Southern Sierra
Merit Badge Midway). For each council in data/blackpug_councils.json this reads the council calendar's
list view (50 per page, a year ahead) and adds any event path the global calendar didn't already provide.
Those listings give the date, title, city and a short description; times come from the event page.
"""
import hashlib
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
from tagging import tag  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "data", "blackpug_councils.json")
EVENTS = os.path.join(ROOT, "docs", "data", "events.json")
SEEN = os.path.join(ROOT, "data", "first_seen.json")
CITIES = os.path.join(ROOT, "data", "cities.json")
CACHE = os.path.join(ROOT, "data", "council_details_cache.json")  # own cache: scrape_global prunes its cache nightly
BASE = "https://scoutingevent.com"
HDR = {"User-Agent": "ScoutEventFinder/1.0 (volunteer Scout leader project; nightly, rate-limited)"}
DELAY = float(os.environ.get("SCRAPE_DELAY", "1.0"))
LA = ZoneInfo("America/Los_Angeles")
SKIP = re.compile(r"office (?:is )?closed|store closed|\bholiday\b|^closed\b", re.I)
TIME_RX = re.compile(r"\b(\d{1,2})(?::(\d\d))?\s*([ap])\.?m\.?\b", re.I)

session = requests.Session()
session.headers.update(HDR)


def load(p, d):
    try:
        with open(p) as f:
            return json.load(f)
    except (OSError, ValueError):
        return d


def get(url, params=None):
    try:
        r = session.get(url, params=params, timeout=60)
        time.sleep(DELAY)
        return r.text if r.ok else ""
    except requests.RequestException as ex:
        print(f"  ! {url}: {ex}", flush=True)
        return ""


def council_listing(code):
    """[(date, path, title, location, snippet)] from the council calendar's list view."""
    out, page = [], 1
    while page <= 15:
        html = get(f"{BASE}/{code}/Calendar/Embed", {"calendarType": "1", "filter-months": "12", "page": str(page)})
        soup = BeautifulSoup(html, "html.parser")
        rows = soup.select("div.cal-event")
        day, n = None, 0
        for row in rows:
            head = row.select_one(".cal-date-title")
            if head:
                try:
                    day = datetime.strptime(head.get_text(" ", strip=True), "%B %d, %Y").date()
                except ValueError:
                    day = None
                continue
            a = row.select_one(".cal-title a")
            if not a or not day:
                continue
            path = re.sub(r"^https?://[^/]+", "", a.get("href", "")).split("?")[0]
            if not re.match(rf"^/{code}-", path):
                continue
            loc = row.select_one(".cal-loc-content")
            desc = row.select_one(".cal-desc")
            out.append((day, path, a.get_text(" ", strip=True), loc.get_text(" ", strip=True) if loc else "",
                        desc.get_text(" ", strip=True).replace("Read More", "").strip() if desc else ""))
            n += 1
        if n == 0:
            break
        page += 1
    return out


def detail_text(path, cache):
    if path in cache:
        return cache[path].get("desc", "")
    html = get(BASE + path)
    box = BeautifulSoup(html, "html.parser").select_one("#eventdescription") if html else None
    text = re.sub(r"\s+", " ", box.get_text(" ", strip=True)) if box else ""
    text = re.sub(r"^.*?\|\s*Share\s*\|\s*Tweet\s*", "", text)
    cache[path] = {"desc": text[:4000], "fees": sorted(set(re.findall(r"\$\s?\d[\d,]*(?:\.\d\d)?", text)))[:6]}
    return cache[path]["desc"]


def first_time(text):
    """First clock time written in the description ("Check in opens at 8:00 am"), if any."""
    m = TIME_RX.search(text or "")
    if not m:
        return None
    h, mnt, ap = int(m.group(1)), int(m.group(2) or 0), m.group(3).lower()
    if not 1 <= h <= 12:
        return None
    h24 = h % 12 + (12 if ap == "p" else 0)
    return (h24, mnt) if 6 <= h24 <= 19 else None  # ignore "registration closes 11:59 pm" and the like


def main():
    councils = load(SRC, [])
    if not councils:
        print("No council calendars configured.")
        return
    data = load(EVENTS, None)
    if data is None:
        sys.exit("events.json missing")
    seen, cities, cache = load(SEEN, {}), load(CITIES, {}), load(CACHE, {})
    have = {re.sub(r"^https?://[^/]+", "", e.get("url", "")).split("?")[0].lower()
            for e in data["events"] if e["id"][0].isdigit()}
    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")
    out, fetched = [], 0
    for c in councils:
        rows = council_listing(c["code"])
        new = [r for r in rows if r[1].lower() not in have and not SKIP.search(r[2])]
        print(f"  {c['name']} ({c['code']}): {len(rows)} listed on the council calendar, "
              f"{len(new)} not on the global calendar", flush=True)
        for day, path, title, loc, snip in new:
            if path in cache:
                desc = detail_text(path, cache) or snip
            elif fetched < int(os.environ.get("MAX_DETAIL_FETCHES", "80")):
                fetched += 1
                desc = detail_text(path, cache) or snip
            else:
                desc = snip  # read the event page on a later night
            t0 = first_time(desc)
            st = datetime.combine(day, datetime.min.time(), LA).replace(hour=t0[0], minute=t0[1]) if t0 \
                else datetime.combine(day, datetime.min.time(), LA)
            en = st if t0 else datetime.combine(day, datetime.max.time().replace(microsecond=0), LA)
            if en < now:
                continue
            parts = [p.strip() for p in loc.split(",") if p.strip()]
            pt = None
            if len(parts) >= 2:
                pt = cities.get(f"{parts[-2].lower()}|{parts[-1].lower()}")
            lat, lng = pt or (c.get("lat"), c.get("lng"))
            sid = "bp-" + hashlib.md5(f"{path}{day.isoformat()}".encode()).hexdigest()[:12]
            seen.setdefault(sid, today)
            out.append({
                "id": sid, "eid": "bp-" + path.strip("/"), "org": "", "council": c["name"], "title": title, "session": "",
                "start": st.strftime("%Y-%m-%dT%H:%M"), "end": en.strftime("%Y-%m-%dT%H:%M"), "tz": "PT" if t0 else "",
                "startUtc": st.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
                "endUtc": en.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
                "lat": lat, "lng": lng, "approx": True, "location": loc,
                "desc": desc[:600], "fees": cache.get(path, {}).get("fees", []),
                "url": BASE + path, "firstSeen": seen[sid], "source": f"{c['name']} calendar",
                **tag(title, desc, set(), loc),
            })
    listed = {o["url"][len(BASE):] for o in out}
    cache = {p: v for p, v in cache.items() if p in listed}
    events = [e for e in data["events"] if not e["id"].startswith("bp-")] + out
    events.sort(key=lambda e: (e["startUtc"] or "", e["title"]))
    data.update(events=events, count=len(events))
    json.dump(data, open(EVENTS, "w"), separators=(",", ":"), ensure_ascii=False)
    json.dump(seen, open(SEEN, "w"))
    json.dump(cache, open(CACHE, "w"), ensure_ascii=False)
    print(f"  council calendars: {len(out)} extra sessions added", flush=True)


if __name__ == "__main__":
    main()
