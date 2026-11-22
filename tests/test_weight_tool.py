import math
import unittest

from examples.shipping.tools import calculate_billable_weight


class BillableWeightTests(unittest.TestCase):
    def test_dimensional_weight_wins_for_example_parcel(self) -> None:
        result = calculate_billable_weight(40, 30, 20, 3.0)
        self.assertEqual(result, {"billable_weight_kg": 4.8})

    def test_actual_weight_can_win(self) -> None:
        result = calculate_billable_weight(10, 10, 10, 2.0)
        self.assertEqual(result, {"billable_weight_kg": 2.0})

    def test_invalid_measurements_are_rejected(self) -> None:
        for value in (0, -1, float("nan"), math.inf, True, "4"):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "length_cm"):
                    calculate_billable_weight(value, 30, 20, 3.0)

    def test_missing_measurement_is_rejected(self) -> None:
        with self.assertRaises(TypeError):
            calculate_billable_weight(width_cm=30, height_cm=20, actual_weight_kg=3.0)

    def test_overflowing_dimensions_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "too large"):
            calculate_billable_weight(1e308, 1e308, 1e308, 3.0)
