"""Optional: merge extra calendar feeds (ICS) into events.json.

For councils that are NOT on Black Pug/global.scoutingevent.com (e.g. Teamup or Google calendars).
Add feeds to data/extra_sources.json like:
  [{"name": "Long Beach Area Council", "url": "https://.../feed.ics", "lat": 33.77, "lng": -118.19, "state": "California"}]
Runs after scrape_global.py. Failures on one feed never break the nightly run.
"""
import hashlib
import json
import os
import re
import sys
from datetime import date, datetime, timezone

import requests

sys.path.insert(0, os.path.dirname(__file__))
from tagging import tag  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "data", "events.json")
SRC = os.path.join(ROOT, "data", "extra_sources.json")
SKIP = re.compile(r"holiday|office clos|closed", re.I)


def main():
    try:
        sources = json.load(open(SRC))
    except (OSError, ValueError):
        sources = []
    if not sources:
        print("No extra feeds configured.")
        return
    from icalendar import Calendar
    data = json.load(open(OUT))
    events = [e for e in data["events"] if not e["id"].startswith("x-")]
    now = datetime.now(timezone.utc)
    for s in sources:
        try:
            r = requests.get(s["url"], timeout=60, headers={"User-Agent": "ScoutEventFinder/1.0"})
            r.raise_for_status()
            cal = Calendar.from_ical(r.content)
        except Exception as ex:  # noqa: BLE001
            print(f"  ! {s.get('name')}: {ex}")
            continue
        n = 0
        for v in cal.walk("VEVENT"):
            title = str(v.get("SUMMARY", "")).strip()
            if not title or SKIP.search(title):
                continue
            st = v.decoded("DTSTART")
            en = v.decoded("DTEND") if v.get("DTEND") else st
            if isinstance(st, date) and not isinstance(st, datetime):
                st = datetime(st.year, st.month, st.day, tzinfo=timezone.utc)
                en = datetime(en.year, en.month, en.day, tzinfo=timezone.utc)
            if st.tzinfo is None:
                st = st.replace(tzinfo=timezone.utc)
                en = en.replace(tzinfo=timezone.utc)
            if en < now:
                continue
            desc = str(v.get("DESCRIPTION", ""))[:900]
            uid = str(v.get("UID", f"{title}{st}"))
            events.append({
                "id": "x-" + hashlib.md5((uid + s["url"]).encode()).hexdigest()[:12], "eid": "x-" + hashlib.md5((title + s["url"]).encode()).hexdigest()[:12],
                "org": "", "council": s["name"], "title": title, "session": "",
                "start": st.strftime("%Y-%m-%dT%H:%M"), "end": en.strftime("%Y-%m-%dT%H:%M"), "tz": "",
                "startUtc": st.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
                "endUtc": en.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
                "lat": s.get("lat"), "lng": s.get("lng"),
                "location": str(v.get("LOCATION", "")) or s.get("state", ""), "image": "",
                "desc": desc, "fees": [], "url": str(v.get("URL", "")) or s.get("page", s["url"]),
                "firstSeen": now.strftime("%Y-%m-%d"), **tag(title, desc, set()),
            })
            n += 1
        print(f"  {s['name']}: {n} events")
    events.sort(key=lambda e: (e["startUtc"] or "", e["title"]))
    data.update(events=events, count=len(events))
    json.dump(data, open(OUT, "w"), separators=(",", ":"), ensure_ascii=False)


if __name__ == "__main__":
    main()
