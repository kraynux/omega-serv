from omega_serv.domain.logs.viewer_type import ViewerType, allowed_viewers


class TestAllowedViewers:
    def test_single_log_allows_all_three(self):
        assert allowed_viewers(1) == (ViewerType.SIMPLE, ViewerType.CLASSIC, ViewerType.LNAV)

    def test_zero_logs_allows_all_three(self):
        assert allowed_viewers(0) == (ViewerType.SIMPLE, ViewerType.CLASSIC, ViewerType.LNAV)

    def test_multiple_logs_allows_only_lnav(self):
        assert allowed_viewers(2) == (ViewerType.LNAV,)
        assert allowed_viewers(5) == (ViewerType.LNAV,)
