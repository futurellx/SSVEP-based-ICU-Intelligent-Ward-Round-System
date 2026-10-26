import queue
import threading
import time
import unittest

from runtime_concurrency import (
    BoundedMessageQueue,
    QueueClosed,
    SequencedRingBuffer,
)


class BoundedMessageQueueTests(unittest.TestCase):
    def test_reject_policy_surfaces_backpressure(self):
        messages = BoundedMessageQueue(maxsize=1, overflow="reject")
        self.assertTrue(messages.put("first"))
        self.assertFalse(messages.put("second"))
        self.assertEqual(messages.dropped, 1)
        self.assertEqual(messages.get_nowait(), "first")

    def test_drop_oldest_policy_keeps_latest_state(self):
        messages = BoundedMessageQueue(maxsize=2, overflow="drop_oldest")
        messages.put(1)
        messages.put(2)
        messages.put(3)
        self.assertEqual(messages.dropped, 1)
        self.assertEqual(messages.get_nowait(), 2)
        self.assertEqual(messages.get_nowait(), 3)

    def test_close_wakes_waiting_consumer(self):
        messages = BoundedMessageQueue(maxsize=1)
        observed = []

        def consume():
            try:
                messages.get(timeout=2)
            except QueueClosed:
                observed.append("closed")

        worker = threading.Thread(target=consume)
        worker.start()
        time.sleep(0.02)
        messages.close()
        worker.join(timeout=1)
        self.assertFalse(worker.is_alive())
        self.assertEqual(observed, ["closed"])
        with self.assertRaises(QueueClosed):
            messages.put("late")


class SequencedRingBufferTests(unittest.TestCase):
    def test_readers_have_independent_cursors(self):
        stream = SequencedRingBuffer(capacity=4)
        stream.publish("a", sequence=100, acquired_at_ns=1)
        stream.publish("b", sequence=101, acquired_at_ns=2)
        first_reader = stream.read_after(-1)
        second_reader = stream.read_after(-1)
        self.assertEqual([item.payload for item in first_reader], ["a", "b"])
        self.assertEqual([item.payload for item in second_reader], ["a", "b"])
        self.assertEqual([item.source_sequence for item in first_reader], [100, 101])

    def test_internal_sequence_survives_source_restart(self):
        stream = SequencedRingBuffer(capacity=4)
        first = stream.publish("before restart", sequence=42)
        second = stream.publish("after restart", sequence=0)
        self.assertEqual(second.sequence, first.sequence + 1)
        self.assertEqual(second.source_sequence, 0)

    def test_wait_after_uses_condition_notification(self):
        stream = SequencedRingBuffer(capacity=4)
        observed = []

        def read():
            observed.extend(stream.wait_after(-1, timeout=1))

        worker = threading.Thread(target=read)
        worker.start()
        time.sleep(0.02)
        stream.publish("ready")
        worker.join(timeout=1)
        self.assertEqual([item.payload for item in observed], ["ready"])


if __name__ == "__main__":
    unittest.main()
