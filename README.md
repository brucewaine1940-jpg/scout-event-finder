# Scout Event Finder

A free, nightly-updated search engine for Scouting America council events: merit badge days, camps, trainings, camporees and more.

**Why:** there's no central place to answer "what can our unit do this weekend / this month?" Council calendars are scattered across Black Pug (scoutingevent.com), Doubleknot, Teamup and plain web pages, and the built-in filters are weak. This project pulls them into one clean database and puts a better search on top.

## How it works

| Piece | What it does |
|---|---|
| `scraper/scrape_global.py` | Every night, reads all public events on global.scoutingevent.com (every Black Pug / 247Scouting council): dates, council, location, map coordinates, site categories, description, fees |
| `scraper/tagging.py` | Tags each event with merit badges, trainings (WFA, Wood Badge, NYLT, RSO, Lifeguard…), event type and audience (Cub / Scouts BSA / Venturing / Adults). Edit the keyword lists here to improve tagging |
| `scraper/extra_feeds.py` | Optional: merges extra ICS calendar feeds listed in `data/extra_sources.json` (for councils not on Black Pug) |
| `.github/workflows/update-events.yml` | Runs the above nightly (~3:17 AM Pacific) on GitHub Actions and saves the results. Can also be run by hand from the Actions tab |
| `docs/` | The search website (GitHub Pages). All filtering happens in the browser |
| `docs/data/events.json` | The database: one record per event session |

## Search features
Keyword · distance from any ZIP · state · date presets (this weekend, 7/30/90 days) or custom range · audience · merit badge (pick one or more) · event type · training type · council · hide long-running listings and fundraisers · "new this week" · sort by soonest/closest/newest · add to calendar · shareable links (filters are saved in the URL).

## Cost
$0. Public GitHub repo + GitHub Actions + GitHub Pages.

## Be a good neighbor
The collector identifies itself, waits ~1 second between requests, and only fetches each event page once (cached in `data/details_cache.json`). Always confirm details and register on the council's own event page. Not affiliated with Scouting America or Black Pug Software.

## Roadmap
- [ ] Add non-Black-Pug councils (Doubleknot, Teamup, WordPress calendars, Google calendars)
- [ ] Scrapers for councils with no feed (e.g. Western LA County, Ventura County)
- [ ] Independent sources: college Merit Badge Universities, OA lodges, high-adventure bases
- [ ] Subscribable .ics feeds per saved search
- [ ] Link to the troop Trailbook and award tracker
