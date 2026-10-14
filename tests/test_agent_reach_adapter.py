import unittest
from scripts.agent_reach_adapter import (
    parse_intent_query_results,
    classify_intent_niche,
    fetch_agent_reach_intent_leads,
)

class TestAgentReachAdapter(unittest.TestCase):
    def test_classify_intent_niche(self):
        self.assertEqual(classify_intent_niche("Looking for AI receptionist for our dental clinic"), "dental")
        self.assertEqual(classify_intent_niche("Need Bland AI alternative for HVAC emergency calls"), "hvac")
        self.assertEqual(classify_intent_niche("Auto repair shop looking for AI phone agent"), "autorepair")
        self.assertEqual(classify_intent_niche("Law firm intake bot pricing"), "legal")
        self.assertEqual(classify_intent_niche("General voice agent question"), "general")

    def test_parse_intent_query_results(self):
        raw_items = [
            {
                "title": "Need Vapi alternative for Dental Office",
                "url": "https://reddit.com/r/SaaS/comments/123",
                "snippet": "We run a dental practice in Austin and our after-hours receptionist costs are too high. Looking for Vapi alternative.",
                "author": "austin_dentist",
            },
            {
                "title": "HVAC dispatch voice agent recommendation",
                "url": "https://reddit.com/r/smallbusiness/comments/456",
                "snippet": "Looking for emergency dispatch voice bot for our HVAC company in Dallas.",
                "author": "dallas_hvac_pro",
            }
        ]

        parsed = parse_intent_query_results(raw_items)
        self.assertEqual(len(parsed), 2)
        self.assertEqual(parsed[0]["niche"], "dental")
        self.assertIn("Austin", parsed[0]["city"])
        self.assertEqual(parsed[1]["niche"], "hvac")
        self.assertIn("Dallas", parsed[1]["city"])

    def test_fetch_agent_reach_intent_leads_structure(self):
        leads = fetch_agent_reach_intent_leads(queries=["dental voice ai"], limit=2)
        self.assertIsInstance(leads, list)
        if leads:
            lead = leads[0]
            self.assertIn("business_name", lead)
            self.assertIn("website", lead)
            self.assertIn("niche", lead)
            self.assertIn("snippet", lead)

if __name__ == "__main__":
    unittest.main()
