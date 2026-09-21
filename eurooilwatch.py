# -*- coding: utf-8 -*-
"""Pure-Python API client and parsing logic for Domoticz-EUFuelPrices.

Deliberately has no `import Domoticz` anywhere in this file, so tests.py can
exercise the parse_*() functions directly without a Domoticz runtime or a
mock module. plugin.py is the only Domoticz-facing file; it imports this
module.

Two independent EuroOilWatch feeds live here, both schema-CONFIRMED against
a live response:

  * /api/v1/prices  - weekly consumer petrol/diesel prices (parse_prices).
  * /api/v1/stocks  - reserve days-of-cover (parse_stocks). Confirmed
    2026-09-21, replacing a wrong 0.1.0-alpha guess - see CHANGELOG.
"""

import datetime
import json
import math
import urllib.request

VERSION = '0.1.1-alpha'

MAX_BYTES = 1024 * 1024

COUNTRIES = {'AT': 'Austria', 'BE': 'Belgium', 'BG': 'Bulgaria', 'HR': 'Croatia', 'CY': 'Cyprus', 'CZ': 'Czechia', 'DK': 'Denmark', 'EE': 'Estonia', 'FI': 'Finland', 'FR': 'France', 'DE': 'Germany', 'GR': 'Greece', 'HU': 'Hungary', 'IE': 'Ireland', 'IT': 'Italy', 'LV': 'Latvia', 'LT': 'Lithuania', 'LU': 'Luxembourg', 'MT': 'Malta', 'NL': 'Netherlands', 'PL': 'Poland', 'PT': 'Portugal', 'RO': 'Romania', 'SK': 'Slovakia', 'SI': 'Slovenia', 'ES': 'Spain', 'SE': 'Sweden'}

# Original Romanian labels, retained only to migrate devices created by the
# very first (pre-English, pre-fork) edition of this plugin to the current
# naming scheme. Never used for anything else.
LEGACY_COUNTRIES = {'AT': 'Austria', 'BE': 'Belgia', 'BG': 'Bulgaria', 'HR': 'Croatia', 'CY': 'Cipru', 'CZ': 'Cehia', 'DK': 'Danemarca', 'EE': 'Estonia', 'FI': 'Finlanda', 'FR': 'Franta', 'DE': 'Germania', 'GR': 'Grecia', 'HU': 'Ungaria', 'IE': 'Irlanda', 'IT': 'Italia', 'LV': 'Letonia', 'LT': 'Lituania', 'LU': 'Luxemburg', 'MT': 'Malta', 'NL': 'Tarile de Jos', 'PL': 'Polonia', 'PT': 'Portugalia', 'RO': 'Romania', 'SK': 'Slovacia', 'SI': 'Slovenia', 'ES': 'Spania', 'SE': 'Suedia'}


