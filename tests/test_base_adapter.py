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
