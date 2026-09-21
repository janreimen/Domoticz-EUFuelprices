# Contributing

## Ground rules

- **Standard library only.** No new third-party dependencies without discussion first - this plugin
  runs inside the Domoticz process and pure-stdlib keeps the supply-chain surface at zero.
- **PEP 8**, and match the existing style (explicit over clever, small functions, comments that explain
  *why* a defensive check exists, not just what it does).
- **`eurooilwatch.py` never imports `Domoticz`.** All parsing/fetch logic lives there so it can be unit
  tested without a Domoticz runtime; `plugin.py` is the thin shim that talks to `Devices`/`Parameters`.
- **Never substitute a fabricated value for missing/invalid data.** A required field that's missing
  raises `ValueError` with the field name; an optional field that's missing is simply left out of the
  result. See `validate_price()` vs `optional_number()` in `eurooilwatch.py`.

## Before submitting a PR

```sh
python3 -m py_compile eurooilwatch.py plugin.py tests.py
python3 -m unittest tests -v
```

Add a test in `tests.py` for any new parsing logic - see the existing `ParsePricesTests` /
`ParseStocksTests` classes for the pattern (a `sample_*_payload()` builder plus one test per edge case:
missing field, null/withheld field, wrong type, duplicate/missing country).

## Filing issues

Include the plugin version (from the Domoticz log line at startup), your Domoticz version, and - for a
parsing bug - the relevant snippet of the raw API response (`curl` the endpoint directly) with any
personal identifiers already stripped.

## If a field-name guess turns out wrong again

Both endpoints this plugin uses are schema-confirmed as of 0.1.1-alpha, but EuroOilWatch can still change
its API shape upstream. If a sensor stops updating, `curl` the endpoint (see DEPLOY.md), compare it
against `parse_prices()` / `parse_stocks()` in `eurooilwatch.py`, and send a PR - include a trimmed,
anonymised real-response excerpt as a `tests.py` fixture, the way `REAL_STOCKS_PAYLOAD_EXCERPT` already
does, so the fix comes with regression coverage.
