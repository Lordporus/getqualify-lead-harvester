# 50 Daily Leads with Agent-Reach & 9 AM Cron Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver 50 high-quality, outreach-ready Voice AI leads daily to the user's existing Google Sheet with ironclad deduplication and an automated 9:00 AM cron trigger using Agent-Reach on pure GitHub Actions (Option A).

**Architecture:** A resilient serverless pipeline running directly on GitHub-hosted Ubuntu runners: (1) An ironclad multi-key deduplication engine preventing duplicates across phones, domains, company names, and URLs; (2) A scaled discovery engine combining Agent-Reach multi-channel web/social queries with B2B local business registries to guarantee 50 leads per run; (3) Contact enrichment (`/contact`, `/about`) and Voice AI pitch hook generation; (4) Automated daily execution at 9:00 AM IST (03:30 UTC) with manual dispatch controls.

**Tech Stack:** Python 3.11, `agent-reach`, `gspread`, `google-auth`, `requests`, `beautifulsoup4`, GitHub Actions (cron + workflow_dispatch).

**Spec:** User requirements for 50 leads/day, 9:00 AM cron trigger, zero-duplicate guarantee, and Option A (pure GitHub Actions runner).

## Global Constraints
- Target output must strictly reach **50 unique, outreach-ready leads per run** before syncing to Google Sheets.
- Zero duplicate leads at any cost: multi-key deduplication against existing sheet records across (a) 10-digit normalized phone number, (b) canonical website domain, (c) company name + city hash, and (d) source URL.
- Zero external paid VPS or container service: runs 100% on GitHub Actions (`ubuntu-latest`).
- Automated cron scheduled for **9:00 AM IST** (`30 3 * * *` in UTC) with timezone handling documented.
- All 13 outreach-ready columns must be fully populated: Platform, Name/Username, Business/Company, Email, Phone Number, Website URL, Source URL, Title/Subject, Lead Type/Intent, Pain Point/Snippet, Recommended Outreach Hook, Date Captured, Outreach Status.

## Review Focus
1. **Quota Shortfall Prevention:** If a specific niche or city yields fewer businesses, the harvester must automatically cascade to adjacent target metros and niches until the exact 50-lead quota is met.
2. **False Deduplication Failures:** Different URL protocols (`http://` vs `https://`), `www.` subdomains, and trailing slashes must resolve to the identical canonical root domain.
3. **Phone Format Collisions:** Different raw notations (e.g. `(512) 555-0199`, `+1 512-555-0199`, `512.555.0199`) must reduce to an identical 10-digit phone key.
4. **Google Sheets Quota & Batch Append:** Appending 50 rows in a single batch call (`sheet.append_rows`) to avoid Google Sheets API rate-limit errors (write quota is 60 requests/minute).
5. **Agent-Reach Cloud Failover:** If an external social channel throttles within GitHub Actions, Agent-Reach must smoothly fail over to public web and directory extractors without halting the 50-lead delivery.

---

### Task 1: Ironclad Multi-Key Deduplication Engine (`scripts/deduplication.py`)

**Files:**
- Create: `scripts/deduplication.py`
- Test: `tests/test_deduplication.py`

**Interfaces:**
- Produces: `class LeadDeduplicator`
  - `load_existing_records(records: list[list]) -> None`
  - `is_duplicate(lead_dict: dict) -> bool`
  - `register_lead(lead_dict: dict) -> None`
  - `canonical_domain(url: str) -> str`
  - `canonical_phone(phone: str) -> str`
  - `lead_signature(company: str, city: str) -> str`

- [ ] **Step 1: Write tests for `LeadDeduplicator`**
```python
# tests/test_deduplication.py
import unittest
from scripts.deduplication import LeadDeduplicator

class TestLeadDeduplicator(unittest.TestCase):
    def setUp(self):
        self.dedup = LeadDeduplicator()

    def test_canonical_domain(self):
        self.assertEqual(self.dedup.canonical_domain("https://www.ApexDental.com/about/"), "apexdental.com")
        self.assertEqual(self.dedup.canonical_domain("http://apexdental.com"), "apexdental.com")

    def test_canonical_phone(self):
        self.assertEqual(self.dedup.canonical_phone("+1 (512) 555-0199"), "5125550199")
        self.assertEqual(self.dedup.canonical_phone("512.555.0199"), "5125550199")

    def test_deduplication_multi_key(self):
        existing = [
            ["Platform", "Name", "Apex Dental", "info@apex.com", "+1 (512) 555-0199", "https://apexdental.com", "https://src.com", "Title", "Type", "Snippet", "Hook", "Date", "Status"]
        ]
        self.dedup.load_existing_records(existing)
        
        # Duplicate by phone
        self.assertTrue(self.dedup.is_duplicate({"phone": "512-555-0199", "website": "https://other.com", "business_name": "Other", "city": "Dallas"}))
        # Duplicate by website domain
        self.assertTrue(self.dedup.is_duplicate({"phone": "999-999-9999", "website": "https://www.apexdental.com/contact", "business_name": "Other", "city": "Dallas"}))
        # Brand new lead
        self.assertFalse(self.dedup.is_duplicate({"phone": "512-555-9999", "website": "https://newdental.com", "business_name": "New Dental", "city": "Austin"}))
```

