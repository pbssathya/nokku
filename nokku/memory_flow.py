"""Truthful Nokku handoff for COSsse Memory operations.

COSsse remains responsible for Memory and Flow semantics. Nokku uses this small
adapter to observe what happened without turning failed discovery, recall, or
preservation into assertion crashes or silently treating missing evidence as
successful data.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from cossse.adapters.memory import MemoryAdapter
from cossse.flow import DispositionStatus, Flow, Meaning
from cossse.memory import Memory


@dataclass(frozen=True, slots=True)
class MemoryDiscoveryResult:
    """Receipt for one discover -> recall pass through COSsse Memory."""

    status: str
    values: tuple[dict[str, object], ...]
    discovered_receipt_count: int
    attempted_memory_ids: tuple[str, ...]
    discovery_disposition_status: str
    failures: tuple[str, ...] = ()
    uncertainty: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class MemoryPreservationResult:
    """Receipt for one preservation attempt through COSsse Memory."""

    status: str
    memory_id: str | None
    disposition_status: str
    feedback_count: int
    memory_event: str | None
    stored_at: object | None = None
    sha256: str | None = None
    failures: tuple[str, ...] = ()
    uncertainty: tuple[str, ...] = ()


def _status_text(status: object) -> str:
    value = getattr(status, "value", None)
    return str(value if value is not None else status)


def preserve_meaning(
    memory: Memory,
    meaning: Meaning,
) -> MemoryPreservationResult:
    """Preserve one meaning and report the complete Flow/Memory handoff."""
    disposition = Flow().encounter(meaning, [MemoryAdapter(memory)])
    disposition_status = _status_text(disposition.status)
    feedback_count = len(disposition.feedback)

    if disposition.status != DispositionStatus.CLAIMED or feedback_count != 1:
        return MemoryPreservationResult(
            status="failed",
            memory_id=None,
            disposition_status=disposition_status,
            feedback_count=feedback_count,
            memory_event=None,
            failures=(
                "memory preservation was not singly claimed: "
                f"disposition={disposition_status}, "
                f"feedback_count={feedback_count}",
            ),
        )

    body = disposition.feedback[0].body
    if not isinstance(body, dict):
        return MemoryPreservationResult(
            status="failed",
            memory_id=None,
            disposition_status=disposition_status,
            feedback_count=feedback_count,
            memory_event=None,
            failures=("memory preservation feedback body is not an object",),
        )

    memory_id = str(body.get("memory_id") or "").strip() or None
    memory_event = str(body.get("memory_event") or "").strip() or None
    stored_at = body.get("stored_at")
    sha256 = str(body.get("sha256") or "").strip() or None

    if memory_id is None:
        return MemoryPreservationResult(
            status="failed",
            memory_id=None,
            disposition_status=disposition_status,
            feedback_count=feedback_count,
            memory_event=memory_event,
            stored_at=stored_at,
            sha256=sha256,
            failures=("memory preservation feedback has no memory_id",),
        )

    uncertainty: tuple[str, ...] = ()
    status = "success"
    if memory_event != "preserved":
        status = "partial"
        uncertainty = (
            f"memory preservation feedback event is {memory_event or 'missing'}, not preserved",
        )

    return MemoryPreservationResult(
        status=status,
        memory_id=memory_id,
        disposition_status=disposition_status,
        feedback_count=feedback_count,
        memory_event=memory_event,
        stored_at=stored_at,
        sha256=sha256,
        uncertainty=uncertainty,
    )


def discover_preserved_values(
    memory: Memory,
    *,
    requester: str = "nokku",
) -> MemoryDiscoveryResult:
    """Discover and recall preserved values while reporting every failed handoff."""
    flow = Flow()
    adapter = MemoryAdapter(memory)
    discovery = flow.encounter(
        Meaning(
            body={
                "need": "discover_preserved_experiences",
                "requester": requester,
            }
        ),
        [adapter],
    )
    discovery_status = _status_text(discovery.status)
    if discovery.status != DispositionStatus.CLAIMED or len(discovery.feedback) != 1:
        return MemoryDiscoveryResult(
            status="failed",
            values=(),
            discovered_receipt_count=0,
            attempted_memory_ids=(),
            discovery_disposition_status=discovery_status,
            failures=(
                "memory discovery was not singly claimed: "
                f"disposition={discovery_status}, "
                f"feedback_count={len(discovery.feedback)}",
            ),
        )

    raw_receipts: Any = discovery.feedback[0].body.get("receipts")
    if not isinstance(raw_receipts, (list, tuple)):
        return MemoryDiscoveryResult(
            status="failed",
            values=(),
            discovered_receipt_count=0,
            attempted_memory_ids=(),
            discovery_disposition_status=discovery_status,
            failures=("memory discovery feedback has no receipts collection",),
        )

    values: list[dict[str, object]] = []
    attempted: list[str] = []
    failures: list[str] = []
    uncertainty: list[str] = []

    for index, receipt in enumerate(raw_receipts):
        if not isinstance(receipt, dict):
            uncertainty.append(f"receipt {index} is not an object")
            continue

        memory_id = str(receipt.get("memory_id") or "").strip()
        if not memory_id:
            uncertainty.append(f"receipt {index} has no memory_id")
            continue
        attempted.append(memory_id)

        recalled = flow.encounter(
            Meaning(
                body={
                    "need": "recall_preserved_experience",
                    "memory_id": memory_id,
                    "requester": requester,
                }
            ),
            [adapter],
        )
        recall_status = _status_text(recalled.status)
        if recalled.status != DispositionStatus.CLAIMED or len(recalled.feedback) != 1:
            failures.append(
                f"memory {memory_id} recall was not singly claimed: "
                f"disposition={recall_status}, "
                f"feedback_count={len(recalled.feedback)}"
            )
            continue

        value = recalled.feedback[0].body.get("value")
        if value is None:
            uncertainty.append(f"memory {memory_id} recall returned no value")
            continue
        if not isinstance(value, dict):
            uncertainty.append(
                f"memory {memory_id} recall returned non-object value: "
                f"{type(value).__name__}"
            )
            continue
        values.append(value)

    status = "success"
    if failures or uncertainty:
        status = "partial"

    return MemoryDiscoveryResult(
        status=status,
        values=tuple(values),
        discovered_receipt_count=len(raw_receipts),
        attempted_memory_ids=tuple(attempted),
        discovery_disposition_status=discovery_status,
        failures=tuple(failures),
        uncertainty=tuple(uncertainty),
    )
