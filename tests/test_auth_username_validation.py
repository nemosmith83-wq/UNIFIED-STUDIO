import unittest

from backend.auth import re_username


class UsernameValidationTests(unittest.TestCase):
    def test_accepts_email_style_username(self):
        self.assertTrue(re_username("fadel@example.com"))

    def test_rejects_email_without_valid_domain_suffix(self):
        self.assertFalse(re_username("fadel@example"))

    def test_keeps_regular_username_rules(self):
        self.assertTrue(re_username("fadel_23"))
        self.assertFalse(re_username("fa"))


if __name__ == "__main__":
    unittest.main()