- [ ] **Step 2: Run test to verify it fails**
Run: `python -m unittest tests/test_deduplication.py`
Expected: FAIL (ModuleNotFoundError)

- [ ] **Step 3: Implement `scripts/deduplication.py`**
Implement `LeadDeduplicator` maintaining 4 lookup sets:
- `seen_phones`: set of clean 10-digit numeric phone numbers.
- `seen_domains`: set of canonical domain names (`example.com`).
- `seen_signatures`: normalized `(company_name.lower(), city.lower())`.
- `seen_urls`: normalized source and post URLs.
Include methods to seed from sheet rows (handling legacy schemas and 13-column schemas) and check new incoming lead dictionaries.

- [ ] **Step 4: Run test to verify it passes**
Run: `python -m unittest tests/test_deduplication.py`
Expected: PASS (100%)

- [ ] **Step 5: Commit**
```bash
git add scripts/deduplication.py tests/test_deduplication.py
git commit -m "feat: implement ironclad multi-key deduplication engine"
```

---

### Task 2: Scaled 50-Lead Harvester Cascade (`scripts/b2b_discovery.py`)

**Files:**
- Modify: `scripts/b2b_discovery.py`
- Modify: `tests/test_b2b_discovery.py`

**Interfaces:**
- Consumes: Target quota `target_count: int = 50`
- Produces: `harvest_target_leads(target_count: int, deduplicator: LeadDeduplicator, niches: list[str], cities: list[str]) -> list[dict]`

- [ ] **Step 1: Write unit tests for cascade harvesting**
```python
# In tests/test_b2b_discovery.py
def test_cascade_harvest_reaches_quota():
    from scripts.deduplication import LeadDeduplicator
    from scripts.b2b_discovery import harvest_target_leads
    dedup = LeadDeduplicator()
    leads = harvest_target_leads(target_count=50, deduplicator=dedup, niches=["dental", "medical", "hvac", "legal", "autorepair"])
    self.assertEqual(len(leads), 50)
```

- [ ] **Step 2: Run test to verify behavior**
Run: `python -m unittest tests/test_b2b_discovery.py`

- [ ] **Step 3: Implement dynamic cascade in `scripts/b2b_discovery.py`**
- Expand default target metro list from 5 to 15 major US metro areas (Austin, Dallas, Miami, Phoenix, Atlanta, Houston, Orlando, Tampa, Charlotte, Nashville, Las Vegas, Denver, San Antonio, Columbus, Indianapolis).
- Implement multi-pass cascading iterator:
  - Rotates across niches and cities.
  - Queries directory mirrors and caches fetched candidates.
  - Checks each candidate against `deduplicator.is_duplicate(candidate)`.
  - If duplicate, discards and continues to next without consuming quota.
  - Loops continuously across city/niche matrix until exactly `target_count` (50) unique leads are collected.

- [ ] **Step 4: Run tests and verify 50-lead quota fulfillment**
Run: `python -m unittest tests/test_b2b_discovery.py`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add scripts/b2b_discovery.py tests/test_b2b_discovery.py
git commit -m "feat: scale business discovery engine with cascading 50-lead quota fulfillment"
```

---

### Task 3: Agent-Reach GitHub Actions Adapter (`scripts/agent_reach_adapter.py`)

**Files:**
- Create: `scripts/agent_reach_adapter.py`
- Modify: `requirements.txt`
- Create: `tests/test_agent_reach_adapter.py`

**Interfaces:**
- Produces: `fetch_agent_reach_intent_leads(queries: list[str], limit: int = 15) -> list[dict]`
  Discovers active Voice AI buyer inquiries via Agent-Reach extractors (Jina Reader, Web Search, Community Posts) and converts them to standardized lead dictionaries.

- [ ] **Step 1: Write tests for `scripts/agent_reach_adapter.py`**
```python
# tests/test_agent_reach_adapter.py
import unittest
from scripts.agent_reach_adapter import parse_agent_reach_output, format_intent_lead

class TestAgentReachAdapter(unittest.TestCase):
    def test_parse_agent_reach_output(self):
        raw_items = [
            {"title": "Need an AI phone agent for dental office", "url": "https://example.com/post/1", "snippet": "Looking for Vapi alternative to handle after-hours bookings", "author": "dental_doc"}
        ]
        parsed = parse_agent_reach_output(raw_items)
        self.assertEqual(len(parsed), 1)
        self.assertIn("dental", parsed[0]["niche"])
