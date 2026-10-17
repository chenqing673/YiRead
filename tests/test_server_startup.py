"""A conflicting local service must not receive YiRead browser requests."""
from pathlib import Path
import socket
import sys
import threading
import unittest
from urllib.request import urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from server import create_server


class Startup(unittest.TestCase):
    def test_two_yiread_instances_do_not_share_port(self):
        first = create_server(0)
        try:
            second = create_server(first.server_port)
            try:
                self.assertNotEqual(first.server_port, second.server_port)
            finally:
                second.server_close()
        finally:
            first.server_close()

    def test_conflicting_port_uses_working_yiread_server(self):
        with socket.socket() as occupied:
            occupied.bind(('127.0.0.1', 0))
            occupied.listen()
            original_port = occupied.getsockname()[1]
            server = create_server(original_port)
            self.assertNotEqual(server.server_port, original_port)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                with urlopen(f'http://127.0.0.1:{server.server_port}/', timeout=5) as response:
                    self.assertEqual(response.status, 200)
                    self.assertIn(b'YiRead', response.read())
            finally:
                server.shutdown()
                server.server_close()
                thread.join()


if __name__ == '__main__': unittest.main()
