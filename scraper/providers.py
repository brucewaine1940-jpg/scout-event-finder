"""Merit badge provider directory (museums, businesses, online academies...) from data/providers.json.

Nightly, for every provider:
  * reads its web page, notes when the page last changed, and pulls out any upcoming dates it mentions
  * turns recurring schedules ("4th Saturday of the month") into dated events
  * optionally ("auto_events") turns dates found on the page into events
Writes docs/data/providers.json for the website's Providers tab and adds the events to events.json.
To add a provider, copy an entry in data/providers.json - no code changes needed.
"""
import hashlib
import json
import os
import re
import sys
import time
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup
from dateutil.rrule import rrulestr

sys.path.insert(0, os.path.dirname(__file__))
from tagging import tag  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "data", "providers.json")
WATCH = os.path.join(ROOT, "data", "provider_watch.json")
SEEN = os.path.join(ROOT, "data", "first_seen.json")
ZIPS = os.path.join(ROOT, "docs", "data", "zips.json")
EVENTS = os.path.join(ROOT, "docs", "data", "events.json")
OUT = os.path.join(ROOT, "docs", "data", "providers.json")
HDR = {"User-Agent": "ScoutEventFinder/1.0 (volunteer Scout leader project; nightly, rate-limited)"}
LA = ZoneInfo("America/Los_Angeles")

MONTHS = {m: i + 1 for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}
DATE_RX = re.compile(
    r"\b(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|June?|July?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|"
    r"Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\.?\s+(\d{1,2})(?:st|nd|rd|th)?\b(?:,?\s+(20\d\d))?", re.I)
LIST_GAP = re.compile(r"^[\s,;&/]*(?:(?:or|and)\s+)?(?:(?:mon|tues|wednes|thurs|fri|satur|sun)day,?\s*)?$", re.I)
NUM_RX = re.compile(r"\b(\d{1,2})/(\d{1,2})/(20\d\d|\d\d)\b")


def find_dates(text, today):
    """Upcoming dates written on a page, e.g. 'Saturdays Feb 13, Mar 27, or Sept 11, 2027'."""
    found = set()
    matches = list(DATE_RX.finditer(text))
    for i, m in enumerate(matches):
        month, day, year = MONTHS[m.group(1)[:3].lower()], int(m.group(2)), m.group(3)
        if not year:
            # a list like "Feb 13, Mar 27, or Sept 11, 2027" shares the year written at its end
            prev = m
            for nxt in matches[i + 1:i + 12]:
                if not LIST_GAP.match(text[prev.end():nxt.start()]):
                    break
                if nxt.group(3):
                    year = nxt.group(3)
                    break
                prev = nxt
        try:
            if year:
                d = date(int(year), month, day)
            else:
                d = date(today.year, month, day)
                if d < today:
                    d = date(today.year + 1, month, day)
        except ValueError:
            continue
        found.add(d)
    for m in NUM_RX.finditer(text):
        y = int(m.group(3)) + (2000 if len(m.group(3)) == 2 else 0)
        try:
            found.add(date(y, int(m.group(1)), int(m.group(2))))
        except ValueError:
            pass
    return sorted(d for d in found if today <= d <= today + timedelta(days=400))


def load(p, d):
    try:
        with open(p) as f:
            return json.load(f)
    except (OSError, ValueError):
        return d


def make_event(pid, prov, title, d, start, end, badges, latlng, seen, today_s, kind):
    st = datetime.combine(d, datetime.strptime(start or "09:00", "%H:%M").time(), LA)
    en = datetime.combine(d, datetime.strptime(end or start or "12:00", "%H:%M").time(), LA)
    sid = f"p-{pid}-{d.isoformat()}-{hashlib.md5(title.encode()).hexdigest()[:4]}"
    seen.setdefault(sid, today_s)
    online = prov.get("format", "").lower().startswith("online")
    desc = f"{prov.get('schedule', '')} {prov.get('notes', '')} ({kind} - confirm on the provider's page before you go.)"
    t = tag(title + " merit badge", desc, set(), "Online" if online else prov.get("address", ""))
    t["badges"] = sorted(set(badges or [b for b in prov.get("badges", []) if b != "*"]) | set(t["badges"]))
    t["trainings"] = []  # provider notes mention "counselors"; these are badge classes, not trainings
    t["topics"] = [x for x in t["topics"] if x != "Training"]
    if "Merit Badge Program" not in t["topics"]:
        t["topics"].insert(0, "Merit Badge Program")
    if online and not t["online"]:
        t["online"] = True
        t["topics"].append("Online / Virtual")
    addr = prov.get("address", "")
    state = "California" if re.search(r"\bCA\b", addr) else ""
    return {
        "id": sid, "eid": f"p-{pid}-{hashlib.md5(title.encode()).hexdigest()[:6]}", "org": "",
        "council": prov["name"], "title": title, "session": "",
        "start": st.strftime("%Y-%m-%dT%H:%M"), "end": en.strftime("%Y-%m-%dT%H:%M"), "tz": "PT" if state else "",
        "startUtc": st.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
        "endUtc": en.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
        "lat": latlng[0] if latlng else None, "lng": latlng[1] if latlng else None,
        "location": "Online" if online else (re.sub(r",?\s*CA\s+\d{5}$", "", addr) + (", California" if state else "")),
        "desc": desc[:600], "fees": [m for m in re.findall(r"\$\d+", prov.get("cost", ""))[:1]],
        "url": prov.get("url", ""), "firstSeen": seen[sid], "source": "Provider directory", "provider": True, **t,
    }


