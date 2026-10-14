"""Integration test suite for the B2B Voice AI Lead Harvester pipeline.

Tests end-to-end lead row generation, Google Sheets 13-column schema compliance,
multi-niche rotation, phone/website deduplication, and CLI execution.
"""

from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Ensure project root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scripts.scrape_leads import (
    DEFAULT_METRO_CITIES,
    DEFAULT_NICHES,
    SHEET_HEADERS,
    build_lead_row,
    extract_existing_keys,
    main,
    normalize_phone_key,
    normalize_url_key,
    scrape_leads,
)


class TestGoogleSheetSchema(unittest.TestCase):
    """Validate 13-column Google Sheet schema."""

    def test_sheet_headers_count_and_order(self):
        """Verify that SHEET_HEADERS has exactly 13 columns with expected names."""
        expected_headers = [
            "Platform",
            "Name / Username",
            "Business / Company",
            "Email",
            "Phone Number",
            "Website URL",
            "Post / Source URL",
            "Title / Subject",
            "Lead Type / Intent",
            "Pain Point / Snippet",
            "Recommended Outreach Hook",
            "Date Captured",
            "Outreach Status",
        ]
        self.assertEqual(len(SHEET_HEADERS), 13)
        self.assertEqual(SHEET_HEADERS, expected_headers)


class TestLeadRowConstruction(unittest.TestCase):
    """Test conversion of discovered & enriched business into 13-column lead rows."""

    def setUp(self):
        self.mock_business = {
            "business_name": "Austin Smile Design",
            "phone": "+1 (512) 441-2098",
            "website": "https://www.austinsmiledesign.com",
            "city": "Austin",
            "niche": "dental",
            "category": "Dental Clinic",
        }
        self.mock_enrichment_with_owner = {
            "email": "contact@austinsmiledesign.com",
            "owner_name": "Dr. Sarah Miller",
            "has_after_hours_notice": False,
        }
        self.mock_enrichment_no_owner = {
            "email": "info@austinsmiledesign.com",
            "owner_name": "N/A",
            "has_after_hours_notice": True,
        }

    def test_build_lead_row_with_enriched_owner(self):
        """Verify lead row populates doctor/owner name when discovered."""
        row = build_lead_row(
            business=self.mock_business,
            enrichment=self.mock_enrichment_with_owner,
            niche="dental",
            city="Austin",
        )
        self.assertEqual(len(row), 13)
        self.assertEqual(row[0], "B2B Directory / Web")
        self.assertEqual(row[1], "Dr. Sarah Miller")
        self.assertEqual(row[2], "Austin Smile Design")
        self.assertEqual(row[3], "contact@austinsmiledesign.com")
        self.assertEqual(row[4], "+1 (512) 441-2098")
        self.assertEqual(row[5], "https://www.austinsmiledesign.com")
        self.assertEqual(row[6], "https://www.austinsmiledesign.com")
        self.assertIn("Austin", row[7])
        self.assertIn("Dental", row[8])
        self.assertTrue(len(row[9]) > 20)  # Pain point statement
        self.assertIn("Dr. Sarah Miller", row[10])  # Pitch hook references owner
        self.assertTrue(row[11].endswith("UTC"))
        self.assertEqual(row[12], "Ready for Outreach")

    def test_build_lead_row_fallback_owner_manager(self):
        """Verify fallback to 'Practice / Business Manager' when owner is N/A."""
        row = build_lead_row(
            business=self.mock_business,
            enrichment=self.mock_enrichment_no_owner,
            niche="dental",
            city="Austin",
        )
        self.assertEqual(len(row), 13)
        self.assertEqual(row[1], "Practice / Business Manager")
        self.assertEqual(row[3], "info@austinsmiledesign.com")
        self.assertEqual(row[12], "Ready for Outreach")

    def test_build_lead_row_missing_email(self):
        """Verify graceful fallback to N/A when email could not be enriched."""
        enrichment_empty = {"email": "N/A", "owner_name": "N/A", "has_after_hours_notice": False}
        row = build_lead_row(
            business=self.mock_business,
            enrichment=enrichment_empty,
            niche="dental",
            city="Austin",
        )
        self.assertEqual(row[3], "N/A")
        self.assertEqual(row[1], "Practice / Business Manager")

    def test_build_lead_row_across_niches(self):
        """Test row construction across all 5 key target niches."""
        niches = [
            ("dental", "Smile Dental", "Dental Clinic"),
            ("medical", "Austin Family Care", "Medical Clinic"),
            ("hvac", "Capital City Heating & Air", "HVAC Services"),
            ("legal", "Travis Law Group", "Law Firm"),
            ("autorepair", "Precision Motor Works", "Auto Repair"),
        ]
        for niche, name, cat in niches:
            biz = {
                "business_name": name,
                "phone": "+1 (512) 555-0100",
                "website": f"https://www.{niche}austin.example.com",
                "city": "Austin",
                "niche": niche,
                "category": cat,
            }
            enrichment = {"email": f"info@{niche}austin.example.com", "owner_name": "N/A", "has_after_hours_notice": False}
            row = build_lead_row(biz, enrichment, niche, "Austin")
            self.assertEqual(len(row), 13)
            self.assertEqual(row[0], "B2B Directory / Web")
            self.assertEqual(row[2], name)
            self.assertIn("Ready for Outreach", row[12])


