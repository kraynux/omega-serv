"""ETag / 304 / Range (OMEGA-SERV_ETUDE_PERFORMANCE.md, priorite 2)."""
import unittest

from omega_serv.domain.http.conditional import (
    ByteRange,
    http_date,
    is_not_modified,
    make_etag,
    resolve_range,
)

_MTIME = 1_761_480_000.7
_SIZE = 1000
_ETAG = make_etag(_SIZE, _MTIME)


class TestValidators(unittest.TestCase):
    def test_etag_depends_on_size_and_second_of_modification(self):
        self.assertEqual(_ETAG, f'"{int(_MTIME):x}-{_SIZE:x}"')
        self.assertNotEqual(_ETAG, make_etag(_SIZE + 1, _MTIME))
        self.assertNotEqual(_ETAG, make_etag(_SIZE, _MTIME + 1))

    def test_http_date_is_rfc_gmt(self):
        self.assertTrue(http_date(_MTIME).endswith(" GMT"))


class TestNotModified(unittest.TestCase):
    def test_if_none_match(self):
        self.assertTrue(is_not_modified(_ETAG, None, _ETAG, _MTIME))
        self.assertTrue(is_not_modified(f'"autre", W/{_ETAG}', None, _ETAG, _MTIME))
        self.assertTrue(is_not_modified("*", None, _ETAG, _MTIME))
        self.assertFalse(is_not_modified('"autre"', None, _ETAG, _MTIME))

    def test_if_none_match_takes_priority_over_if_modified_since(self):
        self.assertFalse(is_not_modified('"autre"', http_date(_MTIME + 3600), _ETAG, _MTIME))

    def test_if_modified_since(self):
        self.assertTrue(is_not_modified(None, http_date(_MTIME), _ETAG, _MTIME))
        self.assertFalse(is_not_modified(None, http_date(_MTIME - 10), _ETAG, _MTIME))
        self.assertFalse(is_not_modified(None, "pas une date", _ETAG, _MTIME))
        self.assertFalse(is_not_modified(None, None, _ETAG, _MTIME))


class TestRange(unittest.TestCase):
    def _range(self, header, if_range=None, size=_SIZE):
        return resolve_range(header, if_range, size, _ETAG, _MTIME)

    def test_single_ranges(self):
        self.assertEqual(self._range("bytes=0-99").byte_range, ByteRange(0, 99))
        self.assertEqual(self._range("bytes=900-").byte_range, ByteRange(900, 999))
        self.assertEqual(self._range("bytes=-100").byte_range, ByteRange(900, 999))
        self.assertEqual(self._range("bytes=950-5000").byte_range, ByteRange(950, 999))
        self.assertEqual(self._range("bytes=-5000").byte_range, ByteRange(0, 999))

    def test_unsatisfiable(self):
        self.assertTrue(self._range("bytes=1000-").unsatisfiable)
        self.assertTrue(self._range("bytes=-0").unsatisfiable)

    def test_ignored_ranges_give_the_full_file(self):
        for header in (None, "bytes=0-1,5-6", "items=0-1", "bytes=abc", "bytes=5-2", "bytes=-", "bytes"):
            decision = self._range(header)
            self.assertIsNone(decision.byte_range, header)
            self.assertFalse(decision.unsatisfiable, header)

    def test_if_range(self):
        self.assertIsNotNone(self._range("bytes=0-9", if_range=_ETAG).byte_range)
        self.assertIsNotNone(self._range("bytes=0-9", if_range=http_date(_MTIME)).byte_range)
        self.assertIsNone(self._range("bytes=0-9", if_range='"perime"').byte_range)
        self.assertIsNone(self._range("bytes=0-9", if_range=f"W/{_ETAG}").byte_range)  # jamais un ETag faible


if __name__ == "__main__":
    unittest.main()
