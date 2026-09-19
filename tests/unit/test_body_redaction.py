"""Retour utilisateur (audit securite) : redact_form_urlencoded_body est
le correctif du vrai bug trouve - le corps de requete capture (Active
Defense, alertes WAF) etait journalise verbatim, exposant en clair tout
mot de passe/token soumis via un formulaire, alors meme que les en-tetes
beneficiaient deja d'une redaction equivalente."""
import unittest

from omega_serv.domain.logging.body_redaction import redact_form_urlencoded_body


class TestRedactFormUrlencodedBody(unittest.TestCase):
    def test_redacts_a_matching_field_case_insensitively(self):
        result = redact_form_urlencoded_body("username=admin&Password=Secret123", ("password",))
        self.assertNotIn("Secret123", result)
        self.assertIn("username=admin", result)

    def test_leaves_non_matching_fields_untouched(self):
        result = redact_form_urlencoded_body("a=1&b=2", ("password",))
        self.assertIn("a=1", result)
        self.assertIn("b=2", result)

    def test_empty_body_returns_unchanged(self):
        self.assertEqual(redact_form_urlencoded_body("", ("password",)), "")

    def test_non_form_text_is_returned_unchanged(self):
        text = '{"password": "still-here"}'
        self.assertEqual(redact_form_urlencoded_body(text, ("password",)), text)

    def test_default_field_list_covers_common_secret_names(self):
        result = redact_form_urlencoded_body("user=bob&token=abc123&api_key=xyz")
        self.assertNotIn("abc123", result)
        self.assertNotIn("xyz", result)
        self.assertIn("user=bob", result)

    def test_multiple_sensitive_fields_all_redacted(self):
        result = redact_form_urlencoded_body("password=one&password_confirm=two", ("password", "password_confirm"))
        self.assertNotIn("one", result)
        self.assertNotIn("two", result)


if __name__ == "__main__":
    unittest.main()
