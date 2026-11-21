# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Plan proxy natif v2, lot 6 : choix du backend du relais natif compare au VRAI proxy Python (`resolve_upstream`,
`ProxyLoadBalancerState`, `ProxyHealthState`) sur des scenarios aleatoires (graine fixe) : 7 strategies, poids,
plafonds, cookie collant, regles par en-tete, echecs et succes (fall/rise), coupe-circuit a demi ouvert apres 10 s,
temps de reponse, scores de charge, etats manuels, exclusion d'un nouvel essai. Horloge virtuelle des deux cotes.

Le binaire rejoue chaque scenario (`--simulate-balance`) et ecrit le backend choisi a chaque etape. Sans build, le test
est saute."""
from __future__ import annotations

import json
import random
import subprocess
import unittest
from unittest import mock

from omega_serv.application.server.serve_proxy import AllUpstreamsAtCapacityError, resolve_upstream
from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.domain.routing.proxy_health import ProxyHealthState
from omega_serv.domain.routing.proxy_zone import (
    ProxyLoadBalancerState,
    parse_proxy_zones,
    sticky_cookie_value_for_key,
)
from omega_serv.infrastructure.server.native_snapshot import proxy_section
from tests.integration.proxy_harness import NATIVE_BINARY

STRATEGIES = ("round_robin", "weighted_round_robin", "least_connections", "weighted_least_connections", "ip_hash",
              "least_response_time", "real_load")
START = 3600.0  # horloge virtuelle du natif : une heure apres son origine


class _Request:
    def __init__(self, ip: str, headers: dict[str, str]) -> None:
        self.remote_ip = ip
        self._headers = {name.lower(): value for name, value in headers.items()}

    def header(self, name: str, default: str | None = None) -> str | None:
        return self._headers.get(name.lower(), default)


def _zone_config(rng: random.Random) -> dict:
    count = rng.randint(2, 4)
    upstreams = [{"host": f"10.0.0.{i + 1}", "port": 8000 + i, "weight": rng.choice((1, 1, 2, 3, 5)),
                  "max_concurrent_requests": rng.choice((None, None, 1, 2)),
                  "active_health_check_enabled": rng.random() < 0.2,
                  "load_source": "declarative" if rng.random() < 0.5 else "none"} for i in range(count)]
    zone = {"url_prefix": "/api/", "upstreams": upstreams, "load_balancing": rng.choice(STRATEGIES),
            "unhealthy_after": rng.randint(1, 3), "healthy_after": rng.randint(1, 2),
            "load_sample_max_age_seconds": rng.choice((5.0, 60.0))}
    if rng.random() < 0.4:
        zone["sticky_session_enabled"] = True
    if rng.random() < 0.4:
        target = rng.choice(upstreams)
        zone["routing_rules"] = [{"header_name": "X-Version", "pattern": rng.choice(("beta", "be*")),
                                  "upstream_key": f"{target['host']}:{target['port']}"}]
    return zone


def _steps(rng: random.Random, keys: list[str], count: int = 80) -> list[dict]:
    steps: list[dict] = []
    held: list[str] = []
    for _ in range(count):
        roll = rng.random()
        key = rng.choice(keys)
        if roll < 0.40:
            headers = {}
            if rng.random() < 0.3:
                headers["X-Version"] = rng.choice(("beta", "beta-2", "stable"))
            if rng.random() < 0.3:
                headers["Cookie"] = f"a=1; omega_proxy_sticky={sticky_cookie_value_for_key(rng.choice(keys))}"
            step = {"op": "select", "ip": f"203.0.113.{rng.randint(1, 40)}", "headers": headers}
            if rng.random() < 0.1:
                step["exclude"] = [rng.choice(keys)]
            steps.append(step)
        elif roll < 0.52 and held:
            steps.append({"op": "release", "key": held.pop(rng.randrange(len(held)))})
        elif roll < 0.64:
            steps.append({"op": "failure", "key": key})
        elif roll < 0.74:
            steps.append({"op": "success", "key": key})
        elif roll < 0.80:
            steps.append({"op": "time", "key": key, "seconds": round(rng.uniform(0.001, 2.0), 3)})
        elif roll < 0.88:
            steps.append({"op": "advance", "seconds": rng.choice((0.5, 3.0, 10.5, 30.0))})
        elif roll < 0.94:
            steps.append({"op": "event", "name": key, "kind": "load", "value": str(rng.randint(0, 100))})
        else:
            steps.append({"op": "event", "name": key, "kind": "manual",
                          "value": rng.choice(("draining", "maintenance", "clear"))})
        if steps[-1]["op"] == "select":
            held.append("?")  # remplace par la cle choisie a la lecture du resultat (voir _python_run)
    return steps


def _python_run(zone_config: dict, steps: list[dict]) -> list[str]:
    """Meme scenario dans le proxy Python. Une reservation suit chaque choix (acquire, comme _attempt_forward)."""
    zone = parse_proxy_zones([zone_config])[0]
    by_key = {f"{u.host}:{u.port}": u for u in zone.upstreams}
    balancer, health = ProxyLoadBalancerState(), ProxyHealthState()
    clock = [START]
    out: list[str] = []
    with mock.patch("time.monotonic", lambda: clock[0]):
        for step in steps:
            op = step["op"]
            upstream = by_key.get(step.get("key", ""))
            if op == "select":
                request = _Request(step["ip"], step["headers"])
                try:
                    chosen = resolve_upstream(request, zone, balancer, health, exclude=frozenset(step.get("exclude", [])))
                except AllUpstreamsAtCapacityError:
                    out.append("capacity")
                    continue
                balancer.acquire(zone.url_prefix, chosen)
                out.append(f"{chosen.host}:{chosen.port}")
            elif op == "release" and step["key"] in by_key:
                balancer.release(zone.url_prefix, upstream)
            elif op == "failure":
                health.record_failure(zone.url_prefix, upstream, unhealthy_after=zone.unhealthy_after, now=clock[0])
            elif op == "success":
                health.record_success(zone.url_prefix, upstream, healthy_after=zone.healthy_after)
            elif op == "time":
                balancer.record_response_time(zone.url_prefix, upstream, step["seconds"])
            elif op == "advance":
                clock[0] += step["seconds"]
            elif op == "event" and step["kind"] == "load":
                health.record_load_sample(zone.url_prefix, by_key[step["name"]], float(step["value"]),
                                          smoothing_samples=1, now=clock[0])
            elif op == "event":
                action = {"draining": health.mark_draining, "maintenance": health.mark_maintenance,
                          "clear": health.clear_manual_state}[step["value"]]
                action(zone.url_prefix, step["name"])
    return out


def _fill_releases(zone_config: dict, steps: list[dict]) -> list[dict]:
    """Les « release » visent des cles reelles : celles que Python a choisies (identiques au natif si tout va bien)."""
    chosen = iter(_python_run(zone_config, [s for s in steps if s["op"] != "release"]))
    held: list[str] = []
    filled: list[dict] = []
    for step in steps:
        if step["op"] == "select":
            key = next(chosen, "capacity")
            if key not in ("capacity", "none"):
                held.append(key)
        elif step["op"] == "release":
            if not held:
                continue
            step = {"op": "release", "key": held.pop(0)}
        filled.append(step)
    return filled


def _native_run(zone_config: dict, steps: list[dict]) -> list[str]:
    config = OmegaServConfig.from_dict({"server": {"engine": "native", "port": 9999}, "options": {
        "reverse_proxy": {"enabled": True, "engine": "native", "zones": [zone_config]}}})
    section = proxy_section(config, False, None)
    scenario = json.dumps({"proxy": section, "zone": zone_config["url_prefix"], "steps": steps})
    result = subprocess.run([str(NATIVE_BINARY), "--simulate-balance"], input=scenario, capture_output=True,
                            text=True, timeout=30, check=True)
    return result.stdout.splitlines()


@unittest.skipUnless(NATIVE_BINARY.is_file(), "binaire natif non construit")
class TestNativeBalanceMatchesPython(unittest.TestCase):
    def test_random_scenarios_choose_the_same_backend(self):
        rng = random.Random(20261113)
        seen_strategies: set[str] = set()
        selections = capacity = 0
        for number in range(240):
            zone_config = _zone_config(rng)
            keys = [f"{u['host']}:{u['port']}" for u in zone_config["upstreams"]]
            steps = _fill_releases(zone_config, _steps(rng, keys))
            python = _python_run(zone_config, steps)
            native = _native_run(zone_config, steps)
            self.assertEqual(native, python, f"scenario {number} : {json.dumps(zone_config)}")
            seen_strategies.add(zone_config["load_balancing"])
            selections += len(python)
            capacity += python.count("capacity")
        self.assertEqual(seen_strategies, set(STRATEGIES))
        self.assertGreater(selections, 4000)
        self.assertGreater(capacity, 10)  # le corpus atteint bien les plafonds (503)

    def test_half_open_trial_is_single_and_waits_ten_seconds(self):
        zone = {"url_prefix": "/api/", "unhealthy_after": 1, "upstreams": [
            {"host": "10.0.0.1", "port": 8000}, {"host": "10.0.0.2", "port": 8001}]}
        a, b = "10.0.0.1:8000", "10.0.0.2:8001"
        steps = [{"op": "failure", "key": a},
                 *({"op": "select", "ip": "1.1.1.1", "headers": {}} for _ in range(3)),
                 {"op": "advance", "seconds": 10.5},
                 *({"op": "select", "ip": "1.1.1.1", "headers": {}} for _ in range(3)),  # un seul essai vers a
                 {"op": "success", "key": a},
                 *({"op": "select", "ip": "1.1.1.1", "headers": {}} for _ in range(2))]
        expected = [b, b, b, a, b, b, b, a]  # essai unique vers a apres 10 s ; de retour, a reprend son tour
        self.assertEqual(_python_run(zone, steps), expected)
        self.assertEqual(_native_run(zone, steps), expected)


if __name__ == "__main__":
    unittest.main()
