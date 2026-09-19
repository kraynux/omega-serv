import unittest

from omega_serv.domain.http.fastcgi_protocol import (
    FCGI_BEGIN_REQUEST,
    FCGI_PARAMS,
    FCGI_REQUEST_COMPLETE,
    FCGI_RESPONDER,
    FastCgiProtocolError,
    decode_end_request_body,
    decode_record_header,
    encode_begin_request,
    encode_name_value_pair,
    encode_params,
    encode_record,
    parse_cgi_response,
)


class TestEncodeRecord(unittest.TestCase):
    def test_header_shape(self):
        raw = encode_record(FCGI_PARAMS, 1, b"hello")
        self.assertEqual(len(raw), 8 + 5)
        header = decode_record_header(raw[:8])
        self.assertEqual(header.type, FCGI_PARAMS)
        self.assertEqual(header.request_id, 1)
        self.assertEqual(header.content_length, 5)
        self.assertEqual(raw[8:], b"hello")

    def test_empty_content_produces_empty_record(self):
        raw = encode_record(FCGI_PARAMS, 1, b"")
        self.assertEqual(len(raw), 8)
        header = decode_record_header(raw[:8])
        self.assertEqual(header.content_length, 0)

    def test_oversized_content_is_split_across_records(self):
        content = b"x" * 70000  # > 65535, la limite d'un champ 16 bits
        raw = encode_record(FCGI_PARAMS, 1, content)
        first_header = decode_record_header(raw[:8])
        self.assertEqual(first_header.content_length, 65535)
        remaining = raw[8 + 65535:]
        second_header = decode_record_header(remaining[:8])
        self.assertEqual(second_header.content_length, len(content) - 65535)


class TestDecodeRecordHeader(unittest.TestCase):
    def test_wrong_length_raises(self):
        with self.assertRaises(FastCgiProtocolError):
            decode_record_header(b"short")

    def test_wrong_version_raises(self):
        header = bytearray(encode_record(FCGI_PARAMS, 1, b"")[:8])
        header[0] = 99
        with self.assertRaises(FastCgiProtocolError):
            decode_record_header(bytes(header))


class TestEncodeNameValuePair(unittest.TestCase):
    def test_short_name_and_value_use_one_byte_lengths(self):
        encoded = encode_name_value_pair(b"KEY", b"value")
        self.assertEqual(encoded[0], 3)
        self.assertEqual(encoded[1], 5)
        self.assertEqual(encoded[2:], b"KEYvalue")

    def test_long_value_uses_four_byte_length(self):
        long_value = b"x" * 200
        encoded = encode_name_value_pair(b"KEY", long_value)
        self.assertEqual(encoded[0], 3)  # nom court : 1 octet
        self.assertTrue(encoded[1] & 0x80)


class TestEncodeParams(unittest.TestCase):
    def test_encodes_multiple_pairs(self):
        encoded = encode_params({"REQUEST_METHOD": "GET", "QUERY_STRING": ""})
        self.assertIn(b"REQUEST_METHOD", encoded)
        self.assertIn(b"GET", encoded)


class TestEncodeBeginRequest(unittest.TestCase):
    def test_encodes_responder_role(self):
        raw = encode_begin_request(1, role=FCGI_RESPONDER, keep_conn=False)
        header = decode_record_header(raw[:8])
        self.assertEqual(header.type, FCGI_BEGIN_REQUEST)
        self.assertEqual(header.content_length, 8)


class TestDecodeEndRequestBody(unittest.TestCase):
    def test_decodes_complete_status(self):
        import struct
        body = struct.pack("!IB3x", 0, FCGI_REQUEST_COMPLETE)
        result = decode_end_request_body(body)
        self.assertEqual(result.app_status, 0)
        self.assertEqual(result.protocol_status, FCGI_REQUEST_COMPLETE)

    def test_too_short_raises(self):
        with self.assertRaises(FastCgiProtocolError):
            decode_end_request_body(b"short")


class TestParseCgiResponse(unittest.TestCase):
    def test_default_status_is_200(self):
        response = parse_cgi_response(b"Content-Type: text/html\r\n\r\n<html></html>")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.body, b"<html></html>")
        self.assertIn(("Content-Type", "text/html"), response.headers)

    def test_status_header_sets_code(self):
        response = parse_cgi_response(b"Status: 404 Not Found\r\nContent-Type: text/plain\r\n\r\nnope")
        self.assertEqual(response.status_code, 404)
        self.assertNotIn(("Status", "404 Not Found"), response.headers)

    def test_no_header_separator_treats_all_as_body(self):
        response = parse_cgi_response(b"just raw output, no headers")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.body, b"just raw output, no headers")
        self.assertEqual(response.headers, ())

    def test_malformed_status_header_falls_back_to_200(self):
        response = parse_cgi_response(b"Status: not-a-number\r\n\r\nbody")
        self.assertEqual(response.status_code, 200)

    def test_multiple_headers_all_preserved(self):
        response = parse_cgi_response(b"Content-Type: text/html\r\nSet-Cookie: a=b\r\n\r\nbody")
        self.assertEqual(len(response.headers), 2)

    def test_lf_only_separator_also_works(self):
        response = parse_cgi_response(b"Content-Type: text/html\n\nbody")
        self.assertEqual(response.body, b"body")
        self.assertIn(("Content-Type", "text/html"), response.headers)


if __name__ == "__main__":
    unittest.main()