class TestDeduplication(unittest.TestCase):
    """Test phone and website normalization and deduplication indexing."""

    def test_normalize_phone_key(self):
        """Verify phone numbers in various formats produce identical 10-digit keys."""
        expected = "5124412098"
        self.assertEqual(normalize_phone_key("+1 (512) 441-2098"), expected)
        self.assertEqual(normalize_phone_key("512-441-2098"), expected)
        self.assertEqual(normalize_phone_key("(512) 441-2098"), expected)
        self.assertEqual(normalize_phone_key("+15124412098"), expected)
        self.assertEqual(normalize_phone_key("1-512-441-2098"), expected)
        self.assertEqual(normalize_phone_key("512.441.2098"), expected)
        self.assertEqual(normalize_phone_key("N/A"), "")
        self.assertEqual(normalize_phone_key(""), "")
        self.assertEqual(normalize_phone_key(None), "")

    def test_normalize_url_key(self):
        """Verify websites in various formats produce canonical bare domain keys."""
        expected = "austindentalcare.com"
        self.assertEqual(normalize_url_key("https://www.austindentalcare.com"), expected)
        self.assertEqual(normalize_url_key("http://austindentalcare.com/"), expected)
        self.assertEqual(normalize_url_key("https://www.austindentalcare.com/about-us"), expected)
        self.assertEqual(normalize_url_key("www.austindentalcare.com"), expected)
        self.assertEqual(normalize_url_key("austindentalcare.com"), expected)
        self.assertEqual(normalize_url_key("N/A"), "")
        self.assertEqual(normalize_url_key(""), "")
        self.assertEqual(normalize_url_key(None), "")

    def test_extract_existing_keys_from_sheet_records(self):
        """Test parsing existing records from Google Sheet rows."""
        sheet_rows = [
            SHEET_HEADERS,
            [
                "B2B Directory / Web",
                "Practice Manager",
                "Existing Dental",
                "info@existingdental.com",
                "+1 (512) 111-2222",
                "https://www.existingdental.com",
                "https://www.existingdental.com",
                "Dental Clinic - Austin, TX",
                "Dental Practice",
                "Pain point",
                "Outreach hook",
                "2026-10-13 12:00:00 UTC",
                "Ready for Outreach",
            ],
            [
                "B2B Directory / Web",
                "Dr. John Doe",
                "Second Clinic",
                "contact@secondclinic.com",
                "+1 (512) 333-4444",
                "https://secondclinic.org/contact",
                "https://secondclinic.org",
                "Medical Clinic - Austin, TX",
                "Medical Practice",
                "Pain point",
                "Outreach hook",
                "2026-10-13 12:00:00 UTC",
                "Ready for Outreach",
            ],
        ]
        phones, websites = extract_existing_keys(sheet_rows)
        self.assertIn("5121112222", phones)
        self.assertIn("5123334444", phones)
        self.assertIn("existingdental.com", websites)
        self.assertIn("secondclinic.org", websites)

    def test_extract_existing_keys_empty_sheet(self):
        """Test extraction on empty sheet returns empty sets."""
        phones, websites = extract_existing_keys([])
        self.assertEqual(len(phones), 0)
        self.assertEqual(len(websites), 0)

        phones2, websites2 = extract_existing_keys([SHEET_HEADERS])
        self.assertEqual(len(phones2), 0)
        self.assertEqual(len(websites2), 0)


