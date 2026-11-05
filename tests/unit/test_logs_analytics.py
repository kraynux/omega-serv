from datetime import datetime, timezone

from omega_serv.domain.logs.analytics import (
    compute_hourly_stats,
    compute_level_distribution,
    compute_stats,
    compute_top_ips,
    compute_traffic_stats,
)
from omega_serv.domain.logs.models import LogEntry, LogLevel, LogSource


def _entry(ip: str | None = "1.2.3.4", level: LogLevel = LogLevel.INFO, hour: int = 10, **overrides) -> LogEntry:
    defaults = {
        "timestamp": datetime(2026, 10, 10, hour, 0, 0, tzinfo=timezone.utc),
        "source": LogSource.ACCESS,
        "level": level,
        "ip": ip,
    }
    defaults.update(overrides)
    return LogEntry(**defaults)


class TestComputeTopIps:
    def test_counts_and_orders_by_descending_occurrence(self):
        entries = [_entry(ip="1.1.1.1"), _entry(ip="1.1.1.1"), _entry(ip="2.2.2.2")]
        top = compute_top_ips(entries)
        assert [t.ip for t in top] == ["1.1.1.1", "2.2.2.2"]
        assert top[0].count == 2

    def test_entries_without_ip_are_ignored(self):
        entries = [_entry(ip=None), _entry(ip="1.1.1.1")]
        top = compute_top_ips(entries)
        assert len(top) == 1

    def test_respects_n_limit(self):
        entries = [_entry(ip=f"10.0.0.{i}") for i in range(5)]
        assert len(compute_top_ips(entries, n=2)) == 2

    def test_http_errors_counted_per_ip(self):
        entries = [_entry(ip="1.1.1.1", http_status=500), _entry(ip="1.1.1.1", http_status=200)]
        top = compute_top_ips(entries)
        assert top[0].http_errors == 1


class TestComputeHourlyStats:
    def test_covers_all_24_hours(self):
        stats = compute_hourly_stats([_entry(hour=5)])
        assert len(stats) == 24
        assert stats[5].count == 1

    def test_error_count_tracked(self):
        stats = compute_hourly_stats([_entry(hour=3, level=LogLevel.ERROR)])
        assert stats[3].error_count == 1
        assert stats[3].error_rate() == 100.0


class TestComputeLevelDistribution:
    def test_counts_by_level(self):
        dist = compute_level_distribution([_entry(level=LogLevel.ERROR), _entry(level=LogLevel.ERROR), _entry()])
        assert dist["error"] == 2
        assert dist["info"] == 1


class TestComputeStats:
    def test_aggregates_everything(self):
        entries = [_entry(ip="1.1.1.1"), _entry(ip="2.2.2.2", level=LogLevel.ERROR)]
        stats = compute_stats(entries, log_path="/var/log/x.log")
        assert stats.log_path == "/var/log/x.log"
        assert stats.parsed_lines == 2
        assert stats.unique_ips == 2
        assert stats.error_rate() == 50.0

    def test_empty_entries_never_crashes(self):
        stats = compute_stats([])
        assert stats.parsed_lines == 0
        assert stats.error_rate() == 0.0
        assert stats.parse_rate() == 0.0


class TestTrafficStatsDashboardAdditions:
    """Repris du cadre FLUX d'Etat & Ressources dans le viewer Simple (2026-11-05)."""

    def test_refusals_top_ips_and_paths_without_query_string(self):
        entries = [
            _entry(ip="1.1.1.1", http_path="/a?x=1", http_status=200),
            _entry(ip="1.1.1.1", http_path="/a?x=2", http_status=200),
            _entry(ip="2.2.2.2", http_path="/wp-login.php", http_status=404),
            _entry(ip="3.3.3.3", http_path="/admin", http_status=403),
            _entry(ip="3.3.3.3", http_path="/a", http_status=429),
        ]
        stats = compute_traffic_stats(entries)
        assert (stats.status_403, stats.status_429) == (1, 1)
        assert stats.top_ips[0] in {("1.1.1.1", 2), ("3.3.3.3", 2)}
        assert stats.top_paths[0] == ("/a", 3)
        assert stats.top_not_found == [("/wp-login.php", 1)]

    def test_log_without_http_fields_has_no_path_tops(self):
        stats = compute_traffic_stats([_entry(), _entry(ip="9.9.9.9")])
        assert stats.top_paths == [] and stats.top_not_found == []
        assert len(stats.top_ips) == 2
