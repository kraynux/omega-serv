# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
import unittest
from pathlib import Path

from omega_serv.domain.services.systemd_unit import (
    SystemdUnitParams,
    find_account_in_use,
    find_conflicting_unit,
    find_name_hijack,
    generate_systemd_unit,
)


def _params(**overrides):
    defaults = {
        "service_name": "omega-serv",
        "description": "OMEGA-SERV web server",
        "python_executable": Path("/opt/omega-serv/.venv/bin/python"),
        "project_root": Path("/opt/omega-serv"),
        "config_path": Path("/opt/omega-serv/config/omega-serve.json"),
        "user": "omega-serv",
        "group": "omega-serv",
    }
    defaults.update(overrides)
    return SystemdUnitParams(**defaults)


class TestGenerateSystemdUnit(unittest.TestCase):
    def test_contains_hardening_directives(self):
        unit = generate_systemd_unit(_params())
        for directive in ("NoNewPrivileges=true", "PrivateTmp=true", "ProtectHome=read-only", "ProtectSystem=strict", "UMask=0007", "Restart=on-failure"):
            self.assertIn(directive, unit)

    def test_exec_reload_sends_sighup_to_main_pid(self):
        # Retour utilisateur 2026-09-11 : sans ExecReload=, `systemctl
        # reload` echoue purement et simplement ("Job type reload is
        # not applicable") - seul moyen de declencher le rechargement a
        # chaud deja code cote applicatif (SIGHUP, interfaces/cli/
        # main.py::run_server_until_stopped) etait un `kill -HUP` manuel
        # en dehors de l'application.
        unit = generate_systemd_unit(_params())
        self.assertIn("ExecReload=/bin/kill -HUP $MAINPID", unit)

    def test_protect_home_is_read_only_not_true(self):
        # Retour utilisateur 2026-09-10, vrai bug trouve : ProtectHome=true
        # rend /home/ INACCESSIBLE ET VIDE pour le service (man
        # systemd.exec) - or ce projet s'installe typiquement sous le
        # HOME de l'utilisateur (~/DEV/SERV/omega-serv, meme install.sh),
        # donc =true empechait le service de voir son propre interpreteur
        # Python. "read-only" reste compatible tout en gardant
        # l'essentiel du durcissement (rien d'ecrivable sous /home hors
        # ReadWritePaths, deja limite a var/).
        unit = generate_systemd_unit(_params())
        self.assertNotIn("ProtectHome=true", unit)
        self.assertIn("ProtectHome=read-only", unit)

    def test_works_for_a_project_installed_under_a_user_home_directory(self):
        # Repli exact du scenario reel qui a revele le bug ci-dessus -
        # les fixtures par defaut de ce fichier utilisaient /opt/, jamais
        # /home/, ce qui n'aurait jamais pu detecter cette incompatibilite.
        unit = generate_systemd_unit(_params(
            python_executable=Path("/home/kraynux/DEV/SERV/omega-serv/.venv/bin/python"),
            project_root=Path("/home/kraynux/DEV/SERV/omega-serv"),
            config_path=Path("/home/kraynux/DEV/SERV/omega-serv/config/omega-serve.json"),
        ))
        self.assertIn("ExecStart=/home/kraynux/DEV/SERV/omega-serv/.venv/bin/python", unit)
        self.assertIn("ReadWritePaths=/home/kraynux/DEV/SERV/omega-serv/var", unit)
        self.assertNotIn("ProtectHome=true", unit)

    def test_umask_is_0007_not_0077(self):
        # Retour utilisateur 2026-09-10, second vrai bug trouve juste
        # apres le premier : meme avec var/ partage au groupe dedie
        # (grant_directory_access), un fichier cree avec UMask=0077
        # (rw proprietaire SEUL) reste illisible par l'utilisateur
        # interactif ajoute a ce groupe - 0007 conserve les droits du
        # groupe, seul "other" reste refuse.
        unit = generate_systemd_unit(_params())
        self.assertNotIn("UMask=0077", unit)
        self.assertIn("UMask=0007", unit)

    def test_read_write_paths_limited_to_var(self):
        unit = generate_systemd_unit(_params())
        self.assertIn("ReadWritePaths=/opt/omega-serv/var", unit)

    def test_dedicated_user_and_group_required(self):
        unit = generate_systemd_unit(_params(user="omega-serv", group="omega-serv"))
        self.assertIn("User=omega-serv", unit)
        self.assertIn("Group=omega-serv", unit)

    def test_execstart_points_to_real_python_and_config(self):
        unit = generate_systemd_unit(_params())
        self.assertIn("/opt/omega-serv/.venv/bin/python -m omega_serv --config /opt/omega-serv/config/omega-serve.json serve", unit)

    def test_no_hardcoded_personal_paths(self):
        # Aucun chemin fige en dur - tout vient des parametres (doc TLS/plan
        # §24.3 : "la definition ne doit pas dependre de chemins personnels").
        unit = generate_systemd_unit(_params(
            project_root=Path("/srv/other-location"),
            python_executable=Path("/srv/other-location/.venv/bin/python"),
            config_path=Path("/srv/other-location/config/omega-serve.json"),
        ))
        self.assertIn("/srv/other-location", unit)
        self.assertNotIn("/opt/omega-serv", unit)

    def test_stop_timeout_configurable_and_above_default(self):
        unit = generate_systemd_unit(_params(stop_timeout_seconds=20))
        self.assertIn("TimeoutStopSec=20", unit)


