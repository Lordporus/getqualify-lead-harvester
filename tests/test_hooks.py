"""Unit tests for Voice AI Pitch Hook & Value Proposition Generator."""

import os
import sys
import unittest

# Ensure repo root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scripts.hooks import generate_voice_ai_hook, normalize_niche


class TestVoiceAIHooks(unittest.TestCase):
    """Test suite for niche-specific Voice AI pitch hook generation."""

    # --- Tests for normalize_niche ---

    def test_normalize_niche_mappings(self):
        """Test niche normalization for all supported categories and variations."""
        self.assertEqual(normalize_niche("dental"), "dental")
        self.assertEqual(normalize_niche("Dentist"), "dental")
        self.assertEqual(normalize_niche("orthodontics"), "dental")
        self.assertEqual(normalize_niche("dental-clinic"), "dental")

        self.assertEqual(normalize_niche("medical"), "medical")
        self.assertEqual(normalize_niche("clinic"), "medical")
        self.assertEqual(normalize_niche("urgent care"), "medical")
        self.assertEqual(normalize_niche("Doctor"), "medical")
        self.assertEqual(normalize_niche("healthcare"), "medical")

        self.assertEqual(normalize_niche("hvac"), "hvac")
        self.assertEqual(normalize_niche("plumber"), "hvac")
        self.assertEqual(normalize_niche("plumbing"), "hvac")
        self.assertEqual(normalize_niche("heating & cooling"), "hvac")
        self.assertEqual(normalize_niche("air conditioning"), "hvac")

        self.assertEqual(normalize_niche("legal"), "legal")
        self.assertEqual(normalize_niche("lawyer"), "legal")
        self.assertEqual(normalize_niche("Attorney"), "legal")
        self.assertEqual(normalize_niche("law firm"), "legal")

        self.assertEqual(normalize_niche("autorepair"), "autorepair")
        self.assertEqual(normalize_niche("auto repair"), "autorepair")
        self.assertEqual(normalize_niche("mechanic"), "autorepair")
        self.assertEqual(normalize_niche("car_repair"), "autorepair")

        self.assertEqual(normalize_niche("roofing"), "general")
        self.assertEqual(normalize_niche("landscaping"), "general")
        self.assertEqual(normalize_niche(""), "general")
        self.assertEqual(normalize_niche(None), "general")

    # --- Tests for Dental Niche ---

    def test_generate_dental_hook(self):
        """Test dental hook generation with business name and city."""
        lead_type, snippet, hook = generate_voice_ai_hook("dental", "Apex Dental", "Austin")

        self.assertIn("Dental", lead_type)
        self.assertTrue("Apex Dental" in snippet or "Apex Dental" in hook)
        self.assertTrue("receptionist" in hook.lower() or "after-hours" in hook.lower())
        self.assertTrue("dentrix" in hook.lower() or "calendar" in hook.lower())
        self.assertIn("Austin", hook)

    def test_generate_dental_hook_aliases(self):
        """Test dental hook aliases like dentist and orthodontics."""
        for alias in ("dentist", "orthodontics"):
            lead_type, snippet, hook = generate_voice_ai_hook(alias, "Smile Crafters")
            self.assertIn("Dental", lead_type)
            self.assertTrue("appointment" in hook.lower() or "patient" in hook.lower())

    # --- Tests for Medical / Clinic Niche ---

    def test_generate_medical_hook(self):
        """Test medical clinic hook generation."""
        lead_type, snippet, hook = generate_voice_ai_hook(
            "medical", "Austin Family Care", "Austin"
        )

        self.assertIn("Medical", lead_type)
        self.assertTrue("Austin Family Care" in snippet or "Austin Family Care" in hook)
        self.assertTrue("triage" in hook.lower() or "intake" in hook.lower())
        self.assertTrue("prescription" in hook.lower() or "intake" in hook.lower())
        self.assertIn("Austin", hook)

    def test_generate_clinic_alias_hook(self):
        """Test clinic alias generates medical hook."""
        lead_type, snippet, hook = generate_voice_ai_hook("clinic", "Metro Urgent Care", "Dallas")

        self.assertIn("Medical", lead_type)
        self.assertTrue("Metro Urgent Care" in snippet or "Metro Urgent Care" in hook)
        self.assertTrue("intake" in hook.lower() or "scheduling" in hook.lower())

    # --- Tests for HVAC & Plumbing Niche ---

    def test_generate_hvac_hook(self):
        """Test HVAC hook generation."""
        lead_type, snippet, hook = generate_voice_ai_hook(
            "hvac", "Precision Air & Heat", "Phoenix"
        )

        self.assertTrue("HVAC" in lead_type or "Plumbing" in lead_type)
        self.assertTrue("Precision Air & Heat" in snippet or "Precision Air & Heat" in hook)
        self.assertTrue("dispatch" in hook.lower() or "emergency" in hook.lower())
        self.assertIn("Phoenix", hook)

    def test_generate_plumber_hook(self):
        """Test plumber alias generates emergency dispatch hook."""
        lead_type, snippet, hook = generate_voice_ai_hook(
            "plumber", "Blue Wave Plumbing", "Miami"
        )

        self.assertTrue("HVAC" in lead_type or "Plumbing" in lead_type)
        self.assertTrue("Blue Wave Plumbing" in snippet or "Blue Wave Plumbing" in hook)
        self.assertTrue("dispatch" in hook.lower() or "technician" in hook.lower())
        self.assertIn("Miami", hook)

    # --- Tests for Legal / Lawyer Niche ---

    def test_generate_legal_hook(self):
        """Test legal / law firm hook generation."""
        lead_type, snippet, hook = generate_voice_ai_hook(
            "legal", "Travis County Legal Group", "Austin"
        )

        self.assertTrue("Law Firm" in lead_type or "Legal" in lead_type)
        self.assertTrue(
            "Travis County Legal Group" in snippet or "Travis County Legal Group" in hook
        )
        self.assertTrue(
            "pre-qualification" in hook.lower() or "intake" in hook.lower() or "retainer" in hook.lower()
        )
        self.assertIn("Austin", hook)

    def test_generate_lawyer_hook(self):
        """Test lawyer alias generates legal hook."""
        lead_type, snippet, hook = generate_voice_ai_hook("lawyer", "Sterling & Partners", "Atlanta")

        self.assertTrue("Law Firm" in lead_type or "Legal" in lead_type)
        self.assertTrue("Sterling & Partners" in snippet or "Sterling & Partners" in hook)
        self.assertTrue("intake" in hook.lower() or "pre-qualif" in hook.lower())

    # --- Tests for Auto Repair Niche ---

    def test_generate_autorepair_hook(self):
        """Test auto repair hook generation."""
        lead_type, snippet, hook = generate_voice_ai_hook(
            "autorepair", "Lone Star Auto Tech", "Dallas"
        )

        self.assertIn("Auto Repair", lead_type)
        self.assertTrue("Lone Star Auto Tech" in snippet or "Lone Star Auto Tech" in hook)
        self.assertTrue(
            "status" in hook.lower() or "estimate" in hook.lower() or "mechanic" in hook.lower()
        )
        self.assertIn("Dallas", hook)

    def test_generate_mechanic_alias_hook(self):
        """Test mechanic alias generates auto repair hook."""
        lead_type, snippet, hook = generate_voice_ai_hook("mechanic", "Downtown Motors")

        self.assertIn("Auto Repair", lead_type)
        self.assertTrue("Downtown Motors" in snippet or "Downtown Motors" in hook)
        self.assertTrue("status" in hook.lower() or "estimate" in hook.lower())

    # --- Tests for General / Fallback Niche ---

    def test_generate_general_fallback_hook(self):
        """Test fallback hook for unlisted or custom niches."""
        lead_type, snippet, hook = generate_voice_ai_hook(
            "roofing", "Apex Roofing Pros", "Denver"
        )

        self.assertIn("Service Business", lead_type)
        self.assertTrue("Apex Roofing Pros" in snippet or "Apex Roofing Pros" in hook)
        self.assertTrue("receptionist" in hook.lower() or "answering" in hook.lower())
        self.assertIn("Denver", hook)

    def test_generate_empty_niche_fallback(self):
        """Test empty niche falls back gracefully."""
        lead_type, snippet, hook = generate_voice_ai_hook("", "Acme Corp")
        self.assertIn("Service Business", lead_type)
        self.assertTrue(len(lead_type) > 0)
        self.assertTrue(len(snippet) > 0)
        self.assertTrue(len(hook) > 0)

    # --- Tests for Target Customization & Optional Parameters ---

    def test_hook_with_owner_name_personalization(self):
        """Test optional owner_name personalization in hook."""
        lead_type, snippet, hook = generate_voice_ai_hook(
            "dental", "Apex Dental", "Austin", owner_name="Dr. Sarah Miller"
        )

        self.assertIn("Dr. Sarah Miller", hook)
        self.assertIn("Apex Dental", hook)
        self.assertIn("Austin", hook)

    def test_hook_with_after_hours_notice_flag(self):
        """Test tailored messaging when after-hours availability is flagged."""
        lead_type, snippet, hook = generate_voice_ai_hook(
            "dental", "Apex Dental", "Austin", has_after_hours_notice=True
        )

        self.assertTrue(len(lead_type) > 0)
        self.assertTrue(len(snippet) > 0)
        self.assertTrue(len(hook) > 0)
        # Should address existing after-hours / emergency coverage upgrade
        self.assertTrue("after-hours" in hook.lower() or "emergency" in hook.lower())

    def test_hook_without_city(self):
        """Test hook formatting when city is omitted."""
        lead_type, snippet, hook = generate_voice_ai_hook("legal", "Premier Law LLC")
        self.assertNotIn(" in ", hook)  # should not have hanging ' in '
        self.assertIn("Premier Law LLC", hook)

    def test_hook_without_business_name(self):
        """Test hook formatting when business name is empty."""
        lead_type, snippet, hook = generate_voice_ai_hook("hvac", "", "Phoenix")
        self.assertTrue(len(hook) > 0)
        self.assertIn("Phoenix", hook)

    def test_return_types_and_structure(self):
        """Test that return value is strictly a 3-element tuple of strings."""
        result = generate_voice_ai_hook("dental", "Apex Dental")
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 3)
        lead_type, snippet, hook = result
        self.assertIsInstance(lead_type, str)
        self.assertIsInstance(snippet, str)
        self.assertIsInstance(hook, str)
        self.assertTrue(all(len(s.strip()) > 10 for s in (lead_type, snippet, hook)))


if __name__ == "__main__":
    unittest.main()
