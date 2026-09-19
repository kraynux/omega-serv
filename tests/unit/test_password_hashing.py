import hashlib
import unittest

from omega_serv.domain.security.auth.password_hashing import hash_password, verify_password


class TestHashPassword(unittest.TestCase):
    def test_encoded_hash_has_expected_shape(self):
        encoded = hash_password("hunter2")
        parts = encoded.split("$")
        self.assertEqual(len(parts), 6)
        self.assertEqual(parts[0], "scrypt")

    def test_same_password_different_salts_produce_different_hashes(self):
        h1 = hash_password("hunter2")
        h2 = hash_password("hunter2")
        self.assertNotEqual(h1, h2)

    def test_same_password_and_salt_produce_same_hash(self):
        salt = b"\x01" * 16
        h1 = hash_password("hunter2", salt=salt)
        h2 = hash_password("hunter2", salt=salt)
        self.assertEqual(h1, h2)

    def test_uses_owasp_recommended_parameters_for_the_configured_memory_budget(self):
        encoded = hash_password("hunter2")
        _algo, n_str, _r_str, p_str, _salt_hex, _hash_hex = encoded.split("$")
        self.assertEqual(int(n_str), 16384)
        self.assertEqual(int(p_str), 5)


class TestVerifyPassword(unittest.TestCase):
    def test_correct_password_verifies(self):
        encoded = hash_password("hunter2")
        self.assertTrue(verify_password("hunter2", encoded))

    def test_incorrect_password_rejected(self):
        encoded = hash_password("hunter2")
        self.assertFalse(verify_password("wrong-password", encoded))

    def test_malformed_hash_never_raises(self):
        self.assertFalse(verify_password("hunter2", "not-a-valid-hash"))

    def test_empty_hash_never_raises(self):
        self.assertFalse(verify_password("hunter2", ""))

    def test_wrong_algorithm_prefix_rejected(self):
        encoded = hash_password("hunter2")
        tampered = "bcrypt" + encoded[len("scrypt"):]
        self.assertFalse(verify_password("hunter2", tampered))

    def test_non_hex_fields_never_raise(self):
        self.assertFalse(verify_password("hunter2", "scrypt$16384$8$1$zz$zz"))

    def test_older_hash_with_previous_p_parameter_still_verifies(self):
        salt = b"\x02" * 16
        legacy_hash = hashlib.scrypt(b"hunter2", salt=salt, n=16384, r=8, p=1, dklen=32)
        legacy_encoded = f"scrypt$16384$8$1${salt.hex()}${legacy_hash.hex()}"
        self.assertTrue(verify_password("hunter2", legacy_encoded))


if __name__ == "__main__":
    unittest.main()
