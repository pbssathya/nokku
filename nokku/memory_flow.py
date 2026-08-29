"""Truthful Nokku handoff for discovering and recalling COSsse Memory values.

COSsse remains responsible for Memory and Flow semantics. Nokku uses this small
adapter to observe what happened without turning an unclaimed/failed recall into
an assertion crash or silently treating a missing value as successful data.
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


def _status_text(status: object) -> str:
    value = getattr(status, "value", None)
    return str(value if value is not None else status)


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
