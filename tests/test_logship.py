import json
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
