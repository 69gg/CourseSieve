from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class ManifestStore:
    path: Path

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"steps": {}}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def save(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def is_step_fresh(self, step: str, params_hash: str) -> bool:
        data = self.load()
        step_data = data.get("steps", {}).get(step, {})
        return bool(step_data.get("done") and step_data.get("params_hash") == params_hash)

    def get_step_outputs(self, step: str) -> dict[str, str]:
        data = self.load()
        return dict(data.get("steps", {}).get(step, {}).get("outputs", {}))

    def mark_step(self, step: str, params_hash: str, outputs: dict[str, str], duration_sec: float) -> None:
        data = self.load()
        data.setdefault("steps", {})[step] = {
            "done": True,
            "params_hash": params_hash,
            "outputs": outputs,
            "duration_sec": round(duration_sec, 3),
            "updated_at": int(time.time()),
        }
        self.save(data)
