# Deploy

## Prerequisites

- Domoticz with Python plugin support enabled (Setup → Settings → check the Python version shown at the
  bottom of Hardware; see the [Domoticz Python plugins wiki](https://www.domoticz.com/wiki/Using_Python_plugins)
  if it's missing).
- Python 3.x, whatever your Domoticz build links against - nothing extra to `pip install`, this plugin
  is standard library only.
- Outbound HTTPS (443) to `eurooilwatch.com` from the host running Domoticz.

## Install

```sh
cd /srv/domoticz/plugins   # or wherever your Domoticz plugins directory is
git clone https://github.com/janreimen/Domoticz-EUFuelPrices.git
sudo systemctl restart domoticz.service
```

Then in the Domoticz UI: **Setup → Hardware**, add new hardware of type **EU Fuel Prices - Petrol and
Diesel**, pick your country, and save. The first heartbeat creates the devices - if nothing appears,
check **Setup → Settings → check for updates → Allow new Hardware Devices** is on, then restart the
hardware instance.

## Update

```sh
cd /srv/domoticz/plugins/Domoticz-EUFuelPrices
git pull
sudo systemctl restart domoticz.service
```

## Multiple countries

Add a **separate hardware instance** per country - don't change the Country field on an existing
instance if you want to keep its history. Changing it is detected and refused (`Domoticz.Error`) rather
than silently reused, exactly so existing graph history is never overwritten by the wrong country.

## Before enabling Mode4

The reserve/stock sensors (units 7-9) parse `/api/v1/stocks`, and unlike the price sensors, that
endpoint's exact field names were **not** confirmed against a live response while building this plugin
(see `eurooilwatch.py`'s module docstring). Before turning Mode4 on:

```sh
curl -s https://eurooilwatch.com/api/v1/stocks | python3 -m json.tool | less
```

Look at one country's entry and compare it against the shape `parse_stocks()` expects (see the comment
above `STOCK_UNIT_META` in `eurooilwatch.py`): either `row["diesel"]["daysOfSupply"]` (nested) or
`row["dieselDaysOfSupply"]` (flat), same for `petrol` / `jetFuel`. If neither matches, adjust
`STOCK_UNIT_META[unit]['fuel_key']` and/or the two lookups inside `parse_stocks()` to fit - the function
already fails with a clear "Country is missing or duplicated" / silently-omits-that-fuel behaviour
rather than showing a wrong number, so a mismatch is safe, just silent (the sensor simply never gets its
first value) until you fix it.

## Uninstall

**Setup → Hardware**, delete the instance(s). This does not delete the devices themselves (Domoticz
convention - your history is never auto-deleted); remove those separately from **Setup → Devices** if
you want them gone too. Then:

```sh
sudo systemctl stop domoticz.service
rm -rf /srv/domoticz/plugins/Domoticz-EUFuelPrices
sudo systemctl start domoticz.service
```

## Troubleshooting

- **Nothing in the log at all** → confirm the plugin folder name matches what Domoticz scanned (restart
  Domoticz after `git clone`, not just after `git pull`).
- **`Fetch failed: ...` in the log** → transient network/API issue; the plugin retries with backoff
  (5 min → up to 1 h) and keeps showing the last good value in the meantime. Persistent failures usually
  mean outbound HTTPS to `eurooilwatch.com` is blocked from this host.
- **`Country changed, or an incompatible device already exists for unit N`** → you changed the Country
  field on an existing instance, or a non-plugin device is squatting that unit. Add a new hardware
  instance instead of repurposing this one.
- **Still stuck** → set Debug (Mode6) to Yes, restart the hardware instance, and read the verbose log
  around the next heartbeat.
