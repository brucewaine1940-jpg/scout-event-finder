"""Events from councils that register on Doubleknot (e.g. WLACC at bsa-la.doubleknot.com).

Doubleknot has no public event list or feed for a council, and its calendar listing is closed to robots.
What it does publish is a page and an "Add to calendar" file for every event. So this script:
  1. finds Doubleknot event links the council itself publishes: it crawls the council's websites
     (data/doubleknot_sources.json), reads the descriptions of events already collected from its
     Google calendars, and takes any seed IDs listed in the config or sent in through the submission form
  2. remembers every event it has found (data/doubleknot_known.json) until the event is over
  3. each night reads each event's calendar file for the exact date, time, address, title and description
Polite: one request at a time with a delay, a clear User-Agent, and only paths robots.txt allows.
"""
import hashlib
import html
import json
import os
import re
import sys
import time
from collections import deque
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser
from zoneinfo import ZoneInfo

import requests

sys.path.insert(0, os.path.dirname(__file__))
from tagging import tag  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "data", "doubleknot_sources.json")
KNOWN = os.path.join(ROOT, "data", "doubleknot_known.json")
EVENTS = os.path.join(ROOT, "docs", "data", "events.json")
SEEN = os.path.join(ROOT, "data", "first_seen.json")
ZIPS = os.path.join(ROOT, "docs", "data", "zips.json")
SUBMITTED = os.path.join(ROOT, "data", "submitted_links.json")  # written by submissions.py
HDR = {"User-Agent": "ScoutEventFinder/1.0 (volunteer Scout leader project; nightly, rate-limited)"}
DELAY = float(os.environ.get("DK_DELAY", "1.0"))
LA = ZoneInfo("America/Los_Angeles")
SKIP_EXT = re.compile(r"\.(?:jpe?g|png|gif|webp|svg|pdf|docx?|xlsx?|pptx?|zip|mp4|mp3|ics|css|js)(?:$|\?)", re.I)
SKIP_PATH = re.compile(r"/(?:wp-admin|wp-json|wp-content|feed|tag|author|cart|checkout|my-account)(?:/|$)|\?(?:replytocom|share)=", re.I)
TZL = {"PDT": "PT", "PST": "PT"}

session = requests.Session()
session.headers.update(HDR)


def load(p, d):
    try:
        with open(p) as f:
            return json.load(f)
    except (OSError, ValueError):
        return d


def event_links(text, sub):
    """(id, slug) pairs for this council's Doubleknot event links found in text."""
    rx = re.compile(rf"https?://{re.escape(sub)}\.doubleknot\.com/event/([a-z0-9\-]+)/(\d+)", re.I)
    return {(m.group(2), m.group(1).lower()) for m in rx.finditer(html.unescape(text or ""))}


def robots_for(start):
    rp = RobotFileParser()
    try:
        r = session.get(urljoin(start, "/robots.txt"), timeout=30)
        rp.parse(r.text.splitlines() if r.ok else [])
    except requests.RequestException:
        rp.parse([])
    return rp


def crawl(start, max_pages, sub):
    """Breadth-first crawl of one website (same host only), collecting Doubleknot event links."""
    host = urlparse(start).netloc.replace("www.", "")
    rp = robots_for(start)
    if not rp.can_fetch(HDR["User-Agent"], start):
        print(f"    {host}: robots.txt asks crawlers to stay out - skipped", flush=True)
        return set()
    queue, seen, found, pages = deque([start]), {start}, set(), 0
    # the site map, when there is one, adds pages the menus don't link to
    for sm in ("/sitemap_index.xml", "/sitemap.xml"):
        try:
            r = session.get(urljoin(start, sm), timeout=30)
            if r.ok and "<loc>" in r.text:
                maps = re.findall(r"<loc>([^<]+)</loc>", r.text)
                for m in maps:
                    if m.endswith(".xml"):
                        rr = session.get(m, timeout=30)
                        maps += re.findall(r"<loc>([^<]+)</loc>", rr.text) if rr.ok else []
                        time.sleep(DELAY)
                for u in maps:
                    if not u.endswith(".xml") and u not in seen:
                        seen.add(u)
                        queue.append(u)
                break
        except requests.RequestException:
            pass
    while queue and pages < max_pages:
        url = queue.popleft()
        if not rp.can_fetch(HDR["User-Agent"], url):
            continue
        try:
            r = session.get(url, timeout=30)
            time.sleep(DELAY)
        except requests.RequestException:
            continue
        if not r.ok or "html" not in r.headers.get("content-type", ""):
            continue
        pages += 1
        found |= event_links(r.text, sub)
        for href in re.findall(r'href="([^"#]+)"', r.text):
            u = urljoin(url, html.unescape(href)).split("#")[0]
            p = urlparse(u)
            if p.scheme in ("http", "https") and p.netloc.replace("www.", "") == host and u not in seen \
                    and not SKIP_EXT.search(p.path) and not SKIP_PATH.search(u):
                seen.add(u)
                queue.append(u)
    print(f"    {host}: {pages} pages read, {len(found)} Doubleknot event links", flush=True)
    return found


def read_ics(sub, eid):
    """The event's own 'Add to calendar' file: exact times, address, title, description."""
    from icalendar import Calendar
    try:
        r = session.get(f"https://{sub}.doubleknot.com/handlers/calenderhandler.ashx", params={"activitykey": eid}, timeout=30)
        time.sleep(DELAY)
    except requests.RequestException:
        return "error", None
    if r.status_code in (404, 410):
        return "gone", None
    if not r.ok or b"BEGIN:VEVENT" not in r.content:
        return ("gone" if r.ok else "error"), None
    try:
        cal = Calendar.from_ical(r.content)
    except ValueError:
        return "error", None
    return "ok", [c for c in cal.walk("VEVENT")]


