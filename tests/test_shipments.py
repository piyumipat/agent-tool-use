import unittest

from examples.shipping.shipments import ShipmentStore


class ShipmentStoreTests(unittest.TestCase):
    def test_repeated_request_returns_same_shipment(self) -> None:
        store = ShipmentStore()
        first = store.create("standard", 4.8, "domestic", "request-1")
        repeated = store.create("standard", 4.8, "domestic", "request-1")
        self.assertEqual(first, repeated)
        self.assertEqual(first["shipment_id"], "SHIP-0001")
        self.assertEqual(len(store.shipments), 1)

    def test_reused_request_id_with_different_details_is_rejected(self) -> None:
        store = ShipmentStore()
        store.create("standard", 4.8, "domestic", "request-1")
        with self.assertRaisesRegex(ValueError, "already used"):
            store.create("express", 4.8, "domestic", "request-1")
        self.assertEqual(len(store.shipments), 1)

    def test_unavailable_option_creates_nothing(self) -> None:
        store = ShipmentStore()
        with self.assertRaisesRegex(ValueError, "unavailable"):
            store.create("standard", 5.1, "domestic", "request-1")
        self.assertEqual(store.shipments, {})
