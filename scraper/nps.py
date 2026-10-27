"""Ranger programs and park events (for the Trailbook, not the Event Finder) from the National Park Service's official events API.

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

import requests


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "data", "events.json")
SEEN = os.path.join(ROOT, "data", "first_seen.json")
PROGRAMS = os.path.join(ROOT, "docs", "data", "ranger_programs.json")
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
    # Ranger programs are public programs, not Scout events: they go to the Trailbook list
    # (docs/data/ranger_programs.json), and any old copies are removed from the Event Finder.
    data.update(events=events, count=len(events))
    json.dump(data, open(OUT, "w"), separators=(",", ":"), ensure_ascii=False)
    programs = []
    for it in items:
        title = html.unescape(it.get("title", "")).strip()
        desc = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", it.get("description", "")))).strip()
        dates = sorted(d[:10] for d in (it.get("dates") or []) if d[:10] >= today)
        if not title or not dates:
            continue
        times = it.get("times") or [{}]
        programs.append({
            "park": it.get("parkfullname", ""), "parkCode": (it.get("sitecode") or "").lower(),
            "title": title, "where": it.get("location", "").strip(),
            "time": " - ".join(x for x in [times[0].get("timestart", ""), times[0].get("timeend", "")] if x),
            "nextDates": dates[:12], "count": len(dates),
            "free": str(it.get("isfree", "")).lower() == "true",
            "url": it.get("infourl") or f"https://www.nps.gov/{(it.get('sitecode') or '').lower()}/planyourvisit/calendar.htm",
            "about": desc[:400],
        })
    programs.sort(key=lambda p: (p["park"], p["nextDates"][0], p["title"]))
    json.dump({"updated": today, "programs": programs}, open(PROGRAMS, "w"), indent=1, ensure_ascii=False)
    print(f"  NPS: {len(programs)} ranger programs saved for the Trailbook ({len(items)} fetched)")


if __name__ == "__main__":
    main()
