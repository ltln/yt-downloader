"""Run blocking work in a thread and deliver callbacks on the Tk main thread."""
from __future__ import annotations

import queue
import threading
from typing import Any, Callable


class Task:
    """Handle for a running job. `progress` and `cancelled` are for the job function to use."""

    def __init__(self, worker: "Worker"):
        self._worker = worker
        self.cancelled = threading.Event()
        self._thread: threading.Thread | None = None

    def progress(self, value: Any) -> None:
        self._worker._q.put(("progress", self, value))

    def cancel(self) -> None:
        self.cancelled.set()


class Worker:
    def __init__(self) -> None:
        self._q: queue.Queue = queue.Queue()
        self._callbacks: dict[Task, tuple] = {}

    def submit(self, fn: Callable[[Task], Any], *, on_result: Callable | None = None,
               on_error: Callable | None = None, on_progress: Callable | None = None) -> Task:
        task = Task(self)
        self._callbacks[task] = (on_result, on_error, on_progress)

        def run() -> None:
            try:
                self._q.put(("result", task, fn(task)))
            except BaseException as exc:  # noqa: BLE001 - delivered to UI
                self._q.put(("error", task, exc))

        task._thread = threading.Thread(target=run, daemon=True)
        task._thread.start()
        return task

    def drain(self) -> None:
        """Dispatch pending messages. Call from the main thread."""
        while True:
            try:
                kind, task, payload = self._q.get_nowait()
            except queue.Empty:
                return
            on_result, on_error, on_progress = self._callbacks.get(task, (None, None, None))
            if kind == "progress":
                cb = on_progress
            else:
                self._callbacks.pop(task, None)
                cb = on_result if kind == "result" else on_error
            if cb:
                cb(payload)

    def attach(self, widget, interval_ms: int = 50) -> None:
        """Poll the queue using a Tk widget's `after`."""
        def tick() -> None:
            self.drain()
            widget.after(interval_ms, tick)
        widget.after(interval_ms, tick)
