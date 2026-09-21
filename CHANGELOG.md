# Changelog

All notable changes to this project are documented here.
Format loosely follows [Keep a Changelog](https://keepachangelog.com/).

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
