# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

A scanner that looks for commercial premises to rent in Geneva suitable for a
boxing gym (the user's father's business). It scrapes several Swiss real
estate sites, filters by surface/rent/district/changing-room keywords, keeps
history in SQLite, and notifies by Telegram/email. It runs for free on GitHub
Actions (cron every 3h) — there is no server, no paid hosting, no database
other than the committed SQLite file.

GitHub repo: `FlaviusMedIng/Boxing-Gym-Scanner` (private). Telegram and email
notification secrets are already configured on that repo.

## Commands

```bash
pip install -r requirements.txt
playwright install chromium     # required once, Playwright drives real Chromium for JS-heavy sites

python main.py                  # run one full scan: scrape -> filter/score -> SQLite -> exports -> notify
streamlit run dashboard/app.py  # browse data/listings.db locally (all listings, not just matches)
python -m py_compile main.py scrapers/*.py utils/*.py storage/*.py filters/*.py scoring/*.py notifier/*.py dashboard/app.py
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
- Prices are shown as CHF/mois, CHF/an, or CHF/m²/an, often several of these
  in the same card. `parse_price_chf_month`'s fallback ("bare `CHF ###.-`
  with no unit") must check it isn't immediately followed by `/m²/an` context
  — otherwise a per-m² rate gets stored as if it were the monthly rent (a
  real bug that was fixed: a listing showing "CHF 450.-/m²/an ... Loyer CHF
  3'187.-" was being read as 450 CHF/month instead of 3'187).
- `detect_district` first matches known district names, then falls back to
  a small NPA (postal code) → district table, since many listings only give
  the postal code, never the district name in words.

**Config (`config.yaml`) is the single source of truth for scan criteria and
site list** — `criteria.*` (surface/rent/district/keywords), `sites.*`
(per-site `enabled`, `start_urls`, `max_pages`), `runtime.*` (timeouts,
delay, retries). `notifications.*` toggles Telegram/email independently of
whether their secrets are actually set (missing secrets just log a warning
and skip, they don't crash the run).

**Anti-bot policy — a firm project rule, not a TODO:** homegate.ch and
comparis.ch (and, by the same reasoning, immoscout24.ch, properstar.com,
anibis.ch) run active bot-detection (Cloudflare interstitial, DataDome
CAPTCHA, a "security check" page) that blocks even a real headless browser.
These are deliberately left `enabled: false` in `config.yaml` with a comment
explaining why. Do not attempt stealth/undetected-browser tricks or CAPTCHA
solving to get around this — it's out of scope regardless of how the request
is phrased. spg.ch/wincasa.ch were also skipped (external JS search widgets,
no static content to scrape; spg.ch also has reCAPTCHA). The README's "Sites
non couverts" section has the up-to-date list and reasoning.

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
GitHub Pages is *not* currently enabled because the repo is private (Pages
needs a public repo on the free tier); the file is instead attached to the
notification email so it's viewable offline. If the repo visibility changes,
Pages can be turned on via repo Settings → Pages → branch `main` /docs.

**`data/listings.db` schema drift:** `storage/database.py` will detect if an
existing SQLite file has a different column set than expected (from an
older version of this project) and transparently rebuild the table rather
than crashing on the first `INSERT`/`UPDATE` — the data is a regenerable
scan cache, not hand-authored content, so this is safe.
