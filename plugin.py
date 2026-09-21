# -*- coding: utf-8 -*-
"""
<plugin key="EUFuelPrices" name="EU Fuel Prices - Petrol and Diesel" author="JanReimen" version="0.1.0-alpha" externallink="https://github.com/janreimen/Domoticz-EUFuelPrices">
    <description>
        <h2>EU Fuel Prices</h2>
        <p>National weekly-average pump prices for petrol (Eurosuper 95) and diesel across the 27 EU
        countries, with optional week-on-week change and EU-27 average comparison sensors, and an
        optional reserve/days-of-cover sensor set.</p>
        <p>Source: <a href="https://eurooilwatch.com/api">EuroOilWatch public API</a> - prices from the
        European Commission's Weekly Oil Bulletin, reserves from Eurostat.</p>
        <p><b>These are national weekly averages, not individual filling-station prices.</b> The upstream
        source does not publish a 98 RON / premium grade or LPG per country, so this plugin does not
        expose those - see the README for details.</p>
        <p><b>Mode4 (reserve sensors) uses a field-name guess, not a confirmed schema</b> - unlike the
        price sensors, this was not checked against a live response while building this plugin. It fails
        loudly with the exact missing field name if the guess is wrong, rather than showing bad data. See
        DEPLOY.md "Before enabling Mode4" before turning it on.</p>
        <p>To track more than one country, add a separate hardware instance per country; each instance
        keeps its own device history.</p>
    </description>
    <params>
        <param field="Mode1" label="Country" width="220px" required="true" default="LU">
            <options>
                <option label="Austria" value="AT"/>
                <option label="Belgium" value="BE"/>
                <option label="Bulgaria" value="BG"/>
                <option label="Croatia" value="HR"/>
                <option label="Cyprus" value="CY"/>
                <option label="Czechia" value="CZ"/>
                <option label="Denmark" value="DK"/>
                <option label="Estonia" value="EE"/>
                <option label="Finland" value="FI"/>
                <option label="France" value="FR"/>
                <option label="Germany" value="DE"/>
                <option label="Greece" value="GR"/>
                <option label="Hungary" value="HU"/>
                <option label="Ireland" value="IE"/>
                <option label="Italy" value="IT"/>
                <option label="Latvia" value="LV"/>
                <option label="Lithuania" value="LT"/>
                <option label="Luxembourg" value="LU" default="true"/>
                <option label="Malta" value="MT"/>
                <option label="Netherlands" value="NL"/>
                <option label="Poland" value="PL"/>
                <option label="Portugal" value="PT"/>
                <option label="Romania" value="RO"/>
                <option label="Slovakia" value="SK"/>
                <option label="Slovenia" value="SI"/>
                <option label="Spain" value="ES"/>
                <option label="Sweden" value="SE"/>
            </options>
        </param>
        <param field="Mode2" label="Price polling interval (hours)" width="100px" default="6">
            <options>
                <option label="1" value="1"/>
                <option label="6" value="6" default="true"/>
                <option label="12" value="12"/>
                <option label="24" value="24"/>
            </options>
        </param>
        <param field="Mode3" label="Extra price sensors" width="260px" default="0">
            <options>
                <option label="Prices only" value="0" default="true"/>
                <option label="Prices + weekly change %" value="1"/>
                <option label="Prices + EU-27 average" value="2"/>
                <option label="Prices + change % + EU-27 average" value="3"/>
            </options>
        </param>
        <param field="Mode4" label="Reserve sensors (unverified schema)" width="200px" default="0">
            <options>
                <option label="Off" value="0" default="true"/>
                <option label="On - days-of-cover for diesel/petrol/jet fuel" value="1"/>
            </options>
        </param>
        <param field="Mode6" label="Debug" width="100px" default="0">
            <options>
                <option label="No" value="0" default="true"/>
                <option label="Yes" value="1"/>
            </options>
        </param>
    </params>
</plugin>
"""

import queue
import threading
import time

import Domoticz
import eurooilwatch as fuel

STOCKS_POLL_SECONDS = 24 * 3600  # Eurostat reserve data has a ~2-month lag; daily is already generous.


