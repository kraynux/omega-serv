import json
import tempfile
import unittest
from pathlib import Path

from omega_serv.domain.security.waf.exceptions import WafRuleLoadError, WafRuleValidationError
from omega_serv.infrastructure.filesystem.local_filesystem import LocalFilesystem
from omega_serv.infrastructure.waf.rule_pack_loader import load_rule_pack, load_rule_packs

_VALID_PACK = {
    "version": 1,
    "pack": "body-sqli",
    "enabled": True,
    "rules": [
        {"id": "SQLI-001", "description": "Union select", "scope": ["query"], "pattern": r"union\s+select", "weight": 5},
    ],
}


class TestLoadRulePack(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.fs = LocalFilesystem()

    def tearDown(self):
        self._tmp.cleanup()

    def test_missing_file_raises(self):
        with self.assertRaises(WafRuleLoadError):
            load_rule_pack(self.fs, self.root / "missing.json")

    def test_invalid_json_raises(self):
        path = self.root / "bad.json"
        path.write_text("{ not json")
        with self.assertRaises(WafRuleLoadError):
            load_rule_pack(self.fs, path)

    def test_non_object_json_raises(self):
        path = self.root / "list.json"
        path.write_text("[1, 2]")
        with self.assertRaises(WafRuleLoadError):
            load_rule_pack(self.fs, path)

    def test_valid_pack_loads_and_compiles(self):
        path = self.root / "core.json"
        path.write_text(json.dumps(_VALID_PACK))
        compiled = load_rule_pack(self.fs, path)
        self.assertEqual(compiled.pack, "body-sqli")
        self.assertEqual(len(compiled.rules), 1)

    def test_invalid_rule_raises_validation_error(self):
        data = dict(_VALID_PACK)
        data["rules"] = [{"id": "", "scope": ["query"], "pattern": "x"}]
        path = self.root / "invalid.json"
        path.write_text(json.dumps(data))
        with self.assertRaises(WafRuleValidationError):
            load_rule_pack(self.fs, path)

    def test_load_rule_packs_loads_all(self):
        path1 = self.root / "a.json"
        path1.write_text(json.dumps(_VALID_PACK))
        data2 = dict(_VALID_PACK)
        data2["pack"] = "sensitive-paths"
        path2 = self.root / "b.json"
        path2.write_text(json.dumps(data2))
        packs = load_rule_packs(self.fs, (path1, path2))
        self.assertEqual(len(packs), 2)
        self.assertEqual({p.pack for p in packs}, {"body-sqli", "sensitive-paths"})


if __name__ == "__main__":
    unittest.main()