class TestFindConflictingUnit(unittest.TestCase):
    """Retour utilisateur 2026-09-10 : rien n'empechait d'installer une
    deuxieme unite (nom different) pointant vers le MEME repertoire
    projet - var/ (fichier PID), config et compte systeme dedie sont
    tous codes en dur par repertoire, jamais par nom de service."""

    _ROOT = Path("/home/kraynux/DEV/SERV/omega-serv")

    def test_detects_other_unit_on_same_directory(self):
        contents = {
            "omega-serv.service": f"[Service]\nWorkingDirectory={self._ROOT}\n",
            "omega-serv-2.service": f"[Service]\nWorkingDirectory={self._ROOT}\n",
        }
        conflict = find_conflicting_unit(contents, self._ROOT, "omega-serv-2")
        self.assertEqual(conflict, "omega-serv")

    def test_no_conflict_when_only_excluded_unit_present(self):
        contents = {"omega-serv.service": f"[Service]\nWorkingDirectory={self._ROOT}\n"}
        self.assertIsNone(find_conflicting_unit(contents, self._ROOT, "omega-serv"))

    def test_no_conflict_for_different_directory(self):
        contents = {"other-app.service": "[Service]\nWorkingDirectory=/opt/other-app\n"}
        self.assertIsNone(find_conflicting_unit(contents, self._ROOT, "omega-serv"))

    def test_no_conflict_when_no_units_present(self):
        self.assertIsNone(find_conflicting_unit({}, self._ROOT, "omega-serv"))

    def test_unrelated_unit_with_same_prefix_path_is_not_a_false_positive(self):
        # /home/kraynux/DEV/SERV/omega-serv-backup ne doit jamais matcher
        # /home/kraynux/DEV/SERV/omega-serv (comparaison de ligne exacte,
        # jamais un prefixe de chaine).
        contents = {"other.service": f"[Service]\nWorkingDirectory={self._ROOT}-backup\n"}
        self.assertIsNone(find_conflicting_unit(contents, self._ROOT, "omega-serv"))


class TestFindNameHijack(unittest.TestCase):
    """Sens inverse de TestFindConflictingUnit, meme retour utilisateur
    2026-09-10 : deux repertoires DIFFERENTS utilisant le meme nom de
    service (jamais renomme en pratique) ne sont detectes par aucun
    autre garde-fou - installer ici volerait silencieusement le nom."""

    _ROOT = Path("/home/kraynux/DEV/SERV/omega-serv")
    _OTHER_ROOT = Path("/home/kraynux/DEV/SERV2/omega-serv")

    def test_detects_name_used_by_another_directory(self):
        contents = {"omega-serv.service": f"[Service]\nWorkingDirectory={self._OTHER_ROOT}\n"}
        hijack = find_name_hijack(contents, self._ROOT, "omega-serv")
        self.assertEqual(hijack, self._OTHER_ROOT)

    def test_no_hijack_when_same_directory(self):
        contents = {"omega-serv.service": f"[Service]\nWorkingDirectory={self._ROOT}\n"}
        self.assertIsNone(find_name_hijack(contents, self._ROOT, "omega-serv"))

    def test_no_hijack_when_name_not_installed_yet(self):
        self.assertIsNone(find_name_hijack({}, self._ROOT, "omega-serv"))

    def test_no_hijack_for_a_different_name(self):
        contents = {"other-name.service": f"[Service]\nWorkingDirectory={self._OTHER_ROOT}\n"}
        self.assertIsNone(find_name_hijack(contents, self._ROOT, "omega-serv"))


class TestFindAccountInUse(unittest.TestCase):
    """OMEGA-SERV_PLAN-DETAILLE_MULTI_INSTANCE.md §8.1/§9 Phase E : le
    compte systeme dedie est IDENTIQUE pour toutes les instances -
    avant de le supprimer a la desinstallation d'une instance, verifier
    qu'aucune AUTRE unite installee ne le reference encore."""

    def test_detects_another_unit_still_using_the_account(self):
        contents = {
            "omega-serv-test.service": "[Service]\nUser=omega-serv\nWorkingDirectory=/tmp/test\n",
            "omega-serv-prod.service": "[Service]\nUser=omega-serv\nWorkingDirectory=/tmp/prod\n",
        }
        still_used = find_account_in_use(contents, "omega-serv", "omega-serv-test")
        self.assertEqual(still_used, "omega-serv-prod")

    def test_no_other_use_when_only_the_excluded_unit_references_it(self):
        contents = {"omega-serv-test.service": "[Service]\nUser=omega-serv\nWorkingDirectory=/tmp/test\n"}
        self.assertIsNone(find_account_in_use(contents, "omega-serv", "omega-serv-test"))

    def test_no_other_use_when_no_units_present(self):
        self.assertIsNone(find_account_in_use({}, "omega-serv", "omega-serv-test"))

    def test_unrelated_unit_with_a_different_account_is_not_a_false_positive(self):
        contents = {"other-app.service": "[Service]\nUser=other-app\nWorkingDirectory=/tmp/other\n"}
        self.assertIsNone(find_account_in_use(contents, "omega-serv", "omega-serv-test"))


if __name__ == "__main__":
    unittest.main()
