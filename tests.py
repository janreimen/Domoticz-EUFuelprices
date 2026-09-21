# -*- coding: utf-8 -*-
"""Unit tests for eurooilwatch.py. Run with: python3 -m unittest tests -v

No Domoticz runtime or mock module is required - eurooilwatch.py has no
`import Domoticz` anywhere, by design (see its module docstring).
"""

import datetime
import unittest

import eurooilwatch


def sample_prices_payload(bulletin='2026-09-14', diesel=2.123, petrol=1.793,
                           diesel_pct=None, petrol_pct=None,
                           eu_diesel=2.075, eu_petrol=1.924, country='LU'):
    row = {
        'countryCode': country,
        'countryName': 'Luxembourg',
        'petrolPrice': petrol,
        'dieselPrice': diesel,
        'petrolChangePct': petrol_pct,
        'dieselChangePct': diesel_pct,
    }
    payload = {
        'lastUpdated': '2026-09-20T09:44:21.882Z',
        'bulletinDate': bulletin,
        'dataSource': 'EC Weekly Oil Bulletin',
        'countries': [row],
    }
    if eu_diesel is not None or eu_petrol is not None:
        payload['euAverage'] = {'petrolPrice': eu_petrol, 'dieselPrice': eu_diesel}
    return payload


def sample_stocks_payload(country='LU', diesel_days=54.0, petrol_days=42.5,
                           jet_fuel_days=None, nested=True):
    """diesel/petrol/jet_fuel_days=None means "withheld this cycle" - the
    real API's zero-policy-2026-09 null convention. `nested` toggles
    between the two shapes parse_stocks() tries (see its docstring)."""
    def figure(days):
        if days is None:
            return {'daysOfSupply': None, 'status': 'unassessed'}
        return {'daysOfSupply': days, 'status': 'ok'}

    row = {'countryCode': country, 'countryName': 'Luxembourg'}
    if nested:
        row['diesel'] = figure(diesel_days)
        row['petrol'] = figure(petrol_days)
        row['jetFuel'] = figure(jet_fuel_days)
    else:
        row['dieselDaysOfSupply'] = diesel_days
        row['petrolDaysOfSupply'] = petrol_days
        row['jetFuelDaysOfSupply'] = jet_fuel_days
    return {'countries': [row]}


TODAY = datetime.date(2026, 9, 20)


class ParsePricesTests(unittest.TestCase):

    def test_core_prices_only(self):
        result, bulletin = eurooilwatch.parse_prices(
            sample_prices_payload(eu_diesel=None, eu_petrol=None), 'LU', today=TODAY)
        self.assertEqual(result, {1: '2.123', 2: '1.793'})
        self.assertEqual(bulletin, '2026-09-14')

    def test_change_percent_included_when_present(self):
        payload = sample_prices_payload(diesel_pct=-0.42, petrol_pct=0.0, eu_diesel=None, eu_petrol=None)
        result, _ = eurooilwatch.parse_prices(payload, 'LU', today=TODAY)
        # A 0.0% change is a real, valid value - it must NOT be rejected the
        # way a zero *price* would be.
        self.assertEqual(result[3], '-0.42')
        self.assertEqual(result[4], '0.00')

    def test_change_percent_null_is_simply_omitted(self):
        payload = sample_prices_payload(diesel_pct=None, petrol_pct=None, eu_diesel=None, eu_petrol=None)
        result, _ = eurooilwatch.parse_prices(payload, 'LU', today=TODAY)
        self.assertNotIn(3, result)
        self.assertNotIn(4, result)
        self.assertIn(1, result)
        self.assertIn(2, result)

    def test_eu_average_included_when_present(self):
        result, _ = eurooilwatch.parse_prices(sample_prices_payload(), 'LU', today=TODAY)
        self.assertEqual(result[5], '2.075')
        self.assertEqual(result[6], '1.924')

    def test_eu_average_block_missing_is_omitted_not_fatal(self):
        # sample_prices_payload() omits the 'euAverage' key entirely when
        # both values are None - exercising an older/partial response shape.
        payload = sample_prices_payload(eu_diesel=None, eu_petrol=None)
        self.assertNotIn('euAverage', payload)
        result, _ = eurooilwatch.parse_prices(payload, 'LU', today=TODAY)
        self.assertNotIn(5, result)
        self.assertNotIn(6, result)

    def test_missing_diesel_price_is_a_hard_error(self):
        payload = sample_prices_payload()
        del payload['countries'][0]['dieselPrice']
        with self.assertRaises(ValueError):
            eurooilwatch.parse_prices(payload, 'LU', today=TODAY)

    def test_zero_diesel_price_is_rejected(self):
        payload = sample_prices_payload(diesel=0.0)
        with self.assertRaises(ValueError):
            eurooilwatch.parse_prices(payload, 'LU', today=TODAY)

    def test_bool_is_never_accepted_as_a_number(self):
        # bool is a subclass of int in Python - must be rejected explicitly.
        payload = sample_prices_payload()
        payload['countries'][0]['dieselPrice'] = True
        with self.assertRaises(ValueError):
            eurooilwatch.parse_prices(payload, 'LU', today=TODAY)

    def test_country_missing_is_a_hard_error(self):
        with self.assertRaises(ValueError):
            eurooilwatch.parse_prices(sample_prices_payload(country='FR'), 'LU', today=TODAY)

    def test_country_duplicated_is_a_hard_error(self):
        payload = sample_prices_payload()
        payload['countries'].append(dict(payload['countries'][0]))
        with self.assertRaises(ValueError):
            eurooilwatch.parse_prices(payload, 'LU', today=TODAY)

    def test_stale_bulletin_is_rejected(self):
        payload = sample_prices_payload(bulletin='2026-08-01')
        with self.assertRaises(ValueError):
            eurooilwatch.parse_prices(payload, 'LU', today=TODAY)

    def test_future_bulletin_is_rejected(self):
        payload = sample_prices_payload(bulletin='2026-09-25')
        with self.assertRaises(ValueError):
            eurooilwatch.parse_prices(payload, 'LU', today=TODAY)

    def test_one_day_ahead_is_tolerated(self):
        # Guards against timezone edge effects between the bulletin's date
        # and the host's local date.
        payload = sample_prices_payload(bulletin='2026-09-21')
        result, _ = eurooilwatch.parse_prices(payload, 'LU', today=TODAY)
        self.assertIn(1, result)

    def test_malformed_payload_shape_is_a_hard_error(self):
        with self.assertRaises(ValueError):
            eurooilwatch.parse_prices({'bulletinDate': '2026-09-14'}, 'LU', today=TODAY)


