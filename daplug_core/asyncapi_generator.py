from __future__ import annotations

import argparse
import importlib
from typing import Any, Dict, List, Optional

import yaml

from . import event_registry, schema_loader
from .event_registry import EventSpec


def _message_name(event: str) -> str:
    parts = [part for part in event.replace("_", "-").split("-") if part]
    return "".join(part[:1].upper() + part[1:] for part in parts)


def build_spec(title: str, version: str, channel: str, events: List[EventSpec]) -> Dict[str, Any]:
    messages: Dict[str, Any] = {}
    schemas: Dict[str, Any] = {}
    channel_messages: Dict[str, Any] = {}
    operations: Dict[str, Any] = {}

    for spec in events:
        event = spec["event"]
        message_key = _message_name(event)
        schemas[spec["schema_key"]] = schema_loader.load_schema(spec["schema_file"], spec["schema_key"])
        messages[message_key] = {
            "name": event,
            "title": spec["description"] or event,
            "payload": {"$ref": f"#/components/schemas/{spec['schema_key']}"},
        }
        channel_messages[event] = {"$ref": f"#/components/messages/{message_key}"}
        operations[f"{event}.send"] = {
            "action": "send",
            "channel": {"$ref": f"#/channels/{channel}"},
            "messages": [{"$ref": f"#/channels/{channel}/messages/{event}"}],
        }

    return {
        "asyncapi": "3.0.0",
        "info": {"title": title, "version": version},
        "channels": {channel: {"address": channel, "messages": channel_messages}},
        "operations": operations,
        "components": {"messages": messages, "schemas": schemas},
    }


def generate(title: str, version: str, channel: str) -> Dict[str, Any]:
    return build_spec(title, version, channel, event_registry.all_events())


def write_spec(spec: Dict[str, Any], output: str) -> None:
    with open(output, "w", encoding="UTF-8") as handle:
        yaml.safe_dump(spec, handle, sort_keys=False, default_flow_style=False)


def _parse_args(argv: Optional[List[str]]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate an AsyncAPI spec from the daplug event registry.")
    parser.add_argument("--title", required=True)
    parser.add_argument("--version", default="v1")
    parser.add_argument("--channel", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--bootstrap", action="append", default=[])
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> None:
    args = _parse_args(argv)
    for module in args.bootstrap:
        importlib.import_module(module)
    write_spec(generate(args.title, args.version, args.channel), args.output)


if __name__ == "__main__":  # pragma: no cover
    main()
