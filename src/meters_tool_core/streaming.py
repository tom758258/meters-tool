from __future__ import annotations

import threading


class RunBoundStreamState:
    """One run's monotonic stream lifecycle, shared by event and HTTP output."""

    def __init__(self, run_id: str) -> None:
        if not run_id:
            raise ValueError("streaming requires a nonempty run_id")
        self.run_id = run_id
        self._state = "waiting"
        self._lock = threading.Lock()

    def activate(self) -> bool:
        with self._lock:
            if self._state != "waiting":
                return False
            self._state = "active"
            return True

    def end(self) -> bool:
        with self._lock:
            if self._state == "ended":
                return False
            self._state = "ended"
            return True

    def status_fields(self) -> dict[str, object]:
        with self._lock:
            return {"stream": {"lifecycle": "run_bound", "state": self._state}}

    def ready_fields(self) -> dict[str, object]:
        return {"stream": {"lifecycle": "run_bound"}}
