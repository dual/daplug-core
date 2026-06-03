import yaml

from daplug_core import asyncapi_generator, event_registry


def setup_function(_):
    event_registry.clear()


def _stub_schema(monkeypatch):
    schema = {"type": "object", "properties": {"document_id": {"type": "string"}}}
    monkeypatch.setattr(asyncapi_generator.schema_loader, "load_schema", lambda *_, **__: schema)
    return schema


def test_message_name_pascal_cases_event():
    assert asyncapi_generator._message_name("v1-documents-document-created") == "V1DocumentsDocumentCreated"
    assert asyncapi_generator._message_name("v1-poa_requirement-completed") == "V1PoaRequirementCompleted"


def test_build_spec_emits_asyncapi_3_envelope(monkeypatch):
    schema = _stub_schema(monkeypatch)
    events = [event_registry.register_event("v1-documents-document-created", "api/v1/openapi.yml", "Document", "Created")]

    spec = asyncapi_generator.build_spec("documents", "v1", "documents", events)

    assert spec["asyncapi"] == "3.0.0"
    assert spec["info"] == {"title": "documents", "version": "v1"}
    assert spec["components"]["schemas"]["Document"] == schema


def test_build_spec_links_channel_message_and_operation(monkeypatch):
    _stub_schema(monkeypatch)
    events = [event_registry.register_event("v1-documents-document-created", "api/v1/openapi.yml", "Document", "Created")]

    spec = asyncapi_generator.build_spec("documents", "v1", "documents", events)

    message = spec["components"]["messages"]["V1DocumentsDocumentCreated"]
    assert message["name"] == "v1-documents-document-created"
    assert message["title"] == "Created"
    assert message["payload"] == {"$ref": "#/components/schemas/Document"}

    channel = spec["channels"]["documents"]
    assert channel["messages"]["v1-documents-document-created"] == {
        "$ref": "#/components/messages/V1DocumentsDocumentCreated"
    }

    operation = spec["operations"]["v1-documents-document-created.send"]
    assert operation["action"] == "send"
    assert operation["channel"] == {"$ref": "#/channels/documents"}
    assert operation["messages"] == [{"$ref": "#/channels/documents/messages/v1-documents-document-created"}]


def test_build_spec_falls_back_to_event_name_when_no_description(monkeypatch):
    _stub_schema(monkeypatch)
    events = [event_registry.register_event("v1-a-b-c", "schema.yml", "Thing")]

    spec = asyncapi_generator.build_spec("svc", "v1", "svc", events)

    assert spec["components"]["messages"]["V1ABC"]["title"] == "v1-a-b-c"


def test_generate_reads_from_registry(monkeypatch):
    _stub_schema(monkeypatch)
    event_registry.register_event("v1-a-b-c", "schema.yml", "Thing")

    spec = asyncapi_generator.generate("svc", "v1", "svc")

    assert "v1-a-b-c.send" in spec["operations"]


def test_write_spec_round_trips_yaml(monkeypatch, tmp_path):
    _stub_schema(monkeypatch)
    event_registry.register_event("v1-a-b-c", "schema.yml", "Thing", "desc")
    spec = asyncapi_generator.generate("svc", "v1", "svc")
    output = tmp_path / "asyncapi.yml"

    asyncapi_generator.write_spec(spec, str(output))

    loaded = yaml.safe_load(output.read_text())
    assert loaded["asyncapi"] == "3.0.0"
    assert "v1-a-b-c.send" in loaded["operations"]


def test_main_bootstraps_module_and_writes(monkeypatch, tmp_path):
    _stub_schema(monkeypatch)
    imported = []
    monkeypatch.setattr(
        asyncapi_generator.importlib,
        "import_module",
        lambda name: imported.append(name) or event_registry.register_event("v1-a-b-c", "schema.yml", "Thing"),
    )
    output = tmp_path / "asyncapi.yml"

    asyncapi_generator.main(
        ["--title", "svc", "--channel", "svc", "--output", str(output), "--bootstrap", "fake.module"]
    )

    assert imported == ["fake.module"]
    loaded = yaml.safe_load(output.read_text())
    assert "v1-a-b-c.send" in loaded["operations"]