class TestScrapeLeadsPipeline(unittest.TestCase):
    """Test full scrape_leads integration pipeline."""

    @patch("scripts.scrape_leads.enrich_business_contact")
    @patch("scripts.scrape_leads.fetch_niche_businesses")
    def test_scrape_leads_dry_run_basic(self, mock_fetch, mock_enrich):
        """Test dry run harvest without external network calls."""
        mock_fetch.return_value = [
            {
                "business_name": "Austin Dental Pros",
                "phone": "+1 (512) 555-0101",
                "website": "https://www.austindentalpros.com",
                "city": "Austin",
                "niche": "dental",
                "category": "Dental Clinic",
            },
            {
                "business_name": "Rose City Dental",
                "phone": "+1 (512) 555-0102",
                "website": "https://www.rosecitydental.com",
                "city": "Austin",
                "niche": "dental",
                "category": "Dental Clinic",
            },
        ]
        mock_enrich.return_value = {
            "email": "contact@example.com",
            "owner_name": "Dr. Sarah Rose",
            "has_after_hours_notice": False,
        }

        leads = scrape_leads(
            limit=2,
            niches=["dental"],
            cities=["Austin"],
            dry_run=True,
        )

        self.assertEqual(len(leads), 2)
        for lead in leads:
            self.assertEqual(len(lead), 13)
            self.assertEqual(lead[0], "B2B Directory / Web")
            self.assertEqual(lead[1], "Dr. Sarah Rose")
            self.assertEqual(lead[3], "contact@example.com")
            self.assertEqual(lead[12], "Ready for Outreach")

    @patch("scripts.scrape_leads.enrich_business_contact")
    @patch("scripts.scrape_leads.fetch_niche_businesses")
    def test_scrape_leads_deduplication_against_existing(self, mock_fetch, mock_enrich):
        """Verify businesses matching existing phones or websites are excluded."""
        mock_fetch.return_value = [
            {
                "business_name": "Duplicate Phone Biz",
                "phone": "+1 (512) 999-0001",
                "website": "https://www.newsite1.com",
                "city": "Austin",
                "niche": "dental",
                "category": "Dental Clinic",
            },
            {
                "business_name": "Duplicate Website Biz",
                "phone": "+1 (512) 888-0002",
                "website": "https://www.existingdomain.com",
                "city": "Austin",
                "niche": "dental",
                "category": "Dental Clinic",
            },
            {
                "business_name": "Fresh Unique Biz",
                "phone": "+1 (512) 777-0003",
                "website": "https://www.freshsite.com",
                "city": "Austin",
                "niche": "dental",
                "category": "Dental Clinic",
            },
        ]
        mock_enrich.return_value = {
            "email": "info@freshsite.com",
            "owner_name": "N/A",
            "has_after_hours_notice": False,
        }

        existing_phones = {"5129990001"}
        existing_websites = {"existingdomain.com"}

        leads = scrape_leads(
            limit=5,
            niches=["dental"],
            cities=["Austin"],
            existing_phones=existing_phones,
            existing_websites=existing_websites,
            dry_run=True,
        )

        self.assertEqual(len(leads), 1)
        self.assertEqual(leads[0][2], "Fresh Unique Biz")
        self.assertEqual(leads[0][4], "+1 (512) 777-0003")

    @patch("scripts.scrape_leads.enrich_business_contact")
    @patch("scripts.scrape_leads.fetch_niche_businesses")
    def test_scrape_leads_in_batch_deduplication(self, mock_fetch, mock_enrich):
        """Verify that duplicate businesses inside the same batch are pruned."""
        mock_fetch.return_value = [
            {
                "business_name": "First Instance",
                "phone": "+1 (512) 555-9999",
                "website": "https://www.batchrepeat.com",
                "city": "Austin",
                "niche": "hvac",
                "category": "HVAC Services",
            },
            {
                "business_name": "Repeated Instance",
                "phone": "+1 (512) 555-9999",
                "website": "https://www.batchrepeat.com",
                "city": "Austin",
                "niche": "hvac",
                "category": "HVAC Services",
            },
        ]
        mock_enrich.return_value = {
            "email": "contact@batchrepeat.com",
            "owner_name": "N/A",
            "has_after_hours_notice": False,
        }

        leads = scrape_leads(
            limit=5,
            niches=["hvac"],
            cities=["Austin"],
            dry_run=True,
        )

        self.assertEqual(len(leads), 1)
        self.assertEqual(leads[0][2], "First Instance")

    @patch("scripts.scrape_leads.enrich_business_contact")
    @patch("scripts.scrape_leads.fetch_niche_businesses")
    def test_scrape_leads_multi_niche_rotation(self, mock_fetch, mock_enrich):
        """Verify scraper rotates through target niches."""
        mock_fetch.side_effect = lambda niche, city, limit: [
            {
                "business_name": f"{city} {niche.title()} Hub",
                "phone": f"+1 (512) 111-{hash(niche) % 9000 + 1000:04d}",
                "website": f"https://www.{niche}hub.com",
                "city": city,
                "niche": niche,
                "category": f"{niche.title()} Services",
            }
        ]
        mock_enrich.return_value = {
            "email": "test@domain.com",
            "owner_name": "N/A",
            "has_after_hours_notice": False,
        }

        leads = scrape_leads(
            limit=5,
            niches=DEFAULT_NICHES,
            cities=DEFAULT_METRO_CITIES,
            dry_run=True,
        )

        self.assertEqual(len(leads), 5)
        harvested_titles = [lead[7] for lead in leads]
        # Should have diverse niches represented
        self.assertTrue(any("Dental" in t for t in harvested_titles))
        self.assertTrue(any("Medical" in t for t in harvested_titles))
        self.assertTrue(any("HVAC" in t.upper() for t in harvested_titles))


