"""Reglages du mode « boost » (OMEGA-SERV_ETUDE_MODE_BOOST.md) : un nombre de workers doit
correspondre a la machine ou omega-serv est installe (decision utilisateur 2026-10-26)."""
import unittest

from omega_serv.core.platform_info import CpuInfo, cpu_info
from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.domain.config.validation import MAX_WORKERS, validate_config
from omega_serv.domain.security.waf.shared_counters import SHARED_RECIDIVE_CAPACITY, boost_errors
from omega_serv.interfaces.cli.serve_workers import effective_worker_count


def _cpu(physical=4, logical=8, affinity=8, quota=None):
    return CpuInfo(logical=logical, physical=physical, affinity=affinity, quota=quota, load_1min=None, detected=True)


class TestCpuInfo(unittest.TestCase):
    def test_available_takes_affinity_and_quota_into_account(self):
        self.assertEqual(_cpu().available, 8)
        self.assertEqual(_cpu(affinity=2).available, 2)          # conteneur / taskset
        self.assertEqual(_cpu(quota=1.5).available, 2)           # CPUQuota=150 % -> 2
        self.assertEqual(_cpu(quota=0.2).available, 1)           # jamais moins de 1

    def test_automatic_is_physical_cores_within_available(self):
        self.assertEqual(_cpu().recommended_workers, 4)          # hyperthreading : coeurs physiques
        self.assertEqual(_cpu(affinity=2).recommended_workers, 2)
        self.assertEqual(_cpu(quota=1.0).recommended_workers, 1)

    def test_real_machine_detection_never_fails(self):
        cpu = cpu_info()
        self.assertGreaterEqual(cpu.available, 1)
        self.assertGreaterEqual(cpu.recommended_workers, 1)
        self.assertLessEqual(cpu.physical, cpu.logical)


class TestEffectiveWorkerCount(unittest.TestCase):
    def test_automatic_and_explicit_values(self):
        self.assertEqual(effective_worker_count(0, 4, 2), (2, None))
        self.assertEqual(effective_worker_count(3, 4, 2), (3, None))
        self.assertEqual(effective_worker_count(1, 4, 2), (1, None))

    def test_more_than_the_machine_is_capped_with_a_message(self):
        count, message = effective_worker_count(16, 4, 2)
        self.assertEqual(count, 4)
        self.assertIn("16", message)


class TestValidation(unittest.TestCase):
    def _config(self, workers, threshold=3):
        return OmegaServConfig.from_dict({
            "server": {"workers": workers},
            "options": {"waf": {"enabled": True, "reputation": {"suspicious_threshold": threshold}}},
        })

    def test_workers_bounds(self):
        self.assertFalse([e for e in validate_config(self._config(0)) if "workers" in e])
        self.assertTrue([e for e in validate_config(self._config(-1)) if "workers" in e])
        self.assertTrue([e for e in validate_config(self._config(MAX_WORKERS + 1)) if "workers" in e])

    def test_recidive_threshold_must_fit_the_shared_queue_with_several_workers(self):
        too_high = SHARED_RECIDIVE_CAPACITY + 1
        self.assertEqual(boost_errors(self._config(1, too_high)), [])
        self.assertEqual(boost_errors(self._config(2, SHARED_RECIDIVE_CAPACITY)), [])
        self.assertEqual(len(boost_errors(self._config(2, too_high))), 1)
        self.assertEqual(len(boost_errors(self._config(0, too_high))), 1)


if __name__ == "__main__":
    unittest.main()
