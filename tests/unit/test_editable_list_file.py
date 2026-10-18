"""Permissions des fichiers de liste edites depuis la TUI et lus par le
service - OMEGA-SERV_PLAN-DETAILLE_SENSITIVE_PATHS.md §3.7 (R1 a R7).
Les tests d'infrastructure tournent sur de VRAIS fichiers, sous umask 077
(le scenario qui rendait un fichier illisible au service, demontre le
2026-10-18)."""
import os
import pwd
import stat
import tempfile
import unittest
from pathlib import Path

from omega_serv.application.security.editable_list_file import (
    KEYWORDS_DIR,
    apply_read_fixes,
    inspect_list_file,
    save_list_file,
)
from omega_serv.domain.security.file_access import (
    AccountIdentity,
    PathNode,
    plan_read_access_fixes,
    service_can_read,
)
from omega_serv.domain.services.systemd_unit import service_user_from_unit
from omega_serv.infrastructure.filesystem.local_file_access import LocalFileAccess

_SERVICE = AccountIdentity(name="omega-serv", uid=955, gids=frozenset({955}))
_USER_UID = 1000


def _node(path, mode, uid=_USER_UID, gid=1001, is_dir=False):
    return PathNode(path=path, mode=mode, uid=uid, gid=gid, is_dir=is_dir)


def _chain(file_mode=0o644, dir_mode=0o755, file_gid=1001, dir_gid=1001):
    return (
        _node("/", 0o755, uid=0, gid=0, is_dir=True),
        _node("/home/u", dir_mode, gid=dir_gid, is_dir=True),
        _node("/home/u/l.txt", file_mode, gid=file_gid),
    )


class _Umask:
    def __init__(self, mask):
        self._mask = mask

    def __enter__(self):
        self._previous = os.umask(self._mask)

    def __exit__(self, *exc):
        os.umask(self._previous)


class TestServiceCanRead(unittest.TestCase):
    def test_world_readable_chain(self):
        self.assertTrue(service_can_read(_chain(), _SERVICE).readable)

    def test_private_file(self):
        verdict = service_can_read(_chain(file_mode=0o600), _SERVICE)
        self.assertFalse(verdict.readable)
        self.assertEqual(verdict.blocking[0].path, "/home/u/l.txt")

    def test_non_traversable_directory(self):
        verdict = service_can_read(_chain(dir_mode=0o750), _SERVICE)
        self.assertFalse(verdict.readable)
        self.assertIn("n'est pas traversable", verdict.explain("omega-serv"))

    def test_group_member_uses_group_bits_only(self):
        """Precedence POSIX : membre du groupe -> les bits 'autres' ne comptent plus."""
        self.assertFalse(service_can_read(_chain(file_mode=0o604, file_gid=955), _SERVICE).readable)
        self.assertTrue(service_can_read(_chain(file_mode=0o640, file_gid=955), _SERVICE).readable)

    def test_root_reads_everything(self):
        root = AccountIdentity(name="root", uid=0, gids=frozenset({0}))
        self.assertTrue(service_can_read(_chain(file_mode=0o600, dir_mode=0o700), root).readable)


class TestPlanReadAccessFixes(unittest.TestCase):
    def test_adds_other_bit_for_non_member(self):
        verdict = service_can_read(_chain(file_mode=0o600, dir_mode=0o700), _SERVICE)
        fixes, not_fixable = plan_read_access_fixes(verdict, _SERVICE, _USER_UID)
        self.assertEqual(not_fixable, ())
        self.assertEqual({(f.path, f.new_mode) for f in fixes}, {("/home/u", 0o701), ("/home/u/l.txt", 0o604)})

    def test_adds_group_bit_for_member(self):
        verdict = service_can_read(_chain(file_mode=0o604, file_gid=955), _SERVICE)
        fixes, _ = plan_read_access_fixes(verdict, _SERVICE, _USER_UID)
        self.assertEqual(fixes[0].new_mode, 0o644)

    def test_never_fixes_what_the_user_does_not_own(self):
        verdict = service_can_read(_chain(dir_mode=0o750), _SERVICE)
        fixes, not_fixable = plan_read_access_fixes(verdict, _SERVICE, current_uid=4242)
        self.assertEqual(fixes, ())
        self.assertEqual(len(not_fixable), 1)


class TestServiceUserFromUnit(unittest.TestCase):
    def test_reads_user_in_service_section(self):
        unit = "[Unit]\nDescription=x\n\n[Service]\nUser=omega-serv\nGroup=omega-serv\n"
        self.assertEqual(service_user_from_unit(unit), "omega-serv")

    def test_ignores_other_sections_and_absence(self):
        self.assertIsNone(service_user_from_unit("[Install]\nUser=nope\n[Service]\nType=simple\n"))


class _RealProject(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / KEYWORDS_DIR).mkdir(parents=True)
        self.access = LocalFileAccess()
        self.me = pwd.getpwuid(os.getuid()).pw_name

    def tearDown(self):
        for path in self.root.rglob("*"):
            if path.is_dir() and not path.is_symlink():
                path.chmod(0o755)
        self._tmp.cleanup()

    def _file(self, name="l.txt") -> Path:
        return self.root / KEYWORDS_DIR / name