class TestCLIExecution(unittest.TestCase):
    """Test CLI execution with arguments."""

    @patch("scripts.scrape_leads.scrape_leads")
    def test_cli_dry_run_flag(self, mock_scrape):
        """Test running main() with --dry-run and --limit."""
        mock_scrape.return_value = [
            [
                "B2B Directory / Web",
                "Dr. Jane Doe",
                "Downtown Smile",
                "contact@downtownsmile.com",
                "+1 (512) 555-1234",
                "https://downtownsmile.com",
                "https://downtownsmile.com",
                "Dental Clinic - Austin, TX",
                "Dental Practice",
                "Pain point",
                "Outreach hook",
                "2026-10-13 12:00:00 UTC",
                "Ready for Outreach",
            ]
        ]

        test_args = ["scrape_leads.py", "--dry-run", "--limit", "1"]
        with patch.object(sys, "argv", test_args):
            main()

        mock_scrape.assert_called_once()
        call_kwargs = mock_scrape.call_args[1]
        self.assertTrue(call_kwargs.get("dry_run"))
        self.assertEqual(call_kwargs.get("limit"), 1)

    @patch("scripts.scrape_leads.get_sheet")
    @patch("scripts.scrape_leads.scrape_leads")
    def test_batch_append_single_call(self, mock_scrape, mock_get_sheet):
        """Verify main() uploads all 50 leads in a single batch append_rows call."""
        mock_sheet = MagicMock()
        mock_sheet.get_all_values.return_value = [SHEET_HEADERS]
        mock_get_sheet.return_value = mock_sheet

        mock_50_leads = [
            [
                "B2B Directory / Web",
                f"Manager {i}",
                f"Biz {i}",
                f"biz{i}@example.com",
                f"+1 (512) 555-{i:04d}",
                f"https://www.biz{i}.com",
                f"https://www.biz{i}.com",
                "Dental Clinic - Austin, TX",
                "Dental Practice",
                "Pain point",
                "Outreach hook",
                "2026-10-14 09:00:00 UTC",
                "Ready for Outreach",
            ]
            for i in range(50)
        ]
        mock_scrape.return_value = mock_50_leads

        test_args = ["scrape_leads.py", "--limit", "50"]
        with patch.object(sys, "argv", test_args):
            main()

        # Assert exactly one call to append_rows with all 50 leads
        mock_sheet.append_rows.assert_called_once_with(mock_50_leads)


