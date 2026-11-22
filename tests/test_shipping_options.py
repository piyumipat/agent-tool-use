import unittest

from examples.shipping.tools import get_shipping_options


class ShippingOptionsTests(unittest.TestCase):
    def test_example_parcel_receives_three_options(self) -> None:
        options = get_shipping_options(4.8, "domestic")
        self.assertEqual(
            options,
            [
                {"option_id": "economy", "price_eur": 8.0, "delivery_days": 5},
                {"option_id": "standard", "price_eur": 11.0, "delivery_days": 3},
                {"option_id": "express", "price_eur": 16.0, "delivery_days": 1},
            ],
        )

    def test_heavier_parcel_has_no_options(self) -> None:
        self.assertEqual(get_shipping_options(5.1, "domestic"), [])

    def test_invalid_weight_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "billable_weight_kg"):
            get_shipping_options(0, "domestic")

    def test_unsupported_zone_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "destination_zone"):
            get_shipping_options(4.8, "international")
