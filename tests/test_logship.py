import json
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

from ship import Ship
from server import serve

class TestShip(unittest.TestCase):
    def test_append_returns_offset(self):
        self.assertEqual(Ship().append("a", "1")["offset"], 1)

    def test_sync_returns_entries(self):
        ship = Ship()
        ship.append("a", "1")
        self.assertEqual(len(ship.sync(0)["entries"]), 1)

    def test_snapshot_after_every(self):
        ship = Ship(snapshot_every=2)
        ship.append("a", "1")
        ship.append("b", "2")
        self.assertEqual(ship.snapshot_offset, 2)

    def test_state_shape(self):
        self.assertIn("offset", Ship().state())

    def test_http_sync(self):
        server = serve(0)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        base = "http://127.0.0.1:%d" % server.server_port
        urllib.request.urlopen(base + "/append", data=b'{"key": "a", "value": "1"}', timeout=5).read()
        with urllib.request.urlopen(base + "/sync?offset=0", timeout=5) as response:
            self.assertEqual(len(json.loads(response.read())["entries"]), 1)
        server.shutdown()
        server.server_close()

    def test_sync_only_after_offset(self):
        ship = Ship()
        for i in range(3):
            ship.append("k%d" % i, str(i))
        result = ship.sync(1)
        self.assertEqual([e["offset"] for e in result["entries"]], [2, 3])

    def test_sync_from_latest_is_empty(self):
        ship = Ship()
        ship.append("a", "1")
        self.assertEqual(ship.sync(1)["entries"], [])

    def test_sync_beyond_length_is_empty(self):
        ship = Ship()
        ship.append("a", "1")
        result = ship.sync(99)
        self.assertEqual(result["entries"], [])
        self.assertEqual(result["offset"], 1)

    def test_duplicate_append_idempotent(self):
        ship = Ship()
        ship.append("a", "1")
        again = ship.append("a", "1", offset=1)
        self.assertEqual(again["offset"], 1)
        self.assertEqual(ship.duplicates, 1)
        self.assertEqual(ship.appends, 1)
        self.assertEqual(len(ship.log), 1)
        self.assertEqual(ship.applied, {"a": "1"})

    def test_catches_count_lagging_syncs(self):
        ship = Ship()
        for i in range(4):
            ship.append("k%d" % i, str(i))
        ship.sync(0)
        self.assertEqual(ship.catches, 0)
        ship.sync(2)
        self.assertEqual(ship.catches, 2)
        ship.sync(4)
        self.assertEqual(ship.catches, 2)

    def test_snapshot_boundary_no_overlap(self):
        ship = Ship(snapshot_every=2)
        for i in range(5):
            ship.append("k%d" % i, str(i))
        self.assertEqual(ship.snapshot_offset, 4)
        replayable = [item[0] for item in ship.log if item[0] >= ship.snapshot_offset]
        covered = [item[0] for item in ship.log if item[0] < ship.snapshot_offset]
        self.assertEqual(replayable, [4, 5])
        self.assertFalse(set(covered) & set(replayable))

    def test_recover_replays_wal(self):
        with tempfile.TemporaryDirectory() as tmp:
            wal = os.path.join(tmp, "ship.wal")
            ship = Ship(snapshot_every=2, wal_path=wal)
            for i in range(5):
                ship.append("k%d" % i, str(i))
            fresh = Ship(snapshot_every=2, wal_path=wal)
            result = fresh.recover()
            self.assertEqual(result["offset"], 5)
            self.assertEqual(result["snapshot_offset"], 4)
            self.assertEqual(result["replayed"], 2)
            self.assertTrue(result["monotonic"])
            self.assertEqual(fresh.applied, ship.applied)
            self.assertEqual(len(fresh.log), 5)

    def test_recover_ignores_half_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            wal = os.path.join(tmp, "ship.wal")
            ship = Ship(wal_path=wal)
            ship.append("a", "1")
            ship.append("b", "2")
            with open(wal, "a", encoding="utf-8") as fh:
                fh.write('{"op": "append", "offset": 3, "ke')
            fresh = Ship(wal_path=wal)
            result = fresh.recover()
            self.assertEqual(result["offset"], 2)
            self.assertEqual(len(fresh.log), 2)
            self.assertEqual(fresh.applied, {"a": "1", "b": "2"})

    def test_recover_offset_monotonic(self):
        with tempfile.TemporaryDirectory() as tmp:
            wal = os.path.join(tmp, "ship.wal")
            ship = Ship(wal_path=wal)
            for i in range(3):
                ship.append("k%d" % i, str(i))
            ship.sync(0)
            first = ship.recover()
            second = ship.recover()
            self.assertTrue(first["monotonic"])
            self.assertTrue(second["monotonic"])
            self.assertEqual(second["offset"], first["offset"])

    def test_http_duplicate_append(self):
        server = serve(0, Ship())
        threading.Thread(target=server.serve_forever, daemon=True).start()
        base = "http://127.0.0.1:%d" % server.server_port
        urllib.request.urlopen(base + "/append", data=b'{"key": "a", "value": "1", "offset": 1}', timeout=5).read()
        urllib.request.urlopen(base + "/append", data=b'{"key": "a", "value": "1", "offset": 1}', timeout=5).read()
        with urllib.request.urlopen(base + "/state", timeout=5) as response:
            self.assertEqual(json.loads(response.read())["duplicates"], 1)
        server.shutdown()
        server.server_close()
