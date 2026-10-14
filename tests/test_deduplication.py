import unittest
from scripts.deduplication import LeadDeduplicator, canonical_domain, canonical_phone, lead_signature

class TestLeadDeduplicator(unittest.TestCase):
    def setUp(self):
        self.dedup = LeadDeduplicator()

    def test_canonical_domain(self):
        self.assertEqual(canonical_domain("https://www.ApexDental.com/about/"), "apexdental.com")
        self.assertEqual(canonical_domain("http://apexdental.com"), "apexdental.com")
        self.assertEqual(canonical_domain("https://carenow.com/locations/dallas/?query=1"), "carenow.com")
        self.assertEqual(canonical_domain("N/A"), "")
        self.assertEqual(canonical_domain(""), "")

    def test_canonical_phone(self):
        self.assertEqual(canonical_phone("+1 (512) 555-0199"), "5125550199")
        self.assertEqual(canonical_phone("512.555.0199"), "5125550199")
        self.assertEqual(canonical_phone("1-512-555-0199"), "5125550199")
        self.assertEqual(canonical_phone("5125550199"), "5125550199")
        self.assertEqual(canonical_phone("N/A"), "")
        self.assertEqual(canonical_phone(""), "")

    def test_lead_signature(self):
        self.assertEqual(lead_signature("Apex Dental Studio", "Austin"), "apex dental studio::austin")
        self.assertEqual(lead_signature("  CareNow Urgent Care  ", "Dallas, TX"), "carenow urgent care::dallas")

    def test_deduplication_from_existing_records(self):
        existing = [
            # Header row
            ["Platform", "Name", "Business", "Email", "Phone", "Website", "Post URL", "Title", "Type", "Snippet", "Hook", "Date", "Status"],
            # Row 1: Apex Dental
            ["B2B Directory", "Dr. Patel", "Apex Dental Studio", "contact@apex.com", "+1 (512) 441-2098", "https://apexdentalcare.com", "https://apexdentalcare.com", "Title", "Type", "Snippet", "Hook", "Date", "Status"],
            # Row 2: Dallas Medical
            ["B2B Directory", "Manager", "Dallas Medical Center", "N/A", "+1 (972) 888-7000", "https://dallasmedicalcenter.com", "https://dallasmedicalcenter.com", "Title", "Type", "Snippet", "Hook", "Date", "Status"]
        ]
        self.dedup.load_existing_records(existing)

        # 1. Duplicate by exact phone number
        dup_by_phone = {
            "business_name": "Different Dental Name",
            "phone": "512-441-2098",
            "website": "https://differentwebsite.com",
            "city": "Austin",
            "url": "https://differenturl.com"
        }
        self.assertTrue(self.dedup.is_duplicate(dup_by_phone))

        # 2. Duplicate by canonical domain
        dup_by_domain = {
            "business_name": "Different Practice",
            "phone": "+1 (512) 999-0000",
            "website": "https://www.apexdentalcare.com/contact-us/",
            "city": "Austin",
            "url": "https://differenturl.com"
        }
        self.assertTrue(self.dedup.is_duplicate(dup_by_domain))

        # 3. Duplicate by signature (company + city)
        dup_by_sig = {
            "business_name": "Apex Dental Studio",
            "phone": "+1 (512) 777-8888",
            "website": "https://brandnewdomain.com",
            "city": "Austin, TX", # normalized match
            "url": "https://brandnewurl.com"
        }
        # Note: Apex Dental Studio in Austin
        self.assertTrue(self.dedup.is_duplicate({"business_name": "Apex Dental Studio", "city": "Austin", "phone": "0000000000", "website": "https://none.com"}))

        # 4. Brand new lead
        fresh_lead = {
            "business_name": "Brand New Dental Practice",
            "phone": "+1 (512) 333-4444",
            "website": "https://brandnewpractice.com",
            "city": "Austin",
            "url": "https://brandnewpractice.com"
        }
        self.assertFalse(self.dedup.is_duplicate(fresh_lead))

    def test_in_batch_deduplication(self):
        lead1 = {
            "business_name": "Unique HVAC",
            "phone": "+1 (305) 555-1111",
            "website": "https://uniquehvac.com",
            "city": "Miami",
            "url": "https://uniquehvac.com"
        }
        self.assertFalse(self.dedup.is_duplicate(lead1))
        self.dedup.register_lead(lead1)

        # Immediate second check should be detected as duplicate
        self.assertTrue(self.dedup.is_duplicate(lead1))

if __name__ == "__main__":
    unittest.main()
