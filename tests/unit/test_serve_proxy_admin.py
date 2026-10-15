import json
import unittest

from omega_serv.application.server.serve_proxy_admin import handle_admin_request
from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.domain.http.headers import HttpHeaders
from omega_serv.domain.http.request import HttpRequest
from omega_serv.domain.http.status_codes import HttpStatus
from omega_serv.domain.routing.proxy_cache_metrics import ProxyCacheMetrics
from omega_serv.domain.routing.proxy_health import ProxyHealthState
from omega_serv.domain.routing.proxy_zone import UpstreamTarget

_TRUSTED = ["10.0.0.0/24"]
_TRUSTED_IP = "10.0.0.5"
_UNTRUSTED_IP = "203.0.113.9"


def _request(path: str, *, method: str = "GET", peer_ip: str = _TRUSTED_IP, query: str = "") -> HttpRequest:
    return HttpRequest(
        request_id="r1", remote_ip=peer_ip, peer_ip=peer_ip, method=method,
        path=path, raw_path=path, query=query,
        headers=HttpHeaders.from_pairs([]), body=None, content_length=None, is_tls=False,
    )


def _config() -> OmegaServConfig:
    return OmegaServConfig.from_dict({
        "server": {"bind": "127.0.0.1", "port": 0},
        "options": {"reverse_proxy": {
            "enabled": True,
            "zones": [{
                "url_prefix": "/api/",
                "upstreams": [{"host": "127.0.0.1", "port": 3000}, {"host": "127.0.0.1", "port": 3001}],
            }],
        }},
    })


class TestHandleAdminRequestAuth(unittest.TestCase):
    def test_untrusted_ip_gets_forbidden(self):
        response = handle_admin_request(
            _request("/.omega-serv-admin/health", peer_ip=_UNTRUSTED_IP, query="zone=/api/"),
            _TRUSTED, _config(), ProxyHealthState(), ProxyCacheMetrics(),
        )
        self.assertEqual(response.status, HttpStatus.FORBIDDEN)

    def test_empty_trusted_networks_fails_closed(self):
        response = handle_admin_request(
            _request("/.omega-serv-admin/health", peer_ip="127.0.0.1", query="zone=/api/"),
            [], _config(), ProxyHealthState(), ProxyCacheMetrics(),
        )
        self.assertEqual(response.status, HttpStatus.FORBIDDEN)

    def test_unknown_subpath_is_not_found(self):
        response = handle_admin_request(
            _request("/.omega-serv-admin/bogus"), _TRUSTED, _config(), ProxyHealthState(), ProxyCacheMetrics(),
        )
        self.assertEqual(response.status, HttpStatus.NOT_FOUND)


class TestHandleAdminRequestHealthGet(unittest.TestCase):
    def test_known_zone_lists_every_upstream_as_up_by_default(self):
        response = handle_admin_request(
            _request("/.omega-serv-admin/health", query="zone=/api/"),
            _TRUSTED, _config(), ProxyHealthState(), ProxyCacheMetrics(),
        )
        self.assertEqual(response.status, HttpStatus.OK)
        data = json.loads(response.body)
        self.assertEqual(data["upstreams"], {"127.0.0.1:3000": "up", "127.0.0.1:3001": "up"})

    def test_unknown_zone_is_not_found(self):
        response = handle_admin_request(
            _request("/.omega-serv-admin/health", query="zone=/nope/"),
            _TRUSTED, _config(), ProxyHealthState(), ProxyCacheMetrics(),
        )
        self.assertEqual(response.status, HttpStatus.NOT_FOUND)

    def test_missing_zone_param_is_bad_request(self):
        response = handle_admin_request(
            _request("/.omega-serv-admin/health"), _TRUSTED, _config(), ProxyHealthState(), ProxyCacheMetrics(),
        )
        self.assertEqual(response.status, HttpStatus.BAD_REQUEST)

    def test_reflects_an_already_down_upstream(self):
        health_state = ProxyHealthState()
        upstream = UpstreamTarget(host="127.0.0.1", port=3000)
        health_state.record_failure("/api/", upstream, unhealthy_after=1)
        response = handle_admin_request(
            _request("/.omega-serv-admin/health", query="zone=/api/"), _TRUSTED, _config(), health_state, ProxyCacheMetrics(),
        )
        data = json.loads(response.body)
        self.assertEqual(data["upstreams"]["127.0.0.1:3000"], "down")


