from __future__ import annotations

from typing import Any, Dict

from . import publisher
from .types import JSONType, PublisherProtocol, SnsAttributes


class BaseAdapter:

    def __init__(self, **kwargs: Any):
        self.publisher: PublisherProtocol = publisher
        self.sns_arn: str | None = kwargs.get("sns_arn")
        self.sns_endpoint: str | None = kwargs.get("sns_endpoint")
        self.sns_defaults: Dict[str, Any] = kwargs.get("sns_attributes", {})

    def publish(self, db_data: JSONType, **kwargs: Any) -> None:
        if kwargs.get("publish") is False:
            return
        payload: JSONType = kwargs["publish_data"] if "publish_data" in kwargs else db_data
        call_attributes: Dict[str, Any] = kwargs.get("sns_attributes", {})
        attributes = self.create_format_attributes(call_attributes)
        self.publisher.publish(
            endpoint=self.sns_endpoint,
            arn=self.sns_arn,
            attributes=attributes,
            data=payload,
            fifo_group_id=kwargs.get("fifo_group_id"),
            fifo_duplication_id=kwargs.get("fifo_duplication_id"),
        )

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