def validate_price(value, field_name):
    """An absolute pump price. Must be a real, finite, strictly positive
    number - never substitute a missing or invalid price with zero."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError('Missing or invalid price: ' + field_name)
    value = float(value)
    if not math.isfinite(value) or value <= 0:
        raise ValueError('Invalid price: ' + field_name)
    return value


def optional_number(value):
    """A field that may legitimately be null this week (e.g. change-percent
    on the first bulletin after a gap, or a withheld reserve figure) or
    absent on an older API version. Returns None instead of raising - only
    core required fields are treated as must-have."""
    if value is None or isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    value = float(value)
    return value if math.isfinite(value) else None


def _get_json(url, timeout=25):
    """Shared HTTP GET + bounded-size JSON decode, used by every fetch_*()
    worker below. Raises on any failure; never returns partial data."""
    request = urllib.request.Request(url, headers={
        'User-Agent': 'Domoticz-EUFuelPrices/{}'.format(VERSION),
        'Accept': 'application/json',
    })
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError('API response is too large')
    return json.loads(raw.decode('utf-8-sig'))


# --------------------------------------------------------------------------
# /api/v1/prices - weekly consumer petrol/diesel prices. CONFIRMED schema.
# --------------------------------------------------------------------------

PRICES_URL = 'https://eurooilwatch.com/api/v1/prices'

# Every price sensor this plugin can create. 'group' ties a unit to the
# Mode3 choice that enables it; unit numbers are stable forever, even for
# groups a given install never enables, so re-enabling a group later never
# collides with a differently-purposed unit.
UNIT_META = {
    1: {'label': 'Diesel', 'axis': '€/l', 'group': 'core'},
    2: {'label': 'Petrol (Eurosuper 95)', 'axis': '€/l', 'group': 'core'},
    3: {'label': 'Diesel - weekly change', 'axis': '%', 'group': 'pct'},
    4: {'label': 'Petrol - weekly change', 'axis': '%', 'group': 'pct'},
    5: {'label': 'Diesel - EU-27 average', 'axis': '€/l', 'group': 'euavg'},
    6: {'label': 'Petrol - EU-27 average', 'axis': '€/l', 'group': 'euavg'},
}
MODE3_GROUPS = {
    '0': {'core'},
    '1': {'core', 'pct'},
    '2': {'core', 'euavg'},
    '3': {'core', 'pct', 'euavg'},
}


def parse_prices(payload, country, today=None):
    """Validate the documented /api/v1/prices schema and return a dict of
    {unit_number: formatted_string} containing only the units for which
    this cycle actually has usable data. Units 1 and 2 (diesel, petrol)
    are required; a missing/invalid value there is a hard error. Units
    3-6 (change %, EU average) are best-effort and are simply left out
    of the result when the API doesn't have them this cycle.

    Note on scope: the upstream EC Weekly Oil Bulletin - and therefore this
    API - only ever reports two road-fuel grades per country: Eurosuper 95
    ("petrol") and automotive gas oil ("diesel"). There is no 98 RON /
    premium grade and no LPG in this feed, so callers should not expect
    units beyond 1-6 from this function.
    """
    if not isinstance(payload, dict) or not isinstance(payload.get('countries'), list):
        raise ValueError('API response is missing the countries list')
    bulletin = payload.get('bulletinDate')
    try:
        date = datetime.datetime.strptime(bulletin, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        raise ValueError('Bulletin date is missing or invalid')
    age = ((today or datetime.datetime.now(datetime.timezone.utc).date()) - date).days
    if age < -1 or age > 21:
        raise ValueError('Bulletin is outdated or dated in the future: ' + bulletin)

    rows = [r for r in payload['countries']
            if isinstance(r, dict) and r.get('countryCode') == country]
    if len(rows) != 1:
        raise ValueError('Country is missing or duplicated: ' + country)
    row = rows[0]

    result = {
        1: format(validate_price(row.get('dieselPrice'), 'dieselPrice'), '.3f'),
        2: format(validate_price(row.get('petrolPrice'), 'petrolPrice'), '.3f'),
    }

    diesel_pct = optional_number(row.get('dieselChangePct'))
    if diesel_pct is not None:
        result[3] = format(diesel_pct, '.2f')
    petrol_pct = optional_number(row.get('petrolChangePct'))
    if petrol_pct is not None:
        result[4] = format(petrol_pct, '.2f')

    eu_average = payload.get('euAverage')
    if isinstance(eu_average, dict):
        try:
            result[5] = format(validate_price(eu_average.get('dieselPrice'), 'euAverage.dieselPrice'), '.3f')
        except ValueError:
            pass
        try:
            result[6] = format(validate_price(eu_average.get('petrolPrice'), 'euAverage.petrolPrice'), '.3f')
        except ValueError:
            pass

    return result, bulletin


def fetch_prices(country, output):
    """Network worker: never call Domoticz or touch Devices from the
    caller's thread. Reports (prices, bulletin, None) on success or
    (None, None, error_message) on any failure via the output queue."""
    try:
        prices, bulletin = parse_prices(_get_json(PRICES_URL), country)
        output.put((prices, bulletin, None))
    except Exception as exc:
        output.put((None, None, str(exc)))


# --------------------------------------------------------------------------
# /api/v1/stocks - reserve days-of-cover. Schema CONFIRMED 2026-09-21
# against a live response (see CHANGELOG 0.1.1-alpha - the 0.1.0-alpha
# guess was wrong; this replaced it).
# --------------------------------------------------------------------------

STOCKS_URL = 'https://eurooilwatch.com/api/v1/stocks'

# Confirmed shape: each country row has a *list* under "fuels", one entry
# per fuel, e.g. {"fuelType": "diesel", "daysOfSupply": 72.5, "status": ...,
# "stockKilotonnes": ..., "consumptionKilotonnes": ..., "provenance": {...}}.
# Note fuelType uses snake_case for jet fuel specifically ("jet_fuel"), not
# "jetFuel" - the 0.1.0-alpha guess assumed uniform camelCase and missed
# this, which is why it silently matched nothing (see CHANGELOG).
STOCK_UNIT_META = {
    7: {'label': 'Diesel - reserve cover', 'axis': 'days', 'fuel_type': 'diesel'},
    8: {'label': 'Petrol - reserve cover', 'axis': 'days', 'fuel_type': 'petrol'},
    9: {'label': 'Jet fuel - reserve cover', 'axis': 'days', 'fuel_type': 'jet_fuel'},
}


def parse_stocks(payload, country):
    """Parse /api/v1/stocks for one country. Returns a dict of
    {unit_number: formatted_string} containing only the fuels for which
    this cycle has an assessable (non-withheld) figure - a null/withheld
    daysOfSupply (status "unassessed", e.g. a reported-zero pending review)
    is not an error, it is simply omitted, exactly like an optional field
    in parse_prices().

    A structurally missing country, or a country row with no "fuels" list
    at all, is a hard error (something is badly wrong with the response).
    A single fuel entry that's missing from the list, or has an
    unrecognised fuelType, is NOT fatal - it's simply left out of the
    result, so one bad entry can't take down the other two.
    """
    if not isinstance(payload, dict) or not isinstance(payload.get('countries'), list):
        raise ValueError('API response is missing the countries list')

    rows = [r for r in payload['countries']
            if isinstance(r, dict) and r.get('countryCode') == country]
    if len(rows) != 1:
        raise ValueError('Country is missing or duplicated: ' + country)
    row = rows[0]

    fuels = row.get('fuels')
    if not isinstance(fuels, list):
        raise ValueError('Country row is missing the fuels list: ' + country)

    by_fuel_type = {}
    for entry in fuels:
        if isinstance(entry, dict) and isinstance(entry.get('fuelType'), str):
            by_fuel_type[entry['fuelType']] = entry

    result = {}
    for unit, meta in STOCK_UNIT_META.items():
        entry = by_fuel_type.get(meta['fuel_type'])
        if not isinstance(entry, dict):
            continue
        days = optional_number(entry.get('daysOfSupply'))
        if days is not None:
            result[unit] = format(days, '.1f')
    return result


def fetch_stocks(country, output):
    """Network worker for the stocks feed. Same contract as fetch_prices():
    reports (values, None) on success or (None, error_message) on any
    failure via the output queue."""
    try:
        values = parse_stocks(_get_json(STOCKS_URL), country)
        output.put((values, None))
    except Exception as exc:
        output.put((None, str(exc)))