class TestAtomicWritePreserving(_RealProject):
    def test_new_file_gets_0644_whatever_the_umask(self):
        with _Umask(0o077):
            outcome = self.access.atomic_write_preserving(self._file(), "/x\n", 0o644)
        self.assertEqual(stat.S_IMODE(self._file().stat().st_mode), 0o644)
        self.assertEqual(outcome.mode, 0o644)

    def test_existing_mode_kept_under_umask_077(self):
        self._file().write_text("/a\n")
        self._file().chmod(0o640)
        with _Umask(0o077):
            self.access.atomic_write_preserving(self._file(), "/b\n", 0o644)
        self.assertEqual(stat.S_IMODE(self._file().stat().st_mode), 0o640)
        self.assertEqual(self._file().read_text(), "/b\n")

    def test_existing_group_kept(self):
        supplementary = [g for g in os.getgroups() if g != os.getgid()]
        if not supplementary:
            self.skipTest("aucun groupe secondaire disponible pour ce test")
        self._file().write_text("/a\n")
        os.chown(self._file(), -1, supplementary[0])
        with _Umask(0o077):
            outcome = self.access.atomic_write_preserving(self._file(), "/b\n", 0o644)
        self.assertTrue(outcome.group_preserved)
        self.assertEqual(self._file().stat().st_gid, supplementary[0])

    def test_no_temporary_file_left_behind(self):
        self.access.atomic_write_preserving(self._file(), "/x\n", 0o644)
        self.assertEqual(sorted(p.name for p in (self.root / KEYWORDS_DIR).iterdir()), ["l.txt"])


class TestLocationRules(_RealProject):
    def _location_error(self, relative):
        return inspect_list_file(self.access, self.root, relative, None).location_error

    def test_valid_location(self):
        self.assertIsNone(self._location_error(f"{KEYWORDS_DIR}/l.txt"))

    def test_refused_locations(self):
        for relative in ("/etc/passwd", f"{KEYWORDS_DIR}/../x.txt", f"{KEYWORDS_DIR}/sub/l.txt",
                         f"{KEYWORDS_DIR}/l.json", "secure/waf/rules/l.txt"):
            with self.subTest(relative=relative):
                self.assertIsNotNone(self._location_error(relative))

    def test_symlinked_file_refused(self):
        target = self.root / "ailleurs.txt"
        target.write_text("x")
        self._file().symlink_to(target)
        self.assertIn("lien symbolique", self._location_error(f"{KEYWORDS_DIR}/l.txt"))

    def test_symlinked_directory_refused(self):
        real = self.root / "vrai"
        (real / "keywords").mkdir(parents=True)
        (self.root / KEYWORDS_DIR).rmdir()
        (self.root / KEYWORDS_DIR).symlink_to(real / "keywords")
        self.assertIn("lien symbolique", self._location_error(f"{KEYWORDS_DIR}/l.txt"))


class TestSaveListFile(_RealProject):
    def _save(self, content="/x\n", expected=None, relative=None):
        return save_list_file(self.access, self.root, relative or f"{KEYWORDS_DIR}/l.txt", content, self.me, expected)

    def test_create_then_update(self):
        created = self._save()
        self.assertTrue(created.saved)
        updated = self._save("/y\n", expected=self.access.fingerprint(self._file()))
        self.assertTrue(updated.saved)
        self.assertEqual(self._file().read_text(), "/y\n")

    def test_external_modification_refused(self):
        self._save()
        stale = self.access.fingerprint(self._file())
        self._file().write_text("/modifie ailleurs, plus long\n")
        result = self._save("/y\n", expected=stale)
        self.assertFalse(result.saved)
        self.assertIn("modifie en dehors", result.refused_reason)
        self.assertEqual(self._file().read_text(), "/modifie ailleurs, plus long\n")

    def test_read_only_directory_refused(self):
        (self.root / KEYWORDS_DIR).chmod(0o555)
        result = self._save()
        self.assertFalse(result.saved)
        self.assertIn("lecture seule", result.refused_reason)

    def test_symlink_never_written_through(self):
        target = self.root / "cible.txt"
        target.write_text("intact\n")
        self._file().symlink_to(target)
        result = self._save(expected=self.access.fingerprint(self._file()))
        self.assertFalse(result.saved)
        self.assertEqual(target.read_text(), "intact\n")

    def test_service_check_after_save(self):
        result = self._save()
        self.assertEqual(result.status.service_check, "readable")

    def test_no_service_account(self):
        status = inspect_list_file(self.access, self.root, f"{KEYWORDS_DIR}/l.txt", "compte-inexistant-xyz")
        self.assertEqual(status.service_check, "no_service")


class TestRealServiceAccount(_RealProject):
    """Avec le VRAI compte du service de cette machine (ignore s'il n'existe pas)."""
    def setUp(self):
        super().setUp()
        try:
            pwd.getpwnam("omega-serv")
        except KeyError:
            self.skipTest("compte omega-serv absent de cette machine")
        service = self.access.lookup_account("omega-serv")
        if os.getuid() == 0 or self.root.stat().st_gid in service.gids:
            self.skipTest("test prevu pour un utilisateur non root, omega-serv hors du groupe du dossier")

    def test_private_temp_directory_detected_then_fixed(self):
        self.root.chmod(0o700)  # comme un dossier cree par tempfile : illisible pour omega-serv
        self.access.atomic_write_preserving(self._file(), "/x\n", 0o644)
        status = inspect_list_file(self.access, self.root, f"{KEYWORDS_DIR}/l.txt", "omega-serv")
        self.assertEqual(status.service_check, "unreadable")
        self.assertEqual(status.readability.blocking[0].path, str(self.root))
        apply_read_fixes(self.access, status.fixes)
        fixed = inspect_list_file(self.access, self.root, f"{KEYWORDS_DIR}/l.txt", "omega-serv")
        self.assertEqual(fixed.service_check, "readable", fixed.service_message())


if __name__ == "__main__":
    unittest.main()
