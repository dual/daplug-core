from __future__ import annotations

from typing import Any, Dict, List

from . import publisher
from .types import JSONType, PublisherProtocol, SnsAttributes


class PublishContractError(Exception):
    """Raised before publishing when the payload/headers contract is not satisfied."""

    def __init__(self, missing_payload_keys: List[str] | None = None, missing_headers: List[str] | None = None):
        self.missing_payload_keys = missing_payload_keys or []
        self.missing_headers = missing_headers or []
        parts = []
        if self.missing_payload_keys:
            parts.append(f"payload missing required keys: {self.missing_payload_keys}")
        if self.missing_headers:
            parts.append(f"headers missing required keys: {self.missing_headers}")
        super().__init__("; ".join(parts) or "publish contract violation")


def _is_model(value: Any) -> bool:
    # Duck-typed Pydantic detection so daplug-core keeps no hard pydantic dependency.
    return hasattr(value, "model_dump") and hasattr(value, "model_json_schema")


class BaseAdapter:

    def __init__(self, **kwargs: Any):
        self.publisher: PublisherProtocol = publisher
        self.sns_arn: str | None = kwargs.get("sns_arn")
        self.sns_endpoint: str | None = kwargs.get("sns_endpoint")
        self.sns_defaults: Dict[str, Any] = kwargs.get("sns_attributes", {})
        # Transport-agnostic publish contract. Empty lists = no enforcement (back-compat).
        self.required_payload_keys: List[str] = list(kwargs.get("required_payload_keys", []))
        self.required_headers: List[str] = list(kwargs.get("required_headers", []))

    def publish(self, db_data: JSONType, **kwargs: Any) -> None:
        if kwargs.get("publish") is False:
            return

        raw_payload: Any = kwargs["publish_data"] if "publish_data" in kwargs else db_data
        call_attributes: Dict[str, Any] = dict(kwargs.get("sns_attributes", {}))

        payload: Any = raw_payload
        if _is_model(raw_payload):
            event_name = getattr(type(raw_payload), "event_name", None)
            payload = raw_payload.model_dump(mode="json", exclude_none=True)
            if event_name and not call_attributes.get("event"):
                call_attributes["event"] = event_name

        headers = {**self.sns_defaults, **call_attributes}
        self._validate_contract(payload, headers)

        attributes = self.create_format_attributes(call_attributes)
        self.publisher.publish(
            endpoint=self.sns_endpoint,
            arn=self.sns_arn,
            attributes=attributes,
            data=payload,
            fifo_group_id=kwargs.get("fifo_group_id"),
            fifo_duplication_id=kwargs.get("fifo_duplication_id"),
        )

    def _validate_contract(self, payload: Any, headers: Dict[str, Any]) -> None:
        missing_payload: List[str] = []
        if self.required_payload_keys:
            keys = payload.keys() if isinstance(payload, dict) else []
            missing_payload = [key for key in self.required_payload_keys if key not in keys]
        missing_headers = [name for name in self.required_headers if name not in headers]
        if missing_payload or missing_headers:
            raise PublishContractError(missing_payload, missing_headers)

    def create_format_attributes(self, call_attributes: Dict[str, Any]) -> SnsAttributes:
        combined: Dict[str, Any] = {**self.sns_defaults, **call_attributes}
        formatted_attributes: SnsAttributes = {}
        for key, value in combined.items():
            if value is not None:
                data_type = "String" if isinstance(value, str) else "Number"
                formatted_attributes[key] = {
                    "DataType": data_type,
                    "StringValue": value,
                }
        return formatted_attributes
