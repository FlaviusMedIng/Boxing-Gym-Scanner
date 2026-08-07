# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

A scanner that looks for commercial premises to rent in Geneva suitable for a
boxing gym (the user's father's business). It scrapes several Swiss real
estate sites, filters by surface/rent/district/property-type/changing-room
keywords, keeps history in SQLite, and notifies by Telegram/email. It runs
for free on GitHub Actions (cron every 3h) — there is no server, no paid
hosting, no database other than the committed SQLite file. The father, who
is not technical, edits the search criteria himself from a public web page
(no GitHub account needed) — see the `docs/criteria.html` section below.

GitHub repo: `FlaviusMedIng/Boxing-Gym-Scanner` (public since 2026-08-07,
specifically so GitHub Pages could serve the results/criteria site — see
below). Telegram, email, and criteria-edit secrets are already configured
on that repo (`TELEGRAM_*`, `EMAIL_*`, `CRITERIA_EDIT_TOKEN`).

## Commands

```bash
pip install -r requirements.txt
playwright install chromium     # required once, Playwright drives real Chromium for JS-heavy sites

python main.py                  # run one full scan: scrape -> filter/score -> SQLite -> exports -> notify
streamlit run dashboard/app.py  # browse data/listings.db locally (all listings, not just matches)
python -m py_compile main.py scrapers/*.py utils/*.py storage/*.py filters/*.py scoring/*.py notifier/*.py dashboard/app.py scripts/*.py
```

There is no unit test suite. Scrapers are validated by fetching the real site
live with Playwright and inspecting the actual HTML with BeautifulSoup before
writing/fixing a selector — see "Debugging a scraper" below.

## Architecture

**Pipeline (`main.py` is the only orchestrator):**
`scrapers/*` (raw listings, no filtering) → dedupe by `id` (md5 of URL) →
`filters/gym_filter.py` (matches criteria?) + `scoring/gym_score.py` (0-100
score) → `storage/database.py` (SQLite upsert, tracks new/changed/removed) →
`storage/excel_export.py` (CSV/XLSX) + `storage/site_generator.py`
(`docs/index.html`) → `notifier/*` (Telegram + email, only fires if there are
new/changed **matching** listings this run).

**Filtering/scoring lives in exactly one place: `main.py`.** `BaseScraper`
and site scrapers must only return raw listings from `parse_list_page`/
`scrape` — no filtering, no scoring inside scrapers. This used to be
duplicated (scrapers pre-filtered *and* main.py filtered again with slightly
different logic), which silently dropped non-matching listings before they
ever reached the database/dashboard. Don't reintroduce that duplication.

**`scrapers/base_scraper.py` is the shared engine; site files only implement
the parsing:**
- `parse_list_page(soup, base_url) -> list[dict]` (required) — build listing
  dicts via `self.make_listing(...)`, which auto-parses price/surface/
  district from combined text if not given explicitly.
- `build_page_url(start_url, page_num) -> str | None` (optional) — return the
  URL for page N≥2; default returns `None` (no pagination). See
  `immobilier_ch.py` (`/page-N` path) or `acheter_louer.py` (`?page=N` query)
  for examples.
- `scrape()` (don't override unless a site needs a fundamentally different
  fetch flow) already handles: pagination loop up to `max_pages`, stopping
  early when a page returns no new URLs; retries with backoff
  (`runtime.max_retries`); a polite delay between page fetches
  (`runtime.delay_between_requests_seconds`, overridable per-site via
  `crawl_delay_seconds`); cookie-consent-banner dismissal for Playwright
  fetches. `homegate.py` and `pilet_renaud.py` override `scrape()` entirely
  for site-specific needs (API interception / hash-fragment filters) and so
  bypass this generic loop.

**`utils/parser.py` has non-obvious Swiss-number-format handling — don't
simplify it without re-testing against real pages:**
- Swiss listings write thousands separators with a *typographic* apostrophe
  `'` (U+2019), not the ASCII `'`. Every regex that matches a CHF amount must
  include both in its character class, or multi-thousand prices get silently
  truncated (e.g. "3'187" parsed as "3").
