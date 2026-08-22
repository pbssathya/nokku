"""Runtime path choices for Nokku's living habitat.

COSsse Memory remains path-agnostic. Nokku chooses where its living experience
is kept. The default deliberately avoids /tmp because Codespace/container
recreation proved that path is not durable enough for accumulated experience.
"""

from __future__ import annotations

import os
from pathlib import Path


def living_memory_path() -> Path:
    """Return Nokku's persistent Memory path, with an environment override."""
    override = os.environ.get("NOKKU_MEMORY_PATH")
    if override:
        path = Path(override).expanduser()
    elif Path("/workspaces").exists():
        path = Path("/workspaces/.nokku/living_memory.sqlite")
    else:
        path = Path.home() / ".local" / "share" / "nokku" / "living_memory.sqlite"

    path.parent.mkdir(parents=True, exist_ok=True)
    return path
