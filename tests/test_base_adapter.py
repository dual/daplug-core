import pytest

from daplug_core import base_adapter
from tests.mocks.fakes import RecordingPublisher


@pytest.fixture
def recording_publisher(monkeypatch):
    publisher = RecordingPublisher()
    monkeypatch.setattr(base_adapter, "publisher", publisher)
    return publisher


def test_publish_forwards_formatted_attributes(recording_publisher):
    adapter = base_adapter.BaseAdapter(
        sns_arn="arn:aws:sns:region:123:topic",
        sns_endpoint="https://sns.test",
        sns_attributes={"default": "value"},
    )

    adapter.publish(
        db_data={"id": 1},
        sns_attributes={"count": 5, "ignored": None},
        fifo_group_id="group-1",
        fifo_duplication_id="dedupe-1",
    )

    assert len(recording_publisher.calls) == 1
    call = recording_publisher.calls[0]
    assert call["arn"] == "arn:aws:sns:region:123:topic"
    assert call["endpoint"] == "https://sns.test"
    assert call["data"] == {"id": 1}
    expected_attributes = {
        "default": {"DataType": "String", "StringValue": "value"},
        "count": {"DataType": "Number", "StringValue": 5},
    }
    assert call["attributes"] == expected_attributes
    assert call["fifo_group_id"] == "group-1"
    assert call["fifo_duplication_id"] == "dedupe-1"


def test_create_format_attributes_excludes_none(recording_publisher):
    adapter = base_adapter.BaseAdapter(
        sns_attributes={"keep": "yes", "skip": None}
    )

    formatted = adapter.create_format_attributes({"new": 1, "skip": None})

    assert "skip" not in formatted
    assert formatted["keep"] == {"DataType": "String", "StringValue": "yes"}
    assert formatted["new"] == {"DataType": "Number", "StringValue": 1}


def test_publish_false_skips_publisher(recording_publisher):
    adapter = base_adapter.BaseAdapter(sns_arn="arn:aws:sns:region:123:topic")

    adapter.publish(db_data={"id": 1}, publish=False)

    assert recording_publisher.calls == []


def test_publish_data_overrides_db_data(recording_publisher):
    adapter = base_adapter.BaseAdapter(sns_arn="arn:aws:sns:region:123:topic")

    adapter.publish(db_data={"id": 1}, publish_data={"event": "custom"})

    assert len(recording_publisher.calls) == 1
    assert recording_publisher.calls[0]["data"] == {"event": "custom"}


def test_publish_false_takes_precedence_over_publish_data(recording_publisher):
    adapter = base_adapter.BaseAdapter(sns_arn="arn:aws:sns:region:123:topic")

    adapter.publish(db_data={"id": 1}, publish=False, publish_data={"event": "custom"})

    assert recording_publisher.calls == []


def test_publish_data_none_is_explicit_override(recording_publisher):
    adapter = base_adapter.BaseAdapter(sns_arn="arn:aws:sns:region:123:topic")

    adapter.publish(db_data={"id": 1}, publish_data=None)

    assert len(recording_publisher.calls) == 1
    assert recording_publisher.calls[0]["data"] is None


def test_required_payload_keys_raises_when_missing(recording_publisher):
    adapter = base_adapter.BaseAdapter(
        sns_arn="arn:aws:sns:region:123:topic",
        required_payload_keys=["id", "user_id"],
    )

    with pytest.raises(base_adapter.PublishContractError) as exc:
        adapter.publish(db_data={"id": 1})

    assert exc.value.missing_payload_keys == ["user_id"]
    assert recording_publisher.calls == []


def test_required_headers_raises_when_missing(recording_publisher):
    adapter = base_adapter.BaseAdapter(
        sns_arn="arn:aws:sns:region:123:topic",
        sns_attributes={"service": "svc", "version": "v1"},
        required_headers=["event", "service", "version"],
    )

    with pytest.raises(base_adapter.PublishContractError) as exc:
        adapter.publish(db_data={"id": 1})

    assert exc.value.missing_headers == ["event"]
    assert recording_publisher.calls == []


def test_contract_passes_when_satisfied(recording_publisher):
    adapter = base_adapter.BaseAdapter(
        sns_arn="arn:aws:sns:region:123:topic",
        sns_attributes={"service": "svc", "version": "v1"},
        required_payload_keys=["id"],
        required_headers=["event", "service", "version"],
    )

    adapter.publish(db_data={"id": 1}, sns_attributes={"event": "v1-a-b-c"})

    assert len(recording_publisher.calls) == 1
    assert recording_publisher.calls[0]["data"] == {"id": 1}


def test_pydantic_payload_is_dumped_and_event_name_injected(recording_publisher):
    from pydantic import BaseModel
    from typing import ClassVar

    class DocumentCreated(BaseModel):
        event_name: ClassVar[str] = "v1-documents-document-created"
        document_id: str
        user_id: str
        envelope_id: str | None = None

    adapter = base_adapter.BaseAdapter(
        sns_arn="arn:aws:sns:region:123:topic",
        sns_attributes={"service": "svc", "version": "v1"},
        required_payload_keys=["document_id", "user_id"],
        required_headers=["event", "service", "version"],
    )

    adapter.publish(db_data=DocumentCreated(document_id="d1", user_id="u1"))

    call = recording_publisher.calls[0]
    # model_dump(exclude_none) drops envelope_id; event_name injected into headers
    assert call["data"] == {"document_id": "d1", "user_id": "u1"}
    assert call["attributes"]["event"] == {"DataType": "String", "StringValue": "v1-documents-document-created"}


def test_explicit_event_attribute_not_overridden_by_marker(recording_publisher):
    from pydantic import BaseModel
    from typing import ClassVar

    class Thing(BaseModel):
        event_name: ClassVar[str] = "v1-marker-name"
        id: str

    adapter = base_adapter.BaseAdapter(sns_arn="arn:aws:sns:region:123:topic")
    adapter.publish(db_data=Thing(id="x"), sns_attributes={"event": "v1-explicit-name"})

    assert recording_publisher.calls[0]["attributes"]["event"]["StringValue"] == "v1-explicit-name"
