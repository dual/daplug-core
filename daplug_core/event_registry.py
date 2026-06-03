from __future__ import annotations

from typing import Dict, List, Optional, TypedDict


class EventSpec(TypedDict):
    event: str
    schema_file: str
    schema_key: str
    description: str


_REGISTRY: Dict[str, EventSpec] = {}


def register_event(event: str, schema_file: str, schema_key: str, description: str = "") -> EventSpec:
    spec: EventSpec = {
        "event": event,
        "schema_file": schema_file,
        "schema_key": schema_key,
        "description": description,
    }
    _REGISTRY[event] = spec
    return spec


def get_event(event: str) -> Optional[EventSpec]:
    return _REGISTRY.get(event)


def all_events() -> List[EventSpec]:
    return [_REGISTRY[name] for name in sorted(_REGISTRY)]


def clear() -> None:
    _REGISTRY.clear()
