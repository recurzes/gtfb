"""Unit tests for domain sanitization utility."""

import unittest

from gtfb.config.sanitizer import clean_domain_input


class TestDomainSanitizer(unittest.TestCase):
    """Test suite for clean_domain_input."""

    def test_clean_standard_domain(self):
        self.assertEqual(clean_domain_input("reddit.com"), "reddit.com")
        self.assertEqual(clean_domain_input("youtube.com"), "youtube.com")
        self.assertEqual(clean_domain_input("x.com"), "x.com")

    def test_clean_domain_with_schemes(self):
        self.assertEqual(clean_domain_input("https://reddit.com"), "reddit.com")
        self.assertEqual(clean_domain_input("http://youtube.com"), "youtube.com")
        self.assertEqual(clean_domain_input("HTTPS://X.COM"), "x.com")

    def test_clean_domain_with_www_prefix(self):
        self.assertEqual(clean_domain_input("www.reddit.com"), "reddit.com")
        self.assertEqual(clean_domain_input("https://www.youtube.com"), "youtube.com")
        self.assertEqual(clean_domain_input("http://www.instagram.com/"), "instagram.com")

    def test_clean_domain_with_paths_and_queries(self):
        self.assertEqual(
            clean_domain_input("https://twitter.com/home"),
            "twitter.com",
        )
        self.assertEqual(
            clean_domain_input("https://www.youtube.com/watch?v=dQw4w9WgXcQ"),
            "youtube.com",
        )
        self.assertEqual(
            clean_domain_input("https://reddit.com/r/all?sort=top#header"),
            "reddit.com",
        )

    def test_clean_domain_with_whitespace_and_casing(self):
        self.assertEqual(
            clean_domain_input("   HTTPS://WWW.TIKTOK.COM/feed   "),
            "tiktok.com",
        )
        self.assertEqual(
            clean_domain_input("  REDDIT.COM  "),
            "reddit.com",
        )

    def test_clean_subdomain_preservation(self):
        self.assertEqual(clean_domain_input("news.ycombinator.com"), "news.ycombinator.com")
        self.assertEqual(
            clean_domain_input("https://api.github.com/users"),
            "api.github.com",
        )
        self.assertEqual(
            clean_domain_input("https://www.blog.example.com"),
            "blog.example.com",
        )

    def test_clean_empty_and_invalid_inputs(self):
        self.assertEqual(clean_domain_input(""), "")
        self.assertEqual(clean_domain_input("   "), "")
        self.assertEqual(clean_domain_input(None), "")  # type: ignore[arg-type]

    def test_clean_domain_with_port(self):
        self.assertEqual(clean_domain_input("http://localhost:8080/dashboard"), "localhost")
        self.assertEqual(clean_domain_input("example.com:8000"), "example.com")


    def test_clean_rejects_invalid_hostnames(self):
        for raw in ("foo bar", "a,b", "exa_mple.com", "-bad.com", "bad-.com", "a..b"):
            with self.subTest(raw=raw):
                self.assertEqual(clean_domain_input(raw), "")

    def test_clean_converts_international_domain_to_punycode(self):
        self.assertEqual(clean_domain_input("https://münchen.de/path"), "xn--mnchen-3ya.de")


if __name__ == "__main__":
    unittest.main()
