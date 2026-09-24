# Changelog

All notable changes to this project are documented here.
Format loosely follows [Keep a Changelog](https://keepachangelog.com/).

## [1.2] - 2026-09-23

First release not tagged alpha - the schema-confirmation work in 0.1.1-alpha, plus this release's fixes
below, are what earned that.

### Added

- **Per-feed "last successfully fetched" timestamp sensors**: unit 10 ("Prices - last updated", always
  on) and unit 11 ("Reserves - last updated", Mode4 only), both Domoticz Text devices. Deliberately track
  the last *successful fetch*, not the last *value change* - diesel/petrol/reserve-days can legitimately
  sit unchanged for weeks, and a "last changed" timestamp would make a perfectly healthy plugin
  indistinguishable from a dead one at a glance. See "Freshness" in DEPLOY.md.

### Fixed

- **The periodic graph-continuity touch could silently clear a failing feed's `TimedOut` flag.**
  `record()` used to iterate the *entire* shared cache unconditionally on every 5-minute continuity pass,
  regardless of which feed a given unit belonged to. If reserves (Mode4) were failing and correctly
  marked `TimedOut=1` by `mark_timeout()`, the next scheduled continuity touch - driven by a single
  shared `next_record` timer that either feed's success could reset - would re-write those same reserve
  units with `TimedOut=0`, silently clearing the stale flag while the feed was still genuinely down.
  Prices and reserves now have fully independent scheduling: separate `next_price_record` /
  `next_stocks_record` timers, separate `price_healthy` / `stocks_healthy` flags, and `record()` now
  takes an explicit `units` argument so each feed can only ever touch its own devices. A failing feed's
  sensors (data and the new "last updated" text alike) are simply left alone - not touched at all - until
  that feed's next successful fetch.

## [0.1.1-alpha] - 2026-09-21

### Fixed

- **Mode4 reserve sensors (units 7-9) never updated - confirmed via a live Domoticz instance, where they
  sat at the Domoticz-default `0 days` indefinitely.** Root cause: `parse_stocks()` guessed the wrong
  `/api/v1/stocks` shape. The 0.1.0-alpha guess assumed either a nested `row["diesel"]["daysOfSupply"]`
  object or a flat `row["dieselDaysOfSupply"]` key, keyed by `diesel` / `petrol` / `jetFuel`. The real
  API instead puts a `"fuels"` **list** on each country row, one entry per fuel with a `fuelType` field
  - and jet fuel's `fuelType` is `"jet_fuel"` (snake_case), not `"jetFuel"`. Neither guessed shape
  matched anything, so `parse_stocks()` silently returned an empty result every cycle - by design, an
  optional field that doesn't match is omitted rather than raising, which is correct behaviour for a
  genuinely-missing figure but meant a *structurally* wrong guess failed silently instead of loudly.
  Rewritten to parse the confirmed `fuels`-list shape; verified against a real captured API excerpt
  (`REAL_STOCKS_PAYLOAD_EXCERPT` in `tests.py`, Luxembourg + a Lithuania row with a genuine withheld
  jet-fuel figure), plus a regression test pinning down the snake_case `jet_fuel` key specifically.
- `/api/v1/stocks` is now schema-CONFIRMED (see `eurooilwatch.py`'s module docstring) - the Mode4
  "unverified schema" warnings in the plugin description, README, SECURITY.md, and DEPLOY.md are removed
  accordingly.

### If you're upgrading from 0.1.0-alpha with Mode4 already enabled

`git pull` and restart the hardware instance - no config change needed, the next heartbeat repopulates
units 7-9 with real values. Nothing needs cleaning up; the devices were never written with fabricated
data, only left at their un-updated default.

## [0.1.0-alpha] - 2026-09-20

### Added

- Optional week-on-week change-percent sensors for diesel/petrol (Mode3 = 1 or 3).
- Optional EU-27 average comparison sensors for diesel/petrol (Mode3 = 2 or 3).
- Optional reserve/days-of-cover sensors for diesel, petrol, and jet fuel, sourced from
  `/api/v1/stocks` (Mode4) - **schema not yet verified against a live response**, see
  "Before enabling Mode4" in DEPLOY.md.
- Full doc suite: README, SECURITY, DEPLOY, CONTRIBUTING, this file, MIT LICENSE.
- `tests.py` (29 tests), runnable with no Domoticz runtime, covering both parsers.
- GitHub Actions CI: compile + test on every push/PR.
- Split the single `plugin.py` into a pure-Python `eurooilwatch.py` (no `import Domoticz`, so it's unit
  testable standalone) and a thin Domoticz-facing `plugin.py` shim - matches the module split already
  used in this author's other Domoticz plugins.

### Changed

- Default country changed from Romania to Luxembourg.
- Petrol sensor's default label now reads "Petrol (Eurosuper 95)" to make the grade explicit.
- Version scheme moved to `0.1.0-alpha` (previously the original single-file edition shipped as `1.0.0`
  with no alpha/beta distinction).

### Fixed

- Week-on-week change-percent is no longer subject to the "must be > 0" price validation - a 0% or
  negative change is a valid, real value; only absolute pump prices must be strictly positive.

### Known limitations

- **No 98 RON / premium petrol grade, and no LPG.** The EC Weekly Oil Bulletin - the only source
  `/api/v1/prices` draws from - only ever reports two road-fuel grades per country: Eurosuper 95 and
  diesel. There is nothing further to add here without a different upstream source. Market-level data
  the API separately exposes (Brent crude, EU gas prices) now lives in the sibling
  [Domoticz-EUEnergyMarkets](https://github.com/janreimen/Domoticz-EUEnergyMarkets) plugin instead of
  here, since it's global/EU-wide rather than per-country.
- **Mode4 reserve sensors use an inferred, not confirmed, field-name schema** - see DEPLOY.md. A wrong
  guess fails loudly (`Domoticz.Error` naming the exact field) rather than showing bad data.

## [1.0.0] - prior to this repository

Original single-file edition (Romanian-labelled defaults, diesel/petrol only, no reserve or comparison
sensors). Superseded by 0.1.0-alpha above; devices created by 1.0.0 are migrated in place, see
`plugin.py`'s legacy-name handling.
