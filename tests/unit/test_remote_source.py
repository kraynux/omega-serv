from pathlib import Path

from omega_serv.domain.logs.remote_source import (
    RemoteLogSource,
    build_scp_command,
    safe_cache_filename,
)


class TestBuildScpCommand:
    def test_minimal_source(self):
        source = RemoteLogSource(label="x", host="backend1", remote_path="/var/log/access.log")
        command = build_scp_command(source, Path("/tmp/dest.log"))
        assert command == [
            "scp", "-o", "ConnectTimeout=10", "backend1:/var/log/access.log", "/tmp/dest.log",
        ]

    def test_with_user_port_and_identity_file(self):
        source = RemoteLogSource(
            label="x", host="backend1", remote_path="/var/log/access.log",
            user="admin", port=2222, identity_file="/home/me/.ssh/id_ed25519",
        )
        command = build_scp_command(source, Path("/tmp/dest.log"))
        assert command == [
            "scp", "-P", "2222", "-i", "/home/me/.ssh/id_ed25519",
            "-o", "ConnectTimeout=10", "admin@backend1:/var/log/access.log", "/tmp/dest.log",
        ]

    def test_result_is_a_list_never_a_shell_string(self):
        """Propriete de securite : l'argv reste une LISTE d'elements
        distincts - aucune concatenation en une seule chaine shell, donc
        aucune injection de commande possible via des caracteres
        speciaux dans host/remote_path."""
        source = RemoteLogSource(
            label="x", host="backend1; rm -rf /", remote_path="/var/log/access.log && echo pwned",
        )
        command = build_scp_command(source, Path("/tmp/dest.log"))
        assert isinstance(command, list)
        assert all(isinstance(part, str) for part in command)
        # Le hote et le chemin dangereux restent chacun un SEUL element
        # de la liste - jamais eclates/interpretes par un shell.
        assert "backend1; rm -rf /:/var/log/access.log && echo pwned" in command

    def test_user_at_host_format(self):
        source = RemoteLogSource(label="x", host="backend1", remote_path="/x", user="admin")
        command = build_scp_command(source, Path("/tmp/dest.log"))
        assert "admin@backend1:/x" in command


class TestSafeCacheFilename:
    def test_slugifies_label(self):
        name = safe_cache_filename("Backend Web 1")
        assert name.startswith("backend-web-1-")
        assert name.endswith(".log")

    def test_different_labels_that_slugify_identically_do_not_collide(self):
        a = safe_cache_filename("Backend A")
        b = safe_cache_filename("Backend_A")
        assert a != b

    def test_same_label_is_deterministic(self):
        assert safe_cache_filename("Backend A") == safe_cache_filename("Backend A")

    def test_never_contains_path_separators(self):
        name = safe_cache_filename("../../etc/passwd")
        assert "/" not in name
        assert ".." not in name

    def test_empty_label_falls_back_to_a_safe_default(self):
        name = safe_cache_filename("   ")
        assert name.startswith("source-")