class TestHandleAdminRequestHealthPost(unittest.TestCase):
    def test_marks_upstream_draining(self):
        health_state = ProxyHealthState()
        response = handle_admin_request(
            _request("/.omega-serv-admin/health", method="POST", query="zone=/api/&upstream=127.0.0.1:3000&status=draining"),
            _TRUSTED, _config(), health_state, ProxyCacheMetrics(),
        )
        self.assertEqual(response.status, HttpStatus.OK)
        self.assertEqual(json.loads(response.body)["status"], "draining")
        get_response = handle_admin_request(
            _request("/.omega-serv-admin/health", query="zone=/api/"), _TRUSTED, _config(), health_state, ProxyCacheMetrics(),
        )
        self.assertEqual(json.loads(get_response.body)["upstreams"]["127.0.0.1:3000"], "draining")

    def test_marks_upstream_maintenance(self):
        health_state = ProxyHealthState()
        handle_admin_request(
            _request("/.omega-serv-admin/health", method="POST", query="zone=/api/&upstream=127.0.0.1:3000&status=maintenance"),
            _TRUSTED, _config(), health_state, ProxyCacheMetrics(),
        )
        get_response = handle_admin_request(
            _request("/.omega-serv-admin/health", query="zone=/api/"), _TRUSTED, _config(), health_state, ProxyCacheMetrics(),
        )
        self.assertEqual(json.loads(get_response.body)["upstreams"]["127.0.0.1:3000"], "maintenance")

    def test_clear_returns_to_automatic_state(self):
        health_state = ProxyHealthState()
        handle_admin_request(
            _request("/.omega-serv-admin/health", method="POST", query="zone=/api/&upstream=127.0.0.1:3000&status=draining"),
            _TRUSTED, _config(), health_state, ProxyCacheMetrics(),
        )
        handle_admin_request(
            _request("/.omega-serv-admin/health", method="POST", query="zone=/api/&upstream=127.0.0.1:3000&status=clear"),
            _TRUSTED, _config(), health_state, ProxyCacheMetrics(),
        )
        get_response = handle_admin_request(
            _request("/.omega-serv-admin/health", query="zone=/api/"), _TRUSTED, _config(), health_state, ProxyCacheMetrics(),
        )
        self.assertEqual(json.loads(get_response.body)["upstreams"]["127.0.0.1:3000"], "up")

    def test_invalid_status_is_bad_request(self):
        response = handle_admin_request(
            _request("/.omega-serv-admin/health", method="POST", query="zone=/api/&upstream=127.0.0.1:3000&status=bogus"),
            _TRUSTED, _config(), ProxyHealthState(), ProxyCacheMetrics(),
        )
        self.assertEqual(response.status, HttpStatus.BAD_REQUEST)

    def test_unknown_upstream_is_not_found(self):
        response = handle_admin_request(
            _request("/.omega-serv-admin/health", method="POST", query="zone=/api/&upstream=10.0.0.9:1234&status=draining"),
            _TRUSTED, _config(), ProxyHealthState(), ProxyCacheMetrics(),
        )
        self.assertEqual(response.status, HttpStatus.NOT_FOUND)

    def test_missing_params_is_bad_request(self):
        response = handle_admin_request(
            _request("/.omega-serv-admin/health", method="POST", query="zone=/api/"),
            _TRUSTED, _config(), ProxyHealthState(), ProxyCacheMetrics(),
        )
        self.assertEqual(response.status, HttpStatus.BAD_REQUEST)


class TestHandleAdminRequestCacheStats(unittest.TestCase):
    def test_no_samples_yet_returns_zeros(self):
        response = handle_admin_request(
            _request("/.omega-serv-admin/cache-stats", query="zone=/api/"),
            _TRUSTED, _config(), ProxyHealthState(), ProxyCacheMetrics(),
        )
        self.assertEqual(response.status, HttpStatus.OK)
        self.assertEqual(json.loads(response.body), {"zone": "/api/", "hits": 0, "misses": 0})

    def test_reflects_recorded_hits_and_misses(self):
        metrics = ProxyCacheMetrics()
        metrics.record_hit("/api/")
        metrics.record_hit("/api/")
        metrics.record_miss("/api/")
        response = handle_admin_request(
            _request("/.omega-serv-admin/cache-stats", query="zone=/api/"),
            _TRUSTED, _config(), ProxyHealthState(), metrics,
        )
        self.assertEqual(json.loads(response.body), {"zone": "/api/", "hits": 2, "misses": 1})

    def test_global_aggregates_across_zones(self):
        metrics = ProxyCacheMetrics()
        metrics.record_hit("/api/")
        metrics.record_hit("/other/")
        response = handle_admin_request(
            _request("/.omega-serv-admin/cache-stats"), _TRUSTED, _config(), ProxyHealthState(), metrics,
        )
        data = json.loads(response.body)
        self.assertIsNone(data["zone"])
        self.assertEqual(data["hits"], 2)


if __name__ == "__main__":
    unittest.main()
