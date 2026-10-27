"""Build subscribable calendar feeds (.ics) from docs/data/events.json.

Creates docs/feeds/:
  merit-badges.ics             every merit badge program nationwide
  trainings.ics                every adult/youth training & certification
  state-<state>.ics            everything in one state (skips fundraisers & long-running listings)
  state-<state>-merit-badges.ics
Paste a feed's URL into Google Calendar ("From URL") or Outlook to have it stay up to date.
"""
import json
import os
import re
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "docs", "data", "events.json")
OUT = os.path.join(ROOT, "docs", "feeds")


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def esc(s):
    return re.sub(r"([\\,;])", r"\\\1", str(s or "")).replace("\n", "\\n")


def fold(line):
    out = []
    while len(line.encode()) > 74:
        cut = 74
        while len(line[:cut].encode()) > 74:
            cut -= 1
        out.append(line[:cut])
        line = " " + line[cut:]
    out.append(line)
    return "\r\n".join(out)


def dt(s):
    return s.replace("-", "").replace(":", "").replace("Z", "00Z")


def write(name, title, events):
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Scout Event Finder//EN", "CALSCALE:GREGORIAN",
             f"X-WR-CALNAME:{esc(title)}", "REFRESH-INTERVAL;VALUE=DURATION:PT12H", "X-PUBLISHED-TTL:PT12H"]
    for e in events:
        if not e.get("startUtc"):
            continue
        desc = (f"NOTE: {e['status']}\n\n" if e.get("delisted") else "") + f"{e['council']}\n{e['url']}\n\n" + ", ".join(e["badges"] + e["trainings"]) + "\n\n" + (e.get("desc") or "")[:500]
        lines += ["BEGIN:VEVENT", f"UID:{e['id']}@scout-event-finder", f"DTSTAMP:{stamp}",
                  f"DTSTART:{dt(e['startUtc'])}", f"DTEND:{dt(e.get('endUtc') or e['startUtc'])}",
                  fold("SUMMARY:" + esc(e["title"] + (f" – {e['session']}" if e.get("session") else ""))),
                  fold("LOCATION:" + esc(e.get("location"))), fold("DESCRIPTION:" + esc(desc)),
                  fold("URL:" + e["url"]), "END:VEVENT"]
    lines.append("END:VCALENDAR")
    with open(os.path.join(OUT, name), "w", newline="") as f:
        f.write("\r\n".join(lines) + "\r\n")


def main():
    data = json.load(open(SRC))
    os.makedirs(OUT, exist_ok=True)
    for f in os.listdir(OUT):
        if f.endswith(".ics"):
            os.remove(os.path.join(OUT, f))

    def short(e):
        try:
            a = datetime.fromisoformat(e["startUtc"].replace("Z", "+00:00"))
            b = datetime.fromisoformat(e["endUtc"].replace("Z", "+00:00"))
            return (b - a).days <= 21
        except (KeyError, ValueError, AttributeError):
            return True

    def keep(e):
        fund = "Fundraising / Dinners" in e["topics"] and not e["badges"] and not e["trainings"]
        admin = "Meetings & Admin" in e["topics"]
        return short(e) and not fund and not admin

    ev = [e for e in data["events"] if keep(e)]
    write("merit-badges.ics", "Scout Events – Merit Badges (US)", [e for e in ev if e["badges"]])
    write("trainings.ics", "Scout Events – Trainings (US)", [e for e in ev if e["trainings"]])
    write("online.ics", "Scout Events – Online", [e for e in ev if e.get("online")])
    states = {}
    for e in ev:
        parts = [p.strip() for p in (e.get("location") or "").split(",") if p.strip()]
        if len(parts) > 1:
            states.setdefault(parts[-1], []).append(e)
    index = []
    for st, items in sorted(states.items()):
        if len(items) < 3:
            continue
        s = slug(st)
        write(f"state-{s}.ics", f"Scout Events – {st}", items)
        mb = [e for e in items if e["badges"]]
        if mb:
            write(f"state-{s}-merit-badges.ics", f"Scout Events – {st} Merit Badges", mb)
        index.append({"state": st, "file": f"state-{s}.ics", "mb": f"state-{s}-merit-badges.ics" if mb else None,
                      "count": len(items)})
    json.dump(index, open(os.path.join(OUT, "index.json"), "w"))
    print(f"feeds: {len(index)} states + merit-badges + trainings")


if __name__ == "__main__":
    main()
