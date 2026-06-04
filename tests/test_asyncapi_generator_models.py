import yaml

from daplug_core import asyncapi_generator

MODEL_MODULE = '''
from typing import ClassVar
from pydantic import BaseModel, Field


class Address(BaseModel):
    line1: str
    city: str


class DocumentCreated(BaseModel):
    """A document was created"""
    event_name: ClassVar[str] = "v1-documents-document-created"
    document_id: str = Field(examples=["doc-1"])
    user_id: str
    address: Address | None = None


class DocumentUpdated(DocumentCreated):
    """A document was updated"""
    event_name: ClassVar[str] = "v1-documents-document-updated"


class NotAnEvent(BaseModel):
    foo: str
'''


def _write_models(tmp_path):
    pkg = tmp_path / "events"
    pkg.mkdir()
    (pkg / "document_events.py").write_text(MODEL_MODULE)
    return str(pkg / "*.py")


def test_discover_only_models_with_event_name(tmp_path):
    glob = _write_models(tmp_path)
    models = asyncapi_generator.discover_event_models([glob])
    names = sorted(m.event_name for m in models)
    assert names == ["v1-documents-document-created", "v1-documents-document-updated"]


def test_build_spec_emits_payload_and_headers(tmp_path):
    glob = _write_models(tmp_path)
    models = asyncapi_generator.discover_event_models([glob])
    spec = asyncapi_generator.build_spec_from_models("documents", "v1", "documents", models)

    assert spec["asyncapi"] == "3.0.0"
    assert set(spec["operations"]) == {
        "v1-documents-document-created.send",
        "v1-documents-document-updated.send",
    }

    msg = spec["components"]["messages"]["V1DocumentsDocumentCreated"]
    assert msg["name"] == "v1-documents-document-created"
    assert msg["title"] == "A document was created"
    assert msg["payload"] == {"$ref": "#/components/schemas/V1DocumentsDocumentCreated"}
    # headers carry the message metadata contract
    assert msg["headers"]["required"] == ["event", "service", "version"]
    assert msg["headers"]["properties"]["event"]["const"] == "v1-documents-document-created"
    assert msg["headers"]["properties"]["service"]["const"] == "documents"


def test_nested_models_are_inlined_no_refs(tmp_path):
    glob = _write_models(tmp_path)
    models = asyncapi_generator.discover_event_models([glob])
    spec = asyncapi_generator.build_spec_from_models("documents", "v1", "documents", models)
    schema = spec["components"]["schemas"]["V1DocumentsDocumentCreated"]

    assert "$defs" not in schema
    dumped = yaml.safe_dump(spec)
    assert "#/$defs/" not in dumped
    # the nested Address resolved inline under address.anyOf
    assert "properties" in schema


def test_main_writes_spec_via_events_glob(tmp_path):
    glob = _write_models(tmp_path)
    output = tmp_path / "asyncapi.yml"
    asyncapi_generator.main(
        ["--title", "documents", "--version", "v1", "--channel", "documents", "--events", glob, "--output", str(output)]
    )
    loaded = yaml.safe_load(output.read_text())
    assert "v1-documents-document-created.send" in loaded["operations"]
    assert loaded["components"]["messages"]["V1DocumentsDocumentCreated"]["headers"]["properties"]["version"]["const"] == "v1"
