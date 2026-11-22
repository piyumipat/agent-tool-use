from threading import Lock

from examples.shipping.tools import get_shipping_options


class ShipmentStore:
    def __init__(self) -> None:
        self.shipments: dict[str, tuple[tuple[str, float, str], dict]] = {}
        self._lock = Lock()

    def create(
        self,
        option_id: str,
        billable_weight_kg: float,
        destination_zone: str,
        request_id: str,
    ) -> dict:
        if not isinstance(request_id, str) or not request_id.strip() or len(request_id) > 128:
            raise ValueError("request_id must be a non-empty string of at most 128 characters")
        options = get_shipping_options(billable_weight_kg, destination_zone)
        selected = next((option for option in options if option["option_id"] == option_id), None)
        if selected is None:
            raise ValueError("Selected shipping option is unavailable")
        details = (option_id, billable_weight_kg, destination_zone)

        with self._lock:
            prior = self.shipments.get(request_id)
            if prior is not None:
                if prior[0] != details:
                    raise ValueError("request_id was already used for a different shipment")
                return prior[1].copy()
            result = {
                "shipment_id": f"SHIP-{len(self.shipments) + 1:04d}",
                "option_id": option_id,
                "price_eur": selected["price_eur"],
                "delivery_days": selected["delivery_days"],
            }
            self.shipments[request_id] = (details, result)
            return result.copy()