```

- [ ] **Step 2: Run test to verify it fails**
Run: `python -m unittest tests/test_agent_reach_adapter.py`
Expected: FAIL

- [ ] **Step 3: Implement `scripts/agent_reach_adapter.py`**
- Implement programmatic wrapper around Agent-Reach CLI / Jina Reader endpoints.
- Scrapes live buyer intent inquiries for keywords (`"Vapi alternative"`, `"Bland AI pricing"`, `"AI receptionist for dental"`, `"AI phone agent for HVAC"`).
- Extracts business hints, domain, and pain points.
- Provides seamless fallback to web search if CLI environment tools are unavailable.

- [ ] **Step 4: Run test to verify it passes**
Run: `python -m unittest tests/test_agent_reach_adapter.py`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add scripts/agent_reach_adapter.py tests/test_agent_reach_adapter.py requirements.txt
git commit -m "feat: add Agent-Reach multi-channel intent adapter"
```

---

### Task 4: Pipeline Integration & 50-Lead Batch Sync (`scripts/scrape_leads.py`)

**Files:**
- Modify: `scripts/scrape_leads.py`
- Modify: `tests/test_integration.py`

**Interfaces:**
- Integrates `LeadDeduplicator`, `harvest_target_leads`, `fetch_agent_reach_intent_leads`, `enrich_business_contact`, and `generate_voice_ai_hook`.
- Guarantees 50 new rows appended in a single atomic batch call (`sheet.append_rows`).

- [ ] **Step 1: Write integration tests for 50-lead quota and deduplication**
```python
# In tests/test_integration.py
def test_pipeline_enforces_50_quota_and_zero_duplicates():
    # Verify exactly 50 rows constructed
    # Verify no duplicate phone or domain in output batch
    ...
```

- [ ] **Step 2: Run test to verify integration behavior**
Run: `python -m unittest tests/test_integration.py`

- [ ] **Step 3: Update `scripts/scrape_leads.py`**
- Set default `--limit` to 50.
- Initialize `LeadDeduplicator` and load all historical Google Sheet records.
- Run harvest: combines Agent-Reach intent leads with cascading local B2B business leads.
- Concurrently enrich websites (with thread-pool or batching for speed) to extract verified business emails and practitioner names.
- Generate customized Voice AI pitch hooks for each lead.
- Execute single batch append `sheet.append_rows(new_rows)` with 50 rows.
- Log metrics: total scanned, duplicates skipped, fresh leads appended, runtime duration.

- [ ] **Step 4: Test live dry run**
Run: `python scripts/scrape_leads.py --dry-run --limit 50`
Verify terminal logs report: `Harvest completed. Total fresh leads collected: 50` with 0 duplicates.

- [ ] **Step 5: Commit**
```bash
git add scripts/scrape_leads.py tests/test_integration.py
git commit -m "feat: integrate 50-lead quota pipeline with atomic batch Google Sheets sync"
```

---

### Task 5: 9:00 AM Cron Schedule & GitHub Actions Automation

**Files:**
- Modify: `.github/workflows/scrape_leads.yml`
- Modify: `README.md`

- [ ] **Step 1: Update `.github/workflows/scrape_leads.yml` schedule**
- Configure cron for 9:00 AM IST (Indian Standard Time is UTC+5:30 -> 03:30 UTC):
  ```yaml
  schedule:
    - cron: '30 3 * * *' # Every day at 09:00 AM IST (03:30 AM UTC)
  ```
- Set default `HARVEST_LIMIT: 50`.
- Install Agent-Reach in runner step:
  ```yaml
  - name: Install Agent-Reach
    run: |
      pip install git+https://github.com/Panniantong/agent-reach.git || echo "Agent-Reach installed or web fallback active"
  ```
- Run harvester:
  ```yaml
  - name: Execute 50-Lead Harvester
    run: |
      python scripts/scrape_leads.py --limit 50
  ```

- [ ] **Step 2: Update `README.md`**
- Document the 50 leads/day guarantee.
- Document the 9:00 AM IST automated cron trigger.
- Document the multi-key deduplication architecture.
- Document how to customize city cascade lists and niches.

- [ ] **Step 3: Commit and Push**
```bash
git add .github/workflows/scrape_leads.yml README.md
git commit -m "feat: configure 9 AM IST cron and 50-lead automated pipeline"
git push origin main
```

- [ ] **Step 4: Live GitHub Actions Verification**
Run: `gh workflow run scrape_leads.yml --repo Lordporus/getqualify-lead-harvester`
Verify execution passes and appends 50 unique leads to the Google Sheet.
