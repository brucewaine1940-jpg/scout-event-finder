"""Merit badge / Scouting events from Eventbrite organizers (museums, independent counselors, online classes...).

Eventbrite blocks automated page reads from GitHub's servers, so this uses Eventbrite's official API instead.
It needs a free Eventbrite API key saved as the GitHub secret EVENTBRITE_TOKEN; without it this step is skipped.
It follows the organizers listed in data/eventbrite_organizers.json (the number at the end of an organizer's
eventbrite.com/o/... link) and keeps their Scouting-related events.
"""
import json
import os
import re
import sys
import time
from datetime import datetime, timezone

import requests

sys.path.insert(0, os.path.dirname(__file__))
from tagging import tag  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "data", "events.json")
ORGS = os.path.join(ROOT, "data", "eventbrite_organizers.json")
SEEN = os.path.join(ROOT, "data", "first_seen.json")
ZIPS = os.path.join(ROOT, "docs", "data", "zips.json")
HDR = {"User-Agent": "ScoutEventFinder/1.0 (volunteer Scout leader project; nightly, rate-limited)"}

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


def load(p, d):
    try:
        with open(p) as f:
            return json.load(f)
    except (OSError, ValueError):
        return d


API = "https://www.eventbriteapi.com/v3"


def api_events(org_id, token):
    """Upcoming events for one organizer. Tries the documented parameters first, then simpler ones."""
    hdr = {"Authorization": f"Bearer {token}", **HDR}
    attempts = [{"status": "live", "order_by": "start_asc", "expand": "venue"},
                {"time_filter": "current_future", "expand": "venue"},
                {"expand": "venue"}]
    for base in attempts:
        out, cont, ok = [], None, True
        for _ in range(10):
            params = dict(base, **({"continuation": cont} if cont else {}))
            try:
                r = requests.get(f"{API}/organizers/{org_id}/events/", params=params, headers=hdr, timeout=60)
            except requests.RequestException as ex:
                print(f"  ! organizer {org_id}: {ex}")
                return out
            time.sleep(0.5)
            if not r.ok:
                print(f"  ! organizer {org_id}: HTTP {r.status_code} with {sorted(base)}: {r.text[:200]}")
                ok = False
                break
            j = r.json()
            out += j.get("events", [])
            pg = j.get("pagination", {})
            if not pg.get("has_more_items") or not pg.get("continuation"):
                break
            cont = pg["continuation"]
        if ok:
            return out
    return []


def main():
    token = os.environ.get("EVENTBRITE_TOKEN", "").strip()
    if not token:
        print("  Eventbrite: no EVENTBRITE_TOKEN secret set - skipping (see README)")
        return
    data = load(OUT, None)
    if not data:
        sys.exit("events.json missing - run scrape_global.py first")
    orgs = load(ORGS, [])
    seen, zips = load(SEEN, {}), load(ZIPS, {})
    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")
    events = [e for e in data["events"] if not e["id"].startswith("eb-")]
    n = 0
    for org in orgs:
        for e in api_events(org["id"], token):
            title = re.sub(r"\s+", " ", (e.get("name") or {}).get("text") or "").strip()
            desc = re.sub(r"\s+", " ", (e.get("description") or {}).get("text") or "").strip()
            if not org.get("all_events") and not scout_related({"name": title, "description": desc}):
                continue
            st = datetime.fromisoformat(e["start"]["utc"].replace("Z", "+00:00"))
            en = datetime.fromisoformat(e["end"]["utc"].replace("Z", "+00:00"))
            if en < now:
                continue
            tzname = e["start"].get("timezone") or "UTC"
            try:
                from zoneinfo import ZoneInfo
                lst, len_ = st.astimezone(ZoneInfo(tzname)), en.astimezone(ZoneInfo(tzname))
            except Exception:  # noqa: BLE001
                lst, len_ = st, en
            online = bool(e.get("online_event"))
            v = e.get("venue") or {}
            a = v.get("address") or {}
            region = STATES.get((a.get("region") or "").upper(), a.get("region") or "")
            z = (a.get("postal_code") or "")[:5]
            latlng = zips.get(z)
            if not latlng and a.get("latitude"):
                try:
                    latlng = [float(a["latitude"]), float(a["longitude"])]
                except (TypeError, ValueError):
                    latlng = None
            place = "Online" if online else ", ".join(x for x in [v.get("name"), a.get("city"), region] if x)
            sid = "eb-" + str(e.get("id"))
            seen.setdefault(sid, today)
            # these organizers are known merit badge providers, so a bare badge name in the title counts
            ttl = title if re.search(r"merit[\s-]*badge|\bMBU?\b", title, re.I) else f"{title} merit badge"
            t = tag(ttl, desc, set(), place)
            if online and not t["online"]:
                t["online"] = True
                t["topics"].append("Online / Virtual")
            if t["online"]:
                place = "Online"
            abbr = lst.strftime("%Z")
            tzl = {"PDT": "PT", "PST": "PT", "MDT": "MT", "MST": "MT", "CDT": "CT", "CST": "CT", "EDT": "ET",
                   "EST": "ET", "HST": "HT", "AKDT": "AKT", "AKST": "AKT"}.get(abbr, abbr if abbr.isalpha() else "")
            events.append({
                "id": sid, "eid": sid, "org": "", "council": org.get("name") or "Eventbrite listing",
                "title": title, "session": "",
                "start": lst.strftime("%Y-%m-%dT%H:%M"), "end": len_.strftime("%Y-%m-%dT%H:%M"),
                "tz": tzl or tz_label(region, lst),
                "startUtc": st.strftime("%Y-%m-%dT%H:%MZ"), "endUtc": en.strftime("%Y-%m-%dT%H:%MZ"),
                "lat": latlng[0] if latlng else None, "lng": latlng[1] if latlng else None, "location": place,
                "desc": desc[:600], "fees": ["Free"] if e.get("is_free") else [],
                "url": e.get("url", ""), "firstSeen": seen[sid], "source": "Eventbrite", **t,
            })
            n += 1
    events.sort(key=lambda x: (x["startUtc"] or "", x["title"]))
    data.update(events=events, count=len(events))
    json.dump(data, open(OUT, "w"), separators=(",", ":"), ensure_ascii=False)
    json.dump(seen, open(SEEN, "w"))
    print(f"  Eventbrite: {n} upcoming events from {len(orgs)} organizers")


if __name__ == "__main__":
    main()
