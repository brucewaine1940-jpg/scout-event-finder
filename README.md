# Scout Event Finder

A free, nightly-updated search engine for Scouting America council events: merit badge days, camps, trainings, camporees and more.

**Why:** there's no central place to answer "what can our unit do this weekend / this month?" Council calendars are scattered across Black Pug (scoutingevent.com), Doubleknot, Teamup and plain web pages, and the built-in filters are weak. This project pulls them into one clean database and puts a better search on top.

## How it works

| Piece | What it does |
|---|---|
| `scraper/scrape_global.py` | Every night, reads all public events on global.scoutingevent.com (every Black Pug / 247Scouting council): dates, council, location, map coordinates, site categories, description, fees |
| `scraper/tagging.py` | Tags each event with merit badges, trainings (WFA, Wood Badge, NYLT, RSO, Lifeguard…), event type and audience (Cub / Scouts BSA / Venturing / Adults). Edit the keyword lists here to improve tagging |
| `scraper/extra_feeds.py` | Adds councils that are NOT on Black Pug, from `data/extra_sources.json`: any ICS feed, or a web page with an embedded Google Calendar (e.g. Western LA County Council). Recurring events are expanded |
| `scraper/build_feeds.py` | Builds subscribable calendar feeds in `docs/feeds/` (all merit badge events, all trainings, and one feed per state) |
| `.github/workflows/update-events.yml` | Runs the above nightly (~3:17 AM Pacific) on GitHub Actions and saves the results. Can also be run by hand from the Actions tab |
| `docs/` | The search website (GitHub Pages). All filtering happens in the browser |
| `docs/data/events.json` | The database: one record per event session |

## Search features
Keyword · distance from any ZIP · state · date presets (this weekend, 7/30/90 days) or custom range · audience · merit badge (pick one or more) · event type · training type · council · hide long-running listings and fundraisers · "new this week" · sort by soonest/closest/newest · add to calendar · shareable links (filters are saved in the URL).

## Add another council
Edit `data/extra_sources.json` on GitHub (pencil icon) and add an entry, then run the workflow from the Actions tab:
```json
{"name": "Long Beach Area Council", "ics": "https://teamup.com/.../events.ics", "state": "California", "lat": 33.80, "lng": -118.17}
```
or, for a council calendar page that embeds a Google Calendar:
```json
{"name": "Some Council", "google_embed_page": "https://example.org/calendar/", "state": "California", "lat": 34.0, "lng": -118.0}
```
`lat`/`lng` is a fallback map point (usually the council office) for events without a ZIP code in their address.

## Cost
$0. Public GitHub repo + GitHub Actions + GitHub Pages.

## Be a good neighbor
The collector identifies itself, waits ~1 second between requests, and only fetches each event page once (cached in `data/details_cache.json`). Always confirm details and register on the council's own event page. Not affiliated with Scouting America or Black Pug Software.

## Roadmap
- [x] Black Pug councils nationwide (global.scoutingevent.com)
- [x] Western Los Angeles County Council (Google Calendar embed)
- [x] Subscribable .ics feeds (merit badges, trainings, per state)
- [ ] Long Beach Area Council (Teamup ICS link needed), Ventura County Council
- [ ] Doubleknot councils
- [ ] Independent sources: college Merit Badge Universities, OA lodges, high-adventure bases
- [ ] Link to the troop Trailbook and award tracker