def to_dt(v):
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=LA)
    return datetime(v.year, v.month, v.day, tzinfo=LA)


def main():
    sources = load(SRC, [])
    if not sources:
        print("No Doubleknot councils configured.")
        return
    known = load(KNOWN, {})
    seen = load(SEEN, {})
    zips = load(ZIPS, {})
    data = load(EVENTS, None)
    if data is None:
        sys.exit("events.json missing")
    submitted = load(SUBMITTED, [])
    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")
    out = []
    for src in sources:
        sub, council = src["subdomain"], src["council"]
        print(f"  {council} ({sub}.doubleknot.com)", flush=True)
        found = set()
        for start in src.get("crawl", []):
            found |= crawl(start, src.get("max_pages", 250), sub)
        # links inside events we already have (e.g. the council's Google calendars)
        for e in data["events"]:
            found |= event_links(f"{e.get('url', '')} {e.get('desc', '')}", sub)
        for s in submitted:
            found |= event_links(s, sub)
        for seed in src.get("seeds", []):  # event links added by hand
            found |= event_links(str(seed), sub)
        for eid, slug in found:
            k = f"{sub}:{eid}"
            known.setdefault(k, {"sub": sub, "id": eid, "slug": slug, "council": council, "found": today})
            if slug and not known[k].get("slug"):
                known[k]["slug"] = slug
        n_ok = n_gone = 0
        for k, info in list(known.items()):
            if info["sub"] != sub:
                continue
            status, vevents = read_ics(sub, info["id"])
            if status == "gone":
                known.pop(k)
                n_gone += 1
                continue
            if status == "error":
                vevents = info.get("last") or []  # keep last night's copy rather than drop it on a hiccup
                vevents = [{"_cached": True, **v} for v in vevents]
            else:
                vevents = [{
                    "summary": str(v.get("SUMMARY", "")).strip(),
                    "start": to_dt(v.decoded("DTSTART")).isoformat(),
                    "end": to_dt(v.decoded("DTEND") if v.get("DTEND") else v.decoded("DTSTART")).isoformat(),
                    "location": re.sub(r",?\s*US$", "", str(v.get("LOCATION", "")).strip()),
                    "desc": re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", str(v.get("DESCRIPTION", ""))))).strip(),
                } for v in vevents]
                info["last"] = vevents
            ended = all(datetime.fromisoformat(v["end"]) < now for v in vevents) if vevents else False
            if ended:
                known.pop(k)
                continue
            for v in vevents:
                st, en = datetime.fromisoformat(v["start"]).astimezone(LA), datetime.fromisoformat(v["end"]).astimezone(LA)
                if en < now:
                    continue
                z = re.search(r"\b(\d{5})(?:-\d{4})?\b", v["location"])
                zl = zips.get(z.group(1)) if z else None
                lat, lng = zl or (src.get("lat"), src.get("lng"))
                sid = "dk-" + hashlib.md5(f"{k}{v['start']}".encode()).hexdigest()[:12]
                seen.setdefault(sid, today)
                desc = v["desc"]
                url = f"https://{sub}.doubleknot.com/event/{info.get('slug') or 'event'}/{info['id']}"
                ev = {
                    "id": sid, "eid": f"dk-{sub}-{info['id']}", "org": "", "council": council,
                    "title": v["summary"], "session": "",
                    "start": st.strftime("%Y-%m-%dT%H:%M"), "end": en.strftime("%Y-%m-%dT%H:%M"),
                    "tz": TZL.get(st.strftime("%Z"), ""),
                    "startUtc": st.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
                    "endUtc": en.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
                    "lat": lat, "lng": lng, "approx": not zl, "location": v["location"],
                    "desc": desc[:600], "fees": sorted(set(re.findall(r"\$\s?\d[\d,]*(?:\.\d\d)?", desc)))[:6],
                    "url": url, "firstSeen": seen[sid], "source": "Doubleknot",
                    **tag(v["summary"], desc, set(), v["location"]),
                }
                if v.get("_cached"):
                    ev["status"] = "Couldn't refresh from Doubleknot tonight - confirm on the event page."
                out.append(ev)
                n_ok += 1
        print(f"    {n_ok} upcoming sessions from {sum(1 for x in known.values() if x['sub'] == sub)} known events"
              f" ({n_gone} removed by the council)", flush=True)
    # Doubleknot has the registration link, so it replaces the same event copied onto a Google calendar
    norm = lambda s: re.sub(r"\W+|\b20\d\d\b", "", s.lower())
    dk_keys = {(norm(e["title"]), e["start"][:10]) for e in out}
    events = [e for e in data["events"] if not e["id"].startswith("dk-")
              and not (e["id"].startswith("x-") and (norm(e["title"]), e["start"][:10]) in dk_keys)]
    events += out
    events.sort(key=lambda e: (e["startUtc"] or "", e["title"]))
    data.update(events=events, count=len(events))
    json.dump(data, open(EVENTS, "w"), separators=(",", ":"), ensure_ascii=False)
    json.dump(known, open(KNOWN, "w"), indent=1, ensure_ascii=False)
    json.dump(seen, open(SEEN, "w"))


if __name__ == "__main__":
    main()
