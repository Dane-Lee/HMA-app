from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class MovementCatalog:
    def __init__(self, config_path: Path) -> None:
        self.config_path = config_path
        self._movements = json.loads(config_path.read_text(encoding="utf-8"))
        self._movement_map = {movement["key"]: movement for movement in self._movements}

    def list(self) -> list[dict[str, Any]]:
        return list(self._movements)

    def get(self, movement_key: str) -> dict[str, Any] | None:
        return self._movement_map.get(movement_key)