def main():
    providers = load(SRC, [])
    watch, seen, zips = load(WATCH, {}), load(SEEN, {}), load(ZIPS, {})
    data = load(EVENTS, None)
    if data is None:
        sys.exit("events.json missing")
    now = datetime.now(LA)
    today = now.date()
    today_s = today.isoformat()
    events = [e for e in data["events"] if not e["id"].startswith("p-")]
    out = []
    for prov in providers:
        pid = re.sub(r"[^a-z0-9]+", "-", prov["name"].lower()).strip("-")[:40]
        latlng = zips.get(prov.get("zip", ""))
        w = watch.get(prov.get("url", ""), {})
        dates, ok = [], None
        if prov.get("url"):
            try:
                r = requests.get(prov["url"], headers=HDR, timeout=60)
                ok = r.ok
                if r.ok:
                    soup = BeautifulSoup(r.text, "html.parser")
                    for t in soup(["script", "style", "nav", "footer", "header", "noscript"]):
                        t.decompose()
                    text = re.sub(r"\s+", " ", soup.get_text(" "))
                    h = hashlib.md5(text.encode()).hexdigest()
                    if w.get("hash") != h:
                        w = {"hash": h, "changed": today_s if w.get("hash") else w.get("changed", "")}
                    dates = find_dates(text, today)
            except requests.RequestException as ex:
                print(f"  ! {prov['name']}: {ex}")
                ok = False
            time.sleep(1.5)
        w["checked"] = today_s
        w["ok"] = ok
        if prov.get("url"):
            watch[prov["url"]] = w
        n_ev = 0
        # recurring schedules
        for rec in prov.get("recurring", []):
            rule = rrulestr(rec["rrule"], dtstart=datetime.combine(today, datetime.min.time()))
            for dt in rule.between(datetime.combine(today, datetime.min.time()) - timedelta(seconds=1),
                                   datetime.combine(today + timedelta(days=365), datetime.min.time()), inc=True):
                events.append(make_event(pid, prov, rec["title"], dt.date(), rec.get("start"), rec.get("end"),
                                         rec.get("badges"), latlng, seen, today_s, "Recurring schedule"))
                n_ev += 1
        # dates written on the provider's page
        auto = prov.get("auto_events")
        if auto:
            for d in dates:
                key = (auto.get("skip_if_listed") or "").lower()
                if key and any(key in f"{e['title']} {e['council']} {e['location']}".lower() and e["start"][:10] == d.isoformat()
                               for e in events):
                    continue  # already listed elsewhere (e.g. on Eventbrite)
                events.append(make_event(pid, prov, auto["title"], d, auto.get("start"), auto.get("end"),
                                         None, latlng, seen, today_s, "Date from provider's page"))
                n_ev += 1
        out.append({
            "id": pid, "name": prov["name"], "badges": prov.get("badges", []), "format": prov.get("format", ""),
            "address": prov.get("address", ""), "lat": latlng[0] if latlng else None, "lng": latlng[1] if latlng else None,
            "url": prov.get("url", ""), "cost": prov.get("cost", ""), "schedule": prov.get("schedule", ""),
            "notes": prov.get("notes", ""), "dates": [d.isoformat() for d in dates[:10]],
            "pageChanged": w.get("changed", ""), "checked": today_s, "ok": ok, "events": n_ev,
        })
        print(f"  {prov['name']}: {len(dates)} dates on page, {n_ev} events")
    events.sort(key=lambda e: (e["startUtc"] or "", e["title"]))
    data.update(events=events, count=len(events))
    json.dump(data, open(EVENTS, "w"), separators=(",", ":"), ensure_ascii=False)
    json.dump({"updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"), "providers": out},
              open(OUT, "w"), ensure_ascii=False)
    json.dump(watch, open(WATCH, "w"))
    json.dump(seen, open(SEEN, "w"))


if __name__ == "__main__":
    main()
