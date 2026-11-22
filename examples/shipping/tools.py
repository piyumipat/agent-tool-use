import math


def _positive_number(value: float, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a positive number")
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise ValueError(f"{name} must be a finite positive number")
    return number


def calculate_billable_weight(
    length_cm: float,
    width_cm: float,
    height_cm: float,
    actual_weight_kg: float,
) -> dict[str, float]:
    length = _positive_number(length_cm, "length_cm")
    width = _positive_number(width_cm, "width_cm")
    height = _positive_number(height_cm, "height_cm")
    actual = _positive_number(actual_weight_kg, "actual_weight_kg")

    dimensional = length * width * height / 5_000
    if not math.isfinite(dimensional):
        raise ValueError("parcel dimensions are too large")
    return {"billable_weight_kg": max(actual, dimensional)}


def get_shipping_options(
    billable_weight_kg: float, destination_zone: str
) -> list[dict[str, str | float | int]]:
    weight = _positive_number(billable_weight_kg, "billable_weight_kg")
    if destination_zone != "domestic":
        raise ValueError("destination_zone must be 'domestic'")
    if weight > 5:
        return []

    return [
        {"option_id": "economy", "price_eur": 8.0, "delivery_days": 5},
        {"option_id": "standard", "price_eur": 11.0, "delivery_days": 3},
        {"option_id": "express", "price_eur": 16.0, "delivery_days": 1},
    ]
