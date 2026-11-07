"""Pool de processus des calculs de logs amorce AVANT toute interface de test, comme __main__.py le fait
avant `App.run()` (2026-11-07) : lance pendant `run_test`, le forkserver echoue (« bad value(s) in
fds_to_keep », descripteurs standard remplaces par Textual)."""
from __future__ import annotations

from collections.abc import Iterator

import pytest

from omega_serv.application.logs.process_pool import shutdown_stats_pool, warm_up_stats_pool


@pytest.fixture(scope="session", autouse=True)
def _stats_pool() -> Iterator[None]:
    warm_up_stats_pool()
    yield
    shutdown_stats_pool()