class BasePlugin:
    def __init__(self):
        self.enabled = False
        self.cached = {}

        self.price_worker = None
        self.price_results = queue.Queue()
        self.bulletin = None
        self.next_price_fetch = 0
        self.price_failures = 0
        self.price_units = []

        self.stocks_enabled = False
        self.stocks_worker = None
        self.stocks_results = queue.Queue()
        self.next_stocks_fetch = 0
        self.stocks_failures = 0
        self.stock_units = []

        self.next_record = 0

    def _meta(self, unit):
        return fuel.UNIT_META.get(unit) or fuel.STOCK_UNIT_META.get(unit)

    def onStart(self):
        self.country = Parameters.get('Mode1', 'LU')
        if self.country not in fuel.COUNTRIES:
            Domoticz.Error('Invalid country: ' + self.country)
            return

        hours = Parameters.get('Mode2', '6')
        if hours not in ('1', '6', '12', '24'):
            Domoticz.Log('Unrecognised price polling interval "{}"; using 6 hours.'.format(hours))
            hours = '6'
        self.price_interval = int(hours) * 3600

        mode3 = Parameters.get('Mode3', '0')
        groups = fuel.MODE3_GROUPS.get(mode3, fuel.MODE3_GROUPS['0'])
        self.price_units = sorted(u for u, meta in fuel.UNIT_META.items() if meta['group'] in groups)

        self.stocks_enabled = Parameters.get('Mode4', '0') == '1'
        self.stock_units = sorted(fuel.STOCK_UNIT_META.keys()) if self.stocks_enabled else []

        all_units = self.price_units + self.stock_units

        if Parameters.get('Mode6') == '1':
            Domoticz.Debugging(1)

        # A different country, or a differently-purposed leftover device,
        # must never silently overwrite an existing device's graph history.
        for unit in all_units:
            expected = 'EUFuel-{}-{}'.format(self.country, unit)
            if unit in Devices and Devices[unit].DeviceID != expected:
                Domoticz.Error('Country changed, or an incompatible device already exists for unit {}. '
                                'Add a new hardware instance for the desired country; existing history is preserved.'.format(unit))
                return

        for unit in all_units:
            meta = self._meta(unit)
            if unit not in Devices:
                Domoticz.Device(
                    Name='{} - {}'.format(meta['label'], fuel.COUNTRIES[self.country]),
                    Unit=unit, DeviceID='EUFuel-{}-{}'.format(self.country, unit),
                    TypeName='Custom', Options={'Custom': '1;' + meta['axis']}, Used=1
                ).Create()
            if unit not in Devices:
                Domoticz.Error('Could not create the sensor for unit {}. Enable "Allow new Hardware Devices" '
                                'and restart the hardware instance.'.format(unit))
                return

        # Rename only names generated by the very first (Romanian-labelled)
        # edition; preserve any name a user has customised since, including
        # the plain "Diesel/Petrol - Country" names from the 1.0.0 release.
        for unit, old_fuel_name in ((1, 'Motorina'), (2, 'Benzina')):
            if unit not in Devices:
                continue
            old_name = '{} - {}'.format(old_fuel_name, fuel.LEGACY_COUNTRIES.get(self.country, ''))
            new_name = '{} - {}'.format(fuel.UNIT_META[unit]['label'], fuel.COUNTRIES[self.country])
            device = Devices[unit]
            prefix = Parameters.get('Name', '') + ' - '
            names = {old_name: new_name, prefix + old_name: prefix + new_name}
            if device.Name in names:
                device.Update(nValue=device.nValue, sValue=device.sValue, Name=names[device.Name])

        self.enabled = True
        Domoticz.Heartbeat(10)
        Domoticz.Log('EU Fuel Prices {} | {} | price sensors: {}{} | Source: EuroOilWatch https://eurooilwatch.com/api'.format(
            fuel.VERSION, fuel.COUNTRIES[self.country],
            ', '.join(fuel.UNIT_META[u]['label'] for u in self.price_units),
            ' | reserve sensors: ' + ', '.join(fuel.STOCK_UNIT_META[u]['label'] for u in self.stock_units) if self.stock_units else ''))
        self.onHeartbeat()

    def record(self):
        for unit, value in self.cached.items():
            if unit in Devices:
                # Record unchanged values too so every graph has a continuous timeline.
                Devices[unit].Update(nValue=0, sValue=value, TimedOut=0)

    def mark_timeout(self, units):
        for unit in units:
            if unit in Devices:
                Devices[unit].Update(nValue=Devices[unit].nValue,
                                     sValue=Devices[unit].sValue, TimedOut=1)

    def onHeartbeat(self):
        if not self.enabled:
            return
        now = time.monotonic()

        # --- Prices feed -----------------------------------------------
        try:
            prices, bulletin, error = self.price_results.get_nowait()
        except queue.Empty:
            pass
        else:
            self.price_worker = None
            if error:
                self.price_failures += 1
                delay = min(3600, 300 * (2 ** min(self.price_failures - 1, 4)))
                self.next_price_fetch = now + delay
                self.mark_timeout(self.price_units)
                Domoticz.Error('Price fetch failed: {}. Previous values are retained; retrying in {} minutes.'.format(error, delay // 60))
            else:
                changed = any(self.cached.get(u) != v for u, v in prices.items()) or bulletin != self.bulletin
                self.cached.update(prices)
                self.bulletin = bulletin
                self.price_failures = 0
                self.next_price_fetch = now + self.price_interval
                self.record()
                self.next_record = now + 300
                if changed:
                    Domoticz.Log('{} | bulletin {} | Diesel {} €/l | Petrol {} €/l'.format(
                        self.country, bulletin, prices[1], prices[2]))
        if self.price_worker is None and now >= self.next_price_fetch:
            self.price_worker = threading.Thread(target=fuel.fetch_prices, args=(self.country, self.price_results), daemon=True)
            self.price_worker.start()

        # --- Stocks feed (optional, Mode4) ------------------------------
        if self.stocks_enabled:
            try:
                values, error = self.stocks_results.get_nowait()
            except queue.Empty:
                pass
            else:
                self.stocks_worker = None
                if error:
                    self.stocks_failures += 1
                    delay = min(6 * 3600, 1800 * (2 ** min(self.stocks_failures - 1, 4)))
                    self.next_stocks_fetch = now + delay
                    self.mark_timeout(self.stock_units)
                    Domoticz.Error('Reserve fetch failed: {}. Previous values are retained; retrying in {} minutes.'.format(error, delay // 60))
                else:
                    self.cached.update(values)
                    self.stocks_failures = 0
                    self.next_stocks_fetch = now + STOCKS_POLL_SECONDS
                    self.record()
                    self.next_record = now + 300
            if self.stocks_worker is None and now >= self.next_stocks_fetch:
                self.stocks_worker = threading.Thread(target=fuel.fetch_stocks, args=(self.country, self.stocks_results), daemon=True)
                self.stocks_worker.start()

        # --- Keep every device's graph continuous ------------------------
        if self.cached and now >= self.next_record:
            self.record()
            self.next_record = now + 300

    def onStop(self):
        self.enabled = False
        # urllib timeouts bound both workers. Each owns only its own queue, no Domoticz state.


_plugin = BasePlugin()


def onStart():
    _plugin.onStart()


def onStop():
    _plugin.onStop()


def onHeartbeat():
    _plugin.onHeartbeat()
