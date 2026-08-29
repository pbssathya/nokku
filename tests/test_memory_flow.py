from types import SimpleNamespace

import nokku.memory_flow as memory_flow
from cossse.flow import DispositionStatus


class _FakeFlow:
    responses = []

    def encounter(self, meaning, adapters):
        assert adapters
        assert meaning.body["requester"] == "nokku"
        if not self.responses:
            raise AssertionError("No fake response left for encounter()")
        return self.responses.pop(0)


class _FakeMemoryAdapter:
    def __init__(self, memory):
        self.memory = memory


def _feedback(body):
    return SimpleNamespace(body=body)


def _disposition(status, *bodies):
    return SimpleNamespace(
        status=status,
        feedback=[_feedback(body) for body in bodies],
    )


def _install(monkeypatch, responses):
    _FakeFlow.responses = list(responses)
    monkeypatch.setattr(memory_flow, "Flow", _FakeFlow)
    monkeypatch.setattr(memory_flow, "MemoryAdapter", _FakeMemoryAdapter)


def test_memory_discovery_reports_successful_discover_and_recall(monkeypatch):
    _install(
        monkeypatch,
        [
            _disposition(
                DispositionStatus.CLAIMED,
                {"receipts": [{"memory_id": "m1"}, {"memory_id": "m2"}]},
            ),
            _disposition(DispositionStatus.CLAIMED, {"value": {"body": {"x": 1}}}),
            _disposition(DispositionStatus.CLAIMED, {"value": {"body": {"x": 2}}}),
        ],
    )

    result = memory_flow.discover_preserved_values(object())

    assert result.status == "success"
    assert result.discovered_receipt_count == 2
    assert result.attempted_memory_ids == ("m1", "m2")
    assert result.values == ({"body": {"x": 1}}, {"body": {"x": 2}})
    assert result.failures == ()
    assert result.uncertainty == ()


def test_memory_discovery_reports_unclaimed_discovery_instead_of_asserting(monkeypatch):
    _install(
        monkeypatch,
        [_disposition(object())],
    )

    result = memory_flow.discover_preserved_values(object())

    assert result.status == "failed"
    assert result.values == ()
    assert result.attempted_memory_ids == ()
    assert result.failures
    assert "memory discovery was not singly claimed" in result.failures[0]


def test_memory_discovery_preserves_partial_recall_failures_and_uncertainty(monkeypatch):
    _install(
        monkeypatch,
        [
            _disposition(
                DispositionStatus.CLAIMED,
                {
                    "receipts": [
                        {"memory_id": "m1"},
                        {"memory_id": "m2"},
                        {"memory_id": "m3"},
                    ]
                },
            ),
            _disposition(object()),
            _disposition(DispositionStatus.CLAIMED, {"value": None}),
            _disposition(DispositionStatus.CLAIMED, {"value": {"body": {"ok": True}}}),
        ],
    )

    result = memory_flow.discover_preserved_values(object())

    assert result.status == "partial"
    assert result.discovered_receipt_count == 3
    assert result.attempted_memory_ids == ("m1", "m2", "m3")
    assert result.values == ({"body": {"ok": True}},)
    assert len(result.failures) == 1
    assert "memory m1 recall was not singly claimed" in result.failures[0]
    assert result.uncertainty == ("memory m2 recall returned no value",)
