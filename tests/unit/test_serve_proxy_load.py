import json
import unittest

from omega_serv.application.server.serve_proxy_load import handle_load_request
from omega_serv.domain.http.headers import HttpHeaders
from omega_serv.domain.http.request import HttpRequest
from omega_serv.domain.http.status_codes import HttpStatus


def _request(peer_ip: str) -> HttpRequest:
    return HttpRequest(
        request_id="r1", remote_ip=peer_ip, peer_ip=peer_ip, method="GET",
        path="/.omega-serv-load/", raw_path="/.omega-serv-load/", query="",
        headers=HttpHeaders.from_pairs([]), body=None, content_length=None, is_tls=False,
    )


class TestHandleLoadRequest(unittest.TestCase):
    def test_trusted_ip_receives_metrics_json(self):
        response = handle_load_request(_request("10.0.0.5"), ["10.0.0.0/24"])
        self.assertEqual(response.status, HttpStatus.OK)
        self.assertEqual(response.headers["Content-Type"], "application/json")
        data = json.loads(response.body)
        self.assertIn("cpu_percent", data)
        self.assertIn("load_average_1m", data)
        self.assertIn("memory_percent", data)

    def test_untrusted_ip_gets_forbidden(self):
        response = handle_load_request(_request("203.0.113.9"), ["10.0.0.0/24"])
        self.assertEqual(response.status, HttpStatus.FORBIDDEN)
        self.assertEqual(response.body, b"")

    def test_empty_trusted_networks_fails_closed(self):
        """§19.1 : jamais de repli "ouvert par defaut" - une liste vide
        (option trusted_proxy absente/desactivee) refuse tout le monde,
        y compris une IP qui paraitrait "locale"."""
        response = handle_load_request(_request("127.0.0.1"), [])
        self.assertEqual(response.status, HttpStatus.FORBIDDEN)


if __name__ == "__main__":
    unittest.main()