- Prices are shown as CHF/mois, CHF/m²/mois, CHF/an, or CHF/m²/an, often
  several of these in the same card. `parse_price_chf_month`'s fallback
  ("bare `CHF ###.-` with no unit") must check it isn't immediately followed
  by `/m²/an` context — otherwise a per-m² rate gets stored as if it were
  the monthly rent (a real bug that was fixed: a listing showing "CHF
  450.-/m²/an ... Loyer CHF 3'187.-" was being read as 450 CHF/month instead
  of 3'187). `compute_monthly_rent`'s priority order is: direct CHF/mois >
  CHF/m²/mois × surface > CHF/an ÷ 12 > CHF/m²/an × surface ÷ 12
  (`parse_price_m2_month` added 2026-08-07 — arcades/dépôts are frequently
  priced per m²/month rather than per m²/year, and before this fix such
  listings silently got `price_chf = None`, invisible to the price filter
  and to the father).
- `detect_district` first matches known district names, then falls back to
  a small NPA (postal code) → district table, since many listings only give
  the postal code, never the district name in words. `DISTRICTS` was
  expanded 2026-08-07 (Cornavin, Pâquis, Servette, Grottes, Petit-Saconnex,
  Charmilles added alongside the original Champel/Eaux-Vives/Rive/Rives/
  Plainpalais/Jonction/Carouge/Acacias) at the user's request to widen the
  search perimeter — deliberately broad, on the assumption the father
  narrows down himself via the site's district dropdown or
  `docs/criteria.html`, not via tight upstream filtering. `docs/criteria.html`
  reads this list directly (`from utils.parser import DISTRICTS`), so it
  always reflects whatever's here — don't hardcode a separate list there.

**Config (`config.yaml`) is the single source of truth for scan criteria and
site list** — `criteria.*` (surface/rent/district/keywords), `sites.*`
(per-site `enabled`, `start_urls`, `max_pages`), `runtime.*` (timeouts,
delay, retries). `notifications.*` toggles Telegram/email independently of
whether their secrets are actually set (missing secrets just log a warning
and skip, they don't crash the run).

**Anti-bot policy — a firm project rule, not a TODO:** homegate.ch and
comparis.ch (and, by the same reasoning, immoscout24.ch, properstar.com,
anibis.ch, newhome.ch — confirmed 2026-08-07, Cloudflare "Just a moment..."
403) run active bot-detection (Cloudflare interstitial, DataDome CAPTCHA, a
"security check" page) that blocks even a real headless browser. These are
deliberately left `enabled: false` in `config.yaml` with a comment
explaining why. Do not attempt stealth/undetected-browser tricks or CAPTCHA
solving to get around this — it's out of scope regardless of how the request
is phrased. spg.ch/wincasa.ch were also skipped (external JS search widgets,
no static content to scrape; spg.ch also has reCAPTCHA). regiefonciere.ch
was skipped deliberately too — not blocked, just redundant, since its
listings are already syndicated through immobilier.ch (already scraped).
The README's "Sites non couverts" section has the up-to-date list and
reasoning, including netimmo.ch as an identified-but-not-yet-implemented
candidate (real static listings, no anti-bot detected, ~2000 Geneva
commercial listings, just needs selector work).

**`scrapers/moservernet.py` gotcha:** the listing page's static HTML
contains real, server-rendered listing cards (`div[data-id]` →
`.property-card__title`) *and*, elsewhere in the same DOM, an unrendered
Mustache/Handlebars template block reusing the exact same `div[data-id]` /
`.property-card__title` structure with literal `{{ property.price }}`-style
placeholders (used client-side for dynamic filtering). `parse_list_page`
filters these out by checking `"{{" not in link.get_text()` — don't remove
that check, it silently lets through fake "listings" whose title is a raw
template string.

**`scrapers/netimmo.py` gotchas:** it's a SvelteKit app — pagination is via
`?p=N` (lowercase, no `page=` — that param is silently ignored and just
re-serves page 1). Its listing-card images are served from
`img.realadvisor.ch`, strongly suggesting it republishes realadvisor.ch's
own data; expect overlapping/duplicate listings between the two sources
rather than netimmo.ch being a genuinely independent inventory. Also: if
you ever test this site with bare `requests.get()` outside the project's
normal Playwright fetch path, `requests` mis-detects the encoding as
ISO-8859-1 (the server doesn't send a charset header) and mojibakes every
accented character — `price_chf`/`surface_m2` then silently parse as
`None` even though the data is there. Not a bug in the actual scraper path
(Playwright decodes correctly), just a trap when spot-checking with `curl`/
`requests` directly.

**`scrapers/pilet_renaud.py` searches multiple property types** (currently
ARCADE and DEPOT) by looping over all of `self.urls` — the site encodes the
"type" filter in a base64 hash-fragment and can't combine multiple types in
one search. `scrape()` is overridden (not just `parse_list_page`) specifically
to do this multi-URL loop within a single browser instance; don't revert it
to only reading `self.urls[0]`.

**Debugging a scraper that returns 0 results:** these are real, independently
operated websites — their markup changes over time (one, rosset.ch, had
already been fully redesigned since this scraper was first written, with the
old URL 404ing). The reliable way to fix it: fetch the live page with
Playwright (`page.goto(...)`, `page.content()`), save the HTML, and inspect
the actual card/link structure with BeautifulSoup before touching the
selector — don't guess selectors from memory or from how similar sites are
usually structured.

**`storage/site_generator.py`** renders `docs/index.html`: a single
self-contained HTML file (data embedded as JSON, vanilla JS filtering, no
build step, no external requests) so it works as a plain static file and via
GitHub Pages. It is committed by the GitHub Actions workflow on every run.
The repo was made public and GitHub Pages enabled (branch `main` / `/docs`)
on 2026-08-07 specifically so this site could be linked from
Telegram/email notifications (`config.yaml` → `output.site_url`) instead of
only being attached to the email — see [[criteria-edit-flow]] in memory for
why. It's still also attached to the email for offline viewing.

**`storage/site_generator.py`** also renders `docs/criteria.html` (via
`generate_criteria_page`), a form letting the father change
`min_surface_m2` / `max_rent_chf_month` / `allowed_districts` /
`allowed_property_types` / `require_possible_changing_rooms` without a
GitHub account or touching this repo. `allowed_property_types` behaves
exactly like `allowed_districts`: only checked types are accepted, and the
Worker/`apply_criteria_update.py` both reject a submission with none
checked — a first version made empty mean "accept all types", which the
user flagged (2026-08-07) as backwards from normal checkbox semantics, so
it was reverted to match districts. `config.yaml` therefore always lists
all `PROPERTY_TYPES` explicitly (not `[]`) to mean "no filtering yet";
`generate_criteria_page` pre-checks every box when the configured list is
empty, purely as a defensive default for a hand-edited config, since the
form itself can no longer produce that state. Both lists are stored
block-style (`- item` per line) and substituted the same way in
`apply_criteria_update.py`. `property_type` itself comes from
`utils.parser.detect_property_type`
(same per-listing detection pattern as `detect_district`), computed once in
`BaseScraper.make_listing` and stored as its own SQLite column — matched by
exact equality in `filters/gym_filter.py`, not substring search like
district, because the vocabulary is closed (`PROPERTY_TYPES`) so there's no
need for that leniency and it avoids an accent-encoding mismatch between a
criteria label and free text.

The whole form is gated by a shared token (`CRITERIA_EDIT_TOKEN` GitHub
secret, passed as `?key=` in the link `main.py` builds) checked
server-side by a Cloudflare Worker (`worker/criteria-worker.js`, live at
`https://boxing-gym-criteria.boxinggym-tracker.workers.dev`), never
embedded in the static HTML. The Worker creates a GitHub issue titled
`[criteria-update] ...`; `.github/workflows/apply-criteria.yml` +
`scripts/apply_criteria_update.py` parse it and edit `config.yaml` by
targeted regex substitution (not a full YAML dump) specifically to
preserve the file's existing comments — don't replace that with
`yaml.safe_dump`. Both the district and property-type lists exist as
manually-synced copies in `worker/criteria-worker.js` (JS can't import
Python) — any change to `utils.parser.DISTRICTS` or `PROPERTY_TYPES` needs
the same edit there **and a `wrangler deploy` from `worker/`**, or the form
silently drops whatever's missing from the copy before it ever reaches the
GitHub issue (this exact bug happened 2026-08-07 with a newly-added
district). `scripts/apply_criteria_update.py` avoids this by importing
`utils.parser.DISTRICTS`/`PROPERTY_TYPES` directly instead of copying —
prefer that pattern for anything Python-side. See [[criteria-edit-flow]]
in memory for the full incident list from shipping this feature.

**`.github/workflows/scanner.yml` has a `concurrency` group** (added
2026-08-07) so an overlapping manual `workflow_dispatch` and scheduled cron
run queue instead of racing — both used to try to `git commit`/`git push`
the scan data at the same time, and whichever lost the race failed outright
(its scrape was silently discarded). Don't remove the concurrency block to
"speed things up."

**`data/listings.db` schema drift:** `storage/database.py` will detect if an
existing SQLite file has a different column set than expected (from an
older version of this project) and transparently rebuild the table rather
than crashing on the first `INSERT`/`UPDATE` — the data is a regenerable
scan cache, not hand-authored content, so this is safe.
