"""Events people send in through the "Submit an event" Google Form, after a leader approves them.

The form's response Sheet has an "Approved" tab that shows only rows marked yes (and never the
submitter's email). That tab is published to the web as CSV; put its link in data/submissions.json.
Nightly this script:
  - saves every link from approved rows to data/submitted_links.json (Doubleknot links are then
    picked up by doubleknot.py, which reads the exact details from the event itself)
  - adds the other approved Scout events to events.json (id prefix s-)
  - saves approved public programs to data/submitted_public.json for the weekend pages / Trailbook
"""
import csv
import hashlib
import io
import json
import os
import re
import sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import requests

sys.path.insert(0, os.path.dirname(__file__))
from tagging import tag  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG = os.path.join(ROOT, "data", "submissions.json")
LINKS = os.path.join(ROOT, "data", "submitted_links.json")
PUBLIC = os.path.join(ROOT, "data", "submitted_public.json")
EVENTS = os.path.join(ROOT, "docs", "data", "events.json")
SEEN = os.path.join(ROOT, "data", "first_seen.json")
ZIPS = os.path.join(ROOT, "docs", "data", "zips.json")
LA = ZoneInfo("America/Los_Angeles")
HDR = {"User-Agent": "ScoutEventFinder/1.0 (volunteer Scout leader project)"}
PROGRAMS = {"cub": "Cub Scouts", "scouts bsa": "Scouts BSA", "venturing": "Venturing", "sea scout": "Sea Scouts",
            "adult": "Adults / Leaders", "leader": "Adults / Leaders"}


def load(p, d):
    try:
        with open(p) as f:
            return json.load(f)
    except (OSError, ValueError):
        return d


def col(row, *names):
    """Value of the first column whose header contains one of the names (headers can be reworded)."""
    for k, v in row.items():
        if any(n in (k or "").lower() for n in names):
            return (v or "").strip()
    return ""


def parse_dt(d, t):
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m/%d/%y"):
        try:
            day = datetime.strptime(d, fmt)
            break
        except ValueError:
            day = None
    if not day:
        return None
    tm = None
    for fmt in ("%I:%M:%S %p", "%I:%M %p", "%H:%M:%S", "%H:%M"):
        try:
            tm = datetime.strptime(t.upper(), fmt).time()
            break
        except ValueError:
            pass
    return datetime.combine(day.date(), tm or datetime.min.time(), LA), tm is not None


def main():
    url = load(CFG, {}).get("csv_url", "")
    if not url:
        print("  submissions: no form connected yet (data/submissions.json)")
        return
    try:
        r = requests.get(url, headers=HDR, timeout=60)
        r.raise_for_status()
        r.encoding = "utf-8"
    except requests.RequestException as ex:
        print(f"  ! submissions: {ex}")
        return
    rows = list(csv.DictReader(io.StringIO(r.text)))
    zips, seen = load(ZIPS, {}), load(SEEN, {})
    data = load(EVENTS, None)
    if data is None:
        sys.exit("events.json missing")
    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")
    links, scout, public = [], [], []
    for row in rows:
        link = col(row, "link", "url", "registration")
        if link:
            links.append(link)
        if "doubleknot.com/event/" in link:
            continue  # doubleknot.py reads these from the source
        title = col(row, "event name", "title")
        start = parse_dt(col(row, "start date"), col(row, "start time"))
        if not title or not start:
            continue
        st, timed = start
        end = parse_dt(col(row, "end date") or col(row, "start date"), col(row, "end time"))
        en = end[0] if end and end[0] >= st else st
        if (en if timed else en.replace(hour=23, minute=59)) < now:
            continue
        where, zipc = col(row, "location", "address"), col(row, "zip")
        z = re.search(r"\b(\d{5})\b", zipc or where)
        zl = zips.get(z.group(1)) if z else None
        who = col(row, "who is it for").lower()
        programs = sorted({v for k, v in PROGRAMS.items() if k in who})
        desc = col(row, "description", "details")
        badges_txt = col(row, "merit badge")
        sid = "s-" + hashlib.md5(f"{title}{st.isoformat()}{link}".encode()).hexdigest()[:12]
        seen.setdefault(sid, today)
        t = tag(title, f"{desc} {badges_txt}", set(), where)
        if programs:
            t["programs"] = programs
        ev = {
            "id": sid, "eid": sid, "org": "", "council": col(row, "organizer", "host") or "Submitted event",
            "title": title, "session": "", "start": st.strftime("%Y-%m-%dT%H:%M"), "end": en.strftime("%Y-%m-%dT%H:%M"),
            "tz": "PT" if timed else "", "startUtc": st.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
            "endUtc": en.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
            "lat": zl[0] if zl else None, "lng": zl[1] if zl else None, "approx": False, "location": where,
            "desc": desc[:600], "fees": sorted(set(re.findall(r"\$\s?\d[\d,]*(?:\.\d\d)?", desc)))[:6],
            "url": link, "firstSeen": seen[sid], "source": "Submitted by a leader", "submitted": True, **t,
        }
        kind = col(row, "scout event or")
        (public if "public" in kind.lower() else scout).append(ev)
    # don't duplicate something another source already lists on the same day
    norm = lambda s: re.sub(r"\W+|\b20\d\d\b", "", s.lower())
    have = {(norm(e["title"]), e["start"][:10]) for e in data["events"] if not e["id"].startswith("s-")}
    scout = [e for e in scout if (norm(e["title"]), e["start"][:10]) not in have]
    events = [e for e in data["events"] if not e["id"].startswith("s-")] + scout
    events.sort(key=lambda e: (e["startUtc"] or "", e["title"]))
    data.update(events=events, count=len(events))
    for e in public:
        e.update(source="Public program", provider=False, trailbook="")
    json.dump(data, open(EVENTS, "w"), separators=(",", ":"), ensure_ascii=False)
    json.dump(sorted(set(links)), open(LINKS, "w"), indent=1)
    json.dump(public, open(PUBLIC, "w"), ensure_ascii=False)
    json.dump(seen, open(SEEN, "w"))
    print(f"  submissions: {len(rows)} approved rows -> {len(scout)} Scout events, {len(public)} public programs, "
          f"{sum('doubleknot.com/event/' in x for x in links)} Doubleknot links")


if __name__ == "__main__":
    main()
