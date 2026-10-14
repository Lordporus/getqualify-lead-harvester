import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# Ensure repo root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scripts.b2b_discovery import normalize_phone, fetch_niche_businesses


class TestB2BDiscovery(unittest.TestCase):
    """Test suite for B2B local business discovery engine."""

    def test_normalize_phone(self):
        """Test normalization of phone numbers across various formats."""
        # 10 digits standard
        self.assertEqual(normalize_phone("5125550199"), "+1 (512) 555-0199")
        # Hyphenated with country code
        self.assertEqual(normalize_phone("+1-512-555-0199"), "+1 (512) 555-0199")
        # Parentheses format
        self.assertEqual(normalize_phone("(512) 555-0199"), "+1 (512) 555-0199")
        # Leading 1 without plus
        self.assertEqual(normalize_phone("1-512-555-0199"), "+1 (512) 555-0199")
        self.assertEqual(normalize_phone("15125550199"), "+1 (512) 555-0199")
        # Dotted format
        self.assertEqual(normalize_phone("512.555.0199"), "+1 (512) 555-0199")
        # Formatted with +1
        self.assertEqual(normalize_phone("+15125550199"), "+1 (512) 555-0199")
        # Empty or invalid inputs
        self.assertEqual(normalize_phone(""), "N/A")
        self.assertEqual(normalize_phone(None), "N/A")
        self.assertEqual(normalize_phone("invalid"), "N/A")
        self.assertEqual(normalize_phone("123"), "N/A")

    def test_fetch_niche_businesses_schema(self):
        """Test fetch_niche_businesses schema and required keys."""
        results = fetch_niche_businesses("dental", "Austin", limit=3)
        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0)

        required_keys = {"business_name", "phone", "website", "city", "niche", "category"}
        for lead in results:
            self.assertTrue(required_keys.issubset(lead.keys()), f"Missing keys in {lead}")
            self.assertTrue(bool(lead["business_name"].strip()))
            self.assertTrue(bool(lead["phone"].strip()))
            self.assertTrue(bool(lead["website"].strip()))
            self.assertEqual(lead["city"], "Austin")
            self.assertEqual(lead["niche"], "dental")
            self.assertTrue(lead["website"].startswith(("http://", "https://")))
            self.assertNotEqual(lead["phone"], "N/A")

    def test_fetch_niche_businesses_multiple_niches(self):
        """Test fetching across multiple high-call niches."""
        niches = ["dental", "hvac", "legal", "autorepair", "medical"]
        for niche in niches:
            results = fetch_niche_businesses(niche, "Dallas", limit=2)
            self.assertIsInstance(results, list)
            self.assertGreater(len(results), 0)
            lead = results[0]
            self.assertEqual(lead["niche"], niche)
            self.assertTrue(bool(lead["business_name"]))
            self.assertTrue(bool(lead["category"]))

    def test_fetch_niche_businesses_overpass_fallback(self):
        """Test fallback data when Overpass network endpoints fail completely."""
        with patch("requests.post", side_effect=Exception("Connection timeout")):
            with patch("requests.get", side_effect=Exception("Connection timeout")):
                results = fetch_niche_businesses("hvac", "Miami", limit=3)
                self.assertIsInstance(results, list)
                self.assertGreater(len(results), 0)
                lead = results[0]
                self.assertIn("business_name", lead)
                self.assertIn("phone", lead)
                self.assertIn("website", lead)
                self.assertEqual(lead["city"], "Miami")
                self.assertEqual(lead["niche"], "hvac")

    def test_fetch_niche_businesses_parsing_overpass_response(self):
        """Test Overpass response parsing when endpoint succeeds."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "elements": [
                {
                    "tags": {
                        "name": "Downtown Smile Dental",
                        "phone": "512-555-7788",
                        "website": "www.downtownsmiledental.com"
                    }
                },
                {
                    "tags": {
                        # Missing phone, should be skipped
                        "name": "No Phone Dental",
                        "website": "www.nophonedental.com"
                    }
                },
                {
                    "tags": {
                        # Missing website, should be skipped
                        "name": "No Web Dental",
                        "phone": "512-555-9900"
                    }
                },
                {
                    "tags": {
                        "name": "Capital Family Dentistry",
                        "contact:phone": "+1 512 555 3344",
                        "contact:website": "https://capitaldental.example"
                    }
                }
            ]
        }

        with patch("requests.post", return_value=mock_response):
            results = fetch_niche_businesses("dental", "Austin", limit=5)
            self.assertIsInstance(results, list)
            names = [r["business_name"] for r in results]
            self.assertIn("Downtown Smile Dental", names)
            self.assertIn("Capital Family Dentistry", names)
            self.assertNotIn("No Phone Dental", names)
            self.assertNotIn("No Web Dental", names)

            for item in results:
                if item["business_name"] == "Downtown Smile Dental":
                    self.assertEqual(item["phone"], "+1 (512) 555-7788")
                    self.assertEqual(item["website"], "https://www.downtownsmiledental.com")

    def test_harvest_target_leads_quota(self):
        """Test that harvest_target_leads satisfies requested target_count quota."""
        from scripts.b2b_discovery import harvest_target_leads
        from scripts.deduplication import LeadDeduplicator

        dedup = LeadDeduplicator()
        leads = harvest_target_leads(target_count=10, deduplicator=dedup)
        self.assertEqual(len(leads), 10)

        # Verify no internal duplicate phone numbers in the returned batch
        phones = [l["phone"] for l in leads]
        self.assertEqual(len(phones), len(set(phones)))


if __name__ == "__main__":
    unittest.main()

