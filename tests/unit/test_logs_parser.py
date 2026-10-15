from datetime import timezone

from omega_serv.domain.logs.models import LogLevel, LogSource
from omega_serv.domain.logs.parser import (
    detect_log_source,
    extract_http_fields,
    extract_ip,
    extract_log_level,
    extract_port,
    extract_service,
    extract_timestamp,
    extract_user,
    parse_log_line,
    parse_log_lines,
)


class TestExtractIp:
    def test_finds_ipv4(self):
        assert extract_ip("203.0.113.5 - - GET /") == "203.0.113.5"

    def test_none_when_absent(self):
        assert extract_ip("no ip here") is None


class TestExtractTimestamp:
    def test_iso_format(self):
        ts = extract_timestamp("2026-10-10T10:00:00 something happened")
        assert ts is not None
        assert (ts.year, ts.month, ts.day, ts.hour) == (2026, 10, 10, 10)
        assert ts.tzinfo is timezone.utc

    def test_apache_combined_format(self):
        ts = extract_timestamp('1.2.3.4 - - [10/Oct/2026:10:00:00 +0200] "GET / HTTP/1.1" 200 12')
        assert ts is not None
        assert (ts.year, ts.month, ts.day) == (2026, 10, 10)
        assert ts.tzinfo is timezone.utc

    def test_syslog_format(self):
        ts = extract_timestamp("Oct 10 10:00:00 host sshd[123]: Accepted password for bob")
        assert ts is not None
        assert (ts.month, ts.day, ts.hour) == (10, 10, 10)

    def test_none_when_no_timestamp(self):
        assert extract_timestamp("just a plain line") is None


class TestExtractLogLevel:
    def test_defaults_to_info(self):
        assert extract_log_level("nothing special here") == LogLevel.INFO

    def test_finds_error(self):
        assert extract_log_level("an ERROR occurred") == LogLevel.ERROR

    def test_finds_critical_synonym(self):
        assert extract_log_level("fatal condition") == LogLevel.CRITICAL


class TestExtractServiceUserPort:
    def test_extract_service(self):
        # Sans le prefixe "jour-du-mois espace heure" (deja gere a part par
        # extract_timestamp) - voir commentaire dans parse_log_line, les deux
        # extractions sont independantes et n'ont pas besoin du meme prefixe.
        assert extract_service("host sshd[123]: Accepted password") == "sshd"

    def test_extract_user_accepted(self):
        assert extract_user("Accepted password for bob from 1.2.3.4") == "bob"

    def test_extract_port(self):
        assert extract_port("connection from 1.2.3.4 port 5555") == 5555

    def test_extract_port_out_of_range_ignored(self):
        assert extract_port("port 999999") is None


class TestExtractHttpFields:
    def test_combined_line(self):
        method, path, status, _latency = extract_http_fields(
            '1.2.3.4 - - [10/Oct/2026:10:00:00 +0200] "GET /index.html HTTP/1.1" 200 1234'
        )
        assert method == "GET"
        assert path == "/index.html"
        assert status == 200

    def test_non_access_line_returns_all_none(self):
        assert extract_http_fields("Oct 10 10:00:00 host sshd[1]: Accepted password") == (None, None, None, None)

    def test_latency_tail_token(self):
        _method, _path, _status, latency = extract_http_fields(
            '1.2.3.4 - - [10/Oct/2026:10:00:00 +0200] "GET / HTTP/1.1" 200 12 45'
        )
        assert latency == 45


class TestDetectLogSource:
    def test_auth(self):
        assert detect_log_source("sshd: Accepted password for bob") == LogSource.AUTH

    def test_fail2ban(self):
        assert detect_log_source("fail2ban.actions: Ban 1.2.3.4") == LogSource.FAIL2BAN

    def test_access(self):
        assert detect_log_source('1.2.3.4 - - "GET / HTTP/1.1" 200 12') == LogSource.ACCESS

    def test_kern(self):
        assert detect_log_source("kernel: iptables denied") == LogSource.KERN

    def test_default_syslog(self):
        assert detect_log_source("some random daemon message") == LogSource.SYSLOG


class TestParseLogLine:
    def test_empty_line_returns_none(self):
        assert parse_log_line("   ") is None

    def test_combined_access_line(self):
        entry = parse_log_line(
            '203.0.113.5 - - [10/Oct/2026:10:00:00 +0200] "GET /api HTTP/1.1" 200 42', line_number=3,
        )
        assert entry is not None
        assert entry.ip == "203.0.113.5"
        assert entry.http_status == 200
        assert entry.source == LogSource.ACCESS
        assert entry.line_number == 3

    def test_http_5xx_promotes_level_to_error(self):
        entry = parse_log_line('1.2.3.4 - - [10/Oct/2026:10:00:00 +0200] "GET / HTTP/1.1" 500 1')
        assert entry is not None
        assert entry.level == LogLevel.ERROR

    def test_http_4xx_promotes_level_to_warning(self):
        entry = parse_log_line('1.2.3.4 - - [10/Oct/2026:10:00:00 +0200] "GET / HTTP/1.1" 404 1')
        assert entry is not None
        assert entry.level == LogLevel.WARNING

    def test_explicit_level_not_overridden_by_http_status(self):
        entry = parse_log_line(
            'CRITICAL 1.2.3.4 - - [10/Oct/2026:10:00:00 +0200] "GET / HTTP/1.1" 404 1',
        )
        assert entry is not None
        assert entry.level == LogLevel.CRITICAL


class TestParseLogLines:
    def test_skips_blank_lines(self):
        entries = parse_log_lines(["", "sshd: Accepted password for bob", "   "])
        assert len(entries) == 1