class TestFiftyLeadsQuotaAndDeduplication(unittest.TestCase):
    """Test 50 leads daily quota guarantee and ironclad deduplication."""

    @patch("scripts.scrape_leads.enrich_business_contact")
    def test_scrape_leads_50_quota_fulfilled(self, mock_enrich):
        """Verify scrape_leads fulfills exactly 50 leads across the cascade."""
        mock_enrich.return_value = {
            "email": "info@domain.com",
            "owner_name": "Dr. Smith",
            "has_after_hours_notice": False,
        }
        leads = scrape_leads(limit=50, dry_run=True)
        self.assertEqual(len(leads), 50)
        for lead in leads:
            self.assertEqual(len(lead), 13)
            self.assertEqual(lead[12], "Ready for Outreach")

    @patch("scripts.scrape_leads.enrich_business_contact")
    @patch("scripts.scrape_leads.fetch_niche_businesses")
    def test_scrape_leads_deduplication_preserves_unique_count(self, mock_fetch, mock_enrich):
        """Verify deduplication skips existing records without sacrificing quota fulfillment."""
        mock_fetch.side_effect = lambda niche, city, limit: [
            {
                "business_name": "Austin Dental Arts",
                "phone": "+1 (512) 999-0001",
                "website": "https://www.austindentalarts.com",
                "city": city,
                "niche": niche,
            },
            {
                "business_name": f"{city} {niche.title()} Care",
                "phone": f"+1 (512) 777-{hash(niche + city) % 9000 + 1000:04d}",
                "website": f"https://www.{niche}{city.lower()}care.com",
                "city": city,
                "niche": niche,
            },
        ]
        mock_enrich.return_value = {
            "email": "contact@clinic.com",
            "owner_name": "N/A",
            "has_after_hours_notice": False,
        }

        from scripts.deduplication import LeadDeduplicator
        dedup = LeadDeduplicator()
        # Seed existing phone and domain into deduplicator
        dedup.seen_phones.add("5129990001")
        dedup.seen_domains.add("austindentalarts.com")

        leads = scrape_leads(
            limit=5,
            niches=["dental", "medical"],
            cities=["Austin", "Dallas"],
            deduplicator=dedup,
            dry_run=True,
        )

        # Ensure no returned lead has the duplicate phone or domain
        for lead in leads:
            self.assertNotEqual(lead[4], "+1 (512) 999-0001")
            self.assertNotEqual(lead[5], "https://www.austindentalarts.com")


if __name__ == "__main__":
    unittest.main()
