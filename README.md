# Scout Event Finder

A free, nightly-updated search engine for Scouting America council events: merit badge days, camps, trainings, camporees and more.

**Why:** there's no central place to answer "what can our unit do this weekend / this month?" Council calendars are scattered across Black Pug (scoutingevent.com), Doubleknot, Teamup and plain web pages, and the built-in filters are weak. This project pulls them into one clean database and puts a better search on top.

## How it works

| Piece | What it does |
|---|---|
| `scraper/scrape_global.py` | Every night, reads all public events on global.scoutingevent.com (every Black Pug / 247Scouting council): dates, council, location, map coordinates, site categories, description, fees |
| `scraper/tagging.py` | Tags each event with merit badges, trainings (WFA, Wood Badge, NYLT, RSO, Lifeguard…), event type and audience (Cub / Scouts BSA / Venturing / Adults). Edit the keyword lists here to improve tagging |
| `scraper/extra_feeds.py` | Adds councils that are NOT on Black Pug, from `data/extra_sources.json`: any ICS feed, or a web page with an embedded Google Calendar (e.g. Western LA County Council). Recurring events are expanded |
| `scraper/eventbrite.py` | Scouting events from the Eventbrite organizers in `data/eventbrite_organizers.json` (museums, independent counselors, online classes), through Eventbrite's official API. Needs the `EVENTBRITE_TOKEN` secret (below) |
| `scraper/providers.py` | The **merit badge provider directory** in `data/providers.json`: re-checks each provider's page nightly, pulls out dates it mentions, turns recurring schedules into events, and powers the Providers tab |
| `scraper/nps.py` | Ranger programs from the National Park Service API, saved to `docs/data/ranger_programs.json` for the Trailbook (public programs are not listed as Scout events). Needs the `NPS_API_KEY` secret (below) |
| `scraper/ridb.py` | Recreation.gov group campgrounds within 200 mi, saved to `docs/data/group_campsites.json` for the Trailbook. Needs the `RIDB_API_KEY` secret |
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
or, for a council website built on **Councilware** (WordPress; e.g. Ventura County Council):
```json
{"name": "Some Council", "councilware": "https://www.example-council.org", "calendar_ids": [1], "state": "California", "lat": 34.2, "lng": -119.0}
```
or, for a council calendar page that embeds a Google Calendar:
```json
{"name": "Some Council", "google_embed_page": "https://example.org/calendar/", "state": "California", "lat": 34.0, "lng": -118.0}
```
`lat`/`lng` is a fallback map point (usually the council office) for events without a ZIP code in their address.

## Add a merit badge provider
Edit `data/providers.json` and copy an existing entry. Useful fields:
- `badges` (official names), `format` ("In person", "Online, live", "Online, on demand"), `address`, `zip`, `url`, `cost`, `schedule`, `notes`
- `recurring`: a repeating schedule, e.g. `{"title": "Railroading Merit Badge Program", "rrule": "FREQ=MONTHLY;BYDAY=4SA", "start": "09:00", "end": "13:00"}`
- `auto_events`: turn dates written on the provider's page into events, e.g. `{"title": "Merit Badge Day", "start": "09:00", "end": "15:00"}`

## Turn on Eventbrite (free, one-time)
Eventbrite blocks automated page reads, so this uses their official API:
1. Sign in at eventbrite.com, open **Account Settings → Developer Links → API Keys**, and create a key (any app name/URL).
2. Copy the **Private token**.
3. In this repo: **Settings → Secrets and variables → Actions → New repository secret**. Name it `EVENTBRITE_TOKEN` and paste the token.
4. To follow another organizer, add the number at the end of their `eventbrite.com/o/...` link to `data/eventbrite_organizers.json`.

## Turn on National Park Service ranger programs (free, one-time)
1. Request a free key at https://www.nps.gov/subjects/developer/get-started.htm (it arrives by email).
2. Add it as a repository secret named `NPS_API_KEY` (Settings → Secrets and variables → Actions).
3. Edit `PARKS` in `scraper/nps.py` to change which parks are included.

## Cost
$0. Public GitHub repo + GitHub Actions + GitHub Pages.

## Be a good neighbor
The collector identifies itself, waits ~1 second between requests, and only fetches each event page once (cached in `data/details_cache.json`). Always confirm details and register on the council's own event page. Not affiliated with Scouting America or Black Pug Software.

## Roadmap
- [x] Black Pug councils nationwide (global.scoutingevent.com)
- [x] Western Los Angeles County Council (Google Calendar embed)
- [x] Subscribable .ics feeds (merit badges, trainings, per state)
- [x] Ventura County Council (Councilware), Wiatava Lodge (OC Order of the Arrow)
- [x] Scope rule: the Event Finder lists programs made for Scouts only. Public programs (ranger talks, library and city rec, trail work days) and places to go belong in the Trailbook; NPS and Recreation.gov data is collected here for it
- [x] Quick picks: merit badges, summer camp, high adventure, NYLT/NAYLE, OA, service, ranger programs, online
- [ ] Doubleknot councils
- [x] Eventbrite listings (museums, independent counselors, online classes)
- [x] Merit badge provider directory with nightly page checks
- [ ] More providers (college Merit Badge Universities, OA lodges, high-adventure bases)
- [ ] Link to the troop Trailbook and award tracker
