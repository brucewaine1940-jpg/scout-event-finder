"""Ranger programs and park events from the National Park Service's official events API.

Needs a free key from https://www.nps.gov/subjects/developer/get-started.htm saved as the GitHub secret
NPS_API_KEY; without it this step is skipped. Edit PARKS to choose which parks to include
(4-letter park codes from nps.gov URLs, e.g. nps.gov/samo -> "samo").
"""
import hashlib
import html
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import requests

sys.path.insert(0, os.path.dirname(__file__))
from tagging import tag  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "data", "events.json")
SEEN = os.path.join(ROOT, "data", "first_seen.json")
API = "https://developer.nps.gov/api/v1/events"
HDR = {"User-Agent": "ScoutEventFinder/1.0 (volunteer Scout leader project)"}

# Southern California and nearby: Santa Monica Mountains, Channel Islands, Cabrillo, Joshua Tree, Mojave,
# Manzanar, Death Valley, Sequoia & Kings Canyon, Pinnacles
PARKS = ["samo", "chis", "cabr", "jotr", "moja", "manz", "deva", "seki", "pinn"]
PARK_TZ = {"default": "America/Los_Angeles"}


def parse_time(t):
    for fmt in ("%I:%M %p", "%I:%M%p", "%H:%M"):
        try:
            return datetime.strptime(t.strip().upper(), fmt).time()
        except ValueError:
            pass
    return None


def main():
    key = os.environ.get("NPS_API_KEY", "").strip()
    if not key:
        print("  NPS: no NPS_API_KEY secret set - skipping (see README)")
        return
    data = json.load(open(OUT))
    try:
        seen = json.load(open(SEEN))
    except (OSError, ValueError):
        seen = {}
    tz = ZoneInfo(PARK_TZ["default"])
    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")
    events = [e for e in data["events"] if not e["id"].startswith("nps-")]
    items, page = [], 1
    while page <= 20:
        try:
            r = requests.get(API, params={"parkCode": ",".join(PARKS), "pageSize": 50, "pageNumber": page},
                             headers={"X-Api-Key": key, **HDR}, timeout=60)
        except requests.RequestException as ex:
            print(f"  ! NPS: {ex}")
            break
        if not r.ok:
            print(f"  ! NPS: HTTP {r.status_code}: {r.text[:200]}")
            break
        j = r.json()
        batch = j.get("data", [])
        items += batch
        total = int(j.get("total", 0) or 0)
        if not batch or len(items) >= total:
            break
        page += 1
        time.sleep(0.5)
    n = 0
    for it in items:
        title = html.unescape(it.get("title", "")).strip()
        desc = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", it.get("description", "")))).strip()
        times = it.get("times") or [{}]
        t0 = parse_time(times[0].get("timestart", "") or "") if times else None
        t1 = parse_time(times[0].get("timeend", "") or "") if times else None
        park = it.get("parkfullname", "")
        place = ", ".join(x for x in [it.get("location", "").strip(), park, "California"] if x)[:160]
        try:
            lat, lng = float(it.get("latitude")), float(it.get("longitude"))
        except (TypeError, ValueError):
            lat = lng = None
        url = it.get("infourl") or f"https://www.nps.gov/{(it.get('sitecode') or '').lower()}/planyourvisit/calendar.htm"
        t = tag(title, desc, set(), place)
        for extra in ["Ranger / Park Program", "Fun / Family Events"]:
            if extra not in t["topics"]:
                t["topics"].append(extra)
        if "Cub Scouts" not in t["programs"]:
            t["programs"].append("Cub Scouts")  # ranger programs are family-friendly; good for packs
        for ds in (it.get("dates") or [])[:60]:
            try:
                d = datetime.strptime(ds[:10], "%Y-%m-%d").date()
            except ValueError:
                continue
            st = datetime.combine(d, t0 or datetime.min.time(), tz)
            en = datetime.combine(d, t1 or t0 or datetime.min.time(), tz)
            if en < now and (t1 or t0):
                continue
            if not (t1 or t0) and d < now.date():
                continue
            sid = "nps-" + hashlib.md5(f"{it.get('id')}{ds}".encode()).hexdigest()[:12]
            seen.setdefault(sid, today)
            events.append({
                "id": sid, "eid": "nps-" + str(it.get("id")), "org": "", "council": park or "National Park Service",
                "title": title, "session": "",
                "start": st.strftime("%Y-%m-%dT%H:%M"), "end": en.strftime("%Y-%m-%dT%H:%M"), "tz": "PT" if (t0 or t1) else "",
                "startUtc": st.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
                "endUtc": en.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
                "lat": lat, "lng": lng, "location": place, "desc": desc[:600],
                "fees": ["Free"] if str(it.get("isfree", "")).lower() == "true" else [],
                "url": url, "firstSeen": seen[sid], "source": "National Park Service", **t,
            })
            n += 1
    events.sort(key=lambda e: (e["startUtc"] or "", e["title"]))
    data.update(events=events, count=len(events))
    json.dump(data, open(OUT, "w"), separators=(",", ":"), ensure_ascii=False)
    json.dump(seen, open(SEEN, "w"))
    print(f"  NPS: {n} event dates from {len(items)} programs")


if __name__ == "__main__":
    main()
