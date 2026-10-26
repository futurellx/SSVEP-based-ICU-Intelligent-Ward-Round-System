"""Runtime concurrency primitives shared by the desktop processes.

The project previously used unbounded queues and "latest value" globals.  This
module keeps the primitives deliberately small so they work on Python 3.8 and
can be reused by the Qt, PsychoPy and Flask-SocketIO processes.
"""

from __future__ import annotations

import queue
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Any, Deque, List, Optional


class QueueClosed(RuntimeError):
    """Raised when a producer writes to a closed queue."""


class BoundedMessageQueue:
    """A closeable bounded queue with an explicit overflow policy.

    ``drop_oldest`` is suitable for replaceable real-time state updates.  The
    ``reject`` policy is suitable for control commands whose loss must be
    surfaced to the caller.  ``put`` never blocks indefinitely.
    """

    _SENTINEL = object()

    def __init__(self, maxsize: int, overflow: str = "reject"):
        if maxsize <= 0:
            raise ValueError("maxsize must be positive")
        if overflow not in ("reject", "drop_oldest"):
            raise ValueError("overflow must be 'reject' or 'drop_oldest'")
        self._queue = queue.Queue(maxsize=maxsize)
        self._overflow = overflow
        self._closed = threading.Event()
        self._stats_lock = threading.Lock()
        self._dropped = 0

    @property
    def dropped(self) -> int:
        with self._stats_lock:
            return self._dropped

    @property
    def closed(self) -> bool:
        return self._closed.is_set()

    def put(self, item: Any, timeout: float = 0.0) -> bool:
        if self.closed:
            raise QueueClosed("queue is closed")
        try:
            self._queue.put(item, timeout=timeout)
            return True
        except queue.Full:
            if self._overflow == "reject":
                with self._stats_lock:
                    self._dropped += 1
                return False

        # Latest-state queues prefer new information to stale information.
        try:
            self._queue.get_nowait()
        except queue.Empty:
            pass
        with self._stats_lock:
            self._dropped += 1
        try:
            self._queue.put_nowait(item)
            return True
        except queue.Full:
            return False

    def get(self, timeout: Optional[float] = None) -> Any:
        item = self._queue.get(timeout=timeout)
        if item is self._SENTINEL:
            # Keep the sentinel available for any other waiting consumer.
            try:
                self._queue.put_nowait(self._SENTINEL)
            except queue.Full:
                pass
            raise QueueClosed("queue is closed")
        return item

    def get_nowait(self) -> Any:
        return self.get(timeout=0.0)

    def close(self) -> None:
        if self._closed.is_set():
            return
        self._closed.set()
        try:
            self._queue.put_nowait(self._SENTINEL)
        except queue.Full:
            # Make room so a blocked consumer is always woken.
            try:
                self._queue.get_nowait()
            except queue.Empty:
                pass
            try:
                self._queue.put_nowait(self._SENTINEL)
            except queue.Full:
                pass


@dataclass(frozen=True)
class SequencedBlock:
    sequence: int
    source_sequence: Optional[int]
    acquired_at_ns: int
    received_at_ns: int
    payload: Any


class SequencedRingBuffer:
    """Multi-reader bounded history addressed by monotonically increasing IDs.

    Readers keep their own last-seen sequence and therefore do not steal data
    from one another.  A condition variable removes the former 1 ms polling
    loop used during training and frequency calibration.
    """

    def __init__(self, capacity: int):
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        self._items: Deque[SequencedBlock] = deque(maxlen=capacity)
        self._condition = threading.Condition()
        self._next_sequence = 0
        self._closed = False

    def publish(
        self,
        payload: Any,
        sequence: Optional[int] = None,
        acquired_at_ns: Optional[int] = None,
    ) -> SequencedBlock:
        with self._condition:
            if self._closed:
                raise QueueClosed("ring buffer is closed")
            source_sequence = sequence
            sequence = self._next_sequence
            self._next_sequence += 1
            block = SequencedBlock(
                sequence=sequence,
                source_sequence=source_sequence,
                acquired_at_ns=acquired_at_ns or time.time_ns(),
                received_at_ns=time.time_ns(),
                payload=payload,
            )
            self._items.append(block)
            self._condition.notify_all()
            return block

    def read_after(self, last_sequence: int) -> List[SequencedBlock]:
        with self._condition:
            return [item for item in self._items if item.sequence > last_sequence]

    def wait_after(self, last_sequence: int, timeout: float) -> List[SequencedBlock]:
        deadline = time.monotonic() + timeout
        with self._condition:
            while not self._closed and not any(item.sequence > last_sequence for item in self._items):
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return []
                self._condition.wait(remaining)
            return [item for item in self._items if item.sequence > last_sequence]

    @property
    def latest_sequence(self) -> int:
        with self._condition:
            return self._items[-1].sequence if self._items else -1

    @property
    def latest(self) -> Optional[SequencedBlock]:
        with self._condition:
            return self._items[-1] if self._items else None

    def close(self) -> None:
        with self._condition:
            self._closed = True
            self._condition.notify_all()
