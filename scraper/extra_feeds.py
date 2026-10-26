"""Merge extra council calendars (councils NOT on Black Pug) into events.json.

Configure in data/extra_sources.json. Each entry is one of:
  {"name": "...", "ics": "https://.../feed.ics", ...}                  a plain ICS feed (Teamup, Google, WordPress...)
  {"name": "...", "google_embed_page": "https://council.org/calendar/"}  a web page with an embedded Google Calendar;
                                                                         every public calendar in the embed is pulled
Optional per source: "lat", "lng" (fallback map point, e.g. council office), "state", "page" (link shown to users),
"skip" (regex of titles to ignore).
Recurring events are expanded for the next 12 months. Failures on one source never break the nightly run.
"""
import base64
import hashlib
import html
import json
import os
import re
import sys
from datetime import date, datetime, timedelta, timezone
from urllib.parse import parse_qs, quote, urlparse

import requests

sys.path.insert(0, os.path.dirname(__file__))
from tagging import tag  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "data", "events.json")
SRC = os.path.join(ROOT, "data", "extra_sources.json")
SEEN = os.path.join(ROOT, "data", "first_seen.json")
ZIPS = os.path.join(ROOT, "docs", "data", "zips.json")
SKIP = re.compile(r"holiday|office (?:clos|hours)|closed|scout shop hours|^busy$", re.I)
HDR = {"User-Agent": "ScoutEventFinder/1.0 (volunteer Scout leader project)"}
TZ_LABEL = {"PDT": "PT", "PST": "PT", "MDT": "MT", "MST": "MT", "CDT": "CT", "CST": "CT", "EDT": "ET", "EST": "ET"}


def google_ids(page_url):
    """Calendar ids from the Google Calendar <iframe> on a web page (ids may be base64-encoded)."""
    r = requests.get(page_url, timeout=60, headers=HDR)
    r.raise_for_status()
    ids = []
    for src in re.findall(r'<iframe[^>]+src="([^"]*calendar\.google\.com/calendar/[^"]*)"', r.text):
        for v in parse_qs(urlparse(html.unescape(src)).query).get("src", []):
            cid = v
            if "@" not in v:
                try:
                    cid = base64.b64decode(v + "=" * (-len(v) % 4)).decode()
                except (ValueError, UnicodeDecodeError):
                    pass
            # skip personal (gmail) and Google's built-in holiday calendars
            if "@" in cid and not cid.endswith("gmail.com") and "holiday" not in cid:
                ids.append(cid)
    return ids


def ics_urls(s):
    if s.get("ics"):
        return [s["ics"]]
    if s.get("google_embed_page"):
        return [f"https://calendar.google.com/calendar/ical/{quote(cid)}/public/basic.ics"
                for cid in google_ids(s["google_embed_page"])]
    return []


def strip_html(t):
    t = re.sub(r"<br\s*/?>|</p>|</li>", "\n", t or "", flags=re.I)
    return html.unescape(re.sub(r"<[^>]+>", "", t)).strip()


def as_dt(v):
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc), False
    return datetime(v.year, v.month, v.day, tzinfo=timezone.utc), True  # all-day


def main():
    try:
        sources = json.load(open(SRC))
    except (OSError, ValueError):
        sources = []
    if not sources:
        print("No extra feeds configured.")
        return
    import recurring_ical_events
    from icalendar import Calendar

    data = json.load(open(OUT))
    try:
        seen = json.load(open(SEEN))
    except (OSError, ValueError):
        seen = {}
    try:
        zips = json.load(open(ZIPS))
    except (OSError, ValueError):
        zips = {}
    events = [e for e in data["events"] if not e["id"].startswith("x-")]
    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")
    for s in sources:
        skip = re.compile(s["skip"], re.I) if s.get("skip") else None
        try:
            urls = ics_urls(s)
        except Exception as ex:  # noqa: BLE001
            print(f"  ! {s.get('name')}: {ex}")
            continue
        n = 0
        for url in urls:
            try:
                r = requests.get(url, timeout=60, headers=HDR)
                r.raise_for_status()
                cal = Calendar.from_ical(r.content)
            except Exception as ex:  # noqa: BLE001
                print(f"  ! {s.get('name')} feed: {str(ex)[:120]}")
                continue
            calname = str(cal.get("X-WR-CALNAME", ""))
            if SKIP.search(calname):
                continue
            for v in recurring_ical_events.of(cal).between(now - timedelta(days=1), now + timedelta(days=365)):
                title = str(v.get("SUMMARY", "")).strip()
                if not title or SKIP.search(title) or (skip and skip.search(title)):
                    continue
                st, allday = as_dt(v.decoded("DTSTART"))
                en = as_dt(v.decoded("DTEND"))[0] if v.get("DTEND") else st
                if allday and en > st:
                    en -= timedelta(minutes=1)  # ICS all-day end is exclusive
                if en < now:
                    continue
                desc = strip_html(str(v.get("DESCRIPTION", "")))
                loc = re.sub(r",?\s*(USA|United States)$", "", str(v.get("LOCATION", "")).strip())
                st_name = s.get("state", "")
                if loc and st_name and not loc.endswith(st_name):
                    loc = f"{loc}, {st_name}"
                z = re.search(r"\b(\d{5})(?:-\d{4})?\b", loc)
                lat, lng = (zips.get(z.group(1)) if z else None) or (s.get("lat"), s.get("lng"))
                uid = str(v.get("UID", title)) + st.isoformat()
                sid = "x-" + hashlib.md5((uid + url).encode()).hexdigest()[:12]
                seen.setdefault(sid, today)
                tzl = TZ_LABEL.get(st.strftime("%Z"), "") if not allday else ""
                link = str(v.get("URL", "")) or (re.search(r"https?://\S+", desc).group(0).rstrip(".,)")
                                                 if re.search(r"https?://\S+", desc) else s.get("page", ""))
                events.append({
                    "id": sid, "eid": "x-" + hashlib.md5((title + url).encode()).hexdigest()[:12],
                    "org": "", "council": s["name"], "title": title, "session": "",
                    "start": st.strftime("%Y-%m-%dT%H:%M") if not allday else st.strftime("%Y-%m-%dT00:00"),
                    "end": en.strftime("%Y-%m-%dT%H:%M"), "tz": tzl,
                    "startUtc": st.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
                    "endUtc": en.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
                    "lat": lat, "lng": lng, "location": loc or st_name,
                    "desc": desc[:600], "fees": sorted(set(re.findall(r"\$\s?\d[\d,]*(?:\.\d\d)?", desc)))[:6],
                    "url": link, "firstSeen": seen[sid], "source": calname or s["name"],
                    **tag(title, desc, set()),
                })
                n += 1
        print(f"  {s['name']}: {n} events from {len(urls)} calendar(s)")
    events.sort(key=lambda e: (e["startUtc"] or "", e["title"]))
    data.update(events=events, count=len(events))
    json.dump(data, open(OUT, "w"), separators=(",", ":"), ensure_ascii=False)
    json.dump(seen, open(SEEN, "w"))


if __name__ == "__main__":
    main()
