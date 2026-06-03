from daplug_core import event_registry


def setup_function(_):
    event_registry.clear()


def test_register_event_stores_and_returns_spec():
    spec = event_registry.register_event(
        "v1-documents-document-created",
        "api/v1/openapi.yml",
        "Document",
        "A document was created",
    )

    assert spec["event"] == "v1-documents-document-created"
    assert spec["schema_key"] == "Document"
    assert spec["description"] == "A document was created"
    assert event_registry.get_event("v1-documents-document-created") == spec


def test_register_event_defaults_blank_description():
    spec = event_registry.register_event("v1-a-b-c", "schema.yml", "Thing")

    assert spec["description"] == ""


def test_get_event_returns_none_when_missing():
    assert event_registry.get_event("v1-not-registered") is None


def test_all_events_sorted_by_name():
    event_registry.register_event("v1-z-y-x", "schema.yml", "Z")
    event_registry.register_event("v1-a-b-c", "schema.yml", "A")

    names = [spec["event"] for spec in event_registry.all_events()]

    assert names == ["v1-a-b-c", "v1-z-y-x"]


def test_register_event_overwrites_same_name():
    event_registry.register_event("v1-a-b-c", "schema.yml", "First")
    event_registry.register_event("v1-a-b-c", "schema.yml", "Second")

    assert len(event_registry.all_events()) == 1
    assert event_registry.get_event("v1-a-b-c")["schema_key"] == "Second"


def test_clear_empties_registry():
    event_registry.register_event("v1-a-b-c", "schema.yml", "A")
    event_registry.clear()

    assert event_registry.all_events() == []