class ParseStocksTests(unittest.TestCase):
    """Schema is unverified against a live response (see eurooilwatch.py's
    module docstring) - these tests pin down the two shapes parse_stocks()
    is designed to tolerate, not a confirmed real payload."""

    def test_nested_shape_is_parsed(self):
        payload = sample_stocks_payload(nested=True, diesel_days=54.0, petrol_days=42.5, jet_fuel_days=30.0)
        result = eurooilwatch.parse_stocks(payload, 'LU')
        self.assertEqual(result, {7: '54.0', 8: '42.5', 9: '30.0'})

    def test_flat_fallback_shape_is_parsed(self):
        payload = sample_stocks_payload(nested=False, diesel_days=54.0, petrol_days=42.5, jet_fuel_days=30.0)
        result = eurooilwatch.parse_stocks(payload, 'LU')
        self.assertEqual(result, {7: '54.0', 8: '42.5', 9: '30.0'})

    def test_withheld_figure_is_omitted_not_fatal(self):
        # jetFuel withheld (null daysOfSupply, status "unassessed") must not
        # block diesel/petrol from updating.
        payload = sample_stocks_payload(nested=True, diesel_days=54.0, petrol_days=42.5, jet_fuel_days=None)
        result = eurooilwatch.parse_stocks(payload, 'LU')
        self.assertEqual(result, {7: '54.0', 8: '42.5'})
        self.assertNotIn(9, result)

    def test_unrecognised_fuel_shape_is_omitted_not_fatal(self):
        # A schema guess mismatch on one fuel must not crash the whole cycle.
        payload = {'countries': [{'countryCode': 'LU', 'diesel': {'daysOfSupply': 54.0}}]}
        result = eurooilwatch.parse_stocks(payload, 'LU')
        self.assertEqual(result, {7: '54.0'})

    def test_country_missing_is_a_hard_error(self):
        with self.assertRaises(ValueError):
            eurooilwatch.parse_stocks(sample_stocks_payload(country='FR'), 'LU')

    def test_malformed_payload_shape_is_a_hard_error(self):
        with self.assertRaises(ValueError):
            eurooilwatch.parse_stocks({'no_countries_key': True}, 'LU')


class OptionalNumberTests(unittest.TestCase):

    def test_none_returns_none(self):
        self.assertIsNone(eurooilwatch.optional_number(None))

    def test_bool_returns_none(self):
        self.assertIsNone(eurooilwatch.optional_number(True))

    def test_nan_returns_none(self):
        self.assertIsNone(eurooilwatch.optional_number(float('nan')))

    def test_negative_number_is_valid(self):
        self.assertEqual(eurooilwatch.optional_number(-1.5), -1.5)

    def test_zero_is_valid(self):
        self.assertEqual(eurooilwatch.optional_number(0), 0.0)


class UnitMetaConsistencyTests(unittest.TestCase):
    """Guards against config/code drift between Mode3/Mode4 and the
    UNIT_META/STOCK_UNIT_META tables plugin.py builds devices from."""

    def test_every_unit_group_is_reachable_from_some_mode3_value(self):
        reachable_groups = set()
        for groups in eurooilwatch.MODE3_GROUPS.values():
            reachable_groups |= groups
        used_groups = {meta['group'] for meta in eurooilwatch.UNIT_META.values()}
        self.assertEqual(used_groups, reachable_groups)

    def test_mode3_all_option_enables_every_price_unit(self):
        groups = eurooilwatch.MODE3_GROUPS['3']
        units = {u for u, meta in eurooilwatch.UNIT_META.items() if meta['group'] in groups}
        self.assertEqual(units, set(eurooilwatch.UNIT_META.keys()))

    def test_price_and_stock_units_never_collide(self):
        # plugin.py merges both tables into one Devices namespace per
        # hardware instance - a shared unit number would silently corrupt
        # whichever sensor lost the collision.
        price_units = set(eurooilwatch.UNIT_META.keys())
        stock_units = set(eurooilwatch.STOCK_UNIT_META.keys())
        self.assertEqual(price_units & stock_units, set())

    def test_country_count_matches_eu27(self):
        self.assertEqual(len(eurooilwatch.COUNTRIES), 27)


if __name__ == '__main__':
    unittest.main()
