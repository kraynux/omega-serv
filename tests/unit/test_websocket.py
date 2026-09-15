# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
import unittest

from omega_serv.domain.http.headers import HttpHeaders
from omega_serv.domain.http.request import HttpRequest
from omega_serv.domain.http.websocket import is_websocket_upgrade_request


def _request(method="GET", headers=None) -> HttpRequest:
    return HttpRequest(
        request_id="r1", remote_ip="203.0.113.1", peer_ip="203.0.113.1", method=method,
        path="/ws/", raw_path="/ws/", query="", headers=HttpHeaders.from_pairs(headers or []),
        body=None, content_length=None, is_tls=False,
    )


class TestIsWebsocketUpgradeRequest(unittest.TestCase):
    def test_valid_upgrade_request(self):
        request = _request(headers=[("Connection", "Upgrade"), ("Upgrade", "websocket")])
        self.assertTrue(is_websocket_upgrade_request(request))

    def test_case_insensitive_header_values(self):
        request = _request(headers=[("Connection", "UPGRADE"), ("Upgrade", "WebSocket")])
        self.assertTrue(is_websocket_upgrade_request(request))

    def test_connection_with_multiple_tokens(self):
        # Certains clients envoient "Connection: keep-alive, Upgrade".
        request = _request(headers=[("Connection", "keep-alive, Upgrade"), ("Upgrade", "websocket")])
        self.assertTrue(is_websocket_upgrade_request(request))

    def test_non_get_method_rejected(self):
        request = _request(method="POST", headers=[("Connection", "Upgrade"), ("Upgrade", "websocket")])
        self.assertFalse(is_websocket_upgrade_request(request))

    def test_missing_connection_header_rejected(self):
        request = _request(headers=[("Upgrade", "websocket")])
        self.assertFalse(is_websocket_upgrade_request(request))

    def test_connection_without_upgrade_token_rejected(self):
        request = _request(headers=[("Connection", "keep-alive"), ("Upgrade", "websocket")])
        self.assertFalse(is_websocket_upgrade_request(request))

    def test_missing_upgrade_header_rejected(self):
        request = _request(headers=[("Connection", "Upgrade")])
        self.assertFalse(is_websocket_upgrade_request(request))

    def test_upgrade_value_not_websocket_rejected(self):
        request = _request(headers=[("Connection", "Upgrade"), ("Upgrade", "h2c")])
        self.assertFalse(is_websocket_upgrade_request(request))

    def test_ordinary_request_rejected(self):
        request = _request(headers=[])
        self.assertFalse(is_websocket_upgrade_request(request))


if __name__ == "__main__":
    unittest.main()
