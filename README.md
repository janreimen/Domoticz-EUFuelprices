# Domoticz-EUFuelPrices

A Domoticz Python plugin for national weekly-average petrol and diesel prices across the 27 EU
countries, with optional week-on-week change, EU-27 average, and fuel-reserve sensors.

Data source: the [EuroOilWatch public API](https://eurooilwatch.com/api) (free, no key, CORS-enabled),
itself sourced from the European Commission's Weekly Oil Bulletin (prices) and Eurostat (reserves).

**Status: 0.1.1-alpha.** Both `/api/v1/prices` and `/api/v1/stocks` are now schema-confirmed against
live responses. (0.1.0-alpha shipped with a wrong field-name guess for the reserve sensors - see
[CHANGELOG.md](CHANGELOG.md) for what broke and how it was fixed.)

## What this is not

- **Not individual filling-station prices.** These are national weekly averages from the EC bulletin,
  not live pump prices at a specific station.
- **Not 98 RON / premium petrol, and not LPG.** The EC Weekly Oil Bulletin - the only price source this
  plugin talks to - reports exactly two road-fuel grades per country: Eurosuper 95 ("petrol" below) and
  automotive gas oil ("diesel"). There's nothing to add here without a different upstream source; see
  [`Domoticz-EUEnergyMarkets`](https://github.com/janreimen/Domoticz-EUEnergyMarkets) for the
  market-level data (Brent crude, EU gas prices) this API separately exposes.

## Devices

One hardware instance = one country. Add another instance per additional country; each keeps its own
device history. Units 1-6 come from `/api/v1/prices`; units 7-9 are the optional Mode4 reserve sensors
from `/api/v1/stocks`.

| Unit | Sensor | Axis | Enabled by |
|---|---|---|---|
| 1 | Diesel | €/l | always |
| 2 | Petrol (Eurosuper 95) | €/l | always |
| 3 | Diesel - weekly change | % | Mode3 = 1 or 3 |
| 4 | Petrol - weekly change | % | Mode3 = 1 or 3 |
| 5 | Diesel - EU-27 average | €/l | Mode3 = 2 or 3 |
| 6 | Petrol - EU-27 average | €/l | Mode3 = 2 or 3 |
| 7 | Diesel - reserve cover | days | Mode4 = 1 |
| 8 | Petrol - reserve cover | days | Mode4 = 1 |
| 9 | Jet fuel - reserve cover | days | Mode4 = 1 |

## Supported countries

All 27 EU member states (no UK, matching the API and the EC bulletin's own coverage):

AT · BE · BG · HR · CY · CZ · DK · EE · FI · FR · DE · GR · HU · IE · IT · LV · LT · LU · MT · NL · PL ·
PT · RO · SK · SI · ES · SE

## Configuration

| Field | Options | Notes |
|---|---|---|
| Country (Mode1) | any EU-27 code, default LU | one instance per country |
| Price polling interval (Mode2) | 1 / 6 / 12 / 24 hours | default 6h; the bulletin itself only updates weekly |
| Extra price sensors (Mode3) | prices only / + change % / + EU average / + both | default: prices only |
| Reserve sensors (Mode4) | off / on | default off (opt-in, since it's a second endpoint + 3 more devices) |
| Debug (Mode6) | no / yes | verbose Domoticz.Debug logging |

Reserve sensors poll on a fixed 24-hour cadence regardless of Mode2 - the underlying Eurostat data has a
~2-month reporting lag, so polling it hourly would just be noise.

## Install / update / troubleshoot

See [DEPLOY.md](DEPLOY.md).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Pure standard library only, PEP 8, and `tests.py` covering any
new parsing logic - see [CHANGELOG.md](CHANGELOG.md) for release history.

## Security

See [SECURITY.md](SECURITY.md).

## Attribution & license

Data: "EuroOilWatch" ([eurooilwatch.com](https://eurooilwatch.com)), citing the EC Weekly Oil Bulletin /
Eurostat as the underlying institutional source, per the [API's usage terms](https://eurooilwatch.com/api).
Code: [MIT](LICENSE).
