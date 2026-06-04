from __future__ import annotations

import argparse
import copy
import glob
import importlib
import importlib.util
import os
from typing import Any, Dict, List, Optional

import yaml

from . import event_registry, schema_loader
from .event_registry import EventSpec


def _message_name(event: str) -> str:
    parts = [part for part in event.replace("_", "-").split("-") if part]
    return "".join(part[:1].upper() + part[1:] for part in parts)


def _headers_schema(event: str, service: str, version: str) -> Dict[str, Any]:
    # The transport-agnostic message metadata (SNS MessageAttributes today). Mirrors
    # the adapter's required_headers contract: event/service/version always present.
    return {
        "type": "object",
        "required": ["event", "service", "version"],
        "properties": {
            "event": {"type": "string", "const": event},
            "service": {"type": "string", "const": service},
            "version": {"type": "string", "const": version},
        },
    }


def _inline_defs(schema: Dict[str, Any]) -> Dict[str, Any]:
    # Resolve Pydantic $defs/$ref into a self-contained schema (no external refs).
    defs: Dict[str, Any] = schema.pop("$defs", None) or schema.pop("definitions", None) or {}

    def resolve(node: Any) -> Any:
        if isinstance(node, dict):
            ref = node.get("$ref")
            if isinstance(ref, str) and ref.rsplit("/", 1)[0] in ("#/$defs", "#/definitions"):
                return resolve(copy.deepcopy(defs.get(ref.rsplit("/", 1)[-1], {})))
            return {key: resolve(value) for key, value in node.items()}
        if isinstance(node, list):
            return [resolve(item) for item in node]
        return node

    return resolve(schema)


def _is_event_model(obj: Any) -> bool:
    name = getattr(obj, "event_name", "")
    return isinstance(obj, type) and hasattr(obj, "model_json_schema") and isinstance(name, str) and bool(name)


def _import_file(path: str) -> Any:
    module_name = "daplug_events_" + os.path.splitext(os.path.basename(path))[0]
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as exc:  # pylint: disable=broad-except
        print(f"WARN: daplug asyncapi generator could not import {path}: {exc}")
        return None
    return module


def discover_event_models(globs: List[str]) -> List[Any]:
    models: List[Any] = []
    seen = set()
    for pattern in globs:
        for path in sorted(glob.glob(pattern, recursive=True)):
            module = _import_file(path)
            if module is None:
                continue
            for obj in vars(module).values():
                if _is_event_model(obj) and obj not in seen:
                    seen.add(obj)
                    models.append(obj)
    return models


def _model_title(model: Any, event: str) -> str:
    doc = (getattr(model, "__doc__", "") or "").strip()
    return doc.splitlines()[0].strip() if doc else event


def build_spec_from_models(title: str, version: str, channel: str, models: List[Any]) -> Dict[str, Any]:
    messages: Dict[str, Any] = {}
    schemas: Dict[str, Any] = {}
    channel_messages: Dict[str, Any] = {}
    operations: Dict[str, Any] = {}

    for model in sorted(models, key=lambda item: item.event_name):
        event = model.event_name
        key = _message_name(event)
        schemas[key] = _inline_defs(model.model_json_schema())
        messages[key] = {
            "name": event,
            "title": _model_title(model, event),
            "headers": _headers_schema(event, title, version),
            "payload": {"$ref": f"#/components/schemas/{key}"},
        }
        channel_messages[event] = {"$ref": f"#/components/messages/{key}"}
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


# --------------------------------------------------------------------------- #
# Deprecated registry/bootstrap path (kept for in-flight repos during migration)
# --------------------------------------------------------------------------- #

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
    parser = argparse.ArgumentParser(description="Generate an AsyncAPI spec from daplug event models.")
    parser.add_argument("--title", required=True)
    parser.add_argument("--version", default="v1")
    parser.add_argument("--channel", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--events", action="append", default=[], help="glob(s) of event model modules to scan")
    parser.add_argument("--bootstrap", action="append", default=[], help="DEPRECATED: registry bootstrap module(s)")
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> None:
    args = _parse_args(argv)
    if args.events:
        models = discover_event_models(args.events)
        spec = build_spec_from_models(args.title, args.version, args.channel, models)
    else:
        for module in args.bootstrap:
            importlib.import_module(module)
        spec = generate(args.title, args.version, args.channel)
    write_spec(spec, args.output)


if __name__ == "__main__":  # pragma: no cover
    main()
