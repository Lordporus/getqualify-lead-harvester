import os
import sys
import unittest
from unittest.mock import patch, MagicMock
import requests

# Ensure repo root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scripts.enrichment import (
    clean_email,
    discover_contact_subpage_urls,
    extract_emails_from_html,
    extract_owner_name_from_html,
    enrich_business_contact,
)


class TestEmailAndContactEnrichment(unittest.TestCase):
    """Test suite for website email and owner enrichment engine."""

    # --- Tests for clean_email and obfuscation ---

    def test_clean_email_valid(self):
        """Test valid standard emails and normalizations."""
        self.assertEqual(clean_email("contact@austindental.com"), "contact@austindental.com")
        self.assertEqual(clean_email("INFO@AustinDental.COM"), "info@austindental.com")
        self.assertEqual(clean_email("mailto:office@austindental.com"), "office@austindental.com")
        self.assertEqual(
            clean_email("mailto:appointments@austindental.com?subject=Booking"),
            "appointments@austindental.com",
        )
        self.assertEqual(clean_email("  support@austindental.com  "), "support@austindental.com")

    def test_clean_email_obfuscated(self):
        """Test unmasking obfuscated email syntax."""
        self.assertEqual(clean_email("info [at] austindental [dot] com"), "info@austindental.com")
        self.assertEqual(clean_email("contact (at) austindental.com"), "contact@austindental.com")
        self.assertEqual(clean_email("office [at] austindental.com"), "office@austindental.com")
        self.assertEqual(clean_email("help at austindental dot com"), "help@austindental.com")

    def test_discover_contact_subpage_urls(self):
        """Test finding up to 5 relevant subpages from homepage HTML."""
        html = """
        <html>
            <body>
                <a href="/about-us">About Our Practice</a>
                <a href="/our-team">Meet the Doctors</a>
                <a href="https://www.austindental.com/contact-us">Contact Us</a>
                <a href="/pricing">Pricing</a>
                <a href="https://facebook.com/austindental">Facebook</a>
                <a href="/staff">Our Dental Staff</a>
            </body>
        </html>
        """
        urls = discover_contact_subpage_urls(html, "https://www.austindental.com", max_subpages=5)
        self.assertLessEqual(len(urls), 5)
        self.assertIn("https://www.austindental.com/contact-us", urls)
        self.assertIn("https://www.austindental.com/about-us", urls)
        self.assertIn("https://www.austindental.com/our-team", urls)
        self.assertNotIn("https://facebook.com/austindental", urls)

    def test_extract_obfuscated_emails_from_html(self):
        """Test extracting obfuscated emails from HTML body."""
        html = """
        <html>
            <body>
                <p>Send appointment requests to: booking [at] austindental [dot] com</p>
                <p>Or reach the doctor directly at drsmith (at) austindental.com</p>
            </body>
        </html>
        """
        emails = extract_emails_from_html(html, "austindental.com")
        self.assertIn("booking@austindental.com", emails)
        self.assertIn("drsmith@austindental.com", emails)

    def test_clean_email_rejects_image_assets(self):
        """Test rejection of image file patterns resembling emails."""
        image_patterns = [
            "logo@2x.png",
            "banner@header.jpg",
            "hero@photo.jpeg",
            "icon@spinner.gif",
            "vector@badge.svg",
            "thumbnail@preview.webp",
        ]
        for pattern in image_patterns:
            self.assertIsNone(clean_email(pattern), f"Failed to reject image pattern: {pattern}")

    def test_clean_email_rejects_junk_and_tracker_domains(self):
        """Test rejection of CMS placeholders and tracker domains."""
        junk_emails = [
            "user@wixpress.com",
            "errors@sentry.io",
            "sample@example.com",
            "test@domain.com",
            "admin@email.com",
            "help@wix.com",
            "info@wordpress.org",
            "dns@cloudflare.com",
            "subdomain@site.sentry.io",
        ]
        for email in junk_emails:
            self.assertIsNone(clean_email(email), f"Failed to reject junk email: {email}")

    def test_clean_email_invalid_inputs(self):
        """Test invalid, malformed, or empty inputs."""
        self.assertIsNone(clean_email(""))
        self.assertIsNone(clean_email(None))
        self.assertIsNone(clean_email("not-an-email"))
        self.assertIsNone(clean_email("@nodomain.com"))
        self.assertIsNone(clean_email("user@localhost"))
        self.assertIsNone(clean_email("user@.com"))

    # --- Tests for extract_emails_from_html ---

    def test_extract_emails_from_html_mailto(self):
        """Test extracting email from mailto links."""
        html = """
        <html>
            <body>
                <header>
                    <a href="mailto:office@austindental.com">Email Us</a>
                </header>
            </body>
        </html>
        """
        emails = extract_emails_from_html(html, "austindental.com")
        self.assertIn("office@austindental.com", emails)

    def test_extract_emails_from_html_body_text(self):
        """Test extracting email from raw body text."""
        html = """
        <html>
            <body>
                <p>For inquiries, please write to info@austindental.com or call (512) 555-0100.</p>
            </body>
        </html>
        """
        emails = extract_emails_from_html(html, "austindental.com")
        self.assertIn("info@austindental.com", emails)

    def test_extract_emails_domain_priority_and_deduplication(self):
        """Test that target domain and operational emails are prioritized and deduplicated."""
        html = """
        <html>
            <body>
                <a href="mailto:support@gmail.com">Gmail Support</a>
                <a href="mailto:contact@austindental.com">Contact Us</a>
                <p>Direct doctor email: drsmith@austindental.com</p>
                <p>Duplicate: contact@austindental.com</p>
                <img src="logo@2x.png" />
                <a href="mailto:alert@sentry.io">Tracker</a>
            </body>
        </html>
        """
        emails = extract_emails_from_html(html, "austindental.com")
        # Target domain operational email should be first
        self.assertGreater(len(emails), 0)
        self.assertEqual(emails[0], "contact@austindental.com")
        self.assertIn("drsmith@austindental.com", emails)
        self.assertIn("support@gmail.com", emails)
        # Sentry and logo image should be filtered out
        self.assertNotIn("logo@2x.png", emails)
        self.assertNotIn("alert@sentry.io", emails)
        # Deduplication check
        self.assertEqual(len(emails), len(set(emails)))

    # --- Tests for extract_owner_name_from_html ---

    def test_extract_owner_name_doctor(self):
        """Test extracting medical/dental doctor names."""
        html1 = """
        <html>
            <body>
                <h1>Welcome to Austin Smile Center</h1>
                <p>Meet Dr. Sarah Miller, our lead cosmetic dentist with 15 years experience.</p>
            </body>
        </html>
        """
        name1 = extract_owner_name_from_html(html1)
        self.assertEqual(name1, "Dr. Sarah Miller")

        html2 = """
        <div>
            <h2>Doctor Robert Chen, DDS</h2>
            <p>Providing exceptional periodontal care.</p>
        </div>
        """
        name2 = extract_owner_name_from_html(html2)
        self.assertIn("Robert Chen", name2)

    def test_extract_owner_name_owner_founder(self):
        """Test extracting business owner, founder, or practice manager."""
        html1 = """
        <div class="team-card">
            <h3>Michael Vance</h3>
            <span class="role">Owner & Master Plumber</span>
        </div>
        """
        name1 = extract_owner_name_from_html(html1)
        self.assertEqual(name1, "Michael Vance")

        html2 = """
        <div>
            <p>Founded by David Martinez in 2008 to serve Travis County homeowners.</p>
        </div>
        """
        name2 = extract_owner_name_from_html(html2)
        self.assertEqual(name2, "David Martinez")

        html3 = """
        <div>
            <p>Practice Manager: Emily Watson</p>
        </div>
        """
        name3 = extract_owner_name_from_html(html3)
        self.assertEqual(name3, "Emily Watson")

    def test_extract_owner_name_not_found(self):
        """Test returning N/A when no owner or practitioner name is present."""
        html = """
        <html>
            <body>
                <p>We provide full service 24/7 heating and air conditioning repair.</p>
            </body>
        </html>
        """
        self.assertEqual(extract_owner_name_from_html(html), "N/A")

    # --- Tests for enrich_business_contact ---

    @patch("scripts.enrichment.requests.Session")
    def test_enrich_business_contact_success(self, mock_session_cls):
        """Test successful enrichment extracting email, owner, and after-hours notice."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session

        homepage_html = """
        <html>
            <head><title>Austin Dental Studio</title></head>
            <body>
                <h1>Meet Dr. Sarah Miller</h1>
                <p>Email: <a href="mailto:contact@austindental.com">contact@austindental.com</a></p>
                <div class="banner">
                    <p>We offer 24/7 emergency service and after hours call triage for dental emergencies.</p>
                </div>
            </body>
        </html>
        """

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = homepage_html
        mock_session.get.return_value = mock_resp

        result = enrich_business_contact("https://www.austindental.com", timeout=6)

        self.assertIsInstance(result, dict)
        self.assertEqual(result["email"], "contact@austindental.com")
        self.assertEqual(result["owner_name"], "Dr. Sarah Miller")
        self.assertTrue(result["has_after_hours_notice"])

    @patch("scripts.enrichment.requests.Session")
    def test_enrich_business_contact_multipage_fallback(self, mock_session_cls):
        """Test multi-page crawling where email is found on /contact."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session

        homepage_html = """
        <html><body><h1>Welcome</h1><a href="/contact">Contact</a></body></html>
        """
        contact_html = """
        <html><body><h1>Contact Us</h1><p>Email info@austindental.com</p></body></html>
        """

        def mock_get(url, **kwargs):
            resp = MagicMock()
            resp.status_code = 200
            if "contact" in url:
                resp.text = contact_html
            else:
                resp.text = homepage_html
            return resp

        mock_session.get.side_effect = mock_get

        result = enrich_business_contact("https://www.austindental.com", timeout=6)
        self.assertEqual(result["email"], "info@austindental.com")
        self.assertEqual(result["owner_name"], "N/A")
        self.assertFalse(result["has_after_hours_notice"])

    @patch("scripts.enrichment.requests.Session")
    def test_enrich_business_contact_multi_subpage_parallel(self, mock_session_cls):
        """Test aggressive 5-subpage discovery where email is on /our-team and owner is on /about-us."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session

        homepage_html = """
        <html>
            <body>
                <h1>Welcome to Premier Dental</h1>
                <a href="/about-us">About</a>
                <a href="/our-team">Our Doctors</a>
            </body>
        </html>
        """
        about_html = """
        <html><body><p>Founder & Owner: Dr. Marcus Vance</p></body></html>
        """
        team_html = """
        <html><body><p>Contact the clinical team at: team@premierdental.com</p></body></html>
        """

        def mock_get(url, **kwargs):
            resp = MagicMock()
            resp.status_code = 200
            if "about" in url:
                resp.text = about_html
            elif "team" in url:
                resp.text = team_html
            else:
                resp.text = homepage_html
            return resp

        mock_session.get.side_effect = mock_get

        result = enrich_business_contact("https://www.premierdental.com", timeout=6)
        self.assertEqual(result["email"], "team@premierdental.com")
        self.assertIn("Marcus Vance", result["owner_name"])

    @patch("scripts.enrichment.requests.Session")
    def test_enrich_business_contact_network_resilience(self, mock_session_cls):
        """Test resilience against timeouts, SSL errors, and network failures."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.get.side_effect = requests.exceptions.ConnectTimeout("Connection timed out")

        result = enrich_business_contact("https://slow-or-broken-site.com", timeout=2)

        self.assertIsInstance(result, dict)
        self.assertEqual(result["email"], "N/A")
        self.assertEqual(result["owner_name"], "N/A")
        self.assertFalse(result["has_after_hours_notice"])

    def test_enrich_business_contact_empty_or_invalid_url(self):
        """Test handling of empty, None, or invalid URL inputs."""
        for invalid_url in ["", "N/A", None]:
            result = enrich_business_contact(invalid_url)
            self.assertEqual(result["email"], "N/A")
            self.assertEqual(result["owner_name"], "N/A")
            self.assertFalse(result["has_after_hours_notice"])


if __name__ == "__main__":
    unittest.main()
